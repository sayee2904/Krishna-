"""FastAPI app for the krish backend."""

from fastapi import FastAPI
from pydantic import BaseModel

from backend import db
from backend.config import OLLAMA_MODEL, USER_NAME
from backend.llm import chat
from backend.persona import build_system_prompt
from backend.rag import retrieve

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
