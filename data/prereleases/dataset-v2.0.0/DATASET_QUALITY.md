# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0-label-all-tokens-4layers/best`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 2,207 | 2,562 | - | - | - |
| validation | 471 | 532 | 0.925 | 0.930 | 0.928 |
| test | 446 | 602 | 0.913 | 0.874 | 0.893 |

## Entity Coverage

Entity coverage assesses whether labels in the test split have enough gold occurrences to support both training and evaluation. Validation does not contribute to coverage. Overall coverage is the weaker of train and test coverage.

| Overall coverage | Labels |
|---|---:|
| adequate | 5 |
| limited | 29 |
| insufficient | 15 |

| Entity label | Train occurrences | Train coverage | Test occurrences | Test coverage | Overall coverage |
|---|---:|---|---:|---|---|
| `org.ent.pressagency.afp` | 287 | adequate | 35 | adequate | **adequate** |
| `org.ent.pressagency.agence-radio` | 16 | limited | 10 | limited | **limited** |
| `org.ent.pressagency.akp` | 8 | insufficient | 12 | limited | **insufficient** |
| `org.ent.pressagency.ansa` | 22 | adequate | 9 | insufficient | **insufficient** |
| `org.ent.pressagency.ap` | 87 | adequate | 15 | limited | **limited** |
| `org.ent.pressagency.apa` | 29 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.ata` | 24 | adequate | 4 | insufficient | **insufficient** |
| `org.ent.pressagency.ats-sda` | 272 | adequate | 37 | adequate | **adequate** |
| `org.ent.pressagency.belga` | 23 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.cip` | 10 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.ctk` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.ddp-dapd` | 19 | limited | 10 | limited | **limited** |
| `org.ent.pressagency.dnb` | 29 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.domei` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.dpa` | 76 | adequate | 12 | limited | **limited** |
| `org.ent.pressagency.europapress` | 20 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.extel` | 30 | adequate | 7 | insufficient | **insufficient** |
| `org.ent.pressagency.havas` | 334 | adequate | 50 | adequate | **adequate** |
| `org.ent.pressagency.keystone` | 11 | limited | 11 | limited | **limited** |
| `org.ent.pressagency.kipa` | 34 | adequate | 11 | limited | **limited** |
| `org.ent.pressagency.kyodo` | 20 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.palach-press` | 10 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.reuters` | 293 | adequate | 52 | adequate | **adequate** |
| `org.ent.pressagency.spk-smp` | 44 | adequate | 11 | limited | **limited** |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.stefani` | 23 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.tanjug` | 26 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.tass` | 28 | adequate | 13 | limited | **limited** |
| `org.ent.pressagency.telegraphen-union` | 17 | limited | 9 | insufficient | **insufficient** |
| `org.ent.pressagency.up-upi` | 120 | adequate | 23 | adequate | **adequate** |
| `org.ent.pressagency.wolff` | 63 | adequate | 14 | limited | **limited** |
| `org.ent.pressagency.xinhua` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.bbc` | 51 | adequate | 14 | limited | **limited** |
| `org.ent.radiostation.china-radio-international` | 10 | limited | 1 | insufficient | **insufficient** |
| `org.ent.radiostation.deutsche-welle` | 13 | limited | 10 | limited | **limited** |
| `org.ent.radiostation.deutschlandfunk` | 16 | limited | 1 | insufficient | **insufficient** |
| `org.ent.radiostation.kol-yisrael` | 21 | adequate | 2 | insufficient | **insufficient** |
| `org.ent.radiostation.polskie-radio` | 27 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.radio-bucharest` | 52 | adequate | 9 | insufficient | **insufficient** |
| `org.ent.radiostation.radio-free-europe` | 58 | adequate | 15 | limited | **limited** |
| `org.ent.radiostation.radio-liberty` | 17 | limited | 9 | insufficient | **insufficient** |
| `org.ent.radiostation.radio-moscow` | 38 | adequate | 7 | insufficient | **insufficient** |
| `org.ent.radiostation.radio-paris` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.radio-prague` | 30 | adequate | 11 | limited | **limited** |
| `org.ent.radiostation.rfi` | 19 | limited | 10 | limited | **limited** |
| `org.ent.radiostation.rtl` | 31 | adequate | 11 | limited | **limited** |
| `org.ent.radiostation.rts` | 21 | adequate | 7 | insufficient | **insufficient** |
| `org.ent.radiostation.vatican-radio` | 29 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.voice-of-america` | 40 | adequate | 11 | limited | **limited** |

## Test Entity Prediction Outcomes

This summarizes every test gold entity plus unmatched extra predictions. The detailed TSV is intended for filtering, sorting, and manual inspection.

Detailed TSV: `reports.d/test-entity-predictions.tsv`

| Outcome | Instances |
|---|---:|
| correct | 526 |
| wrong_label | 3 |
| span_mismatch | 13 |
| wrong_label_and_span | 4 |
| complex_overlap | 7 |
| missed | 49 |
| extra | 16 |

## Test Prediction Outcomes by Gold Label

| Entity label | Gold rows | Correct | Wrong label | Span mismatch | Wrong label + span | Complex overlap | Missed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 35 | 33 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.agence-radio` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.akp` | 12 | 12 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ansa` | 9 | 8 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.ap` | 15 | 14 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.apa` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ata` | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ats-sda` | 37 | 37 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.belga` | 10 | 8 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.cip` | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ctk` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ddp-dapd` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.dnb` | 10 | 8 | 0 | 1 | 0 | 0 | 1 |
| `org.ent.pressagency.domei` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.dpa` | 12 | 12 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.europapress` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.extel` | 7 | 6 | 0 | 0 | 1 | 0 | 0 |
| `org.ent.pressagency.havas` | 50 | 48 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.keystone` | 11 | 9 | 0 | 1 | 0 | 0 | 1 |
| `org.ent.pressagency.kipa` | 11 | 8 | 0 | 0 | 0 | 1 | 2 |
| `org.ent.pressagency.kyodo` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.palach-press` | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.reuters` | 52 | 48 | 1 | 0 | 0 | 0 | 3 |
| `org.ent.pressagency.spk-smp` | 11 | 8 | 1 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 3 | 1 | 0 | 0 | 1 | 1 | 0 |
| `org.ent.pressagency.stefani` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.tanjug` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.tass` | 13 | 12 | 1 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.telegraphen-union` | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.up-upi` | 23 | 18 | 0 | 1 | 0 | 0 | 4 |
| `org.ent.pressagency.wolff` | 14 | 8 | 0 | 0 | 0 | 0 | 6 |
| `org.ent.pressagency.xinhua` | 10 | 9 | 0 | 1 | 0 | 0 | 0 |
| `org.ent.radiostation.bbc` | 14 | 8 | 0 | 1 | 0 | 1 | 4 |
| `org.ent.radiostation.china-radio-international` | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.deutsche-welle` | 10 | 9 | 0 | 0 | 1 | 0 | 0 |
| `org.ent.radiostation.deutschlandfunk` | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.kol-yisrael` | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.radiostation.polskie-radio` | 10 | 6 | 0 | 1 | 1 | 1 | 1 |
| `org.ent.radiostation.radio-bucharest` | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.radiostation.radio-free-europe` | 15 | 14 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.radio-liberty` | 9 | 8 | 0 | 0 | 0 | 1 | 0 |
| `org.ent.radiostation.radio-moscow` | 7 | 6 | 0 | 1 | 0 | 0 | 0 |
| `org.ent.radiostation.radio-paris` | 10 | 7 | 0 | 2 | 0 | 0 | 1 |
| `org.ent.radiostation.radio-prague` | 11 | 9 | 0 | 2 | 0 | 0 | 0 |
| `org.ent.radiostation.rfi` | 10 | 5 | 0 | 0 | 0 | 0 | 5 |
| `org.ent.radiostation.rtl` | 11 | 8 | 0 | 0 | 0 | 0 | 3 |
| `org.ent.radiostation.rts` | 7 | 5 | 0 | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.vatican-radio` | 10 | 8 | 0 | 1 | 0 | 1 | 0 |
| `org.ent.radiostation.voice-of-america` | 11 | 10 | 0 | 1 | 0 | 0 | 0 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 287 | 38 | 0.974 | 35 | 1.000 | 0.943 | 0.971 |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 0.857 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.akp` | 8 | 10 | 1.000 | 12 | 0.857 | 1.000 | 0.923 |
| `org.ent.pressagency.ansa` | 22 | 9 | 0.941 | 9 | 1.000 | 0.889 | 0.941 |
| `org.ent.pressagency.ap` | 87 | 16 | 0.897 | 15 | 0.875 | 0.933 | 0.903 |
| `org.ent.pressagency.apa` | 29 | 8 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ata` | 24 | 2 | 0.667 | 4 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ats-sda` | 272 | 40 | 0.963 | 37 | 0.949 | 1.000 | 0.974 |
| `org.ent.pressagency.belga` | 23 | 11 | 0.900 | 10 | 1.000 | 0.800 | 0.889 |
| `org.ent.pressagency.cip` | 10 | 0 | 0.000 | 3 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ctk` | 25 | 11 | 0.952 | 10 | 0.909 | 1.000 | 0.952 |
| `org.ent.pressagency.ddp-dapd` | 19 | 6 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.dnb` | 29 | 11 | 0.900 | 10 | 0.889 | 0.800 | 0.842 |
| `org.ent.pressagency.domei` | 25 | 10 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.dpa` | 76 | 12 | 0.923 | 12 | 0.857 | 1.000 | 0.923 |
| `org.ent.pressagency.europapress` | 20 | 10 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.extel` | 30 | 5 | 0.571 | 7 | 0.750 | 0.857 | 0.800 |
| `org.ent.pressagency.havas` | 334 | 33 | 0.969 | 50 | 0.980 | 0.960 | 0.970 |
| `org.ent.pressagency.keystone` | 11 | 12 | 0.714 | 11 | 0.692 | 0.818 | 0.750 |
| `org.ent.pressagency.kipa` | 34 | 11 | 0.870 | 11 | 0.800 | 0.727 | 0.762 |
| `org.ent.pressagency.kyodo` | 20 | 7 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.reuters` | 293 | 46 | 0.957 | 52 | 1.000 | 0.923 | 0.960 |
| `org.ent.pressagency.spk-smp` | 44 | 12 | 0.880 | 11 | 1.000 | 0.727 | 0.842 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | 4 | 0.750 | 3 | 0.500 | 0.333 | 0.400 |
| `org.ent.pressagency.stefani` | 23 | 8 | 0.933 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.tanjug` | 26 | 10 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.tass` | 28 | 10 | 0.778 | 13 | 0.923 | 0.923 | 0.923 |
| `org.ent.pressagency.telegraphen-union` | 17 | 12 | 1.000 | 9 | 0.900 | 1.000 | 0.947 |
| `org.ent.pressagency.up-upi` | 120 | 11 | 1.000 | 23 | 0.947 | 0.783 | 0.857 |
| `org.ent.pressagency.wolff` | 63 | 11 | 0.952 | 14 | 0.889 | 0.571 | 0.696 |
| `org.ent.pressagency.xinhua` | 25 | 10 | 0.870 | 10 | 0.900 | 0.900 | 0.900 |
| `org.ent.radiostation.bbc` | 51 | 14 | 0.833 | 14 | 0.667 | 0.571 | 0.615 |
| `org.ent.radiostation.china-radio-international` | 10 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.deutsche-welle` | 13 | 10 | 0.952 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.radiostation.deutschlandfunk` | 16 | 2 | 0.667 | 1 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.kol-yisrael` | 21 | 0 | 0.000 | 2 | 1.000 | 1.000 | 1.000 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 0.900 | 10 | 0.750 | 0.600 | 0.667 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 1.000 | 1.000 | 1.000 |
| `org.ent.radiostation.radio-free-europe` | 58 | 10 | 1.000 | 15 | 0.824 | 0.933 | 0.875 |
| `org.ent.radiostation.radio-liberty` | 17 | 11 | 0.957 | 9 | 0.800 | 0.889 | 0.842 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 0.889 | 7 | 0.750 | 0.857 | 0.800 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 0.941 | 10 | 0.778 | 0.700 | 0.737 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 0.909 | 11 | 0.818 | 0.818 | 0.818 |
| `org.ent.radiostation.rfi` | 19 | 11 | 0.952 | 10 | 1.000 | 0.500 | 0.667 |
| `org.ent.radiostation.rtl` | 31 | 9 | 0.941 | 11 | 1.000 | 0.727 | 0.842 |
| `org.ent.radiostation.rts` | 21 | 5 | 0.800 | 7 | 0.714 | 0.714 | 0.714 |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 1.000 | 10 | 0.727 | 0.800 | 0.762 |
| `org.ent.radiostation.voice-of-america` | 40 | 12 | 0.880 | 11 | 0.769 | 0.909 | 0.833 |
