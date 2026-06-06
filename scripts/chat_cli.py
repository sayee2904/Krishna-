#!/usr/bin/env python3
"""Terminal chat loop for talking to Krish.

Uses only the stdlib. POSTs each line you type to the backend /chat endpoint
and prints Krish's reply. Type "quit" to exit.
"""

import json
import urllib.error
import urllib.request

CHAT_URL = "http://localhost:8000/chat"


def ask(text: str) -> str:
    payload = json.dumps(
        {"messages": [{"role": "user", "content": text}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        CHAT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data["reply"]


def main() -> None:
    print("talking to krish. type 'quit' to exit.\n")
    while True:
        try:
            text = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() == "quit":
            break
        try:
            reply = ask(text)
        except urllib.error.URLError as e:
            print(f"[error: could not reach backend at {CHAT_URL} — {e}]")
            continue
        print(f"krish: {reply}\n")


if __name__ == "__main__":
    main()
