# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 1,962 | 2,318 | - | - | - |
| validation | 292 | 324 | 0.829 | 0.806 | 0.817 |
| test | 300 | 392 | 0.827 | 0.778 | 0.802 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 276 | 29 | 1.000 | 28 | 1.000 | 0.929 | 0.963 | adequate |
| `org.ent.pressagency.agence-radio` | 16 | 5 | 1.000 | 5 | 0.833 | 1.000 | 0.909 | insufficient |
| `org.ent.pressagency.akp` | 0 | 1 | 0.000 | 5 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ansa` | 21 | 5 | 0.750 | 5 | 0.750 | 0.600 | 0.667 | insufficient |
| `org.ent.pressagency.ap` | 83 | 14 | 0.615 | 14 | 0.917 | 0.786 | 0.846 | limited |
| `org.ent.pressagency.apa` | 17 | 3 | 0.500 | 5 | 0.667 | 0.400 | 0.500 | insufficient |
| `org.ent.pressagency.ata` | 24 | 2 | 1.000 | 4 | 0.400 | 0.500 | 0.444 | insufficient |
| `org.ent.pressagency.ats-sda` | 251 | 32 | 1.000 | 28 | 0.964 | 0.964 | 0.964 | adequate |
| `org.ent.pressagency.belga` | 22 | 5 | 0.750 | 5 | 1.000 | 0.800 | 0.889 | insufficient |
| `org.ent.pressagency.cip` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ctk` | 25 | 4 | 0.000 | 5 | 0.182 | 0.400 | 0.250 | insufficient |
| `org.ent.pressagency.ddp-dapd` | 19 | 4 | 0.333 | 5 | 1.000 | 0.800 | 0.889 | insufficient |
| `org.ent.pressagency.dnb` | 27 | 6 | 0.727 | 7 | 0.556 | 0.714 | 0.625 | insufficient |
| `org.ent.pressagency.domei` | 26 | 5 | 0.800 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.dpa` | 56 | 5 | 0.800 | 5 | 0.500 | 0.800 | 0.615 | insufficient |
| `org.ent.pressagency.europapress` | 19 | 5 | 0.800 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.extel` | 29 | 5 | 0.571 | 5 | 1.000 | 0.800 | 0.889 | insufficient |
| `org.ent.pressagency.havas` | 333 | 31 | 0.852 | 50 | 0.933 | 0.840 | 0.884 | adequate |
| `org.ent.pressagency.keystone` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.kipa` | 21 | 5 | 0.667 | 6 | 0.333 | 0.167 | 0.222 | insufficient |
| `org.ent.pressagency.palach-press` | 10 | 1 | 0.000 | 3 | 0.500 | 0.667 | 0.571 | insufficient |
| `org.ent.pressagency.reuters` | 284 | 35 | 0.971 | 42 | 0.974 | 0.881 | 0.925 | adequate |
| `org.ent.pressagency.spk-smp` | 32 | 6 | 0.833 | 5 | 0.375 | 0.600 | 0.462 | insufficient |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 0.857 | 2 | 1.000 | 0.500 | 0.667 | insufficient |
| `org.ent.pressagency.stefani` | 23 | 4 | 1.000 | 5 | 0.833 | 1.000 | 0.909 | insufficient |
| `org.ent.pressagency.tanjug` | 24 | 5 | 0.833 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.tass` | 25 | 5 | 0.400 | 6 | 1.000 | 0.667 | 0.800 | insufficient |
| `org.ent.pressagency.telegraphen-union` | 18 | 5 | 0.167 | 5 | 0.750 | 0.600 | 0.667 | insufficient |
| `org.ent.pressagency.up-upi` | 117 | 10 | 0.900 | 22 | 0.947 | 0.818 | 0.878 | adequate |
| `org.ent.pressagency.wolff` | 62 | 5 | 0.800 | 11 | 0.778 | 0.636 | 0.700 | limited |
| `org.ent.pressagency.xinhua` | 25 | 5 | 0.400 | 7 | 0.333 | 0.286 | 0.308 | insufficient |
| `org.ent.radiostation.bbc` | 48 | 8 | 0.533 | 9 | 0.600 | 0.333 | 0.429 | insufficient |
| `org.ent.radiostation.deutsche-welle` | 14 | 5 | 0.909 | 6 | 0.750 | 1.000 | 0.857 | insufficient |
| `org.ent.radiostation.polskie-radio` | 27 | 7 | 0.857 | 6 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 1.000 | 0.889 | 0.941 | insufficient |
| `org.ent.radiostation.radio-free-europe` | 55 | 6 | 0.923 | 8 | 0.800 | 1.000 | 0.889 | insufficient |
| `org.ent.radiostation.radio-liberty` | 16 | 6 | 0.769 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-paris` | 25 | 5 | 0.909 | 5 | 1.000 | 0.800 | 0.889 | insufficient |
| `org.ent.radiostation.radio-prague` | 30 | 5 | 0.889 | 5 | 0.600 | 0.600 | 0.600 | insufficient |
| `org.ent.radiostation.rfi` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.rtl` | 30 | 6 | 1.000 | 6 | 0.833 | 0.833 | 0.833 | insufficient |
| `org.ent.radiostation.rts` | 21 | 5 | 0.400 | 6 | 0.600 | 0.500 | 0.545 | insufficient |
| `org.ent.radiostation.vatican-radio` | 29 | 5 | 0.909 | 6 | 0.714 | 0.833 | 0.769 | insufficient |
| `org.ent.radiostation.voice-of-america` | 35 | 5 | 0.727 | 8 | 0.889 | 1.000 | 0.941 | insufficient |
