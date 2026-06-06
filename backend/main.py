"""FastAPI app for the krish backend."""

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from backend import db
from backend.config import (
    DISTRACTION_APPS,
    FOCUS_APPS,
    OLLAMA_MODEL,
    USER_NAME,
)
from backend.llm import chat
from backend.persona import build_system_prompt
from backend.rag import retrieve

# How far back /nudge looks, and how little active time counts as "barely here".
NUDGE_WINDOW_MIN = 20
MIN_ACTIVE_SECONDS = 120

app = FastAPI(title="krish backend")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class LogRequest(BaseModel):
    activity: str
    app: str | None = None
    seconds: int | None = None


@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    # The latest user turn is whatever the client just sent.
    latest_content = ""
    if request.messages:
        latest = request.messages[-1]
        latest_content = latest.content
        db.save_message(latest.role, latest.content)

    # Build context from persisted history, not just this request — so Krish
    # remembers across separate calls.
    history = db.recent_messages(limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    # RAG: pull Gita teachings relevant to the latest message, if any are
    # close enough to be worth weaving in.
    verses = retrieve(latest_content)
    gita_context = None
    if verses:
        gita_context = "\n".join(
            f"- {v['chapter']}.{v['verse']}: {v['translation']}" for v in verses
        )

    system = build_system_prompt(user_name=USER_NAME, gita_context=gita_context)
    reply = chat(messages, system=system)
    db.save_message("assistant", reply)
    return {"reply": reply}


@app.get("/history")
def history(limit: int = 20):
    return {"messages": db.recent_messages(limit=limit)}


@app.post("/log")
def log_endpoint(request: LogRequest):
    db.save_log(request.activity, app=request.app, seconds=request.seconds)
    return {"status": "ok"}


@app.get("/logs")
def logs(limit: int = 50):
    return {"logs": db.recent_logs(limit=limit)}


# --- activity analysis: daily summary + proactive nudges -------------------


def _start_of_today_utc() -> str:
    """ISO-8601 UTC timestamp for local midnight today (logs are stored UTC)."""
    local_midnight = datetime.now().astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return local_midnight.astimezone(timezone.utc).isoformat()


def _minutes_ago_utc(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _fmt_dur(seconds: int) -> str:
    """Human duration like '1h 12m' / '12m' / '40s'."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m"
    return f"{s}s"


def _aggregate(rows: list[dict]) -> tuple[list[tuple[str, int]], int]:
    """Sum seconds per app and overall; return (top-apps-desc, total)."""
    by_app: dict[str, int] = {}
    total = 0
    for r in rows:
        secs = r["seconds"] or 0
        app = r["app"] or "(unknown)"
        by_app[app] = by_app.get(app, 0) + secs
        total += secs
    top = sorted(by_app.items(), key=lambda kv: kv[1], reverse=True)
    return top, total


@app.get("/daily-summary")
def daily_summary():
    rows = db.logs_since(_start_of_today_utc())
    top, total = _aggregate(rows)

    aggregates = {
        "total_seconds": total,
        "sessions": len(rows),
        "by_app": [{"app": a, "seconds": s} for a, s in top],
    }

    # Compact, factual brief for the model to react to — no spin, just numbers.
    if total == 0:
        summary = "no focused activity has been tracked yet today."
    else:
        lines = [f"total tracked focus today: {_fmt_dur(total)}, across {len(rows)} sessions.", "breakdown by app:"]
        lines += [
            f"- {a}: {_fmt_dur(s)} ({round(100 * s / total)}%)" for a, s in top
        ]
        summary = "\n".join(lines)

    user_msg = (
        "here's my auto-tracked focus data for today:\n\n"
        f"{summary}\n\n"
        "give me a short in-character recap of my day. be honest about the time "
        "sinks, but give real credit where i actually put in focus. end with ONE "
        "concrete piece of guidance for tomorrow. keep it to a few sentences."
    )
    message = chat(
        [{"role": "user", "content": user_msg}],
        system=build_system_prompt(user_name=USER_NAME),
    )
    return {
        "date": datetime.now().astimezone().date().isoformat(),
        "aggregates": aggregates,
        "summary": summary,
        "message": message,
    }


@app.get("/nudge")
def nudge():
    rows = db.logs_since(_minutes_ago_utc(NUDGE_WINDOW_MIN))
    top, total = _aggregate(rows)

    # Split the window's logged time into likely-distraction vs. real focus.
    distraction = focus = 0
    for r in rows:
        secs = r["seconds"] or 0
        text = f"{r['app'] or ''} {r['activity'] or ''}".lower()
        if any(k in text for k in DISTRACTION_APPS):
            distraction += secs
        elif any(k in text for k in FOCUS_APPS):
            focus += secs

    if distraction >= focus and distraction >= max(total * 0.5, MIN_ACTIVE_SECONDS):
        state = "distraction"
    elif focus >= max(distraction, MIN_ACTIVE_SECONDS):
        state = "focus"
    else:
        # Little/no logged activity, or a mixed bag. Note: the logger only
        # flushes a row when focus *changes*, so a long unbroken focus stretch
        # also shows up as "no recent rows" — so we deliberately stay quiet
        # here rather than risk nagging someone who's actually heads-down.
        state = "quiet"

    base = {"state": state, "window_seconds": total}

    # Never nag when working: focus / quiet get a short, static, non-LLM reply.
    if state == "focus":
        return {**base, "nudge": "locked in 🫡 keep cooking — no notes."}
    if state == "quiet":
        return {**base, "nudge": ""}

    # Distraction: one punchy in-character line to get back to it.
    top_app = top[0][0] if top else "something shiny"
    user_msg = (
        f"i've spent most of the last {NUDGE_WINDOW_MIN} minutes on {top_app} "
        "instead of doing my actual work. hit me with ONE short, punchy line to "
        "get me back to it. one sentence max, no lecture."
    )
    line = chat(
        [{"role": "user", "content": user_msg}],
        system=build_system_prompt(user_name=USER_NAME),
    ).strip()
    return {**base, "nudge": line, "top_app": top_app}
