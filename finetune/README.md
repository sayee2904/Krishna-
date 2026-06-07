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

## Training (local QLoRA)

`train_lora.py` QLoRA fine-tunes `Qwen2.5-3B-Instruct` (4-bit, via Unsloth) on
`krish_dataset.jsonl`. Each row is rendered with the Qwen chat template:
system = the Krish persona from `backend/persona.py`, user = `instruction`,
assistant = `output` — so the model trains on the exact system prompt it serves
with. It prints GPU/VRAM at start, runs a 3-prompt generation test before and
after training, then saves the LoRA adapter to `krish-lora/` and a merged
16-bit model to `merged/`.

Run it **inside the training venv**:

```bash
python finetune/train_lora.py
```

Keep `nvidia-smi` open in another terminal to watch VRAM. This is tuned for a
6GB card (RTX 4050): batch 2, grad accum 4, bf16, `paged_adamw_8bit`, 3 epochs,
`max_seq_length=1024`. **If you OOM**, back off one knob at a time, in order:

1. drop `PER_DEVICE_BATCH` 2 → 1
2. drop `MAX_SEQ_LENGTH` 1024 → 512
3. drop `BASE_MODEL` to `unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit`
