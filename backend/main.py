"""FastAPI app for the krish backend."""

from fastapi import FastAPI
from pydantic import BaseModel

from backend.config import OLLAMA_MODEL
from backend.llm import chat
from backend.persona import KRISHNA_SYSTEM

app = FastAPI(title="krish backend")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    messages = [m.model_dump() for m in request.messages]
    reply = chat(messages, system=KRISHNA_SYSTEM)
    return {"reply": reply}
