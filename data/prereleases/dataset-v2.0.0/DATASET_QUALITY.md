# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 50 gold mentions; **limited** = 20-49; **insufficient** = fewer than 20.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 1,938 | 2,281 | - | - | - |
| validation | 245 | 265 | 0.882 | 0.845 | 0.863 |
| test | 260 | 331 | 0.828 | 0.816 | 0.822 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 275 | 29 | 1.000 | 26 | 0.889 | 0.923 | 0.906 | limited |
| `org.ent.pressagency.agence-radio` | 16 | 3 | 1.000 | 5 | 0.833 | 1.000 | 0.909 | insufficient |
| `org.ent.pressagency.ansa` | 21 | 3 | 0.500 | 3 | 0.500 | 0.333 | 0.400 | insufficient |
| `org.ent.pressagency.ap` | 80 | 14 | 0.720 | 13 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.apa` | 17 | 2 | 0.667 | 5 | 0.500 | 0.400 | 0.444 | insufficient |
| `org.ent.pressagency.ata` | 24 | 2 | 0.800 | 3 | 0.250 | 0.333 | 0.286 | insufficient |
| `org.ent.pressagency.ats-sda` | 248 | 30 | 1.000 | 28 | 0.966 | 1.000 | 0.982 | limited |
| `org.ent.pressagency.belga` | 21 | 4 | 0.400 | 3 | 1.000 | 0.667 | 0.800 | insufficient |
| `org.ent.pressagency.ctk` | 25 | 3 | 0.333 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ddp-dapd` | 19 | 3 | 0.500 | 3 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.dnb` | 27 | 5 | 0.889 | 7 | 0.857 | 0.857 | 0.857 | insufficient |
| `org.ent.pressagency.domei` | 26 | 4 | 1.000 | 4 | 0.750 | 0.750 | 0.750 | insufficient |
| `org.ent.pressagency.dpa` | 51 | 3 | 0.500 | 5 | 0.571 | 0.800 | 0.667 | insufficient |
| `org.ent.pressagency.europapress` | 19 | 3 | 0.571 | 3 | 0.667 | 0.667 | 0.667 | insufficient |
| `org.ent.pressagency.extel` | 27 | 3 | 0.800 | 4 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.havas` | 333 | 31 | 0.933 | 49 | 0.875 | 0.857 | 0.866 | limited |
| `org.ent.pressagency.kipa` | 20 | 1 | 0.000 | 6 | 0.500 | 0.167 | 0.250 | insufficient |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 0.500 | 0.667 | 0.571 | insufficient |
| `org.ent.pressagency.reuters` | 282 | 33 | 0.954 | 41 | 0.923 | 0.878 | 0.900 | limited |
| `org.ent.pressagency.spk-smp` | 26 | 1 | 0.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 0.667 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.stefani` | 23 | 1 | 1.000 | 4 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.tanjug` | 23 | 5 | 0.462 | 4 | 0.667 | 1.000 | 0.800 | insufficient |
| `org.ent.pressagency.tass` | 25 | 5 | 0.400 | 6 | 0.800 | 0.667 | 0.727 | insufficient |
| `org.ent.pressagency.telegraphen-union` | 18 | 2 | 1.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.up-upi` | 117 | 10 | 0.952 | 20 | 0.941 | 0.800 | 0.865 | limited |
| `org.ent.pressagency.wolff` | 60 | 4 | 0.571 | 11 | 0.900 | 0.818 | 0.857 | insufficient |
| `org.ent.pressagency.xinhua` | 24 | 2 | 0.667 | 7 | 0.333 | 0.429 | 0.375 | insufficient |
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
