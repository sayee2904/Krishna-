# finetune — teaching Krish's voice

`build_dataset.py` builds `krish_dataset.jsonl`, the LoRA training set for the
**Krish voice**: the sarcastic, gen-z, tough-love Krishna tone.

This teaches **voice, grounded in the Gita** — not facts. Each example is
generated straight from the source texts: for every verse in `data/gita.json`
Krish answers a realistic student situation by *living out* that verse's
teaching (without quoting it), plus a batch grounded in well-known
**Mahabharata** moments and Krishna's role in them.

Factual recall is deliberately **not** trained in here — at runtime that comes
from **RAG** over the Gita (see the top-level README). Keeping facts in RAG and
voice in the fine-tune stops the model from hallucinating scripture.

## Generating

```bash
python finetune/build_dataset.py
```

- The generator is your **local Ollama** model, set via `GEN_MODEL`
  (default `qwen2.5:3b`). **Generator quality caps dataset quality** — if you've
  pulled it, `GEN_MODEL=qwen2.5:7b` produces noticeably better data, just slower.
- Tune size with `GITA_PAIRS_PER_VERSE` (default 18) and `MAHA_PAIRS`
  (default 50); the defaults target ~250–350 examples.
- Output is validated (non-empty, sane length, generator preambles stripped,
  near-identical instructions de-duped) and written to `krish_dataset.jsonl`.
  Each line is `{"instruction": <student situation>, "output": <Krish reply>}`.
