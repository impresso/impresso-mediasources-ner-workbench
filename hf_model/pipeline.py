from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

try:
    from .decoding import DECODER_FIRST_SUBTOKEN_VITERBI, compile_bio_schema, decode_document
except ImportError:
    from decoding import DECODER_FIRST_SUBTOKEN_VITERBI, compile_bio_schema, decode_document


TOKENIZATION_PROFILE = "unicode-word-punctuation-v1"
TOKEN_RE = re.compile(r"[^\W\d_]+|\d+|_+|[^\w\s]", re.UNICODE)
DEFAULT_MAX_SEQUENCE_LEN = 512
DEFAULT_MAX_WORDS_PER_WINDOW = 256
DEFAULT_STRIDE_WORDS = 32


@dataclass(frozen=True)
class Window:
    start_word: int
    tokens: list[str]


def tokenize_with_offsets(text: str) -> tuple[list[str], list[int], list[int]]:
    matches = list(TOKEN_RE.finditer(text))
    return (
        [match.group(0) for match in matches],
        [match.start() for match in matches],
        [match.end() for match in matches],
    )


def make_windows(tokens: list[str], *, max_words: int, stride_words: int) -> list[Window]:
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if stride_words < 0:
        raise ValueError("stride_words must not be negative")
    step = max_words - stride_words
    if step <= 0:
        raise ValueError("stride_words must be smaller than max_words")
    if not tokens:
        return []

    windows: list[Window] = []
    start = 0
    while start < len(tokens):
        stop = min(start + max_words, len(tokens))
        windows.append(Window(start_word=start, tokens=tokens[start:stop]))
        if stop == len(tokens):
            break
        start += step
    return windows


def normalize_id2label(id2label: dict[Any, str] | list[str]) -> dict[int, str]:
    if isinstance(id2label, list):
        return {index: str(label) for index, label in enumerate(id2label)}
    return {int(index): str(label) for index, label in id2label.items()}


def bio_labels_to_entities(
    labels: list[str],
    tokens: list[str],
    starts: list[int],
    stops: list[int],
    text: str,
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    active_start: int | None = None
    active_stop: int | None = None
    active_label = ""

    def close() -> None:
        nonlocal active_start, active_stop, active_label
        if active_start is None or active_stop is None:
            return
        entities.append(
            {
                "label": active_label,
                "start": active_start,
                "stop": active_stop,
                "surface": text[active_start:active_stop],
            }
        )
        active_start = active_stop = None
        active_label = ""

    for index, label in enumerate(labels):
        if label == "O":
            close()
            continue
        prefix, separator, entity_label = label.partition("-")
        if not separator or prefix not in {"B", "I"}:
            close()
            continue
        if prefix == "B" or active_start is None or active_label != entity_label:
            close()
            active_start = starts[index]
            active_label = entity_label
        active_stop = stops[index]
    close()
    return entities


class MediaAgenciesPipeline:
    """Self-contained inference pipeline for Impresso media-source NER."""

    def __init__(
        self,
        model: Any,
        tokenizer: Any,
        *,
        device: str | int | None = None,
        max_sequence_len: int = DEFAULT_MAX_SEQUENCE_LEN,
        max_words_per_window: int = DEFAULT_MAX_WORDS_PER_WINDOW,
        stride_words: int = DEFAULT_STRIDE_WORDS,
        **_: Any,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.max_sequence_len = max_sequence_len
        self.max_words_per_window = max_words_per_window
        self.stride_words = stride_words
        self.id2label = normalize_id2label(model.config.id2label)
        self.schema = compile_bio_schema(self.id2label)
        self.device = self._resolve_device(device)
        self._validate_config()
        if hasattr(self.model, "to"):
            self.model.to(self.device)
        if hasattr(self.model, "eval"):
            self.model.eval()

    def _resolve_device(self, device: str | int | None) -> Any:
        import torch

        if device is None or device == -1:
            return torch.device("cpu")
        if isinstance(device, int):
            return torch.device(f"cuda:{device}")
        return torch.device(device)

    def _validate_config(self) -> None:
        annotation_tokenization = getattr(self.model.config, "annotation_tokenization", None)
        if annotation_tokenization != TOKENIZATION_PROFILE:
            raise ValueError(
                f"unsupported or missing annotation_tokenization: {annotation_tokenization!r}; "
                f"expected {TOKENIZATION_PROFILE!r}"
            )
        decoder = getattr(self.model.config, "subtoken_decoding", None)
        if decoder != DECODER_FIRST_SUBTOKEN_VITERBI:
            raise ValueError(
                f"unsupported or missing subtoken_decoding: {decoder!r}; "
                f"expected {DECODER_FIRST_SUBTOKEN_VITERBI!r}"
            )

    def __call__(self, texts: str | list[str], *args: Any, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
        single = isinstance(texts, str)
        items = [texts] if single else list(texts)
        outputs = [self.predict_one(str(text)) for text in items]
        return outputs[0] if single else outputs

    def predict_one(self, text: str) -> dict[str, Any]:
        tokens, starts, stops = tokenize_with_offsets(text)
        if not tokens:
            return {"text": text, "tokens": [], "entities": []}

        word_log_probs = self._word_log_probs(tokens)
        pred_ids = decode_document(
            word_log_probs,
            decoder=DECODER_FIRST_SUBTOKEN_VITERBI,
            schema=self.schema,
        )
        labels = [self.id2label[int(label_id)] for label_id in pred_ids]
        return {
            "text": text,
            "tokens": tokens,
            "token_start_offsets": starts,
            "token_end_offsets": stops,
            "token_labels": labels,
            "entities": bio_labels_to_entities(labels, tokens, starts, stops, text),
        }

    def _word_log_probs(self, tokens: list[str]) -> list[list[list[float]]]:
        import torch

        windows = make_windows(tokens, max_words=self.max_words_per_window, stride_words=self.stride_words)
        word_log_probs: list[list[list[float]] | None] = [None for _ in tokens]
        word_source_window: list[int | None] = [None for _ in tokens]

        with torch.no_grad():
            for window_index, window in enumerate(windows):
                encoding = self.tokenizer(
                    window.tokens,
                    is_split_into_words=True,
                    truncation=True,
                    max_length=self.max_sequence_len,
                    return_offsets_mapping=False,
                    return_tensors="pt",
                )
                word_ids = encoding.word_ids()
                model_inputs = {
                    key: value.to(self.device) if hasattr(value, "to") else value
                    for key, value in dict(encoding).items()
                    if key != "offset_mapping"
                }
                outputs = self.model(**model_inputs)
                logits = outputs.logits.detach().cpu()
                log_probabilities = torch.log_softmax(logits, dim=-1)
                attention_mask = model_inputs.get("attention_mask")
                attention_mask_values = attention_mask.detach().cpu().tolist()[0] if attention_mask is not None else None

                for subtoken_index, word_id in enumerate(word_ids):
                    if attention_mask_values is not None and not attention_mask_values[subtoken_index]:
                        continue
                    if word_id is None:
                        continue
                    absolute_word = window.start_word + int(word_id)
                    if not 0 <= absolute_word < len(tokens):
                        continue
                    source_window = word_source_window[absolute_word]
                    if source_window is None:
                        word_source_window[absolute_word] = window_index
                        word_log_probs[absolute_word] = []
                    if word_source_window[absolute_word] == window_index:
                        word_log_probs[absolute_word].append(log_probabilities[0, subtoken_index].tolist())

        out: list[list[list[float]]] = []
        for token_index, subtokens in enumerate(word_log_probs):
            if not subtokens:
                raise ValueError(f"model/tokenizer produced no subtokens for token {token_index}: {tokens[token_index]!r}")
            out.append(subtokens)
        return out


# Compatibility alias for older users while the new pipeline name lands.
NewsAgenciesPipeline = MediaAgenciesPipeline
