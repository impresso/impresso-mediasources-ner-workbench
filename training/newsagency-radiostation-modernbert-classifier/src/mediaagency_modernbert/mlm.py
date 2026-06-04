from __future__ import annotations

import argparse
import inspect
import json
import math
from pathlib import Path


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(".env"))


def import_runtime():
    load_dotenv_if_available()
    try:
        import accelerate
        import torch
        from datasets import load_dataset, load_from_disk
        from transformers import AutoModelForMaskedLM, AutoTokenizer, DataCollatorForLanguageModeling, Trainer, TrainingArguments
    except ImportError as exc:
        raise SystemExit(
            "Continued MLM training requires accelerate>=1.1.0, datasets, torch, and transformers. "
            'Install with: python -m pip install -e ".[hf]" && '
            "python -m pip install -e training/newsagency-radiostation-modernbert-classifier"
        ) from exc
    return {
        "accelerate": accelerate,
        "torch": torch,
        "load_dataset": load_dataset,
        "load_from_disk": load_from_disk,
        "AutoModelForMaskedLM": AutoModelForMaskedLM,
        "AutoTokenizer": AutoTokenizer,
        "DataCollatorForLanguageModeling": DataCollatorForLanguageModeling,
        "Trainer": Trainer,
        "TrainingArguments": TrainingArguments,
    }


def train(args: argparse.Namespace) -> None:
    runtime = import_runtime()
    print("Loading MLM dataset...")
    dataset = runtime["load_dataset"](
        "json",
        data_files={"train": args.train_file, "validation": args.validation_file},
    )
    tokenizer = runtime["AutoTokenizer"].from_pretrained(args.model_name_or_path)
    model = runtime["AutoModelForMaskedLM"].from_pretrained(args.model_name_or_path)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=args.max_sequence_len,
            padding="max_length" if args.pad_to_max_length else False,
        )

    tokenized_cache_dir = Path(args.tokenized_cache_dir) if args.tokenized_cache_dir else None
    if tokenized_cache_dir and tokenized_cache_dir.exists():
        print(f"Loading tokenized MLM dataset from {tokenized_cache_dir}...")
        tokenized = runtime["load_from_disk"](str(tokenized_cache_dir))
    else:
        print("Tokenizing MLM dataset...")
        map_kwargs = {
            "batched": True,
            "batch_size": args.map_batch_size,
            "remove_columns": dataset["train"].column_names,
            "desc": "Tokenizing MLM dataset",
        }
        if args.preprocessing_num_workers > 1:
            map_kwargs["num_proc"] = args.preprocessing_num_workers
        tokenized = dataset.map(tokenize_function, **map_kwargs)
        if tokenized_cache_dir:
            print(f"Saving tokenized MLM dataset to {tokenized_cache_dir}...")
            tokenized.save_to_disk(str(tokenized_cache_dir))
    if args.max_train_samples > 0:
        train_count = min(args.max_train_samples, len(tokenized["train"]))
        print(f"Limiting MLM train dataset to {train_count:,} samples from {len(tokenized['train']):,}.")
        tokenized["train"] = tokenized["train"].select(range(train_count))
    if args.max_eval_samples > 0:
        eval_count = min(args.max_eval_samples, len(tokenized["validation"]))
        print(f"Limiting MLM validation dataset to {eval_count:,} samples from {len(tokenized['validation']):,}.")
        tokenized["validation"] = tokenized["validation"].select(range(eval_count))
    data_collator = runtime["DataCollatorForLanguageModeling"](
        tokenizer=tokenizer,
        mlm=True,
        mlm_probability=args.mlm_probability,
    )
    optimizer_steps_per_epoch = math.ceil(
        len(tokenized["train"]) / max(1, args.train_batch_size * args.gradient_accumulation_steps)
    )
    warmup_steps = args.warmup_steps
    if warmup_steps < 0:
        warmup_steps = math.ceil(optimizer_steps_per_epoch * args.warmup_fraction)
    eval_steps = None
    training_arg_kwargs = {
        "output_dir": args.output_dir,
        "per_device_train_batch_size": args.train_batch_size,
        "per_device_eval_batch_size": args.eval_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "num_train_epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "warmup_steps": warmup_steps,
        "logging_steps": args.logging_steps,
        "save_total_limit": args.save_total_limit,
        "report_to": "none",
        "dataloader_pin_memory": False,
        "seed": args.seed,
    }
    signature = inspect.signature(runtime["TrainingArguments"])
    if "save_strategy" in signature.parameters:
        training_arg_kwargs["save_strategy"] = args.save_strategy
    if args.save_strategy == "steps" and args.save_steps > 0:
        training_arg_kwargs["save_steps"] = args.save_steps
    if args.evals_per_epoch > 0:
        eval_steps = max(1, optimizer_steps_per_epoch // args.evals_per_epoch)
        strategy_arg = "eval_strategy" if "eval_strategy" in signature.parameters else "evaluation_strategy"
        training_arg_kwargs[strategy_arg] = "steps"
        training_arg_kwargs["eval_steps"] = eval_steps
    training_args = runtime["TrainingArguments"](
        **training_arg_kwargs,
    )
    trainer = runtime["Trainer"](
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=data_collator,
    )
    print("Starting continued MLM training...")
    train_result = trainer.train()
    metrics = trainer.evaluate()
    final_dir = Path(args.output_dir) / "final"
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)
    write_json(Path(args.output_dir) / "train_metrics.json", train_result.metrics)
    write_json(Path(args.output_dir) / "eval_metrics.json", metrics)
    write_json(
        Path(args.output_dir) / "model_card_data.json",
        {
            "base_model": args.model_name_or_path,
            "task": "continued-mlm",
            "train_file": args.train_file,
            "validation_file": args.validation_file,
            "mlm_probability": args.mlm_probability,
            "max_sequence_len": args.max_sequence_len,
            "pad_to_max_length": args.pad_to_max_length,
            "tokenized_cache_dir": args.tokenized_cache_dir,
            "preprocessing_num_workers": args.preprocessing_num_workers,
            "map_batch_size": args.map_batch_size,
            "max_train_samples": args.max_train_samples,
            "max_eval_samples": args.max_eval_samples,
            "train_samples_used": len(tokenized["train"]),
            "eval_samples_used": len(tokenized["validation"]),
            "per_device_train_batch_size": args.train_batch_size,
            "gradient_checkpointing": args.gradient_checkpointing,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "effective_train_batch_size_per_device": args.train_batch_size * args.gradient_accumulation_steps,
            "evals_per_epoch": args.evals_per_epoch,
            "eval_steps": eval_steps,
            "optimizer_steps_per_epoch_estimate": optimizer_steps_per_epoch,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "warmup_steps": warmup_steps,
            "warmup_fraction": args.warmup_fraction if args.warmup_steps < 0 else None,
            "save_strategy": args.save_strategy,
            "save_steps": args.save_steps if args.save_strategy == "steps" else None,
        },
    )
    print(f"Final continued-MLM model saved to: {final_dir}")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Continue MLM pretraining for multilingual Impresso mmBERT.")
    parser.add_argument("--model-name-or-path", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--train-file", required=True)
    parser.add_argument("--validation-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-sequence-len", type=int, default=512)
    parser.add_argument("--pad-to-max-length", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--tokenized-cache-dir", default=None, help="Optional datasets.save_to_disk directory for reusable tokenized MLM data.")
    parser.add_argument("--preprocessing-num-workers", type=int, default=1)
    parser.add_argument("--map-batch-size", type=int, default=1000)
    parser.add_argument("--max-train-samples", type=int, default=0, help="Use only the first N sampled training rows. Use 0 for all rows.")
    parser.add_argument("--max-eval-samples", type=int, default=0, help="Use only the first N sampled validation rows. Use 0 for all rows.")
    parser.add_argument("--mlm-probability", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--train-batch-size", type=int, default=2)
    parser.add_argument("--eval-batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=16)
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-steps", type=int, default=-1, help="Warmup steps. Use -1 to compute from --warmup-fraction.")
    parser.add_argument("--warmup-fraction", type=float, default=0.06)
    parser.add_argument("--evals-per-epoch", type=int, default=3, help="Run validation this many times per epoch. Use 0 for final evaluation only.")
    parser.add_argument("--save-strategy", choices=["no", "steps", "epoch"], default="no", help="Intermediate checkpoint strategy. The final model is always saved to output_dir/final.")
    parser.add_argument("--save-steps", type=int, default=0)
    parser.add_argument("--logging-steps", type=int, default=50)
    parser.add_argument("--save-total-limit", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
