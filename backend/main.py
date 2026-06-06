"""FastAPI app for the krish backend."""

from fastapi import FastAPI
from pydantic import BaseModel

from backend import db
from backend.config import OLLAMA_MODEL, USER_NAME
from backend.llm import chat
from backend.persona import build_system_prompt

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
    if request.messages:
        latest = request.messages[-1]
        db.save_message(latest.role, latest.content)

    # Build context from persisted history, not just this request — so Krish
    # remembers across separate calls.
    history = db.recent_messages(limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    system = build_system_prompt(user_name=USER_NAME)
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
