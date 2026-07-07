# Subtoken Training Strategy Comparison

## Decision

Use strategy B for v2 training:

```make
LABEL_ALL_TOKENS = true
```

Strategy B supervises all model subtokens. The first subtoken keeps its annotation-token BIO label, while continuation subtokens convert `B-X` to `I-X`. Inference remains unchanged: predictions are decoded from the first model subtoken for each annotation token.

## Compared Runs

Both runs used:

- dataset tokenization `unicode-word-punctuation-v1`;
- the same v2 train, validation, and test splits;
- seed 42;
- three unfrozen encoder layers;
- maximum 20 epochs with early-stopping patience 2;
- first-subtoken inference decoding.

| Strategy | Model directory | Training supervision | Best epoch |
| --- | --- | --- | ---: |
| A | `models.d/newsagency_radiostation_modernbert_v2.0.0/best` | first subtoken; continuation subtokens `-100` | 8 |
| B | `models.d/newsagency_radiostation_modernbert_v2.0.0-label-all-tokens/best` | all subtokens; continuation `B-X` becomes `I-X` | 6 |

## Validation Results

| Strategy | Correct | Gold | Predicted | Precision | Recall | Entity F1 | Token non-O F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 303 | 375 | 372 | 0.8145 | 0.8080 | 0.8112 | 0.8543 |
| B | 305 | 375 | 361 | **0.8449** | **0.8133** | **0.8288** | **0.8560** |

Strategy B improved entity F1 by 0.0176. Its main advantage was higher precision, while recall also increased slightly.

## Test Results

| Strategy | Correct | Gold | Predicted | Precision | Recall | Entity F1 | Token non-O F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 340 | 465 | 435 | 0.7816 | 0.7312 | 0.7556 | 0.7970 |
| B | 346 | 465 | 425 | **0.8141** | **0.7441** | **0.7775** | **0.8056** |

On test, strategy B improved entity F1 by 0.0220. Relative to A, it produced:

- 6 more correct entities;
- 16 fewer false positives, from 95 to 79;
- 6 fewer false negatives, from 125 to 119.

At document level, B had more correct entities in 17 documents, A in 9, and 314 documents tied. A paired document bootstrap placed the approximate 95% interval for the B-minus-A F1 difference at `-0.0047` to `0.0481`; B was better in approximately 95% of bootstrap samples.

## Per-Label Observations

The largest observed B improvements included Vatican Radio, DDP/DAPD, DNB, Domei, AP, BBC, Radio Free Europe, and Havas. Regressions included Agence Radio, RTL, Tanjug, CTK, AFP, and Radio Prague.

Most individual test buckets contain only 5-10 mentions. These per-label changes are therefore diagnostic signals, not reliable standalone model-selection evidence.

## Conclusion

Strategy B improved both validation and held-out test entity F1. In both splits, the main gain came from reduced overprediction without sacrificing recall. This consistent result supports using all-subtoken supervision as the v2 default while retaining first-subtoken decoding for inference.
