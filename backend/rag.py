"""Retrieval over the Bhagavad Gita ChromaDB collection."""

from pathlib import Path

import chromadb
from ollama import Client

from backend.config import OLLAMA_HOST

ROOT_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT_DIR / "chroma_db"
COLLECTION_NAME = "gita"
EMBED_MODEL = "nomic-embed-text"

# Max cosine distance for a verse to count as "relevant" to the query.
# Empirically, on-topic emotional/study queries land ~0.48-0.53 here while
# clearly off-topic ones (weather, CSS) sit at ~0.56+, so 0.55 separates them.
RELEVANCE_THRESHOLD = 0.55

_ollama = Client(host=OLLAMA_HOST)
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))


def _collection():
    return _client.get_collection(COLLECTION_NAME)


def retrieve(query: str, k: int = 3) -> list[dict]:
    """Embed `query` and return the top-k matching Gita verses.

    Each result is a dict with id, chapter, verse, and translation. Returns an
    empty list if the collection is missing or empty (e.g. not yet ingested).
    """
    query = (query or "").strip()
    if not query:
        return []

    try:
        collection = _collection()
        embedding = _ollama.embed(model=EMBED_MODEL, input=query)["embeddings"][0]
        result = collection.query(query_embeddings=[embedding], n_results=k)
    except Exception:
        return []

    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    verses = []
    for meta, dist in zip(metadatas, distances):
        # Skip verses that aren't close enough to be genuinely relevant.
        if dist > RELEVANCE_THRESHOLD:
            continue
        verses.append(
            {
                "id": meta["id"],
                "chapter": meta["chapter"],
                "verse": meta["verse"],
                "translation": meta["translation"],
            }
        )
    return verses
