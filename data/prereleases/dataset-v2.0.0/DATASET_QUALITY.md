# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 1,954 | 2,303 | - | - | - |
| validation | 278 | 302 | 0.851 | 0.811 | 0.831 |
| test | 286 | 364 | 0.805 | 0.794 | 0.799 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 275 | 29 | 1.000 | 28 | 0.867 | 0.929 | 0.897 | adequate |
| `org.ent.pressagency.agence-radio` | 16 | 5 | 1.000 | 5 | 0.833 | 1.000 | 0.909 | insufficient |
| `org.ent.pressagency.akp` | 0 | 1 | 0.000 | 5 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ansa` | 21 | 5 | 0.571 | 5 | 0.750 | 0.600 | 0.667 | insufficient |
| `org.ent.pressagency.ap` | 81 | 14 | 0.692 | 14 | 1.000 | 0.929 | 0.963 | limited |
| `org.ent.pressagency.apa` | 17 | 3 | 0.500 | 5 | 0.500 | 0.400 | 0.444 | insufficient |
| `org.ent.pressagency.ata` | 24 | 2 | 0.800 | 4 | 0.200 | 0.250 | 0.222 | insufficient |
| `org.ent.pressagency.ats-sda` | 250 | 31 | 1.000 | 28 | 0.966 | 1.000 | 0.982 | adequate |
| `org.ent.pressagency.belga` | 22 | 5 | 0.571 | 5 | 1.000 | 0.600 | 0.750 | insufficient |
| `org.ent.pressagency.ctk` | 25 | 4 | 0.250 | 5 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ddp-dapd` | 19 | 4 | 0.400 | 5 | 0.667 | 0.400 | 0.500 | insufficient |
| `org.ent.pressagency.dnb` | 27 | 6 | 0.727 | 7 | 0.857 | 0.857 | 0.857 | insufficient |
| `org.ent.pressagency.domei` | 26 | 5 | 0.800 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.dpa` | 55 | 5 | 0.667 | 5 | 0.571 | 0.800 | 0.667 | insufficient |
| `org.ent.pressagency.europapress` | 19 | 5 | 0.727 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.extel` | 29 | 5 | 0.571 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.havas` | 333 | 31 | 0.933 | 50 | 0.878 | 0.860 | 0.869 | adequate |
| `org.ent.pressagency.kipa` | 21 | 5 | 0.600 | 6 | 0.500 | 0.167 | 0.250 | insufficient |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 0.500 | 0.667 | 0.571 | insufficient |
| `org.ent.pressagency.reuters` | 283 | 33 | 0.954 | 41 | 0.923 | 0.878 | 0.900 | adequate |
| `org.ent.pressagency.spk-smp` | 32 | 6 | 0.833 | 5 | 0.667 | 0.400 | 0.500 | insufficient |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 0.667 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.stefani` | 23 | 4 | 0.857 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.tanjug` | 24 | 5 | 0.462 | 5 | 0.500 | 0.800 | 0.615 | insufficient |
| `org.ent.pressagency.tass` | 25 | 5 | 0.364 | 6 | 0.800 | 0.667 | 0.727 | insufficient |
| `org.ent.pressagency.telegraphen-union` | 18 | 5 | 0.400 | 5 | 0.750 | 0.600 | 0.667 | insufficient |
| `org.ent.pressagency.up-upi` | 117 | 10 | 0.952 | 21 | 0.944 | 0.810 | 0.872 | adequate |
| `org.ent.pressagency.wolff` | 62 | 5 | 0.444 | 11 | 0.900 | 0.818 | 0.857 | limited |
| `org.ent.pressagency.xinhua` | 25 | 5 | 0.545 | 7 | 0.300 | 0.429 | 0.353 | insufficient |
| `org.ent.radiostation.bbc` | 45 | 3 | 1.000 | 2 | 0.250 | 0.500 | 0.333 | insufficient |
| `org.ent.radiostation.deutsche-welle` | 14 | 3 | 1.000 | 4 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.polskie-radio` | 27 | 7 | 0.857 | 6 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 0.889 | 0.889 | 0.889 | insufficient |
| `org.ent.radiostation.radio-free-europe` | 54 | 6 | 1.000 | 6 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-liberty` | 15 | 6 | 1.000 | 2 | 1.000 | 0.500 | 0.667 | insufficient |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-paris` | 24 | 2 | 1.000 | 2 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-prague` | 30 | 3 | 0.800 | 2 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.rtl` | 29 | 4 | 1.000 | 6 | 0.800 | 0.667 | 0.727 | insufficient |
| `org.ent.radiostation.rts` | 21 | 4 | 0.222 | 4 | 0.600 | 0.750 | 0.667 | insufficient |
| `org.ent.radiostation.vatican-radio` | 29 | 5 | 0.909 | 6 | 0.625 | 0.833 | 0.714 | insufficient |
| `org.ent.radiostation.voice-of-america` | 33 | 1 | 1.000 | 7 | 0.875 | 1.000 | 0.933 | insufficient |
