from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data import labels_to_entities, load_jsonl, load_label_map, make_windows, write_json, write_jsonl
from .decoding import (
    DECODER_ALL_SUBTOKEN_VITERBI,
    DECODER_CHOICES,
    DECODER_FIRST_SUBTOKEN,
    DECODER_FIRST_SUBTOKEN_VITERBI,
    compile_bio_schema,
    decode_document,
)
from .metrics import entity_metrics, entity_metrics_by_label, token_metrics


IGNORE_INDEX = -100
FIRST_SUBTOKEN_DECODING = DECODER_FIRST_SUBTOKEN
DEFAULT_DECODER = DECODER_FIRST_SUBTOKEN_VITERBI


@dataclass
class Runtime:
    torch: Any
    Adafactor: Any
    AutoConfig: Any
    AutoModelForTokenClassification: Any
    AutoTokenizer: Any


class WindowDataset:
    def __init__(
        self,
        windows: list[Any],
        tokenizer: Any,
        max_length: int,
        *,
        label_all_tokens: bool = False,
        continuation_label_ids: dict[int, int] | None = None,
    ):
        self.windows = windows
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.label_all_tokens = label_all_tokens
        self.continuation_label_ids = continuation_label_ids or {}

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        window = self.windows[index]
        encoding = self.tokenizer(
            window.tokens,
            is_split_into_words=True,
            truncation=True,
            max_length=self.max_length,
            return_offsets_mapping=False,
        )
        labels: list[int] = []
        word_ids = encoding.word_ids()
        previous_word_id = None
        for word_id in word_ids:
            if word_id is None:
                labels.append(IGNORE_INDEX)
            elif word_id != previous_word_id:
                labels.append(window.label_ids[word_id])
            elif self.label_all_tokens:
                label_id = int(window.label_ids[word_id])
                labels.append(self.continuation_label_ids.get(label_id, label_id))
            else:
                labels.append(IGNORE_INDEX)
            previous_word_id = word_id
        encoding["labels"] = labels
        encoding["window_index"] = index
        encoding["doc_index"] = window.doc_index
        encoding["start_word"] = window.start_word
        encoding["word_ids_for_eval"] = [-1 if word_id is None else int(word_id) for word_id in word_ids]
        return encoding


class Collator:
    def __init__(self, tokenizer: Any, torch: Any):
        self.tokenizer = tokenizer
        self.torch = torch

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, Any]:
        meta = {
            "window_index": [feature.pop("window_index") for feature in features],
            "doc_index": [feature.pop("doc_index") for feature in features],
            "start_word": [feature.pop("start_word") for feature in features],
            "word_ids_for_eval": [feature.pop("word_ids_for_eval") for feature in features],
        }
        batch = self.tokenizer.pad(features, padding=True, return_tensors="pt")
        batch.update(meta)
        return batch


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(".env"))


def import_runtime() -> Runtime:
    load_dotenv_if_available()
    try:
        import torch
        from transformers import Adafactor, AutoConfig, AutoModelForTokenClassification, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Training requires torch and transformers. Install with: "
            'python -m pip install -e ".[hf]" && '
            "python -m pip install -e training/newsagency-radiostation-modernbert-classifier"
        ) from exc
    return Runtime(
        torch=torch,
        Adafactor=Adafactor,
        AutoConfig=AutoConfig,
        AutoModelForTokenClassification=AutoModelForTokenClassification,
        AutoTokenizer=AutoTokenizer,
    )


def set_seed(seed: int, torch: Any) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def device_for(name: str, torch: Any) -> Any:
    if name == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(name)


def resolve_model_ref(value: str) -> str:
    if value.startswith("hf://"):
        return value[len("hf://") :]
    return value


def git_provenance(repo: Path | str = ".") -> dict[str, Any]:
    repo_path = Path(repo)

    def run_git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_path,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return result.stdout.strip()

    commit = run_git("rev-parse", "HEAD")
    short_commit = run_git("rev-parse", "--short", "HEAD") if commit else None
    status = run_git("status", "--short")
    return {
        "commit": commit,
        "short_commit": short_commit,
        "dirty": None if status is None else bool(status),
        "status": "unknown" if commit is None or status is None else ("dirty" if status else "clean"),
    }


def label_map_from_model_config(config: Any) -> dict[str, dict[str, Any]]:
    id2label_raw = getattr(config, "id2label", None)
    label2id_raw = getattr(config, "label2id", None)
    num_labels = getattr(config, "num_labels", None)
    if not isinstance(id2label_raw, dict) or not id2label_raw:
        raise ValueError("checkpoint config must define id2label")
    id2label = {str(idx): str(label) for idx, label in sorted(id2label_raw.items(), key=lambda item: int(item[0]))}
    label2id = {label: int(idx) for idx, label in id2label.items()}
    expected_ids = {str(idx) for idx in range(len(id2label))}
    if set(id2label) != expected_ids:
        raise ValueError("checkpoint config id2label ids must be contiguous from 0")
    if num_labels is not None and int(num_labels) != len(id2label):
        raise ValueError(
            f"checkpoint config num_labels={num_labels} does not match id2label length={len(id2label)}"
        )
    if not isinstance(label2id_raw, dict):
        raise ValueError("checkpoint config must define label2id")
    normalized_label2id = {str(label): int(idx) for label, idx in label2id_raw.items()}
    if normalized_label2id != label2id:
        raise ValueError("checkpoint config id2label and label2id must be exact inverses")
    if not id2label or id2label.get("0") != "O":
        raise ValueError("checkpoint config must define label 0 as O")
    if len(set(id2label.values())) != len(id2label):
        raise ValueError("checkpoint config contains duplicate label names")
    compile_bio_schema({int(idx): label for idx, label in id2label.items()})
    return {
        "id2label": id2label,
        "label2id": label2id,
    }


def entity_type_set(label_map: dict[str, Any]) -> set[str]:
    return {
        str(label)[2:]
        for label in label_map["label2id"]
        if str(label).startswith(("B-", "I-"))
    }


def label_compatibility_summary(dataset_label_map: dict[str, Any], checkpoint_label_map: dict[str, Any]) -> dict[str, Any]:
    dataset_labels = set(str(label) for label in dataset_label_map["label2id"])
    checkpoint_labels = set(str(label) for label in checkpoint_label_map["label2id"])
    dataset_entities = entity_type_set(dataset_label_map)
    checkpoint_entities = entity_type_set(checkpoint_label_map)
    return {
        "dataset_labels": len(dataset_labels),
        "checkpoint_labels": len(checkpoint_labels),
        "shared_labels": len(dataset_labels & checkpoint_labels),
        "dataset_only": sorted(dataset_labels - checkpoint_labels),
        "checkpoint_only": sorted(checkpoint_labels - dataset_labels),
        "dataset_entity_types": len(dataset_entities),
        "checkpoint_entity_types": len(checkpoint_entities),
        "shared_entity_types": len(dataset_entities & checkpoint_entities),
        "dataset_only_entity_types": sorted(dataset_entities - checkpoint_entities),
        "checkpoint_only_entity_types": sorted(checkpoint_entities - dataset_entities),
    }


def evaluation_label_map(args: argparse.Namespace, runtime: Runtime) -> dict[str, Any]:
    if not args.use_checkpoint_label_map:
        return load_label_map(args.label_map)
    if not args.checkpoint:
        raise ValueError("--use-checkpoint-label-map requires --checkpoint")
    source = resolve_model_ref(args.checkpoint)
    return label_map_from_model_config(runtime.AutoConfig.from_pretrained(source))


def load_model_and_tokenizer(args: argparse.Namespace, label_map: dict[str, Any], runtime: Runtime) -> tuple[Any, Any]:
    source = resolve_model_ref(args.checkpoint or args.model_name_or_path)
    tokenizer = runtime.AutoTokenizer.from_pretrained(source)
    id2label = {int(idx): label for idx, label in label_map["id2label"].items()}
    label2id = {label: int(idx) for label, idx in label_map["label2id"].items()}
    model = runtime.AutoModelForTokenClassification.from_pretrained(
        source,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
    )
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    if args.freeze_base_model:
        freeze_base_model(model, args.unfreeze_top_layers)
    return model, tokenizer


def classifier_out_features(model: Any) -> int | None:
    classifier = getattr(model, "classifier", None)
    out_features = getattr(classifier, "out_features", None)
    return int(out_features) if out_features is not None else None


def validate_checkpoint_classifier_contract(model: Any, checkpoint_label_map: dict[str, Any]) -> None:
    expected = len(checkpoint_label_map["label2id"])
    config_num_labels = getattr(model.config, "num_labels", None)
    if config_num_labels is not None and int(config_num_labels) != expected:
        raise ValueError(
            f"checkpoint classifier contract violation: config num_labels={config_num_labels}, "
            f"label map labels={expected}"
        )
    out_features = classifier_out_features(model)
    if out_features is not None and out_features != expected:
        raise ValueError(
            f"checkpoint classifier contract violation: classifier out_features={out_features}, "
            f"label map labels={expected}"
        )


def load_eval_model_and_tokenizer(args: argparse.Namespace, runtime: Runtime) -> tuple[Any, Any, dict[str, Any]]:
    source = resolve_model_ref(args.checkpoint or args.model_name_or_path)
    tokenizer = runtime.AutoTokenizer.from_pretrained(source)
    model = runtime.AutoModelForTokenClassification.from_pretrained(source)
    checkpoint_label_map = label_map_from_model_config(model.config)
    validate_checkpoint_classifier_contract(model, checkpoint_label_map)
    return model, tokenizer, checkpoint_label_map


def validate_dataset_label_map(label_map: dict[str, Any]) -> None:
    compile_bio_schema({int(idx): label for idx, label in label_map["id2label"].items()})


def configure_inference_metadata(model: Any, rows: list[dict[str, Any]], *, label_all_tokens: bool) -> None:
    profiles = {str(row.get("tokenization") or "") for row in rows}
    profiles.discard("")
    if len(profiles) > 1:
        raise ValueError(f"training data mixes tokenization profiles: {sorted(profiles)}")
    model.config.annotation_tokenization = next(iter(profiles), "unspecified")
    model.config.label_all_tokens = bool(label_all_tokens)
    model.config.subtoken_labeling = "all_subtokens_b_to_i" if label_all_tokens else "first_subtoken_only"
    model.config.subtoken_decoding = DEFAULT_DECODER


def freeze_base_model(model: Any, unfreeze_top_layers: int) -> None:
    layer_indices = []
    for name, _parameter in model.named_parameters():
        match = re.match(r"model\.layers\.(\d+)\.", name)
        if match:
            layer_indices.append(int(match.group(1)))
    unfreeze_from = None
    if unfreeze_top_layers > 0 and layer_indices:
        unfreeze_from = max(layer_indices) - unfreeze_top_layers + 1

    trainable = 0
    frozen = 0
    for name, parameter in model.named_parameters():
        is_top_layer = False
        match = re.match(r"model\.layers\.(\d+)\.", name)
        if match and unfreeze_from is not None:
            is_top_layer = int(match.group(1)) >= unfreeze_from
        if name.startswith("classifier.") or is_top_layer:
            parameter.requires_grad = True
            trainable += parameter.numel()
        else:
            parameter.requires_grad = False
            frozen += parameter.numel()
    print(
        json.dumps(
            {
                "freeze_base_model": True,
                "unfreeze_top_layers": unfreeze_top_layers,
                "unfreeze_from_layer": unfreeze_from,
                "trainable_parameters": trainable,
                "frozen_parameters": frozen,
            }
        )
    )


def make_optimizer(model: Any, args: argparse.Namespace, runtime: Runtime) -> Any:
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if args.optimizer == "adafactor":
        return runtime.Adafactor(
            parameters,
            lr=args.learning_rate,
            relative_step=False,
            scale_parameter=False,
            warmup_init=False,
            weight_decay=args.weight_decay,
        )
    if args.optimizer == "adamw":
        return runtime.torch.optim.AdamW(parameters, lr=args.learning_rate, weight_decay=args.weight_decay)
    raise ValueError(f"unsupported optimizer: {args.optimizer}")


def continuation_label_ids(label_map: dict[str, Any]) -> dict[int, int]:
    label2id = {str(label): int(label_id) for label, label_id in label_map["label2id"].items()}
    mapping = {label_id: label_id for label_id in label2id.values()}
    for label, label_id in label2id.items():
        if not label.startswith("B-"):
            continue
        inside = f"I-{label[2:]}"
        if inside not in label2id:
            raise ValueError(f"label_all_tokens requires corresponding continuation label: {inside}")
        mapping[label_id] = label2id[inside]
    return mapping


def make_dataloader(
    rows: list[dict[str, Any]],
    tokenizer: Any,
    label_map: dict[str, Any],
    args: argparse.Namespace,
    runtime: Runtime,
    shuffle: bool,
) -> tuple[Any, list[Any]]:
    windows = make_windows(rows, max_words=args.max_words_per_window, stride_words=args.stride_words)
    dataset = WindowDataset(
        windows,
        tokenizer,
        args.max_sequence_len,
        label_all_tokens=bool(args.label_all_tokens),
        continuation_label_ids=continuation_label_ids(label_map) if args.label_all_tokens else None,
    )
    return runtime.torch.utils.data.DataLoader(
        dataset,
        batch_size=args.train_batch_size if shuffle else args.eval_batch_size,
        shuffle=shuffle,
        collate_fn=Collator(tokenizer, runtime.torch),
    ), windows


def count_parameters(model: Any) -> dict[str, int]:
    trainable = 0
    frozen = 0
    for parameter in model.parameters():
        if parameter.requires_grad:
            trainable += parameter.numel()
        else:
            frozen += parameter.numel()
    return {"trainable_parameters": trainable, "frozen_parameters": frozen, "total_parameters": trainable + frozen}


def dataset_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    entity_count = 0
    docs_with_entities = 0
    label_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    token_count = 0
    for row in rows:
        labels = row["token_labels"]
        token_count += len(labels)
        language = row.get("language") or ""
        language_counts[language] = language_counts.get(language, 0) + 1
        entities = labels_to_entities(labels)
        if entities:
            docs_with_entities += 1
        for _start, _stop, label in entities:
            entity_count += 1
            label_counts[label] = label_counts.get(label, 0) + 1
    return {
        "documents": len(rows),
        "tokens": token_count,
        "gold_entities": entity_count,
        "documents_with_entities": docs_with_entities,
        "languages": dict(sorted(language_counts.items())),
        "labels": dict(sorted(label_counts.items())),
    }


def ner_eval_summary(metrics: dict[str, Any], *, top_k: int = 8) -> dict[str, Any]:
    by_label = metrics.get("entity_by_label", {})
    labels = [
        {"label": label, **values}
        for label, values in by_label.items()
        if values.get("gold", 0) or values.get("pred", 0)
    ]
    labels_by_gold = sorted(labels, key=lambda item: (-int(item.get("gold", 0)), item["label"]))[:top_k]
    labels_by_pred = sorted(labels, key=lambda item: (-int(item.get("pred", 0)), item["label"]))[:top_k]
    return {
        "split": metrics.get("split"),
        "documents": metrics.get("documents"),
        "entity_exact_match": {
            "precision": metrics.get("entity_precision"),
            "recall": metrics.get("entity_recall"),
            "f1": metrics.get("entity_f1"),
            "gold": metrics.get("entity_gold"),
            "pred": metrics.get("entity_pred"),
            "correct": metrics.get("entity_correct"),
        },
        "token_non_o": {
            "precision": metrics.get("token_non_o_precision"),
            "recall": metrics.get("token_non_o_recall"),
            "f1": metrics.get("token_non_o_f1"),
            "gold": metrics.get("token_non_o_gold"),
            "pred": metrics.get("token_non_o_pred"),
        },
        "token_accuracy": metrics.get("token_accuracy"),
        "top_entity_labels_by_gold": labels_by_gold,
        "top_entity_labels_by_pred": labels_by_pred,
    }


def metric_is_better(value: float, best: float | None, mode: str, min_delta: float) -> bool:
    if best is None:
        return True
    if mode == "max":
        return value > best + min_delta
    if mode == "min":
        return value < best - min_delta
    raise ValueError(f"unsupported early stopping mode: {mode}")


def train(args: argparse.Namespace, runtime: Runtime) -> None:
    label_map = load_label_map(args.label_map)
    train_rows = load_jsonl(args.train_jsonl, label_map=label_map)
    validation_rows = load_jsonl(args.validation_jsonl, label_map=label_map) if args.validation_jsonl else []
    model, tokenizer = load_model_and_tokenizer(args, label_map, runtime)
    configure_inference_metadata(model, train_rows, label_all_tokens=bool(args.label_all_tokens))
    device = device_for(args.device, runtime.torch)
    model.to(device)
    set_seed(args.seed, runtime.torch)

    train_loader, train_windows = make_dataloader(train_rows, tokenizer, label_map, args, runtime, shuffle=True)
    validation_windows = []
    if validation_rows:
        _validation_loader, validation_windows = make_dataloader(validation_rows, tokenizer, label_map, args, runtime, shuffle=False)
    optimizer = make_optimizer(model, args, runtime)
    total_steps = args.max_steps if args.max_steps > 0 else args.epochs * max(1, len(train_loader))
    warmup_steps = args.warmup_steps

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "training_args.json", vars(args))
    write_json(output_dir / "label_map.json", label_map)
    startup_report = {
        "event": "training_start",
        "git": git_provenance(),
        "model_source": resolve_model_ref(args.model_name_or_path),
        "checkpoint": resolve_model_ref(args.checkpoint) if args.checkpoint else "",
        "output_dir": str(output_dir),
        "device": str(device),
        "optimizer": args.optimizer,
        "parameters": count_parameters(model),
        "epochs": args.epochs,
        "max_steps": args.max_steps,
        "estimated_optimizer_steps": total_steps,
        "batch": {
            "train_batch_size": args.train_batch_size,
            "eval_batch_size": args.eval_batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
        },
        "subtoken_labels": {
            "label_all_tokens": bool(args.label_all_tokens),
            "continuation_policy": "b_to_i" if args.label_all_tokens else "ignore_index",
        },
        "windows": {
            "train": len(train_windows),
            "validation": len(validation_windows),
            "max_sequence_len": args.max_sequence_len,
            "max_words_per_window": args.max_words_per_window,
            "stride_words": args.stride_words,
        },
        "freezing": {
            "freeze_base_model": args.freeze_base_model,
            "unfreeze_top_layers": args.unfreeze_top_layers,
            "gradient_checkpointing": args.gradient_checkpointing,
        },
        "early_stopping": {
            "enabled": args.early_stopping_patience >= 0,
            "metric": args.early_stopping_metric,
            "mode": args.early_stopping_mode,
            "patience": args.early_stopping_patience,
            "min_delta": args.early_stopping_min_delta,
            "best_checkpoint_dir": str(output_dir / "best"),
        },
        "data": {
            "train": dataset_summary(train_rows),
            "validation": dataset_summary(validation_rows) if validation_rows else None,
        },
    }
    write_json(output_dir / "training_start_report.json", startup_report)
    print(json.dumps(startup_report, sort_keys=True))

    global_step = 0
    best_metric: float | None = None
    best_epoch: int | None = None
    epochs_without_improvement = 0
    stopped_early = False
    model.train()
    for epoch in range(args.epochs):
        running_loss = 0.0
        for step, batch in enumerate(train_loader, start=1):
            tensor_batch = batch_to_device(batch, device, runtime.torch)
            outputs = model(**tensor_batch)
            loss = outputs.loss / args.gradient_accumulation_steps
            loss.backward()
            running_loss += float(loss.detach().cpu()) * args.gradient_accumulation_steps
            if step % args.gradient_accumulation_steps == 0:
                if warmup_steps and global_step < warmup_steps:
                    scale = float(global_step + 1) / float(max(1, warmup_steps))
                    for group in optimizer.param_groups:
                        group["lr"] = args.learning_rate * scale
                optimizer.step()
                optimizer.zero_grad()
                global_step += 1
                if args.logging_steps and global_step % args.logging_steps == 0:
                    print(json.dumps({"epoch": epoch + 1, "step": global_step, "loss": running_loss / max(1, step)}))
                if args.max_steps > 0 and global_step >= args.max_steps:
                    break
        print(json.dumps({"epoch": epoch + 1, "train_loss": running_loss / max(1, len(train_loader)), "windows": len(train_windows)}))
        if (args.evaluate_during_training or args.early_stopping_patience >= 0) and validation_rows:
            metrics = evaluate_rows(validation_rows, model, tokenizer, label_map, args, runtime, split_name="validation")
            write_json(output_dir / f"validation_metrics_epoch_{epoch + 1}.json", metrics)
            print(json.dumps({"event": "validation_epoch", "epoch": epoch + 1, "ner": ner_eval_summary(metrics)}, sort_keys=True))
            metric_value = metrics.get(args.early_stopping_metric)
            if metric_value is None:
                raise KeyError(f"early stopping metric not found: {args.early_stopping_metric}")
            metric_value = float(metric_value)
            summary = {
                "epoch": epoch + 1,
                "validation_metric": args.early_stopping_metric,
                "validation_value": metric_value,
            }
            if args.early_stopping_patience >= 0:
                if metric_is_better(metric_value, best_metric, args.early_stopping_mode, args.early_stopping_min_delta):
                    best_metric = metric_value
                    best_epoch = epoch + 1
                    epochs_without_improvement = 0
                    model.save_pretrained(output_dir / "best")
                    tokenizer.save_pretrained(output_dir / "best")
                    write_json(output_dir / "best_validation_metrics.json", metrics)
                    summary["best"] = True
                else:
                    epochs_without_improvement += 1
                    summary["best"] = False
                    summary["epochs_without_improvement"] = epochs_without_improvement
                    if epochs_without_improvement > args.early_stopping_patience:
                        stopped_early = True
                summary["best_epoch"] = best_epoch
                summary["best_metric"] = best_metric
            print(json.dumps(summary))
            model.train()
        if args.max_steps > 0 and global_step >= args.max_steps:
            break
        if stopped_early:
            print(json.dumps({"early_stopping": True, "epoch": epoch + 1, "best_epoch": best_epoch, "best_metric": best_metric}))
            break

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    if validation_rows:
        metrics, predictions = evaluate_rows(
            validation_rows,
            model,
            tokenizer,
            label_map,
            args,
            runtime,
            split_name="validation",
            return_predictions=True,
        )
        write_json(output_dir / "validation_metrics.json", metrics)
        write_jsonl(output_dir / "validation_predictions.jsonl", predictions)
        print(json.dumps({"event": "validation_final", "ner": ner_eval_summary(metrics)}, sort_keys=True))


def batch_to_device(batch: dict[str, Any], device: Any, torch: Any) -> dict[str, Any]:
    tensor_batch = {}
    for key, value in batch.items():
        if key in {"window_index", "doc_index", "start_word", "word_ids_for_eval"}:
            continue
        if key == "token_type_ids":
            continue
        tensor_batch[key] = value.to(device)
    return tensor_batch


def top_label_summary(probabilities: Any, id2label: dict[int, str], torch: Any, *, top_k: int = 3) -> str:
    k = min(top_k, len(id2label))
    values, indices = torch.topk(probabilities, k=k)
    return "; ".join(
        f"{id2label[int(label_id)]}:{float(probability):.6f}"
        for probability, label_id in zip(values.tolist(), indices.tolist(), strict=True)
    )


def escape_tsv(value: Any) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(escape_tsv(row.get(column, "")) for column in columns) + "\n")


def write_prediction_diagnostics(output_dir: Path, split_name: str, token_rows: list[dict[str, Any]], subtoken_rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    token_path = Path(args.write_token_predictions) if args.write_token_predictions else output_dir / f"{split_name}_token_predictions.tsv"
    subtoken_path = Path(args.write_subtoken_predictions) if args.write_subtoken_predictions else output_dir / f"{split_name}_subtoken_predictions.tsv"
    write_tsv(
        token_path,
        [
            "split",
            "document_id",
            "language",
            "date",
            "newspaper",
            "token_index",
            "token",
            "gold_label",
            "pred_label",
            "pred_confidence",
            "source_window_index",
            "source_window_start_word",
            "source_subtoken_index",
            "top_labels",
        ],
        token_rows,
    )
    write_tsv(
        subtoken_path,
        [
            "split",
            "document_id",
            "language",
            "date",
            "newspaper",
            "window_index",
            "window_start_word",
            "absolute_word_index",
            "word",
            "subtoken_index",
            "subtoken",
            "word_id",
            "is_first_subtoken",
            "gold_loss_id",
            "gold_loss_label",
            "pred_label",
            "pred_confidence",
            "top_labels",
        ],
        subtoken_rows,
    )


def write_decoder_comparison(
    output_dir: Path,
    split_name: str,
    rows: list[dict[str, Any]],
    decoded_by_name: dict[str, list[list[int]]],
    id2label: dict[int, str],
) -> None:
    comparison_rows: list[dict[str, Any]] = []
    first_subtoken = decoded_by_name[DECODER_FIRST_SUBTOKEN]
    word_viterbi = decoded_by_name[DECODER_FIRST_SUBTOKEN_VITERBI]
    all_subtoken_viterbi = decoded_by_name[DECODER_ALL_SUBTOKEN_VITERBI]
    for doc_index, row in enumerate(rows):
        for token_index, (token, gold_label) in enumerate(zip(row["tokens"], row["token_labels"], strict=True)):
            first_label = id2label[first_subtoken[doc_index][token_index]]
            word_viterbi_label = id2label[word_viterbi[doc_index][token_index]]
            all_subtoken_label = id2label[all_subtoken_viterbi[doc_index][token_index]]
            comparison_rows.append(
                {
                    "split": split_name,
                    "document_id": row["id"],
                    "language": row.get("language", ""),
                    "date": row.get("date", ""),
                    "newspaper": row.get("newspaper", ""),
                    "token_index": token_index,
                    "token": token,
                    "gold_label": gold_label,
                    DECODER_FIRST_SUBTOKEN: first_label,
                    DECODER_FIRST_SUBTOKEN_VITERBI: word_viterbi_label,
                    DECODER_ALL_SUBTOKEN_VITERBI: all_subtoken_label,
                    "changed_by_word_viterbi": int(word_viterbi_label != first_label),
                    "changed_by_subtoken_viterbi": int(all_subtoken_label != first_label),
                }
            )
    write_tsv(
        output_dir / f"{split_name}_decoder_comparison.tsv",
        [
            "split",
            "document_id",
            "language",
            "date",
            "newspaper",
            "token_index",
            "token",
            "gold_label",
            DECODER_FIRST_SUBTOKEN,
            DECODER_FIRST_SUBTOKEN_VITERBI,
            DECODER_ALL_SUBTOKEN_VITERBI,
            "changed_by_word_viterbi",
            "changed_by_subtoken_viterbi",
        ],
        comparison_rows,
    )


def metrics_for_predictions(rows: list[dict[str, Any]], pred_ids_by_doc: list[list[int]], id2label: dict[int, str]) -> dict[str, Any]:
    gold_by_doc: dict[str, list[str]] = {}
    pred_by_doc: dict[str, list[str]] = {}
    all_gold: list[str] = []
    all_pred: list[str] = []
    for row, pred_ids in zip(rows, pred_ids_by_doc, strict=True):
        gold_labels = row["token_labels"]
        pred_labels = [id2label[int(label_id)] for label_id in pred_ids]
        gold_by_doc[row["id"]] = gold_labels
        pred_by_doc[row["id"]] = pred_labels
        all_gold.extend(gold_labels)
        all_pred.extend(pred_labels)
    metrics = {}
    metrics.update(token_metrics(all_gold, all_pred))
    metrics.update(entity_metrics(gold_by_doc, pred_by_doc))
    metrics["entity_by_label"] = entity_metrics_by_label(gold_by_doc, pred_by_doc)
    return metrics


def evaluate_rows(
    rows: list[dict[str, Any]],
    model: Any,
    tokenizer: Any,
    label_map: dict[str, Any],
    args: argparse.Namespace,
    runtime: Runtime,
    *,
    split_name: str,
    return_predictions: bool = False,
    model_label_map: dict[str, Any] | None = None,
) -> Any:
    dataset_id2label = {int(idx): label for idx, label in label_map["id2label"].items()}
    output_label_map = model_label_map or label_map
    id2label = {int(idx): label for idx, label in output_label_map["id2label"].items()}
    decoder = getattr(args, "decoder", DEFAULT_DECODER)
    decoder_schema = compile_bio_schema(id2label) if decoder != DECODER_FIRST_SUBTOKEN or getattr(args, "compare_decoders", False) else None
    device = next(model.parameters()).device
    loader, windows = make_dataloader(rows, tokenizer, label_map, args, runtime, shuffle=False)
    pred_ids_by_doc = [[0 for _ in row["tokens"]] for row in rows]
    seen_by_doc = [[False for _ in row["tokens"]] for row in rows]
    word_source_window_by_doc: list[list[int | None]] = [[None for _ in row["tokens"]] for row in rows]
    word_log_probs_by_doc: list[list[list[list[float]] | None]] = [[None for _ in row["tokens"]] for row in rows]
    token_provenance_by_doc: list[list[dict[str, Any] | None]] = [[None for _ in row["tokens"]] for row in rows]
    write_diagnostics = bool(
        getattr(args, "write_prediction_diagnostics", False)
        or getattr(args, "write_token_predictions", "")
        or getattr(args, "write_subtoken_predictions", "")
    )
    subtoken_rows: list[dict[str, Any]] = []
    token_rows: list[dict[str, Any]] = []
    model.eval()
    with runtime.torch.no_grad():
        for batch in loader:
            meta_window_indices = batch["window_index"]
            meta_doc_indices = batch["doc_index"]
            meta_starts = batch["start_word"]
            meta_word_ids = batch["word_ids_for_eval"]
            input_ids = batch["input_ids"].detach().cpu().tolist()
            attention_masks = batch.get("attention_mask")
            attention_mask_rows = attention_masks.detach().cpu().tolist() if attention_masks is not None else None
            gold_loss_ids = batch["labels"].detach().cpu().tolist()
            tensor_batch = batch_to_device(batch, device, runtime.torch)
            # Evaluation compares gold and predicted label strings; do not feed dataset-label IDs
            # into a checkpoint whose classifier may use a different output vocabulary.
            tensor_batch.pop("labels", None)
            outputs = model(**tensor_batch)
            logits = outputs.logits.detach().cpu()
            log_probabilities = runtime.torch.log_softmax(logits, dim=-1)
            probabilities = runtime.torch.softmax(logits, dim=-1)
            pred_ids = runtime.torch.argmax(logits, dim=-1).tolist()
            for item_i, sequence_preds in enumerate(pred_ids):
                window_index = meta_window_indices[item_i]
                doc_index = meta_doc_indices[item_i]
                start_word = meta_starts[item_i]
                word_ids = meta_word_ids[item_i]
                previous_word = -1
                for token_i, word_id in enumerate(word_ids):
                    if attention_mask_rows is not None and not attention_mask_rows[item_i][token_i]:
                        continue
                    pred_id = int(sequence_preds[token_i])
                    pred_confidence = float(probabilities[item_i, token_i, pred_id])
                    is_first_subtoken = word_id >= 0 and word_id != previous_word
                    absolute_word = start_word + word_id if word_id >= 0 else -1
                    if 0 <= absolute_word < len(word_log_probs_by_doc[doc_index]):
                        source_window = word_source_window_by_doc[doc_index][absolute_word]
                        if source_window is None:
                            source_window = int(window_index)
                            word_source_window_by_doc[doc_index][absolute_word] = source_window
                            word_log_probs_by_doc[doc_index][absolute_word] = []
                        if source_window == int(window_index):
                            word_log_probs_by_doc[doc_index][absolute_word].append(log_probabilities[item_i, token_i].tolist())
                    if write_diagnostics:
                        gold_loss_id = int(gold_loss_ids[item_i][token_i])
                        subtoken_rows.append(
                            {
                                "split": split_name,
                                "document_id": rows[doc_index]["id"],
                                "language": rows[doc_index].get("language", ""),
                                "date": rows[doc_index].get("date", ""),
                                "newspaper": rows[doc_index].get("newspaper", ""),
                                "window_index": window_index,
                                "window_start_word": start_word,
                                "absolute_word_index": absolute_word,
                                "word": rows[doc_index]["tokens"][absolute_word] if 0 <= absolute_word < len(rows[doc_index]["tokens"]) else "",
                                "subtoken_index": token_i,
                                "subtoken": tokenizer.convert_ids_to_tokens(int(input_ids[item_i][token_i])),
                                "word_id": word_id,
                                "is_first_subtoken": int(is_first_subtoken),
                                "gold_loss_id": gold_loss_id,
                                "gold_loss_label": dataset_id2label.get(gold_loss_id, "IGNORED") if gold_loss_id != IGNORE_INDEX else "IGNORED",
                                "pred_label": id2label[pred_id],
                                "pred_confidence": f"{pred_confidence:.6f}",
                                "top_labels": top_label_summary(probabilities[item_i, token_i], id2label, runtime.torch),
                            }
                        )
                    if word_id < 0 or word_id == previous_word:
                        previous_word = word_id
                        continue
                    if absolute_word < len(pred_ids_by_doc[doc_index]) and not seen_by_doc[doc_index][absolute_word]:
                        pred_ids_by_doc[doc_index][absolute_word] = pred_id
                        seen_by_doc[doc_index][absolute_word] = True
                        token_provenance_by_doc[doc_index][absolute_word] = {
                            "confidence": pred_confidence,
                            "source_window_index": window_index,
                            "source_window_start_word": start_word,
                            "source_subtoken_index": token_i,
                            "top_labels": top_label_summary(probabilities[item_i, token_i], id2label, runtime.torch),
                        }
                    previous_word = word_id

    normalized_word_log_probs_by_doc: list[list[list[list[float]]]] = []
    for doc_index, row in enumerate(rows):
        normalized_doc: list[list[list[float]]] = []
        for token_index, token_subtokens in enumerate(word_log_probs_by_doc[doc_index]):
            if token_subtokens:
                normalized_doc.append(token_subtokens)
                continue
            fallback = [-1.0e9 for _label in id2label]
            fallback[pred_ids_by_doc[doc_index][token_index]] = 0.0
            normalized_doc.append([fallback])
        normalized_word_log_probs_by_doc.append(normalized_doc)

    decoded_by_name: dict[str, list[list[int]]] = {DECODER_FIRST_SUBTOKEN: pred_ids_by_doc}
    requested_decoders = [decoder]
    if getattr(args, "compare_decoders", False):
        requested_decoders = list(DECODER_CHOICES)
    for decoder_name in requested_decoders:
        if decoder_name == DECODER_FIRST_SUBTOKEN:
            continue
        decoded_by_name[decoder_name] = [
            decode_document(
                word_log_probs,
                decoder=decoder_name,
                schema=decoder_schema,
            )
            for word_log_probs in normalized_word_log_probs_by_doc
        ]
    selected_pred_ids_by_doc = decoded_by_name[decoder]

    predictions: list[dict[str, Any]] = []
    for doc_index, (row, pred_ids) in enumerate(zip(rows, selected_pred_ids_by_doc, strict=True)):
        gold_labels = row["token_labels"]
        pred_labels = [id2label[int(label_id)] for label_id in pred_ids]
        if write_diagnostics:
            raw_first_subtoken_labels = [id2label[int(label_id)] for label_id in pred_ids_by_doc[doc_index]]
            for token_index, (token, gold_label, pred_label) in enumerate(zip(row["tokens"], gold_labels, raw_first_subtoken_labels, strict=True)):
                provenance = token_provenance_by_doc[doc_index][token_index] or {}
                token_rows.append(
                    {
                        "split": split_name,
                        "document_id": row["id"],
                        "language": row.get("language", ""),
                        "date": row.get("date", ""),
                        "newspaper": row.get("newspaper", ""),
                        "token_index": token_index,
                        "token": token,
                        "gold_label": gold_label,
                        "pred_label": pred_label,
                        "pred_confidence": f"{float(provenance.get('confidence', 0.0)):.6f}",
                        "source_window_index": provenance.get("source_window_index", ""),
                        "source_window_start_word": provenance.get("source_window_start_word", ""),
                        "source_subtoken_index": provenance.get("source_subtoken_index", ""),
                        "top_labels": provenance.get("top_labels", ""),
                    }
                )
        if return_predictions:
            predictions.append(
                {
                    "id": row["id"],
                    "split": split_name,
                    "language": row.get("language", ""),
                    "date": row.get("date", ""),
                    "newspaper": row.get("newspaper", ""),
                    "tokens": row["tokens"],
                    "gold_labels": gold_labels,
                    "pred_labels": pred_labels,
                }
            )
    metrics = metrics_for_predictions(rows, selected_pred_ids_by_doc, id2label)
    metrics["documents"] = len(rows)
    metrics["split"] = split_name
    metrics["windows"] = len(windows)
    metrics["decoder"] = decoder
    metrics["decoder_description"] = {
        DECODER_FIRST_SUBTOKEN: "Raw argmax on the first subtoken of each word; first covering window wins.",
        DECODER_FIRST_SUBTOKEN_VITERBI: "BIO-constrained Viterbi over first-subtoken emissions; first covering window wins.",
        DECODER_ALL_SUBTOKEN_VITERBI: "BIO-constrained Viterbi over legal word-expansion emissions from all subtokens; first covering window wins.",
    }[decoder]
    if getattr(args, "compare_decoders", False):
        metrics["decoder_comparison"] = {
            decoder_name: {
                key: value
                for key, value in metrics_for_predictions(rows, decoded_by_name[decoder_name], id2label).items()
                if key != "entity_by_label"
            }
            for decoder_name in DECODER_CHOICES
        }
        write_decoder_comparison(Path(args.output_dir), split_name, rows, decoded_by_name, id2label)
    if write_diagnostics:
        output_dir = Path(args.output_dir)
        write_prediction_diagnostics(output_dir, split_name, token_rows, subtoken_rows, args)
    if return_predictions:
        return metrics, predictions
    return metrics


def evaluate(args: argparse.Namespace, runtime: Runtime) -> None:
    label_map = load_label_map(args.label_map)
    validate_dataset_label_map(label_map)
    rows = load_jsonl(args.eval_jsonl, label_map=label_map, unknown_label_id=IGNORE_INDEX)
    model, tokenizer, model_label_map = load_eval_model_and_tokenizer(args, runtime)
    device = device_for(args.device, runtime.torch)
    model.to(device)
    metrics, predictions = evaluate_rows(
        rows,
        model,
        tokenizer,
        label_map,
        args,
        runtime,
        split_name=args.split_name,
        return_predictions=True,
        model_label_map=model_label_map,
    )
    metrics["label_compatibility"] = label_compatibility_summary(label_map, model_label_map)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / f"{args.split_name}_metrics.json", metrics)
    write_jsonl(output_dir / f"{args.split_name}_predictions.jsonl", predictions)
    print(json.dumps({"event": "evaluation", "ner": ner_eval_summary(metrics)}, indent=2, sort_keys=True))
    print(json.dumps(metrics, indent=2, sort_keys=True))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train or evaluate a ModernBERT token classifier.")
    parser.add_argument("--model-name-or-path", default="answerdotai/ModernBERT-base")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--train-jsonl")
    parser.add_argument("--validation-jsonl")
    parser.add_argument("--eval-jsonl")
    parser.add_argument("--label-map", required=True)
    parser.add_argument(
        "--use-checkpoint-label-map",
        action="store_true",
        help=(
            "Deprecated compatibility flag. Checkpoint evaluation always interprets logits "
            "with the checkpoint config label map; --label-map remains the dataset/gold schema."
        ),
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--split-name", default="validation")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--train-batch-size", type=int, default=4)
    parser.add_argument("--eval-batch-size", type=int, default=8)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--label-all-tokens",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Label every model subtoken; continuation subtokens convert B-X to I-X. Default labels only the first subtoken.",
    )
    parser.add_argument("--freeze-base-model", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--unfreeze-top-layers", type=int, default=0, help="When freezing the base model, keep this many top encoder layers trainable.")
    parser.add_argument("--optimizer", choices=["adafactor", "adamw"], default="adafactor")
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--warmup-steps", type=int, default=0)
    parser.add_argument("--max-sequence-len", type=int, default=512)
    parser.add_argument("--max-words-per-window", type=int, default=256)
    parser.add_argument("--stride-words", type=int, default=32)
    parser.add_argument("--logging-steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--evaluate-during-training", action="store_true")
    parser.add_argument("--early-stopping-patience", type=int, default=1, help="Epochs without improvement before stopping. Use -1 to disable.")
    parser.add_argument("--early-stopping-metric", default="entity_f1")
    parser.add_argument("--early-stopping-mode", choices=["max", "min"], default="max")
    parser.add_argument("--early-stopping-min-delta", type=float, default=0.0)
    parser.add_argument("--do-train", action="store_true")
    parser.add_argument("--do-eval", action="store_true")
    parser.add_argument(
        "--decoder",
        choices=DECODER_CHOICES,
        default=DEFAULT_DECODER,
        help=(
            "Word-level evaluation decoder. Default is first_subtoken_viterbi. "
            "first_subtoken preserves the previous raw first-subtoken argmax behavior; "
            "the Viterbi modes add BIO constraints over first-subtoken or all-subtoken emissions."
        ),
    )
    parser.add_argument(
        "--compare-decoders",
        action="store_true",
        help="During evaluation, run all decoder modes from the same logits and write SPLIT_decoder_comparison.tsv plus summary metrics.",
    )
    parser.add_argument(
        "--write-prediction-diagnostics",
        action="store_true",
        help=(
            "During evaluation, write token- and subtoken-level prediction TSV diagnostics. "
            "The subtoken TSV includes tokenizer special/non-word tokens as word_id=-1 with gold_loss_label=IGNORED."
        ),
    )
    parser.add_argument(
        "--write-token-predictions",
        default="",
        help="Optional path for token-level prediction diagnostics TSV; also enables diagnostics and writes the companion subtoken TSV to its default path unless overridden.",
    )
    parser.add_argument(
        "--write-subtoken-predictions",
        default="",
        help="Optional path for subtoken-level prediction diagnostics TSV; also enables diagnostics and writes the companion token TSV to its default path unless overridden.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    runtime = import_runtime()
    if args.do_train:
        if not args.train_jsonl:
            parser.error("--do-train requires --train-jsonl")
        train(args, runtime)
    if args.do_eval:
        if not args.eval_jsonl:
            parser.error("--do-eval requires --eval-jsonl")
        evaluate(args, runtime)
    if not args.do_train and not args.do_eval:
        parser.error("choose --do-train and/or --do-eval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
