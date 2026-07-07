# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 1,994 | 2,357 | - | - | - |
| validation | 333 | 375 | 0.814 | 0.792 | 0.803 |
| test | 340 | 465 | 0.795 | 0.733 | 0.763 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 276 | 29 | 1.000 | 31 | 1.000 | 0.968 | 0.984 | adequate |
| `org.ent.pressagency.agence-radio` | 16 | 5 | 0.909 | 5 | 0.714 | 1.000 | 0.833 | insufficient |
| `org.ent.pressagency.akp` | 0 | 1 | 0.000 | 7 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ansa` | 21 | 5 | 0.750 | 5 | 0.750 | 0.600 | 0.667 | insufficient |
| `org.ent.pressagency.ap` | 84 | 14 | 0.714 | 14 | 1.000 | 0.786 | 0.880 | limited |
| `org.ent.pressagency.apa` | 17 | 3 | 0.400 | 5 | 0.667 | 0.400 | 0.500 | insufficient |
| `org.ent.pressagency.ata` | 24 | 2 | 0.667 | 4 | 0.400 | 0.500 | 0.444 | insufficient |
| `org.ent.pressagency.ats-sda` | 253 | 32 | 0.938 | 29 | 0.964 | 0.931 | 0.947 | adequate |
| `org.ent.pressagency.belga` | 22 | 5 | 0.750 | 5 | 1.000 | 0.600 | 0.750 | insufficient |
| `org.ent.pressagency.cip` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ctk` | 25 | 4 | 0.222 | 5 | 0.125 | 0.200 | 0.154 | insufficient |
| `org.ent.pressagency.ddp-dapd` | 19 | 4 | 0.286 | 5 | 0.750 | 0.600 | 0.667 | insufficient |
| `org.ent.pressagency.dnb` | 27 | 6 | 0.800 | 7 | 0.625 | 0.714 | 0.667 | insufficient |
| `org.ent.pressagency.domei` | 26 | 5 | 1.000 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.dpa` | 56 | 5 | 0.667 | 6 | 0.714 | 0.833 | 0.769 | insufficient |
| `org.ent.pressagency.europapress` | 19 | 5 | 0.727 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.extel` | 29 | 5 | 0.571 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.havas` | 333 | 31 | 0.906 | 50 | 0.915 | 0.860 | 0.887 | adequate |
| `org.ent.pressagency.keystone` | 0 | 0 | 0.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.kipa` | 21 | 5 | 0.667 | 6 | 0.333 | 0.167 | 0.222 | insufficient |
| `org.ent.pressagency.kyodo` | 0 | 0 | 0.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.palach-press` | 10 | 1 | 0.000 | 3 | 0.667 | 0.667 | 0.667 | insufficient |
| `org.ent.pressagency.reuters` | 285 | 36 | 0.971 | 43 | 0.950 | 0.884 | 0.916 | adequate |
| `org.ent.pressagency.spk-smp` | 32 | 6 | 0.714 | 6 | 0.364 | 0.667 | 0.471 | insufficient |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 0.857 | 2 | 1.000 | 0.500 | 0.667 | insufficient |
| `org.ent.pressagency.stefani` | 23 | 4 | 0.571 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.tanjug` | 24 | 5 | 0.800 | 5 | 0.800 | 0.800 | 0.800 | insufficient |
| `org.ent.pressagency.tass` | 25 | 5 | 0.400 | 6 | 0.600 | 0.500 | 0.545 | insufficient |
| `org.ent.pressagency.telegraphen-union` | 18 | 5 | 0.364 | 5 | 0.333 | 0.400 | 0.364 | insufficient |
| `org.ent.pressagency.up-upi` | 117 | 10 | 0.842 | 22 | 0.947 | 0.818 | 0.878 | adequate |
| `org.ent.pressagency.wolff` | 62 | 5 | 0.889 | 11 | 0.889 | 0.727 | 0.800 | limited |
| `org.ent.pressagency.xinhua` | 25 | 5 | 0.400 | 7 | 0.333 | 0.286 | 0.308 | insufficient |
| `org.ent.radiostation.bbc` | 59 | 11 | 0.833 | 13 | 0.533 | 0.615 | 0.571 | limited |
| `org.ent.radiostation.china-radio-international` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.deutsche-welle` | 14 | 10 | 0.900 | 10 | 0.900 | 0.900 | 0.900 | limited |
| `org.ent.radiostation.deutschlandfunk` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 0.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 0.600 | 10 | 0.600 | 0.600 | 0.600 | limited |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-free-europe` | 60 | 10 | 1.000 | 14 | 0.812 | 0.929 | 0.867 | limited |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 0.762 | 10 | 0.700 | 0.700 | 0.700 | limited |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 5 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 0.941 | 10 | 0.667 | 0.600 | 0.632 | limited |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 0.769 | 10 | 0.778 | 0.700 | 0.737 | limited |
| `org.ent.radiostation.rfi` | 9 | 10 | 0.462 | 10 | 1.000 | 0.200 | 0.333 | limited |
| `org.ent.radiostation.rtl` | 33 | 10 | 0.900 | 10 | 0.900 | 0.900 | 0.900 | limited |
| `org.ent.radiostation.rts` | 22 | 10 | 0.375 | 10 | 1.000 | 0.500 | 0.667 | limited |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 0.824 | 10 | 0.500 | 0.600 | 0.545 | limited |
| `org.ent.radiostation.voice-of-america` | 40 | 10 | 0.667 | 11 | 0.643 | 0.818 | 0.720 | limited |
