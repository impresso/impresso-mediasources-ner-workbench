from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import logging
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .snippet_data import load_jsonl, write_jsonl


SUPPORTED_FAMILIES = {"pressagency", "radiostation"}
DEFAULT_MIN_CONFIDENCE = 0.30
DEFAULT_MAX_CONFIDENCE = 0.80
DEFAULT_CONTEXT_CHARS = 256
DEFAULT_MAX_FETCH_FAILURES = 25
DEFAULT_PROGRESS_EVERY = 25
DEFAULT_DIAGNOSTIC_EXAMPLES = 10
DEFAULT_IMPRESSO_API_URL = "https://dev.impresso-project.ch/public-api/v1"
DEFAULT_HEALTHCHECK_CONTENT_ITEM = "NZZ-1794-08-09-a-i0002"
DEFAULT_SMOKE_CONTENT_ITEMS = 10
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_HTTP_RETRIES = 3
LOGGER_NAME = "sample_cookbook_snippets"


class ImpressoApiError(RuntimeError):
    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status


def label_family(label: str) -> str:
    if label.startswith("org.ent.pressagency."):
        return "pressagency"
    if label.startswith("org.ent.radiostation."):
        return "radiostation"
    return ""


def parse_ci_metadata(ci_id: str) -> dict[str, Any]:
    match = re.match(r"^(?P<newspaper>[^-]+)-(?P<date>\d{4}-\d{2}-\d{2})-", ci_id)
    if not match:
        return {}
    return {
        "newspaper": match.group("newspaper"),
        "mediaId": match.group("newspaper"),
        "date": match.group("date"),
        "year": int(match.group("date")[:4]),
    }


def content_item_url(ci_id: str) -> str:
    return f"https://impresso-project.ch/app/content-item/{ci_id}"


def prediction_diagnostics(prediction: dict[str, Any]) -> dict[str, Any]:
    ci_id = str(prediction.get("ci_id") or "")
    return {
        "ci_id": ci_id,
        "issue_id": sample_issue_id(ci_id),
        "content_item_url": content_item_url(ci_id) if ci_id else "",
        **parse_ci_metadata(ci_id),
        "label": prediction.get("label"),
        "surface": prediction.get("surface"),
        "confidence": prediction.get("confidence"),
        "offsets": [prediction.get("start"), prediction.get("stop")],
    }


def base_document_id(value: Any) -> str:
    return str(value or "").split("#", 1)[0]


def sample_issue_id(value: Any) -> str:
    document_id = base_document_id(value)
    if "-i" in document_id:
        return document_id.rsplit("-i", 1)[0]
    return document_id


def document_id_from_row(row: dict[str, Any]) -> str:
    for field in ("ci_id", "content_item_id", "document_id", "id"):
        value = row.get(field)
        if value:
            return base_document_id(value)
    source = row.get("source")
    if isinstance(source, dict) and source.get("document_id"):
        return base_document_id(source["document_id"])
    legacy = row.get("legacy")
    if isinstance(legacy, dict) and legacy.get("source_document_id"):
        return base_document_id(legacy["source_document_id"])
    return ""


def existing_document_ids(paths: Iterable[Path]) -> set[str]:
    ids: set[str] = set()
    for path in paths:
        for row in load_jsonl(path):
            document_id = document_id_from_row(row)
            if document_id:
                ids.add(document_id)
    return ids


def load_cookbook_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    opener = bz2.open if path.suffix == ".bz2" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def iter_predictions(rows: Iterable[dict[str, Any]], family: str) -> Iterable[dict[str, Any]]:
    for row_index, row in enumerate(rows):
        ci_id = str(row.get("ci_id") or "").strip()
        if not ci_id:
            continue
        nes = row.get("nes")
        if not isinstance(nes, list):
            continue
        for ne_index, ne in enumerate(nes):
            if not isinstance(ne, dict):
                continue
            label = str(ne.get("fine_grained_type") or "").strip()
            if label_family(label) != family:
                continue
            yield {
                "row_index": row_index,
                "ne_index": ne_index,
                "ci_id": ci_id,
                "label": label,
                "surface": str(ne.get("surface") or ""),
                "start": ne.get("lOffset"),
                "stop": ne.get("rOffset"),
                "confidence": ne.get("confidence_ner"),
                "wkdata_qid": ne.get("wkdata_qid"),
                "raw": ne,
            }


def probability(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def prediction_is_usable(prediction: dict[str, Any]) -> bool:
    try:
        start = int(prediction["start"])
        stop = int(prediction["stop"])
        confidence = float(prediction["confidence"])
    except (TypeError, ValueError):
        return False
    return 0 <= start < stop and 0.0 <= confidence <= 1.0


def ranking_key(prediction: dict[str, Any], label_counts: Counter[str]) -> tuple[int, float, str]:
    confidence = float(prediction["confidence"])
    confidence_distance = abs(confidence - 0.5)
    stable = hashlib.sha1(
        f"{prediction['ci_id']}\t{prediction['label']}\t{prediction['start']}\t{prediction['stop']}".encode("utf-8")
    ).hexdigest()
    return (label_counts[str(prediction["label"])], confidence_distance, stable)


def choose_one_prediction_per_document(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    label_counts = Counter(str(prediction["label"]) for prediction in predictions)
    selected: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for prediction in predictions:
        ci_id = str(prediction["ci_id"])
        if ci_id not in selected:
            order.append(ci_id)
        previous = selected.get(ci_id)
        if previous is None or ranking_key(prediction, label_counts) < ranking_key(previous, label_counts):
            selected[ci_id] = prediction
    return [selected[ci_id] for ci_id in order]


def top_counts(values: Iterable[Any], limit: int) -> dict[str, int]:
    counter = Counter(str(value) for value in values if value not in {None, ""})
    return dict(counter.most_common(limit))


def prediction_year(prediction: dict[str, Any]) -> int | None:
    metadata = parse_ci_metadata(str(prediction.get("ci_id") or ""))
    year = metadata.get("year")
    return int(year) if isinstance(year, int) else None


def prediction_media(prediction: dict[str, Any]) -> str:
    metadata = parse_ci_metadata(str(prediction.get("ci_id") or ""))
    return str(metadata.get("newspaper") or "")


def context_window(content: str, start: int, stop: int, radius: int) -> tuple[str, int, int]:
    left = max(0, start - radius)
    right = min(len(content), stop + radius)
    while left > 0 and not content[left - 1].isspace():
        left -= 1
    while right < len(content) and not content[right].isspace():
        right += 1
    raw = content[left:right]
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw) - len(raw.rstrip())
    adjusted_left = left + leading
    adjusted_right = right - trailing
    return content[adjusted_left:adjusted_right], adjusted_left, adjusted_right


def unique_surface_location(content: str, surface: str, expected_start: int, expected_stop: int, *, radius: int = 32) -> tuple[int, int] | None:
    if not surface:
        return None
    if 0 <= expected_start < expected_stop <= len(content) and content[expected_start:expected_stop] == surface:
        return expected_start, expected_stop
    left = max(0, expected_start - radius)
    right = min(len(content), expected_stop + radius)
    haystack = content[left:right]
    matches = [match for match in re.finditer(re.escape(surface), haystack)]
    if len(matches) != 1:
        return None
    match = matches[0]
    return left + match.start(), left + match.end()


def build_candidate(prediction: dict[str, Any], content: str, *, context_chars: int) -> tuple[dict[str, Any] | None, str]:
    absolute_start = int(prediction["start"])
    absolute_stop = int(prediction["stop"])
    surface = str(prediction["surface"])
    relocated = unique_surface_location(content, surface, absolute_start, absolute_stop)
    if relocated is None:
        return None, "offset_mismatch"
    absolute_start, absolute_stop = relocated
    text, context_start, context_stop = context_window(content, absolute_start, absolute_stop, context_chars)
    if not text:
        return None, "empty_context"
    local_start = absolute_start - context_start
    local_stop = absolute_stop - context_start
    if not (0 <= local_start < local_stop <= len(text)):
        return None, "span_outside_context"
    ci_id = str(prediction["ci_id"])
    label = str(prediction["label"])
    row = {
        "id": f"cookbook-snippet:{ci_id}",
        "candidate_label": label,
        "label": label,
        "query": surface,
        "text": text,
        "text_source": "cookbook_prediction_offset_window",
        "context_start": context_start,
        "context_stop": context_stop,
        "match_start": absolute_start,
        "match_stop": absolute_stop,
        "match_text": text[local_start:local_stop],
        "sample_document_id": ci_id,
        "sample_issue_id": sample_issue_id(ci_id),
        "source": {
            "type": "cookbook_low_confidence_prediction",
            "document_id": ci_id,
        },
        "cookbook_prediction": {
            "label": label,
            "surface": surface,
            "absolute_start": absolute_start,
            "absolute_stop": absolute_stop,
            "snippet_start": local_start,
            "snippet_stop": local_stop,
            "confidence": float(prediction["confidence"]),
            "wkdata_qid": prediction.get("wkdata_qid"),
            "raw": prediction.get("raw"),
        },
        "curation": {
            "status": "candidate",
            "label": label,
            "source": "cookbook_low_confidence_prediction",
            "reasons": ["cookbook_low_confidence"],
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        },
    }
    row.update(parse_ci_metadata(ci_id))
    return row, "ok"


def api_join(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def load_impresso_api_token(api_url: str) -> str:
    token = os.getenv("IMPRESSO_API_TOKEN")
    if token and token.strip():
        return token.strip()
    persisted_token = os.getenv("IMPRESSO_PERSISTED_TOKEN")
    if persisted_token is not None and not parse_bool(persisted_token, default=True):
        raise ImpressoApiError(
            401,
            "No IMPRESSO_API_TOKEN is set and IMPRESSO_PERSISTED_TOKEN=false disables the impresso-py token cache.",
        )
    try:
        from impresso.config_file import ImpressoPyConfig  # type: ignore
    except ImportError as exc:
        raise ImpressoApiError(401, "No IMPRESSO_API_TOKEN is set and impresso-py is unavailable for cache lookup.") from exc
    cached = ImpressoPyConfig().get_token(api_url)
    if cached:
        return cached
    raise ImpressoApiError(
        401,
        f"No Impresso API token available for {api_url}. Set IMPRESSO_API_TOKEN or populate ~/.impresso_py.yml with impresso-py.",
    )


def http_json_get(url: str, *, token: str, timeout: float, retries: int, logger: logging.Logger | None = None) -> Any:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    attempt = 0
    while True:
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            status = int(exc.code)
            body = exc.read().decode("utf-8", errors="replace")
            if status == 429 and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                pause = float(retry_after) if retry_after and retry_after.isdigit() else min(30.0, 2.0**attempt)
                if logger:
                    logger.warning("rate limited by Impresso API; retrying in %.1fs", pause)
                time.sleep(pause)
                attempt += 1
                continue
            if 500 <= status < 600 and attempt < retries:
                pause = min(30.0, 2.0**attempt)
                if logger:
                    logger.warning("Impresso API %s for %s; retrying in %.1fs", status, url, pause)
                time.sleep(pause)
                attempt += 1
                continue
            raise ImpressoApiError(status, f"HTTP {status}: {body or exc.reason}") from exc
        except URLError as exc:
            if attempt < retries:
                pause = min(30.0, 2.0**attempt)
                if logger:
                    logger.warning("Impresso API network error for %s; retrying in %.1fs: %s", url, pause, exc)
                time.sleep(pause)
                attempt += 1
                continue
            raise ImpressoApiError(None, f"network error: {exc}") from exc


class ImpressoRestClient:
    def __init__(
        self,
        api_url: str,
        token: str,
        *,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        retries: int = DEFAULT_HTTP_RETRIES,
        logger: logging.Logger | None = None,
    ) -> None:
        self.api_url = api_url
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.logger = logger

    def version(self) -> Any:
        return http_json_get(
            api_join(self.api_url, "version"),
            token=self.token,
            timeout=self.timeout,
            retries=self.retries,
            logger=self.logger,
        )

    def content_item(self, document_id: str) -> dict[str, Any]:
        item = http_json_get(
            api_join(self.api_url, f"content-items/{quote(document_id, safe='')}"),
            token=self.token,
            timeout=self.timeout,
            retries=self.retries,
            logger=self.logger,
        )
        return item if isinstance(item, dict) else {}

    def content_text(self, document_id: str) -> str:
        from .sample_newsagencies import content_text_from_raw

        return content_text_from_raw(self.content_item(document_id))


def load_content_fetcher(
    impresso_api_url: str,
    *,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    retries: int = DEFAULT_HTTP_RETRIES,
    logger: logging.Logger | None = None,
) -> Callable[[str], str]:
    client = ImpressoRestClient(
        impresso_api_url,
        load_impresso_api_token(impresso_api_url),
        timeout=timeout,
        retries=retries,
        logger=logger,
    )
    api_version = client.version()
    if logger:
        logger.info("API connectivity: OK")
        logger.info("API version: %s", json.dumps(api_version, ensure_ascii=False, sort_keys=True))

    def fetch(document_id: str) -> str:
        return client.content_text(document_id)

    setattr(fetch, "api_version", api_version)
    setattr(fetch, "client", client)
    return fetch


def resolve_impresso_api_url(cli_value: str | None) -> str:
    return cli_value or os.getenv("COOKBOOK_IMPRESSO_API_URL") or os.getenv("IMPRESSO_API_URL") or DEFAULT_IMPRESSO_API_URL


def fetch_error_reason(exc: Exception) -> str:
    status = getattr(exc, "status", None)
    text = str(exc).lower()
    if status in {401, 403} or any(marker in text for marker in ("provided token is invalid", "jwt expired", "unauthorized", "forbidden", "401", "403")):
        return "auth_error"
    if status == 404 or "404" in text or "not found" in text:
        return "content_item_not_found"
    return "content_fetch_failed"


def sample_rows(
    input_path: Path,
    *,
    family: str,
    min_confidence: float,
    max_confidence: float,
    context_chars: int,
    limit: int,
    max_fetch_failures: int,
    existing_paths: list[Path],
    fetch_content: Callable[[str], str],
    impresso_api_url: str | None = None,
    api_version: Any = None,
    healthcheck_content_item: str | None = None,
    smoke_content_items: int = 0,
    logger: logging.Logger | None = None,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
    diagnostic_examples: int = DEFAULT_DIAGNOSTIC_EXAMPLES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    counts: Counter[str] = Counter()
    content_cache: dict[str, str] = {}
    unavailable_newspapers: dict[str, dict[str, Any]] = {}
    input_rows = load_cookbook_jsonl(input_path)
    existing_ids = existing_document_ids(existing_paths)
    if logger:
        if impresso_api_url:
            logger.info("Impresso API: %s", impresso_api_url)
        logger.info("input: %s", input_path)
        logger.info("loaded cookbook rows: %d", len(input_rows))
        logger.info("existing content-item ids suppressed: %d", len(existing_ids))
        logger.info("family: %s; confidence band: %.2f <= confidence_ner < %.2f", family, min_confidence, max_confidence)
    filtered_predictions: list[dict[str, Any]] = []
    for prediction in iter_predictions(input_rows, family):
        counts["predictions_total"] += 1
        if not prediction_is_usable(prediction):
            counts["invalid_prediction"] += 1
            continue
        confidence = float(prediction["confidence"])
        if confidence < min_confidence:
            counts["below_min_confidence"] += 1
            continue
        if confidence >= max_confidence:
            counts["at_or_above_max_confidence"] += 1
            continue
        if str(prediction["ci_id"]) in existing_ids:
            counts["existing_content_item"] += 1
            continue
        filtered_predictions.append(prediction)

    selected_predictions = choose_one_prediction_per_document(filtered_predictions)
    counts["duplicates_same_content_item"] = len(filtered_predictions) - len(selected_predictions)
    if logger:
        logger.info("family predictions seen: %d", counts["predictions_total"])
        logger.info("eligible predictions after filters: %d", len(filtered_predictions))
        logger.info("selected content items after one-ci_id deduplication: %d", len(selected_predictions))
        logger.info("top selected labels: %s", top_counts((prediction["label"] for prediction in selected_predictions), diagnostic_examples))
        logger.info("top selected newspapers: %s", top_counts((prediction_media(prediction) for prediction in selected_predictions), diagnostic_examples))
        logger.info("top selected years: %s", top_counts((prediction_year(prediction) for prediction in selected_predictions), diagnostic_examples))
        if selected_predictions:
            logger.info("first selected content items:")
            for prediction in selected_predictions[:diagnostic_examples]:
                logger.info(
                    "  %s label=%s surface=%r conf=%.3f offsets=%s:%s url=%s",
                    prediction["ci_id"],
                    prediction["label"],
                    prediction["surface"],
                    float(prediction["confidence"]),
                    prediction["start"],
                    prediction["stop"],
                    content_item_url(str(prediction["ci_id"])),
                )

    preflight_results: list[dict[str, Any]] = []
    if healthcheck_content_item:
        if logger:
            logger.info("known content-item retrieval: %s", healthcheck_content_item)
        counts["content_items_attempted"] += 1
        try:
            healthcheck_content = fetch_content(healthcheck_content_item)
        except Exception as exc:
            reason = fetch_error_reason(exc)
            preflight_results.append({"ci_id": healthcheck_content_item, "kind": "healthcheck", "status": reason, "error": str(exc)})
            if reason == "auth_error":
                raise RuntimeError(
                    "Impresso authentication failed during healthcheck; check that the token matches the configured API environment."
                ) from exc
            raise RuntimeError(f"Impresso API healthcheck failed for {healthcheck_content_item}: {reason} ({exc})") from exc
        counts["content_items_retrieved"] += 1
        content_cache[healthcheck_content_item] = healthcheck_content
        preflight_results.append(
            {
                "ci_id": healthcheck_content_item,
                "kind": "healthcheck",
                "status": "ok",
                "text_chars": len(healthcheck_content),
            }
        )
        if logger:
            logger.info("known content-item retrieval: OK (%d text chars)", len(healthcheck_content))

    smoke_ids: list[str] = []
    smoke_newspapers: set[str] = set()
    for prediction in selected_predictions:
        ci_id = str(prediction["ci_id"])
        newspaper = prediction_media(prediction)
        if len(smoke_ids) >= max(0, smoke_content_items):
            break
        if newspaper and newspaper in smoke_newspapers:
            continue
        if ci_id not in smoke_ids:
            smoke_ids.append(ci_id)
        if newspaper:
            smoke_newspapers.add(newspaper)

    smoke_successes = 0
    for index, ci_id in enumerate(smoke_ids, start=1):
        newspaper = str(parse_ci_metadata(ci_id).get("newspaper") or "")
        if newspaper in unavailable_newspapers:
            counts["ignored_unavailable_newspaper"] += 1
            preflight_results.append(
                {
                    "ci_id": ci_id,
                    "kind": "cookbook_smoke",
                    "status": "ignored_unavailable_newspaper",
                    "newspaper_probe": unavailable_newspapers[newspaper],
                }
            )
            continue
        if logger:
            logger.info("cookbook smoke %d/%d: %s newspaper=%s", index, len(smoke_ids), ci_id, newspaper or "<unknown>")
        counts["content_items_attempted"] += 1
        try:
            content = fetch_content(ci_id)
        except Exception as exc:
            reason = fetch_error_reason(exc)
            preflight_results.append({"ci_id": ci_id, "kind": "cookbook_smoke", "status": reason, "error": str(exc)})
            if reason == "auth_error":
                raise RuntimeError(
                    "Impresso authentication failed during cookbook sampler preflight; check that the token matches the configured API environment."
                ) from exc
            if reason == "content_item_not_found":
                counts["content_item_not_found"] += 1
                if newspaper:
                    unavailable_newspapers.setdefault(
                        newspaper,
                        {
                            "newspaper": newspaper,
                            "sample_content_item": ci_id,
                            "reason": reason,
                            "error": str(exc),
                        },
                    )
                if logger:
                    logger.warning("cookbook smoke: 404 for %s; ignoring later %s candidates", ci_id, newspaper or "<unknown newspaper>")
                continue
            counts["content_fetch_failed"] += 1
            if logger:
                logger.warning("preflight: %s for %s (%s)", reason, ci_id, exc)
            if max_fetch_failures > 0 and counts["content_fetch_failed"] >= max_fetch_failures:
                raise RuntimeError(f"Impresso preflight failed after {counts['content_fetch_failed']} API/network failures.") from exc
            continue
        content_cache[ci_id] = content
        counts["content_items_retrieved"] += 1
        smoke_successes += 1
        preflight_results.append({"ci_id": ci_id, "kind": "cookbook_smoke", "status": "ok", "text_chars": len(content)})
        if logger:
            logger.info("cookbook smoke: OK (%s, %d text chars)", ci_id, len(content))
    if smoke_ids and smoke_successes == 0:
        raise RuntimeError(f"API/corpus mismatch: none of the sampled cookbook IDs exists in this API corpus: {impresso_api_url or '<unknown API>'}.")

    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for fetch_index, prediction in enumerate(selected_predictions, start=1):
        if limit > 0 and len(rows) >= limit:
            counts["limit_reached"] += 1
            if logger:
                logger.info("stopping: snippet limit reached (%d)", limit)
            break
        if max_fetch_failures > 0 and counts["content_fetch_failed"] >= max_fetch_failures:
            counts["max_fetch_failures_reached"] += 1
            if logger:
                logger.warning("stopping: max fetch failures reached (%d)", max_fetch_failures)
            break
        ci_id = str(prediction["ci_id"])
        newspaper = prediction_media(prediction)
        if newspaper in unavailable_newspapers:
            counts["ignored_unavailable_newspaper"] += 1
            rejected.append(
                {
                    "ci_id": ci_id,
                    "reason": "ignored_unavailable_newspaper",
                    "diagnostics": prediction_diagnostics(prediction),
                    "newspaper_probe": unavailable_newspapers[newspaper],
                    "prediction": prediction,
                }
            )
            continue
        if logger and (fetch_index == 1 or progress_every <= 1 or fetch_index % progress_every == 0):
            logger.info(
                "fetching %d/%d: %s label=%s surface=%r conf=%.3f",
                fetch_index,
                len(selected_predictions),
                ci_id,
                prediction["label"],
                prediction["surface"],
                float(prediction["confidence"]),
            )
        try:
            if ci_id in content_cache:
                content = content_cache[ci_id]
            else:
                counts["content_items_attempted"] += 1
                content = fetch_content(ci_id)
                content_cache[ci_id] = content
                counts["content_items_retrieved"] += 1
        except Exception as exc:
            reason = fetch_error_reason(exc)
            if reason == "auth_error":
                raise RuntimeError(
                    "Impresso authentication failed while fetching content items; refresh the token or set the matching Impresso API URL."
                ) from exc
            counts[reason] += 1
            if reason == "content_item_not_found" and newspaper:
                unavailable_newspapers.setdefault(
                    newspaper,
                    {
                        "newspaper": newspaper,
                        "sample_content_item": ci_id,
                        "reason": reason,
                        "error": str(exc),
                    },
                )
            rejected.append(
                {
                    "ci_id": ci_id,
                    "reason": reason,
                    "error": str(exc),
                    "diagnostics": prediction_diagnostics(prediction),
                    "prediction": prediction,
                }
            )
            if logger:
                logger.warning(
                    "rejected %s: %s (%s); issue=%s url=%s",
                    ci_id,
                    reason,
                    exc,
                    sample_issue_id(ci_id),
                    content_item_url(ci_id),
                )
            continue
        if not content:
            counts["empty_transcript"] += 1
            rejected.append(
                {
                    "ci_id": ci_id,
                    "reason": "empty_transcript",
                    "diagnostics": prediction_diagnostics(prediction),
                    "prediction": prediction,
                }
            )
            if logger:
                logger.warning("rejected %s: empty_transcript; issue=%s url=%s", ci_id, sample_issue_id(ci_id), content_item_url(ci_id))
            continue
        candidate, status = build_candidate(prediction, content, context_chars=context_chars)
        if candidate is None:
            counts[status] += 1
            rejected.append(
                {
                    "ci_id": ci_id,
                    "reason": status,
                    "diagnostics": prediction_diagnostics(prediction),
                    "prediction": prediction,
                }
            )
            if logger:
                logger.warning(
                    "rejected %s: %s label=%s surface=%r offsets=%s:%s issue=%s url=%s",
                    ci_id,
                    status,
                    prediction["label"],
                    prediction["surface"],
                    prediction["start"],
                    prediction["stop"],
                    sample_issue_id(ci_id),
                    content_item_url(ci_id),
                )
            continue
        rows.append(candidate)
        counts["sampled"] += 1
        if logger:
            logger.info("sampled %s: label=%s text_chars=%d", ci_id, candidate["candidate_label"], len(candidate["text"]))

    summary = {
        "input": str(input_path),
        "family": family,
        "impresso_api_url": impresso_api_url,
        "impresso_api_version": api_version,
        "healthcheck_content_item": healthcheck_content_item,
        "preflight_results": preflight_results,
        "ignored_newspapers": list(unavailable_newspapers.values()),
        "content_items_attempted": counts["content_items_attempted"],
        "content_items_retrieved": counts["content_items_retrieved"],
        "settings": {
            "min_confidence": min_confidence,
            "max_confidence": max_confidence,
            "context_chars": context_chars,
            "limit": limit,
            "max_fetch_failures": max_fetch_failures,
            "smoke_content_items": smoke_content_items,
            "deduplication": "one_snippet_per_content_item",
            "existing_paths": [str(path) for path in existing_paths],
        },
        "counts": dict(sorted(counts.items())),
        "counts_by_label": dict(sorted(Counter(row["candidate_label"] for row in rows).items())),
        "eligible_counts_by_label": top_counts((prediction["label"] for prediction in filtered_predictions), 100),
        "selected_counts_by_label": top_counts((prediction["label"] for prediction in selected_predictions), 100),
        "selected_counts_by_newspaper": top_counts((prediction_media(prediction) for prediction in selected_predictions), 100),
        "selected_counts_by_year": top_counts((prediction_year(prediction) for prediction in selected_predictions), 100),
        "first_selected": [prediction_diagnostics(prediction) for prediction in selected_predictions[:diagnostic_examples]],
    }
    if logger:
        logger.info("summary counts:")
        for key, value in sorted(counts.items()):
            logger.info("  %s: %s", key, value)
        logger.info("sampled rows: %d", len(rows))
    return rows, rejected, summary


def configure_logging(level_name: str) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level_name.upper()))
    return logger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample snippet candidates from low-confidence media-source cookbook predictions.")
    parser.add_argument("--family", choices=sorted(SUPPORTED_FAMILIES), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--rejected-out", type=Path)
    parser.add_argument("--min-confidence", type=probability, default=DEFAULT_MIN_CONFIDENCE)
    parser.add_argument("--max-confidence", type=probability, default=DEFAULT_MAX_CONFIDENCE)
    parser.add_argument("--context-chars", type=int, default=DEFAULT_CONTEXT_CHARS)
    parser.add_argument("--limit", type=int, default=0, help="Maximum successfully sampled snippets to write; 0 means no limit.")
    parser.add_argument(
        "--impresso-api-url",
        help=(
            "Impresso public API base URL. Defaults to COOKBOOK_IMPRESSO_API_URL, "
            "then IMPRESSO_API_URL, then the dev API."
        ),
    )
    parser.add_argument(
        "--healthcheck-content-item",
        default=DEFAULT_HEALTHCHECK_CONTENT_ITEM,
        help="Known-good content-item id to retrieve before cookbook smoke tests; empty disables this healthcheck.",
    )
    parser.add_argument(
        "--smoke-content-items",
        type=int,
        default=DEFAULT_SMOKE_CONTENT_ITEMS,
        help="Number of first selected cookbook content-item ids to probe before the full job.",
    )
    parser.add_argument("--http-timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    parser.add_argument("--http-retries", type=int, default=DEFAULT_HTTP_RETRIES)
    parser.add_argument(
        "--max-fetch-failures",
        type=int,
        default=DEFAULT_MAX_FETCH_FAILURES,
        help="Stop after this many full-text fetch failures; 0 means no cap.",
    )
    parser.add_argument("--quiet-api-errors", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    parser.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)
    parser.add_argument("--diagnostic-examples", type=int, default=DEFAULT_DIAGNOSTIC_EXAMPLES)
    parser.add_argument("--existing-jsonl", type=Path, action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.quiet_api_errors:
        logging.getLogger().setLevel(logging.CRITICAL)
    logger = configure_logging(args.log_level)
    from .sample_newsagencies import load_local_env

    load_local_env()
    impresso_api_url = resolve_impresso_api_url(args.impresso_api_url)
    try:
        content_fetcher = load_content_fetcher(
            impresso_api_url,
            timeout=max(0.1, args.http_timeout),
            retries=max(0, args.http_retries),
            logger=logger,
        )
        api_version = getattr(content_fetcher, "api_version", None)
        rows, rejected, summary = sample_rows(
            args.input,
            family=args.family,
            min_confidence=args.min_confidence,
            max_confidence=args.max_confidence,
            context_chars=args.context_chars,
            limit=max(0, args.limit),
            max_fetch_failures=max(0, args.max_fetch_failures),
            existing_paths=args.existing_jsonl,
            fetch_content=content_fetcher,
            impresso_api_url=impresso_api_url,
            api_version=api_version,
            healthcheck_content_item=args.healthcheck_content_item.strip() or None,
            smoke_content_items=max(0, args.smoke_content_items),
            logger=logger,
            progress_every=max(1, args.progress_every),
            diagnostic_examples=max(0, args.diagnostic_examples),
        )
    except RuntimeError as exc:
        logger.error("aborted: %s", exc)
        return 2
    write_jsonl(args.out, rows)
    if args.rejected_out:
        write_jsonl(args.rejected_out, rejected)
        summary["rejected_output"] = str(args.rejected_out)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    logger.info("wrote candidates: %s", args.out)
    if args.rejected_out:
        logger.info("wrote rejected candidates: %s", args.rejected_out)
    logger.info("wrote summary: %s", args.summary_out)
    print(json.dumps({"rows": len(rows), "output": str(args.out), "summary": str(args.summary_out)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
