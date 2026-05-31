from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_COLUMNS = [
    "TOKEN",
    "NE-COARSE-LIT",
    "NE-COARSE-METO",
    "NE-FINE-LIT",
    "NE-FINE-METO",
    "NE-FINE-COMP",
    "NE-NESTED",
    "NEL-LIT",
    "NEL-METO",
    "RENDER",
    "SEG",
    "OCR-INFO",
    "MISC",
]

DOC_COMMENT_KEYS = {
    "language",
    "newspaper",
    "date",
    "document_id",
    "news-agency-as-source",
}

FORBIDDEN_BASE_REASONS = {
    "org.ent.pressagency.unk": "unknown_agency",
    "org.ent.pressagency.ag": "generic_agency_marker",
    "pers.ind.articleauthor": "article_author",
}

NEWSPAPER_LANGUAGE_HINTS = {
    "DTT": "de",
    "EZR": "de",
    "FZG": "de",
    "NZG": "de",
    "OIZ": "de",
    "SGZ": "de",
    "VHT": "de",
    "WHD": "de",
    "buergerbeamten": "de",
    "diekwochen": "de",
    "luxwort": "de",
    "luxzeit1858": "de",
    "obermosel": "de",
    "tageblatt": "de",
    "waechtersauer": "de",
    "CDV": "fr",
    "EXP": "fr",
    "GAV": "fr",
    "GDL": "fr",
    "IMP": "fr",
    "JDG": "fr",
    "LAB": "fr",
    "LBP": "fr",
    "LCE": "fr",
    "LCG": "fr",
    "LCR": "fr",
    "LLE": "fr",
    "LNF": "fr",
    "LSE": "fr",
    "NTS": "fr",
    "avenirgdl": "fr",
    "courriergdl": "fr",
    "indeplux": "fr",
    "lunion": "fr",
    "luxembourg1935": "fr",
}


@dataclass
class TokenRow:
    columns: list[str]
    source_line: int
    segment_index: int | None
    segment_link: str

    @property
    def token(self) -> str:
        return self.columns[0]

    @property
    def fine_label(self) -> str:
        return self.columns[3]

    @property
    def nel(self) -> str:
        return clean_empty(self.columns[7])

    @property
    def render(self) -> str:
        return clean_empty(self.columns[9])

    @property
    def seg(self) -> str:
        return clean_empty(self.columns[10])

    @property
    def ocr(self) -> str:
        return clean_empty(self.columns[11])


@dataclass
class HipeDocument:
    comments: dict[str, str] = field(default_factory=dict)
    original_comments: list[tuple[str, str]] = field(default_factory=list)
    tokens: list[TokenRow] = field(default_factory=list)
    source_file: Path | None = None
    start_line: int = 0
    end_line: int = 0


@dataclass
class ConvertedDocument:
    split: str
    public: dict[str, Any]
    audit: dict[str, Any]
    excluded_entities: list[dict[str, Any]]
    accepted_label_count: Counter[str]
    excluded_reason_count: Counter[str]
    quality_flags: set[str]


class ConversionError(ValueError):
    pass


def clean_empty(value: str | None) -> str:
    if value is None or value == "_":
        return ""
    return value


def parse_comment(line: str) -> tuple[str, str] | None:
    if not line.startswith("#"):
        return None
    body = line[1:].strip()
    if "=" not in body:
        return body, ""
    key, value = body.split("=", 1)
    return key.strip(), value.strip()


def discover_inputs(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.tsv")))
        elif path.is_file():
            files.append(path)
        else:
            raise ConversionError(f"input path does not exist: {path}")
    return sorted(dict.fromkeys(files))


def split_from_path(path: Path, override: str | None = None) -> str:
    if override:
        return override
    name = path.name.lower()
    if "train" in name:
        return "train"
    if "dev" in name:
        return "validation"
    if "test" in name:
        return "test"
    raise ConversionError(f"cannot infer split from filename: {path}")


def relative_source(path: Path, source_root: Path | None) -> str:
    if source_root is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(source_root.resolve()))
    except ValueError:
        return str(path)


def parse_hipe_file(path: Path) -> Iterable[HipeDocument]:
    current = HipeDocument(source_file=path)
    active_segment_index: int | None = None
    active_segment_link = ""
    seen_global_columns = False

    def has_content(doc: HipeDocument) -> bool:
        return bool(doc.tokens or doc.comments or doc.original_comments)

    def flush(end_line: int) -> HipeDocument | None:
        nonlocal current, active_segment_index, active_segment_link, seen_global_columns
        if not has_content(current):
            return None
        current.end_line = end_line
        finished = current
        global_columns = finished.comments.get("global.columns")
        current = HipeDocument(source_file=path)
        active_segment_index = None
        active_segment_link = ""
        if global_columns:
            current.comments["global.columns"] = global_columns
        seen_global_columns = bool(global_columns)
        return finished

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\n")
            if not line:
                continue

            parsed_comment = parse_comment(line)
            if parsed_comment is not None:
                key, value = parsed_comment
                if key == "global.columns":
                    expected = " ".join(EXPECTED_COLUMNS)
                    if value != expected:
                        raise ConversionError(
                            f"{path}:{line_number}: unexpected global.columns: {value!r}"
                        )
                    if current.tokens:
                        finished = flush(line_number - 1)
                        if finished is not None:
                            yield finished
                    current.comments[key] = value
                    current.original_comments.append((key, value))
                    seen_global_columns = True
                    if current.start_line == 0:
                        current.start_line = line_number
                    continue

                if key in DOC_COMMENT_KEYS and key == "language" and current.tokens:
                    finished = flush(line_number - 1)
                    if finished is not None:
                        yield finished

                if key == "segment_iiif_link":
                    if active_segment_link != value:
                        active_segment_index = 0 if active_segment_index is None else active_segment_index + 1
                        active_segment_link = value
                    current.original_comments.append((key, value))
                else:
                    current.comments[key] = value
                    current.original_comments.append((key, value))
                if current.start_line == 0:
                    current.start_line = line_number
                continue

            columns = line.split("\t")
            if len(columns) != len(EXPECTED_COLUMNS):
                raise ConversionError(
                    f"{path}:{line_number}: expected {len(EXPECTED_COLUMNS)} columns, got {len(columns)}"
                )
            if not seen_global_columns:
                raise ConversionError(f"{path}:{line_number}: token row before global.columns")
            if current.start_line == 0:
                current.start_line = line_number
            current.tokens.append(
                TokenRow(
                    columns=columns,
                    source_line=line_number,
                    segment_index=active_segment_index,
                    segment_link=active_segment_link,
                )
            )

    finished = flush(line_number if "line_number" in locals() else 0)
    if finished is not None:
        yield finished


def load_seed_labels(path: Path) -> dict[str, dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    labels: dict[str, dict[str, Any]] = {}
    for row in rows:
        canonical_id = row.get("canonical_id")
        label = row.get("label")
        if not canonical_id:
            continue
        key = f"org.ent.pressagency.{canonical_id}".lower()
        if row.get("trainable") and label:
            labels[key] = row
        else:
            labels[key] = row
    return labels


def base_label(label: str) -> str:
    if label in {"", "_", "O"}:
        return "O"
    if label.startswith("B-") or label.startswith("I-"):
        return label[2:]
    return label


def bio_prefix(label: str) -> str:
    if label.startswith("B-") or label.startswith("I-"):
        return label[:1]
    return "O"


def canonicalize_base(base: str, seed_labels: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    lowered = base.lower()
    row = seed_labels.get(lowered)
    if not row or not row.get("trainable") or not row.get("label"):
        return None, row
    return row["label"], row


def forbidden_reason(base: str, seed_row: dict[str, Any] | None) -> str | None:
    lowered = base.lower()
    if lowered in FORBIDDEN_BASE_REASONS:
        return FORBIDDEN_BASE_REASONS[lowered]
    if seed_row and not seed_row.get("trainable"):
        if seed_row.get("canonical_id") == "ag":
            return "generic_agency_marker"
        return "non_trainable_label"
    return None


def parse_source_qids(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_year(value: str) -> int | None:
    if not value:
        return None
    match = re.match(r"^(\d{4})", value)
    return int(match.group(1)) if match else None


def parse_ocr_info(value: str) -> tuple[str | None, float | None]:
    if not value:
        return None, None
    transcript = None
    led = None
    for part in value.split("|"):
        if part.startswith("Transcript:"):
            transcript = part[len("Transcript:") :]
        elif part.startswith("LED"):
            try:
                led = float(part[len("LED") :])
            except ValueError:
                led = None
    return transcript, led


def reconstruct_text(tokens: list[TokenRow]) -> tuple[str, str, list[int], list[int]]:
    text_parts: list[str] = []
    layout_parts: list[str] = []
    starts: list[int] = []
    stops: list[int] = []
    cursor = 0

    for token in tokens:
        token_text = token.token
        starts.append(cursor)
        text_parts.append(token_text)
        layout_parts.append(token_text)
        cursor += len(token_text)
        stops.append(cursor)

        no_space_after = "NoSpaceAfter" in token.render
        end_of_line = "EndOfLine" in token.render
        if not no_space_after:
            text_parts.append(" ")
            layout_parts.append("\n" if end_of_line else " ")
            cursor += 1

    text = "".join(text_parts).rstrip()
    layout_text = "".join(layout_parts).rstrip()
    return text, layout_text, starts, stops


def build_segments(tokens: list[TokenRow], starts: list[int], stops: list[int]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    if not tokens:
        return segments
    index = tokens[0].segment_index
    link = tokens[0].segment_link
    token_start = 0
    for i, token in enumerate(tokens[1:], start=1):
        if token.segment_index != index or token.segment_link != link:
            segments.append(
                {
                    "index": index if index is not None else len(segments),
                    "iiif_link": link,
                    "token_start": token_start,
                    "token_stop": i,
                    "text_start": starts[token_start],
                    "text_stop": stops[i - 1],
                }
            )
            index = token.segment_index
            link = token.segment_link
            token_start = i
    segments.append(
        {
            "index": index if index is not None else len(segments),
            "iiif_link": link,
            "token_start": token_start,
            "token_stop": len(tokens),
            "text_start": starts[token_start],
            "text_stop": stops[-1],
        }
    )
    return segments


def build_sentences(tokens: list[TokenRow], starts: list[int], stops: list[int]) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    token_start = 0
    for i, token in enumerate(tokens):
        if "EndOfSentence" in token.seg:
            sentences.append(
                {
                    "index": len(sentences),
                    "token_start": token_start,
                    "token_stop": i + 1,
                    "text_start": starts[token_start],
                    "text_stop": stops[i],
                }
            )
            token_start = i + 1
    if token_start < len(tokens):
        sentences.append(
            {
                "index": len(sentences),
                "token_start": token_start,
                "token_stop": len(tokens),
                "text_start": starts[token_start],
                "text_stop": stops[-1],
            }
        )
    return sentences


def make_excluded_entity(
    doc_id: str,
    split: str,
    language: str,
    source_file: str,
    reason: str,
    label_original: str,
    text: str,
    tokens: list[TokenRow],
    starts: list[int],
    stops: list[int],
    token_start: int,
    token_stop: int,
) -> dict[str, Any]:
    start = starts[token_start]
    stop = stops[token_stop - 1]
    return {
        "document_id": doc_id,
        "split": split,
        "language": language,
        "source_file": source_file,
        "reason": reason,
        "label_original": label_original,
        "surface": text[start:stop],
        "token_start": token_start,
        "token_stop": token_stop,
        "start": start,
        "stop": stop,
        "nel": next((tokens[i].nel for i in range(token_start, token_stop) if tokens[i].nel), ""),
        "ocr_info": [tokens[i].ocr for i in range(token_start, token_stop) if tokens[i].ocr],
    }


def close_entity(
    *,
    doc_id: str,
    text: str,
    tokens: list[TokenRow],
    starts: list[int],
    stops: list[int],
    token_start: int,
    token_stop: int,
    label_original: str,
    canonical_label: str,
    seed_row: dict[str, Any] | None,
    entity_index: int,
) -> dict[str, Any]:
    start = starts[token_start]
    stop = stops[token_stop - 1]
    ocr_values = [parse_ocr_info(tokens[i].ocr) for i in range(token_start, token_stop)]
    transcripts = [transcript for transcript, _led in ocr_values if transcript]
    led_values = [led for _transcript, led in ocr_values if led is not None]
    return {
        "entity_id": f"{doc_id}#ent-{entity_index}",
        "token_start": token_start,
        "token_stop": token_stop,
        "start": start,
        "stop": stop,
        "surface": text[start:stop],
        "normalized_surface": " ".join(transcripts) if transcripts else text[start:stop],
        "label_original": label_original,
        "label": canonical_label,
        "entity_family": "pressagency",
        "nel": next((tokens[i].nel for i in range(token_start, token_stop) if tokens[i].nel), ""),
        "wikidata_url": seed_row.get("wikidata_url") if seed_row else None,
        "has_ocr_correction": bool(transcripts),
        "max_ocr_levenshtein": max(led_values) if led_values else 0.0,
        "status": "accepted",
    }


def convert_bio_labels(
    *,
    doc: HipeDocument,
    split: str,
    source_file: str,
    text: str,
    starts: list[int],
    stops: list[int],
    seed_labels: dict[str, dict[str, Any]],
    forbidden_label_policy: str,
    unknown_label_policy: str,
    malformed_bio_policy: str,
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], set[str], Counter[str], Counter[str]]:
    doc_id = doc.comments.get("document_id", "")
    language = doc.comments.get("language", "")
    public_labels = ["O"] * len(doc.tokens)
    entities: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    quality_flags: set[str] = set()
    accepted_count: Counter[str] = Counter()
    excluded_count: Counter[str] = Counter()

    active_start: int | None = None
    active_base = ""
    active_canonical = ""
    active_seed: dict[str, Any] | None = None
    active_original = ""

    def flush_active(stop: int) -> None:
        nonlocal active_start, active_base, active_canonical, active_seed, active_original
        if active_start is None:
            return
        entity = close_entity(
            doc_id=doc_id,
            text=text,
            tokens=doc.tokens,
            starts=starts,
            stops=stops,
            token_start=active_start,
            token_stop=stop,
            label_original=active_original,
            canonical_label=active_canonical,
            seed_row=active_seed,
            entity_index=len(entities),
        )
        entities.append(entity)
        accepted_count[active_canonical] += 1
        active_start = None
        active_base = ""
        active_canonical = ""
        active_seed = None
        active_original = ""

    def exclude_span(start: int, stop: int, reason: str, original: str) -> None:
        excluded.append(
            make_excluded_entity(
                doc_id,
                split,
                language,
                source_file,
                reason,
                original,
                text,
                doc.tokens,
                starts,
                stops,
                start,
                stop,
            )
        )
        excluded_count[reason] += 1
        quality_flags.add("has_forbidden_legacy_labels")

    i = 0
    while i < len(doc.tokens):
        raw = doc.tokens[i].fine_label
        if raw in {"", "_", "O"}:
            flush_active(i)
            i += 1
            continue

        prefix = bio_prefix(raw)
        base = base_label(raw)
        canonical, seed_row = canonicalize_base(base, seed_labels)
        reason = forbidden_reason(base, seed_row)

        if canonical is None:
            if reason is None:
                reason = "unknown_label"
                if unknown_label_policy == "error":
                    raise ConversionError(f"{doc.source_file}:{doc.tokens[i].source_line}: unknown label {raw!r}")
            if forbidden_label_policy == "error":
                raise ConversionError(f"{doc.source_file}:{doc.tokens[i].source_line}: forbidden label {raw!r}")
            flush_active(i)
            start = i
            i += 1
            while i < len(doc.tokens) and base_label(doc.tokens[i].fine_label).lower() == base.lower():
                i += 1
            exclude_span(start, i, reason, raw)
            continue

        if prefix == "I" and active_start is None:
            if malformed_bio_policy == "error":
                raise ConversionError(f"{doc.source_file}:{doc.tokens[i].source_line}: I label without active span {raw!r}")
            quality_flags.add("repaired_bio")
            prefix = "B"
        elif prefix == "I" and active_base.lower() != base.lower():
            if malformed_bio_policy == "error":
                raise ConversionError(f"{doc.source_file}:{doc.tokens[i].source_line}: I label changes entity {raw!r}")
            quality_flags.add("repaired_bio")
            flush_active(i)
            prefix = "B"

        if prefix == "B":
            flush_active(i)
            active_start = i
            active_base = base
            active_canonical = canonical
            active_seed = seed_row
            active_original = base
            public_labels[i] = f"B-{canonical}"
        else:
            public_labels[i] = f"I-{canonical}"
        i += 1

    flush_active(len(doc.tokens))
    return public_labels, entities, excluded, quality_flags, accepted_count, excluded_count


def validate_required_metadata(doc: HipeDocument, allow_missing: bool) -> None:
    missing = [key for key in ["language", "newspaper", "date", "document_id"] if not doc.comments.get(key)]
    if missing and not allow_missing:
        raise ConversionError(f"{doc.source_file}:{doc.start_line}: missing required metadata: {', '.join(missing)}")


def infer_missing_language(doc: HipeDocument, source_file: str) -> bool:
    if doc.comments.get("language"):
        return False
    parts = Path(source_file).parts
    if "de" in parts:
        doc.comments["language"] = "de"
        return True
    if "fr" in parts:
        doc.comments["language"] = "fr"
        return True
    newspaper = doc.comments.get("newspaper", "")
    if newspaper in NEWSPAPER_LANGUAGE_HINTS:
        doc.comments["language"] = NEWSPAPER_LANGUAGE_HINTS[newspaper]
        return True
    return False


def convert_document(
    doc: HipeDocument,
    *,
    split: str,
    source_file: str,
    seed_labels: dict[str, dict[str, Any]],
    forbidden_label_policy: str,
    unknown_label_policy: str,
    malformed_bio_policy: str,
    allow_missing_metadata: bool,
) -> ConvertedDocument:
    inferred_language = infer_missing_language(doc, source_file)
    validate_required_metadata(doc, allow_missing_metadata)
    text, layout_text, starts, stops = reconstruct_text(doc.tokens)
    for token, start, stop in zip(doc.tokens, starts, stops, strict=True):
        if text[start:stop] != token.token:
            raise ConversionError(f"{doc.source_file}:{token.source_line}: offset reconstruction mismatch")

    labels, entities, excluded, quality_flags, accepted_count, excluded_count = convert_bio_labels(
        doc=doc,
        split=split,
        source_file=source_file,
        text=text,
        starts=starts,
        stops=stops,
        seed_labels=seed_labels,
        forbidden_label_policy=forbidden_label_policy,
        unknown_label_policy=unknown_label_policy,
        malformed_bio_policy=malformed_bio_policy,
    )

    for token in doc.tokens:
        transcript, led = parse_ocr_info(token.ocr)
        if transcript or (led is not None and led > 0):
            quality_flags.add("has_ocr_corrections")
    if inferred_language:
        quality_flags.add("inferred_language")

    doc_id = doc.comments.get("document_id") or f"{Path(source_file).stem}:{doc.start_line}"
    date = doc.comments.get("date", "")
    public = {
        "schema_version": "mediasources-jsonl-v0.1",
        "id": doc_id,
        "split": split,
        "source_format": "hipe-tsv",
        "source_file": source_file,
        "language": doc.comments.get("language", ""),
        "newspaper": doc.comments.get("newspaper", ""),
        "date": date,
        "year": parse_year(date),
        "document_id": doc_id,
        "news_agency_as_source": parse_source_qids(doc.comments.get("news-agency-as-source", "")),
        "text": text,
        "tokens": [token.token for token in doc.tokens],
        "token_start_offsets": starts,
        "token_end_offsets": stops,
        "token_labels": labels,
        "token_label_ids": [],
        "token_nel": [token.nel for token in doc.tokens],
        "token_ocr": [token.ocr for token in doc.tokens],
        "token_render": [token.render for token in doc.tokens],
        "token_segment_ids": [token.segment_index if token.segment_index is not None else -1 for token in doc.tokens],
        "segments": build_segments(doc.tokens, starts, stops),
        "sentences": build_sentences(doc.tokens, starts, stops),
        "entities": entities,
        "quality_flags": sorted(quality_flags),
    }
    audit = {
        "id": doc_id,
        "split": split,
        "source_file": source_file,
        "source_line_start": doc.start_line,
        "source_line_end": doc.end_line,
        "comments": doc.comments,
        "original_comments": [{"key": key, "value": value} for key, value in doc.original_comments],
        "layout_text": layout_text,
        "tokens": [
            {
                "line": token.source_line,
                "segment_index": token.segment_index,
                "segment_iiif_link": token.segment_link,
                "columns": dict(zip(EXPECTED_COLUMNS, token.columns, strict=True)),
            }
            for token in doc.tokens
        ],
        "excluded_entities": excluded,
    }
    return ConvertedDocument(
        split=split,
        public=public,
        audit=audit,
        excluded_entities=excluded,
        accepted_label_count=accepted_count,
        excluded_reason_count=excluded_count,
        quality_flags=quality_flags,
    )


def make_label_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, int] | dict[str, str]]:
    labels = sorted({label for row in rows for label in row["token_labels"] if label != "O"}, key=label_sort_key)
    label2id = {"O": 0}
    for label in labels:
        label2id[label] = len(label2id)
    id2label = {str(value): key for key, value in label2id.items()}
    return {"label2id": label2id, "id2label": id2label}


def label_sort_key(label: str) -> tuple[str, int]:
    base = base_label(label)
    prefix_order = 0 if label.startswith("B-") else 1
    return base, prefix_order


def fill_label_ids(rows: list[dict[str, Any]], label_map: dict[str, Any]) -> None:
    label2id = label_map["label2id"]
    for row in rows:
        row["token_label_ids"] = [label2id[label] for label in row["token_labels"]]


def validate_public_row(row: dict[str, Any], label_map: dict[str, Any]) -> None:
    token_count = len(row["tokens"])
    for field_name in [
        "token_start_offsets",
        "token_end_offsets",
        "token_labels",
        "token_label_ids",
        "token_nel",
        "token_ocr",
        "token_render",
        "token_segment_ids",
    ]:
        if len(row[field_name]) != token_count:
            raise ConversionError(f"{row['id']}: {field_name} length does not match tokens")
    for token, start, stop in zip(row["tokens"], row["token_start_offsets"], row["token_end_offsets"], strict=True):
        if row["text"][start:stop] != token:
            raise ConversionError(f"{row['id']}: token offset mismatch for {token!r}")
    for label, label_id in zip(row["token_labels"], row["token_label_ids"], strict=True):
        if label_map["label2id"][label] != label_id:
            raise ConversionError(f"{row['id']}: token_label_ids mismatch")
        lowered = label.lower()
        if "pressagency.unk" in lowered or "pressagency.ag" in lowered or "pers.ind.articleauthor" in lowered:
            raise ConversionError(f"{row['id']}: forbidden public label {label}")
    for entity in row["entities"]:
        if row["text"][entity["start"] : entity["stop"]] != entity["surface"]:
            raise ConversionError(f"{row['id']}: entity surface mismatch")
        lowered = entity["label"].lower()
        if "pressagency.unk" in lowered or "pressagency.ag" in lowered or "pers.ind.articleauthor" in lowered:
            raise ConversionError(f"{row['id']}: forbidden public entity label {entity['label']}")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_conversion(args: argparse.Namespace) -> dict[str, Any]:
    inputs = discover_inputs([Path(value) for value in args.input])
    output_dir = Path(args.output)
    source_root = Path(args.source_root) if args.source_root else None
    seed_labels = load_seed_labels(Path(args.newsagency_seeds))
    converted: list[ConvertedDocument] = []

    for input_file in inputs:
        split = split_from_path(input_file, args.split)
        source_file = relative_source(input_file, source_root)
        for doc in parse_hipe_file(input_file):
            converted.append(
                convert_document(
                    doc,
                    split=split,
                    source_file=source_file,
                    seed_labels=seed_labels,
                    forbidden_label_policy=args.forbidden_label_policy,
                    unknown_label_policy=args.unknown_label_policy,
                    malformed_bio_policy=args.malformed_bio_policy,
                    allow_missing_metadata=args.allow_missing_metadata,
                )
            )

    seen_ids: dict[str, str] = {}
    duplicate_ids: list[str] = []
    public_rows = [item.public for item in converted]
    for row in public_rows:
        comparable = dict(row)
        comparable.pop("source_file", None)
        encoded = json.dumps(comparable, ensure_ascii=False, sort_keys=True)
        existing = seen_ids.get(row["id"])
        if existing is None:
            seen_ids[row["id"]] = encoded
        elif existing == encoded:
            duplicate_ids.append(row["id"])
        elif args.duplicate_policy == "error":
            raise ConversionError(f"conflicting duplicate document_id: {row['id']}")
        else:
            duplicate_ids.append(row["id"])

    if duplicate_ids and args.duplicate_policy == "keep-first":
        unique: dict[str, ConvertedDocument] = {}
        for item in converted:
            unique.setdefault(item.public["id"], item)
        converted = list(unique.values())
        public_rows = [item.public for item in converted]

    label_map = make_label_map(public_rows)
    fill_label_ids(public_rows, label_map)
    for row in public_rows:
        validate_public_row(row, label_map)

    rows_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audits_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_entities: list[dict[str, Any]] = []
    for item in converted:
        rows_by_split[item.split].append(item.public)
        audits_by_split[item.split].append(item.audit)
        excluded_entities.extend(item.excluded_entities)

    for split in ["train", "validation", "test"]:
        write_jsonl(output_dir / f"{split}.jsonl", rows_by_split.get(split, []))
        write_jsonl(output_dir / "audit" / f"{split}.audit.jsonl", audits_by_split.get(split, []))
    write_jsonl(output_dir / "audit" / "excluded_entities.jsonl", excluded_entities)
    (output_dir / "label_map.json").write_text(json.dumps(label_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = build_report(inputs, converted, duplicate_ids, label_map)
    (output_dir / "conversion_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_report(
    inputs: list[Path],
    converted: list[ConvertedDocument],
    duplicate_ids: list[str],
    label_map: dict[str, Any],
) -> dict[str, Any]:
    doc_counts: Counter[str] = Counter()
    token_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    accepted_counts: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()

    for item in converted:
        split = item.split
        row = item.public
        doc_counts[split] += 1
        token_counts[split] += len(row["tokens"])
        language_counts[f"{split}:{row['language']}"] += 1
        accepted_counts.update(item.accepted_label_count)
        excluded_counts.update(item.excluded_reason_count)
        quality_counts.update(item.quality_flags)

    return {
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "input_files": [str(path) for path in inputs],
        "document_counts_by_split": dict(sorted(doc_counts.items())),
        "token_counts_by_split": dict(sorted(token_counts.items())),
        "document_counts_by_split_language": dict(sorted(language_counts.items())),
        "accepted_entity_counts_by_label": dict(sorted(accepted_counts.items())),
        "excluded_entity_counts_by_reason": dict(sorted(excluded_counts.items())),
        "quality_flag_counts": dict(sorted(quality_counts.items())),
        "duplicate_document_ids": sorted(set(duplicate_ids)),
        "label_count": len(label_map["label2id"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert legacy HIPE TSV annotations to HF-style JSONL.")
    parser.add_argument("--input", action="append", required=True, help="Input TSV file or directory. Can be repeated.")
    parser.add_argument("--output", required=True, help="Output directory for split JSONL files.")
    parser.add_argument("--source-root", help="Root used to make source_file paths relative.")
    parser.add_argument(
        "--split",
        choices=["train", "validation", "test"],
        help="Optional split override for all input files. Otherwise inferred from filenames.",
    )
    parser.add_argument(
        "--newsagency-seeds",
        default="resources/newsagency_seeds.json",
        help="Canonical newsagency seed metadata JSON.",
    )
    parser.add_argument(
        "--forbidden-label-policy",
        choices=["exclude", "error"],
        default="exclude",
        help="How to handle known forbidden labels such as unk, ag, and article authors.",
    )
    parser.add_argument(
        "--unknown-label-policy",
        choices=["error", "exclude"],
        default="error",
        help="How to handle labels that are not in seed metadata.",
    )
    parser.add_argument(
        "--malformed-bio-policy",
        choices=["error", "repair"],
        default="error",
        help="How to handle malformed BIO sequences.",
    )
    parser.add_argument(
        "--duplicate-policy",
        choices=["error", "keep-first"],
        default="error",
        help="How to handle duplicate document IDs after conversion.",
    )
    parser.add_argument("--allow-missing-metadata", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    report = run_conversion(args)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
