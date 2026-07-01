from pathlib import Path

from lib.dataset_subword_stats import analyze_split, fixed_word_windows, parse_split


class Encoding(dict):
    def __init__(self, input_ids: list[int], word_ids: list[int | None]):
        super().__init__(input_ids=input_ids)
        self._word_ids = word_ids

    def word_ids(self) -> list[int | None]:
        return self._word_ids


class FakeTokenizer:
    def pieces(self, token: str) -> int:
        return 3 if token.startswith("long") else 1

    def __call__(
        self,
        value,
        *,
        add_special_tokens=True,
        is_split_into_words=False,
        truncation=False,
        max_length=None,
    ):
        tokens = value if is_split_into_words else [value]
        input_ids = [0] if add_special_tokens else []
        word_ids: list[int | None] = [None] if add_special_tokens else []
        for index, token in enumerate(tokens):
            count = self.pieces(str(token))
            input_ids.extend([index + 1] * count)
            word_ids.extend([index] * count)
        if add_special_tokens:
            input_ids.append(0)
            word_ids.append(None)
        if truncation and max_length is not None:
            input_ids = input_ids[:max_length]
            word_ids = word_ids[:max_length]
        return Encoding(input_ids, word_ids)


def test_fixed_word_windows_are_deterministic() -> None:
    rows = [{"tokens": ["a", "b", "c", "d", "e"]}]

    windows = fixed_word_windows(rows, max_words=3, stride_words=1)

    assert windows == [(0, 0, ["a", "b", "c"]), (0, 2, ["c", "d", "e"])]


def test_analyze_split_reports_truncation_and_coverage() -> None:
    rows = [{"tokens": ["long-a", "long-b", "long-c", "long-d"]}]

    report = analyze_split(
        rows,
        FakeTokenizer(),
        max_words=3,
        stride_words=1,
        sequence_lengths=[4, 16],
    )

    assert report["words"] == 4
    assert report["subwords_per_word"]["mean"] == 3
    assert report["windows"]["subwords"]["max"] == 11
    assert report["windows"]["sequence_lengths"]["4"] == {
        "windows_over_limit": 2,
        "truncated_windows": 2,
        "documents_with_uncovered_words": 1,
        "uncovered_words": 2,
    }
    assert report["windows"]["sequence_lengths"]["16"]["uncovered_words"] == 0


def test_parse_split() -> None:
    assert parse_split("train=data/train.jsonl") == ("train", Path("data/train.jsonl"))
