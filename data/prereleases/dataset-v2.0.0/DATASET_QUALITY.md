# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 50 gold mentions; **limited** = 20-49; **insufficient** = fewer than 20.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| validation | 241 | 260 | 0.884 | 0.854 | 0.869 |
| test | 254 | 321 | 0.841 | 0.826 | 0.833 |

## Quality by Entity

| Entity label | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 29 | 1.000 | 26 | 0.889 | 0.923 | 0.906 | limited |
| `org.ent.pressagency.agence-radio` | 3 | 1.000 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.ansa` | 2 | 0.000 | 3 | 0.500 | 0.333 | 0.400 | insufficient |
| `org.ent.pressagency.ap` | 13 | 0.750 | 13 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.apa` | 2 | 0.667 | 4 | 0.333 | 0.250 | 0.286 | insufficient |
| `org.ent.pressagency.ata` | 2 | 0.800 | 3 | 0.250 | 0.333 | 0.286 | insufficient |
| `org.ent.pressagency.ats-sda` | 30 | 1.000 | 27 | 0.964 | 1.000 | 0.982 | limited |
| `org.ent.pressagency.belga` | 4 | 0.400 | 3 | 1.000 | 0.667 | 0.800 | insufficient |
| `org.ent.pressagency.ctk` | 3 | 0.333 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ddp-dapd` | 3 | 0.500 | 3 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.dnb` | 5 | 0.889 | 7 | 0.857 | 0.857 | 0.857 | insufficient |
| `org.ent.pressagency.domei` | 3 | 1.000 | 4 | 0.750 | 0.750 | 0.750 | insufficient |
| `org.ent.pressagency.dpa` | 3 | 0.500 | 4 | 0.500 | 0.750 | 0.600 | insufficient |
| `org.ent.pressagency.europapress` | 3 | 0.571 | 3 | 0.667 | 0.667 | 0.667 | insufficient |
| `org.ent.pressagency.extel` | 3 | 0.800 | 4 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.havas` | 31 | 0.933 | 49 | 0.875 | 0.857 | 0.866 | limited |
| `org.ent.pressagency.kipa` | 1 | 0.000 | 6 | 0.500 | 0.167 | 0.250 | insufficient |
| `org.ent.pressagency.palach-press` | 1 | 1.000 | 3 | 0.500 | 0.667 | 0.571 | insufficient |
| `org.ent.pressagency.reuters` | 33 | 0.954 | 40 | 0.921 | 0.875 | 0.897 | limited |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 4 | 0.667 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.stefani` | 1 | 1.000 | 4 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.tanjug` | 5 | 0.462 | 4 | 0.800 | 1.000 | 0.889 | insufficient |
| `org.ent.pressagency.tass` | 3 | 0.333 | 4 | 1.000 | 0.750 | 0.857 | insufficient |
| `org.ent.pressagency.telegraphen-union` | 2 | 1.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.up-upi` | 10 | 0.952 | 20 | 0.941 | 0.800 | 0.865 | limited |
| `org.ent.pressagency.wolff` | 4 | 0.571 | 11 | 0.900 | 0.818 | 0.857 | insufficient |
| `org.ent.pressagency.xinhua` | 3 | 0.800 | 6 | 0.375 | 0.500 | 0.429 | insufficient |
| `org.ent.radiostation.bbc` | 3 | 1.000 | 2 | 0.250 | 0.500 | 0.333 | insufficient |
| `org.ent.radiostation.deutsche-welle` | 3 | 1.000 | 4 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.polskie-radio` | 7 | 0.857 | 6 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-bucharest` | 6 | 1.000 | 9 | 0.889 | 0.889 | 0.889 | insufficient |
| `org.ent.radiostation.radio-free-europe` | 6 | 1.000 | 6 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-liberty` | 6 | 1.000 | 2 | 1.000 | 0.500 | 0.667 | insufficient |
| `org.ent.radiostation.radio-moscow` | 4 | 1.000 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-paris` | 2 | 1.000 | 2 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-prague` | 3 | 0.800 | 2 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.rtl` | 4 | 1.000 | 6 | 0.800 | 0.667 | 0.727 | insufficient |
| `org.ent.radiostation.rts` | 4 | 0.222 | 4 | 0.600 | 0.750 | 0.667 | insufficient |
| `org.ent.radiostation.vatican-radio` | 5 | 0.909 | 6 | 0.714 | 0.833 | 0.769 | insufficient |
| `org.ent.radiostation.voice-of-america` | 1 | 1.000 | 7 | 0.875 | 1.000 | 0.933 | insufficient |
