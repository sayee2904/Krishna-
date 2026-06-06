# krish

A local, Ubuntu-based AI companion — a sarcastic Gen-Z Krishna desktop buddy that
logs your work, nudges you to stay on track, and drops wisdom when you need it.
Everything runs **locally** on your machine: no cloud calls, no telemetry, your
data stays yours.

> Part accountability buddy, part divine charioteer, part group-chat menace.

---

## What it does

- **Desktop pet** — a little Krishna that lives on your screen, reacts to what
  you're doing, and talks back with Gen-Z sarcasm.
- **Work logging & guidance** — quietly tracks what you're working on and offers
  (occasionally unsolicited) guidance to keep you moving.
- **Bhagavad Gita knowledge** — when you ask for the real stuff, it answers
  grounded in the actual text of the Gita rather than making things up.

## Architecture: "fine-tune for voice, RAG for knowledge"

The core design principle is a clean split between **how Krish talks** and
**what Krish knows**:

- **Fine-tune for voice** — a LoRA fine-tune over a small local base model
  (`qwen2.5:3b` via Ollama) teaches Krish its *personality*: the sarcastic,
  Gen-Z, lovingly-judgmental Krishna tone. Fine-tuning shapes style and
  voice, not facts.
- **RAG for knowledge** — the actual wisdom (verses, meaning, context from the
  Bhagavad Gita) lives in a **ChromaDB** vector store. At query time we retrieve
  the relevant passages and feed them to the model as context, so answers are
  grounded in the source text and stay accurate.

This separation keeps the model small and fast, prevents the fine-tune from
hallucinating scripture, and lets us update knowledge (re-index) independently
from personality (re-train).

```
   You ──▶ Backend (FastAPI)
              │
              ├── retrieve ──▶ ChromaDB (Gita verses)   ← RAG: knowledge
              │
              └── generate ──▶ Ollama (qwen2.5:3b + Krish LoRA)  ← fine-tune: voice
                                   │
                                   ▼
                              Desktop pet (UI)
```

## Repo structure

```
krish/
├── backend/     FastAPI service: chat, RAG retrieval, work-logging endpoints
├── pet/         Desktop pet UI (the on-screen Krishna companion)
├── finetune/    LoRA training scripts & configs for the Krish voice
├── data/        Source data: Bhagavad Gita text, training datasets, work logs
├── scripts/     Setup / indexing / utility scripts
├── requirements.txt
├── .env.example
└── README.md
```

## Getting started

```bash
# 1. Create & activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env        # then edit if needed

# 4. Pull the base model with Ollama
ollama pull qwen2.5:3b
```

## Roadmap — build phases

- **Phase 0 — Scaffold** *(done)*: repo structure, venv, dependencies, env config.
- **Phase 1 — Backend core**: FastAPI app, Ollama chat endpoint, `.env` loading,
  health check.
- **Phase 2 — RAG over the Gita**: ingest the Bhagavad Gita into ChromaDB, build
  the retrieval pipeline, wire grounded answers into the chat endpoint.
- **Phase 3 — Voice fine-tune**: build the persona dataset, run the LoRA
  fine-tune, merge & convert to GGUF, register the Krish model with Ollama.
- **Phase 4 — Desktop pet**: on-screen Krishna UI that talks to the backend,
  with idle animations and reactions.
- **Phase 5 — Work logging & guidance**: capture what you're working on, persist
  logs, and surface proactive, in-character nudges.
- **Phase 6 — Polish**: packaging for Ubuntu, autostart, tray controls, settings.

## License

TBD.
