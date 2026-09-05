# Validation and Test Quality: v2.1.0

Model: `hf.d/model-v2.0.0`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 2,339 | 2,630 | - | - | - |
| validation | 483 | 545 | 0.940 | 0.917 | 0.929 |
| test | 458 | 612 | 0.935 | 0.864 | 0.898 |

## Entity Coverage

Entity coverage assesses whether labels in the test split have enough gold occurrences to support both training and evaluation. Validation does not contribute to coverage. Overall coverage is the weaker of train and test coverage.

| Overall coverage | Labels |
|---|---:|
| adequate | 5 |
| limited | 29 |
| insufficient | 15 |

| Entity label | Train occurrences | Train coverage | Test occurrences | Test coverage | Overall coverage |
|---|---:|---|---:|---|---|
| `org.ent.pressagency.afp` | 290 | adequate | 35 | adequate | **adequate** |
| `org.ent.pressagency.agence-radio` | 15 | limited | 10 | limited | **limited** |
| `org.ent.pressagency.akp` | 8 | insufficient | 14 | limited | **insufficient** |
| `org.ent.pressagency.ansa` | 22 | adequate | 9 | insufficient | **insufficient** |
| `org.ent.pressagency.ap` | 104 | adequate | 16 | limited | **limited** |
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
| `org.ent.pressagency.extel` | 33 | adequate | 7 | insufficient | **insufficient** |
| `org.ent.pressagency.havas` | 343 | adequate | 50 | adequate | **adequate** |
| `org.ent.pressagency.keystone` | 13 | limited | 11 | limited | **limited** |
| `org.ent.pressagency.kipa` | 34 | adequate | 11 | limited | **limited** |
| `org.ent.pressagency.kyodo` | 20 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.palach-press` | 10 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.reuters` | 319 | adequate | 52 | adequate | **adequate** |
| `org.ent.pressagency.spk-smp` | 44 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 8 | insufficient | 2 | insufficient | **insufficient** |
| `org.ent.pressagency.stefani` | 24 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.tanjug` | 26 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.tass` | 32 | adequate | 13 | limited | **limited** |
| `org.ent.pressagency.telegraphen-union` | 17 | limited | 9 | insufficient | **insufficient** |
| `org.ent.pressagency.up-upi` | 120 | adequate | 23 | adequate | **adequate** |
| `org.ent.pressagency.wolff` | 73 | adequate | 14 | limited | **limited** |
| `org.ent.pressagency.xinhua` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.bbc` | 51 | adequate | 14 | limited | **limited** |
| `org.ent.radiostation.china-radio-international` | 10 | limited | 1 | insufficient | **insufficient** |
| `org.ent.radiostation.deutsche-welle` | 13 | limited | 9 | insufficient | **insufficient** |
| `org.ent.radiostation.deutschlandfunk` | 16 | limited | 10 | limited | **limited** |
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
| `org.ent.radiostation.voice-of-america` | 40 | adequate | 12 | limited | **limited** |

## Test Entity Prediction Outcomes

This summarizes every test gold entity plus unmatched extra predictions. The detailed TSV is intended for filtering, sorting, and manual inspection.

Detailed TSV: `reports.d/test-entity-predictions.tsv`

| Outcome | Instances |
|---|---:|
| correct | 529 |
| wrong_label | 1 |
| span_mismatch | 12 |
| wrong_label_and_span | 3 |
| complex_overlap | 3 |
| missed | 64 |
| extra | 15 |

## Test Prediction Outcomes by Gold Label

| Entity label | Gold rows | Correct | Wrong label | Span mismatch | Wrong label + span | Complex overlap | Missed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 35 | 35 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.agence-radio` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.akp` | 14 | 14 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ansa` | 9 | 8 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.ap` | 16 | 14 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.apa` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ata` | 4 | 3 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.ats-sda` | 37 | 37 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.belga` | 10 | 8 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.cip` | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ctk` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.ddp-dapd` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.dnb` | 10 | 8 | 0 | 1 | 0 | 0 | 1 |
| `org.ent.pressagency.domei` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.dpa` | 12 | 12 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.europapress` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.extel` | 7 | 6 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.havas` | 50 | 49 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.keystone` | 11 | 8 | 0 | 0 | 0 | 0 | 3 |
| `org.ent.pressagency.kipa` | 11 | 8 | 0 | 1 | 0 | 0 | 2 |
| `org.ent.pressagency.kyodo` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.pressagency.palach-press` | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.reuters` | 52 | 45 | 1 | 0 | 0 | 0 | 6 |
| `org.ent.pressagency.spk-smp` | 10 | 8 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 2 | 0 | 0 | 0 | 1 | 1 | 0 |
| `org.ent.pressagency.stefani` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.tanjug` | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.tass` | 13 | 13 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.pressagency.telegraphen-union` | 9 | 6 | 0 | 1 | 1 | 0 | 1 |
| `org.ent.pressagency.up-upi` | 23 | 18 | 0 | 1 | 0 | 0 | 4 |
| `org.ent.pressagency.wolff` | 14 | 8 | 0 | 0 | 0 | 0 | 6 |
| `org.ent.pressagency.xinhua` | 10 | 8 | 0 | 1 | 0 | 0 | 1 |
| `org.ent.radiostation.bbc` | 14 | 8 | 0 | 2 | 0 | 0 | 4 |
| `org.ent.radiostation.china-radio-international` | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.deutsche-welle` | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.radiostation.deutschlandfunk` | 10 | 9 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.kol-yisrael` | 2 | 1 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.polskie-radio` | 10 | 6 | 0 | 1 | 1 | 1 | 1 |
| `org.ent.radiostation.radio-bucharest` | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| `org.ent.radiostation.radio-free-europe` | 15 | 14 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.radio-liberty` | 9 | 8 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.radio-moscow` | 7 | 6 | 0 | 0 | 0 | 0 | 1 |
| `org.ent.radiostation.radio-paris` | 10 | 8 | 0 | 0 | 0 | 0 | 2 |
| `org.ent.radiostation.radio-prague` | 11 | 8 | 0 | 2 | 0 | 0 | 1 |
| `org.ent.radiostation.rfi` | 10 | 5 | 0 | 0 | 0 | 0 | 5 |
| `org.ent.radiostation.rtl` | 11 | 6 | 0 | 0 | 0 | 0 | 5 |
| `org.ent.radiostation.rts` | 7 | 5 | 0 | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.vatican-radio` | 10 | 8 | 0 | 2 | 0 | 0 | 0 |
| `org.ent.radiostation.voice-of-america` | 12 | 11 | 0 | 0 | 0 | 0 | 1 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 290 | 40 | 0.975 | 35 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.agence-radio` | 15 | 9 | 0.947 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.akp` | 8 | 10 | 1.000 | 14 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ansa` | 22 | 9 | 0.941 | 9 | 1.000 | 0.889 | 0.941 |
| `org.ent.pressagency.ap` | 104 | 16 | 0.897 | 16 | 0.933 | 0.875 | 0.903 |
| `org.ent.pressagency.apa` | 29 | 8 | 0.941 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ata` | 24 | 2 | 0.500 | 4 | 0.750 | 0.750 | 0.750 |
| `org.ent.pressagency.ats-sda` | 272 | 41 | 0.976 | 37 | 0.949 | 1.000 | 0.974 |
| `org.ent.pressagency.belga` | 23 | 11 | 0.952 | 10 | 1.000 | 0.800 | 0.889 |
| `org.ent.pressagency.cip` | 10 | 0 | 0.000 | 3 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ctk` | 25 | 11 | 0.952 | 10 | 0.909 | 1.000 | 0.952 |
| `org.ent.pressagency.ddp-dapd` | 19 | 6 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.dnb` | 29 | 12 | 0.857 | 10 | 0.889 | 0.800 | 0.842 |
| `org.ent.pressagency.domei` | 25 | 10 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.dpa` | 76 | 12 | 0.960 | 12 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.europapress` | 20 | 10 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.extel` | 33 | 6 | 0.714 | 7 | 0.857 | 0.857 | 0.857 |
| `org.ent.pressagency.havas` | 343 | 33 | 0.970 | 50 | 0.980 | 0.980 | 0.980 |
| `org.ent.pressagency.keystone` | 13 | 13 | 0.818 | 11 | 1.000 | 0.727 | 0.842 |
| `org.ent.pressagency.kipa` | 34 | 11 | 0.857 | 11 | 0.889 | 0.727 | 0.800 |
| `org.ent.pressagency.kyodo` | 20 | 7 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.reuters` | 319 | 46 | 0.956 | 52 | 1.000 | 0.865 | 0.928 |
| `org.ent.pressagency.spk-smp` | 44 | 12 | 0.880 | 10 | 1.000 | 0.800 | 0.889 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 8 | 2 | 1.000 | 2 | 0.000 | 0.000 | 0.000 |
| `org.ent.pressagency.stefani` | 24 | 8 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.tanjug` | 26 | 10 | 1.000 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.tass` | 32 | 10 | 0.778 | 13 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.telegraphen-union` | 17 | 12 | 0.750 | 9 | 0.600 | 0.667 | 0.632 |
| `org.ent.pressagency.up-upi` | 120 | 11 | 1.000 | 23 | 0.900 | 0.783 | 0.837 |
| `org.ent.pressagency.wolff` | 73 | 11 | 0.900 | 14 | 0.889 | 0.571 | 0.696 |
| `org.ent.pressagency.xinhua` | 25 | 9 | 0.900 | 10 | 0.889 | 0.800 | 0.842 |
| `org.ent.radiostation.bbc` | 51 | 14 | 0.800 | 14 | 0.800 | 0.571 | 0.667 |
| `org.ent.radiostation.china-radio-international` | 10 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.deutsche-welle` | 13 | 10 | 0.909 | 9 | 1.000 | 1.000 | 1.000 |
| `org.ent.radiostation.deutschlandfunk` | 16 | 10 | 0.952 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.radiostation.kol-yisrael` | 21 | 0 | 0.000 | 2 | 1.000 | 0.500 | 0.667 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 0.842 | 10 | 0.750 | 0.600 | 0.667 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 1.000 | 1.000 | 1.000 |
| `org.ent.radiostation.radio-free-europe` | 58 | 11 | 0.909 | 15 | 1.000 | 0.933 | 0.966 |
| `org.ent.radiostation.radio-liberty` | 17 | 11 | 0.909 | 9 | 0.889 | 0.889 | 0.889 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 7 | 0.750 | 0.857 | 0.800 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 1.000 | 10 | 1.000 | 0.800 | 0.889 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 0.909 | 11 | 0.800 | 0.727 | 0.762 |
| `org.ent.radiostation.rfi` | 19 | 11 | 0.909 | 10 | 0.714 | 0.500 | 0.588 |
| `org.ent.radiostation.rtl` | 31 | 9 | 1.000 | 11 | 1.000 | 0.545 | 0.706 |
| `org.ent.radiostation.rts` | 21 | 5 | 0.667 | 7 | 0.455 | 0.714 | 0.556 |
| `org.ent.radiostation.vatican-radio` | 29 | 9 | 1.000 | 10 | 0.800 | 0.800 | 0.800 |
| `org.ent.radiostation.voice-of-america` | 40 | 12 | 0.870 | 12 | 0.917 | 0.917 | 0.917 |
