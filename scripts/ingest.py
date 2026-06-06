#!/usr/bin/env python3
"""Ingest the Bhagavad Gita verses into a persistent ChromaDB collection.

Reads data/gita.json, embeds each verse with Ollama's nomic-embed-text model,
and stores it in a Chroma collection at ./chroma_db with the verse fields as
metadata. Idempotent: the collection is dropped and rebuilt on every run.
"""

import json
from pathlib import Path

import chromadb
from ollama import Client

ROOT_DIR = Path(__file__).resolve().parent.parent
GITA_PATH = ROOT_DIR / "data" / "gita.json"
CHROMA_DIR = ROOT_DIR / "chroma_db"
COLLECTION_NAME = "gita"
EMBED_MODEL = "nomic-embed-text"

_ollama = Client()


def embed(text: str) -> list[float]:
    """Return the embedding vector for a single piece of text."""
    return _ollama.embed(model=EMBED_MODEL, input=text)["embeddings"][0]


def main() -> None:
    verses = json.loads(GITA_PATH.read_text(encoding="utf-8"))

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Idempotent rebuild: drop any existing collection, then recreate it.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    ids, embeddings, documents, metadatas = [], [], [], []
    for v in verses:
        doc = f"Chapter {v['chapter']}.{v['verse']} — {v['theme']}: {v['translation']}"
        ids.append(v["id"])
        embeddings.append(embed(doc))
        documents.append(doc)
        metadatas.append(
            {
                "id": v["id"],
                "chapter": v["chapter"],
                "verse": v["verse"],
                "speaker": v["speaker"],
                "theme": v["theme"],
                "sanskrit": v["sanskrit"],
                "translation": v["translation"],
            }
        )

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"Indexed {len(ids)} verses into '{COLLECTION_NAME}' at {CHROMA_DIR}")


if __name__ == "__main__":
    main()
