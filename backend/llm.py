"""Thin wrapper over the Ollama python client."""

from ollama import Client

from backend.config import OLLAMA_HOST, OLLAMA_MODEL

_client = Client(host=OLLAMA_HOST)


def chat(messages: list[dict], system: str) -> str:
    """Send a chat to the configured Ollama model.

    Prepends `system` as a system message ahead of the conversation
    `messages` (each a dict with "role" and "content") and returns the
    assistant's reply text.
    """
    full_messages = [{"role": "system", "content": system}, *messages]
    response = _client.chat(model=OLLAMA_MODEL, messages=full_messages)
    return response["message"]["content"]
