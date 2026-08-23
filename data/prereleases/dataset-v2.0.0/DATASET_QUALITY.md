# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0/best`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 2,115 | 2,464 | - | - | - |
| validation | 464 | 525 | 0.895 | 0.811 | 0.851 |
| test | 441 | 594 | 0.897 | 0.763 | 0.824 |

## Entity Coverage

Entity coverage assesses whether labels in the test split have enough gold occurrences to support both training and evaluation. Validation does not contribute to coverage. Overall coverage is the weaker of train and test coverage.

| Overall coverage | Labels |
|---|---:|
| adequate | 5 |
| limited | 28 |
| insufficient | 16 |

| Entity label | Train occurrences | Train coverage | Test occurrences | Test coverage | Overall coverage |
|---|---:|---|---:|---|---|
| `org.ent.pressagency.afp` | 280 | adequate | 35 | adequate | **adequate** |
| `org.ent.pressagency.agence-radio` | 16 | limited | 10 | limited | **limited** |
| `org.ent.pressagency.akp` | 0 | insufficient | 11 | limited | **insufficient** |
| `org.ent.pressagency.ansa` | 22 | adequate | 9 | insufficient | **insufficient** |
| `org.ent.pressagency.ap` | 85 | adequate | 14 | limited | **limited** |
| `org.ent.pressagency.apa` | 29 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.ata` | 24 | adequate | 4 | insufficient | **insufficient** |
| `org.ent.pressagency.ats-sda` | 268 | adequate | 37 | adequate | **adequate** |
| `org.ent.pressagency.belga` | 23 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.cip` | 10 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.ctk` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.ddp-dapd` | 19 | limited | 10 | limited | **limited** |
| `org.ent.pressagency.dnb` | 29 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.domei` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.dpa` | 69 | adequate | 12 | limited | **limited** |
| `org.ent.pressagency.europapress` | 20 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.extel` | 30 | adequate | 7 | insufficient | **insufficient** |
| `org.ent.pressagency.havas` | 334 | adequate | 50 | adequate | **adequate** |
| `org.ent.pressagency.keystone` | 11 | limited | 11 | limited | **limited** |
| `org.ent.pressagency.kipa` | 34 | adequate | 11 | limited | **limited** |
| `org.ent.pressagency.kyodo` | 0 | insufficient | 10 | limited | **insufficient** |
| `org.ent.pressagency.palach-press` | 10 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.reuters` | 290 | adequate | 51 | adequate | **adequate** |
| `org.ent.pressagency.spk-smp` | 36 | adequate | 11 | limited | **limited** |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | limited | 3 | insufficient | **insufficient** |
| `org.ent.pressagency.stefani` | 23 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.tanjug` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.tass` | 20 | adequate | 10 | limited | **limited** |
| `org.ent.pressagency.telegraphen-union` | 17 | limited | 9 | insufficient | **insufficient** |
| `org.ent.pressagency.up-upi` | 119 | adequate | 23 | adequate | **adequate** |
| `org.ent.pressagency.wolff` | 63 | adequate | 14 | limited | **limited** |
| `org.ent.pressagency.xinhua` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.bbc` | 50 | adequate | 14 | limited | **limited** |
| `org.ent.radiostation.china-radio-international` | 10 | limited | 1 | insufficient | **insufficient** |
| `org.ent.radiostation.deutsche-welle` | 13 | limited | 10 | limited | **limited** |
| `org.ent.radiostation.deutschlandfunk` | 16 | limited | 1 | insufficient | **insufficient** |
| `org.ent.radiostation.kol-yisrael` | 0 | insufficient | 2 | insufficient | **insufficient** |
| `org.ent.radiostation.polskie-radio` | 27 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.radio-bucharest` | 52 | adequate | 9 | insufficient | **insufficient** |
| `org.ent.radiostation.radio-free-europe` | 58 | adequate | 15 | limited | **limited** |
| `org.ent.radiostation.radio-liberty` | 17 | limited | 9 | insufficient | **insufficient** |
| `org.ent.radiostation.radio-moscow` | 38 | adequate | 6 | insufficient | **insufficient** |
| `org.ent.radiostation.radio-paris` | 25 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.radio-prague` | 30 | adequate | 11 | limited | **limited** |
| `org.ent.radiostation.rfi` | 12 | limited | 10 | limited | **limited** |
| `org.ent.radiostation.rtl` | 31 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.rts` | 21 | adequate | 7 | insufficient | **insufficient** |
| `org.ent.radiostation.vatican-radio` | 29 | adequate | 10 | limited | **limited** |
| `org.ent.radiostation.voice-of-america` | 40 | adequate | 11 | limited | **limited** |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 280 | 38 | 0.961 | 35 | 1.000 | 0.914 | 0.955 |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 0.889 | 10 | 0.667 | 0.800 | 0.727 |
| `org.ent.pressagency.akp` | 0 | 10 | 0.000 | 11 | 0.000 | 0.000 | 0.000 |
| `org.ent.pressagency.ansa` | 22 | 9 | 1.000 | 9 | 1.000 | 0.889 | 0.941 |
| `org.ent.pressagency.ap` | 85 | 16 | 0.786 | 14 | 1.000 | 0.857 | 0.923 |
| `org.ent.pressagency.apa` | 29 | 8 | 0.933 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.ata` | 24 | 2 | 0.400 | 4 | 0.750 | 0.750 | 0.750 |
| `org.ent.pressagency.ats-sda` | 268 | 40 | 0.974 | 37 | 1.000 | 0.946 | 0.972 |
| `org.ent.pressagency.belga` | 23 | 11 | 0.900 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.cip` | 10 | 0 | 0.000 | 3 | 0.000 | 0.000 | 0.000 |
| `org.ent.pressagency.ctk` | 25 | 11 | 0.737 | 10 | 0.833 | 1.000 | 0.909 |
| `org.ent.pressagency.ddp-dapd` | 19 | 6 | 0.833 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.dnb` | 29 | 11 | 0.857 | 10 | 1.000 | 0.800 | 0.889 |
| `org.ent.pressagency.domei` | 25 | 10 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.dpa` | 69 | 12 | 1.000 | 12 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.europapress` | 20 | 10 | 1.000 | 10 | 1.000 | 0.900 | 0.947 |
| `org.ent.pressagency.extel` | 30 | 5 | 0.727 | 7 | 0.857 | 0.857 | 0.857 |
| `org.ent.pressagency.havas` | 334 | 33 | 0.954 | 50 | 0.980 | 0.960 | 0.970 |
| `org.ent.pressagency.keystone` | 11 | 12 | 0.700 | 11 | 1.000 | 0.182 | 0.308 |
| `org.ent.pressagency.kipa` | 34 | 11 | 0.800 | 11 | 1.000 | 0.727 | 0.842 |
| `org.ent.pressagency.kyodo` | 0 | 7 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.reuters` | 290 | 45 | 0.932 | 51 | 1.000 | 0.863 | 0.926 |
| `org.ent.pressagency.spk-smp` | 36 | 12 | 0.880 | 11 | 0.750 | 0.818 | 0.783 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | 4 | 0.750 | 3 | 1.000 | 0.333 | 0.500 |
| `org.ent.pressagency.stefani` | 23 | 8 | 0.933 | 10 | 1.000 | 1.000 | 1.000 |
| `org.ent.pressagency.tanjug` | 25 | 10 | 1.000 | 10 | 0.909 | 1.000 | 0.952 |
| `org.ent.pressagency.tass` | 20 | 9 | 0.750 | 10 | 1.000 | 0.700 | 0.824 |
| `org.ent.pressagency.telegraphen-union` | 17 | 12 | 0.615 | 9 | 0.300 | 0.333 | 0.316 |
| `org.ent.pressagency.up-upi` | 119 | 11 | 0.909 | 23 | 1.000 | 0.783 | 0.878 |
| `org.ent.pressagency.wolff` | 63 | 11 | 0.900 | 14 | 0.889 | 0.571 | 0.696 |
| `org.ent.pressagency.xinhua` | 25 | 10 | 0.952 | 10 | 0.778 | 0.700 | 0.737 |
| `org.ent.radiostation.bbc` | 50 | 12 | 0.700 | 14 | 0.778 | 0.500 | 0.609 |
| `org.ent.radiostation.china-radio-international` | 10 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.deutsche-welle` | 13 | 9 | 0.947 | 10 | 0.889 | 0.800 | 0.842 |
| `org.ent.radiostation.deutschlandfunk` | 16 | 1 | 0.000 | 1 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 0.000 | 2 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 0.700 | 10 | 1.000 | 0.600 | 0.750 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 0.727 | 0.889 | 0.800 |
| `org.ent.radiostation.radio-free-europe` | 58 | 10 | 0.857 | 15 | 0.938 | 1.000 | 0.968 |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 0.778 | 9 | 0.583 | 0.778 | 0.667 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 6 | 0.714 | 0.833 | 0.769 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 0.842 | 10 | 0.500 | 0.500 | 0.500 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 0.909 | 11 | 0.750 | 0.545 | 0.632 |
| `org.ent.radiostation.rfi` | 12 | 10 | 0.000 | 10 | 0.000 | 0.000 | 0.000 |
| `org.ent.radiostation.rtl` | 31 | 9 | 0.889 | 10 | 1.000 | 0.600 | 0.750 |
| `org.ent.radiostation.rts` | 21 | 5 | 0.444 | 7 | 0.714 | 0.714 | 0.714 |
| `org.ent.radiostation.vatican-radio` | 29 | 9 | 0.842 | 10 | 0.727 | 0.800 | 0.762 |
| `org.ent.radiostation.voice-of-america` | 40 | 12 | 0.560 | 11 | 0.750 | 0.818 | 0.783 |
