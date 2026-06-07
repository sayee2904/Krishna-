#!/usr/bin/env python3
"""Local QLoRA fine-tune of the Krish voice — Ubuntu + RTX 4050 (6GB).

Teaches the *voice* (see finetune/README.md): sarcastic, gen-z, tough-love
Krishna. Facts stay in RAG at runtime, not here.

This is tuned to fit in 6GB of VRAM via Unsloth + 4-bit QLoRA. Run it inside
the training venv:

    python finetune/train_lora.py

Watch `nvidia-smi` in another terminal. If you hit OOM, walk down these knobs
in order (see the bottom of finetune/README.md):
    1. PER_DEVICE_BATCH 2 -> 1
    2. MAX_SEQ_LENGTH   1024 -> 512
    3. BASE_MODEL  Qwen2.5-3B -> unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit
"""

import os

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

import json
import sys
from pathlib import Path

import torch

# Unsloth must be imported before transformers/trl so its patches land.
from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTConfig, SFTTrainer

# Pull the Krish persona straight from the backend so the system prompt the
# model trains on is the exact one it serves with.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.persona import KRISHNA_SYSTEM  # noqa: E402

# --- config (6GB-safe) -------------------------------------------------------
BASE_MODEL = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
MAX_SEQ_LENGTH = 640
RANDOM_STATE = 42

DATASET_PATH = Path(__file__).parent / "krish_dataset.jsonl"
OUTPUT_DIR = Path(__file__).parent / "outputs"
LORA_DIR = Path(__file__).parent / "krish-lora"
MERGED_DIR = Path(__file__).parent / "merged"

PER_DEVICE_BATCH = 1
GRAD_ACCUM = 8
WARMUP_STEPS = 10
EPOCHS = 3
LEARNING_RATE = 2e-4
LOGGING_STEPS = 5

TEST_PROMPTS = [
    "bro i keep refreshing my email waiting for the internship result and i can't focus on anything else",
    "i've been procrastinating on my ml assignment for 3 days. due tomorrow. send help",
    "my model won't converge no matter what i try and i'm starting to think i'm just not cut out for this",
]


def vram_report(tag: str) -> None:
    """Print GPU name + current VRAM usage."""
    if not torch.cuda.is_available():
        print(f"[{tag}] no CUDA device visible — training will be painfully slow on CPU")
        return
    name = torch.cuda.get_device_name(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    reserved = torch.cuda.memory_reserved(0) / 1024**3
    allocated = torch.cuda.memory_allocated(0) / 1024**3
    print(f"[{tag}] {name} | {total:.1f}GB total | {reserved:.2f}GB reserved | {allocated:.2f}GB allocated")


def load_examples(tokenizer) -> Dataset:
    """Read the jsonl and render each row with the Qwen chat template.

    system = the Krish persona, user = instruction, assistant = output.

    Belt-and-suspenders against the cross-entropy length mismatch: SFTConfig's
    max_length already truncates, but we also drop any example whose tokenized
    length exceeds MAX_SEQ_LENGTH so an over-length sequence can never reach the
    loss with misaligned input/labels.
    """
    rows = []
    total = 0
    dropped = 0
    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            ex = json.loads(line)
            messages = [
                {"role": "system", "content": KRISHNA_SYSTEM},
                {"role": "user", "content": ex["instruction"]},
                {"role": "assistant", "content": ex["output"]},
            ]
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
            # Count tokens the same way the trainer will (the template already
            # emits special tokens inline, so don't add them again).
            n_tokens = len(tokenizer(text, add_special_tokens=False)["input_ids"])
            if n_tokens > MAX_SEQ_LENGTH:
                dropped += 1
                continue
            rows.append({"text": text})
    kept = len(rows)
    print(
        f"loaded {total} examples from {DATASET_PATH.name} | "
        f"kept {kept}, dropped {dropped} over {MAX_SEQ_LENGTH} tokens"
    )
    return Dataset.from_list(rows)


def run_generation_test(model, tokenizer, tag: str) -> None:
    """Generate replies to the test prompts so we can eyeball voice drift."""
    FastLanguageModel.for_inference(model)
    print(f"\n===== generation test: {tag} =====")
    for prompt in TEST_PROMPTS:
        messages = [
            {"role": "system", "content": KRISHNA_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(model.device)
        out = model.generate(
            input_ids=inputs,
            max_new_tokens=128,
            temperature=0.8,
            top_p=0.95,
            do_sample=True,
            use_cache=True,
        )
        reply = tokenizer.decode(out[0][inputs.shape[1]:], skip_special_tokens=True)
        print(f"\n  USER: {prompt}\n  KRISH: {reply.strip()}")
    print(f"===== end {tag} =====\n")


def main() -> None:
    vram_report("start")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # auto: bf16 on Ampere+ (the 4050 qualifies)
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",   # attention
            "gate_proj", "up_proj", "down_proj",      # mlp
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=RANDOM_STATE,
    )

    dataset = load_examples(tokenizer)

    # Baseline voice before any training.
    run_generation_test(model, tokenizer, "BEFORE training")
    FastLanguageModel.for_training(model)

    # trl 0.24: truncation length is `max_length` on SFTConfig (not the old
    # `max_seq_length` kwarg on SFTTrainer). Setting it here is what guarantees
    # over-length sequences are truncated *consistently* for both input and
    # labels before they ever reach the cross-entropy loss.
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            dataset_text_field="text",
            max_length=MAX_SEQ_LENGTH,
            packing=False,
            per_device_train_batch_size=PER_DEVICE_BATCH,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=WARMUP_STEPS,
            num_train_epochs=EPOCHS,
            learning_rate=LEARNING_RATE,
            bf16=True,
            optim="paged_adamw_8bit",
            logging_steps=LOGGING_STEPS,
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=RANDOM_STATE,
            output_dir=str(OUTPUT_DIR),
            report_to="none",
        ),
    )

    trainer.train()
    vram_report("after training")

    # Voice after training — compare against the BEFORE block above.
    run_generation_test(model, tokenizer, "AFTER training")

    # Save the LoRA adapter (small, stackable on the base model)...
    model.save_pretrained(str(LORA_DIR))
    tokenizer.save_pretrained(str(LORA_DIR))
    print(f"saved LoRA adapter -> {LORA_DIR}")

    # ...and a merged 16-bit model for easy serving.
    model.save_pretrained_merged(
        str(MERGED_DIR), tokenizer, save_method="merged_16bit"
    )
    print(f"saved merged 16-bit model -> {MERGED_DIR}")


if __name__ == "__main__":
    main()
