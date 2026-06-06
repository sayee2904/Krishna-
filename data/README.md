# data/

Source data and local state for krish.

## gita.json

A **curated seed** of Bhagavad Gita verses used for RAG (retrieval-augmented
generation). Each entry has these fields:

| field         | description                                              |
| ------------- | -------------------------------------------------------- |
| `id`          | stable verse id, e.g. `"BG2.47"`                         |
| `chapter`     | chapter number                                           |
| `verse`       | verse number                                             |
| `speaker`     | who is speaking (usually Krishna)                        |
| `theme`       | short comma-separated themes, used in the embedding text |
| `sanskrit`    | transliterated Sanskrit                                  |
| `translation` | plain-English, friendly translation                      |

This seed is intentionally small — a handpicked set of verses that map well to
the kinds of things a stressed AI/ML student actually says (procrastination,
fear of results, burnout, motivation). It's enough to make the RAG layer real
and demonstrable.

**It can be replaced** with a full public-domain ~700-verse dataset of the
Bhagavad Gita as long as it uses the **same fields** above. Drop in the larger
file and re-run the ingest:

```bash
python scripts/ingest.py
```

The ingest is idempotent — it rebuilds the ChromaDB collection from scratch — so
swapping datasets is just replace-and-reingest.

## Other contents

- `krish.db` — SQLite database of chat history and activity logs (gitignored).
