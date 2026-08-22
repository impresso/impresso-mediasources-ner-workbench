# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0/best`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 2,041 | 2,386 | - | - | - |
| validation | 442 | 482 | 0.883 | 0.830 | 0.856 |
| test | 432 | 576 | 0.853 | 0.766 | 0.807 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 278 | 34 | 0.970 | 35 | 1.000 | 0.943 | 0.971 | adequate |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 1.000 | 10 | 0.900 | 0.900 | 0.900 | limited |
| `org.ent.pressagency.akp` | 0 | 10 | 0.000 | 11 | 0.000 | 0.000 | 0.000 | limited |
| `org.ent.pressagency.ansa` | 22 | 10 | 0.824 | 9 | 1.000 | 0.889 | 0.941 | insufficient |
| `org.ent.pressagency.ap` | 81 | 14 | 0.815 | 14 | 0.909 | 0.714 | 0.800 | limited |
| `org.ent.pressagency.apa` | 29 | 3 | 1.000 | 10 | 1.000 | 1.000 | 1.000 | limited |
| `org.ent.pressagency.ata` | 24 | 2 | 0.667 | 4 | 0.600 | 0.750 | 0.667 | insufficient |
| `org.ent.pressagency.ats-sda` | 265 | 39 | 0.949 | 34 | 0.971 | 0.971 | 0.971 | adequate |
| `org.ent.pressagency.belga` | 23 | 8 | 0.875 | 10 | 1.000 | 0.900 | 0.947 | limited |
| `org.ent.pressagency.cip` | 0 | 0 | 0.000 | 3 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ctk` | 25 | 10 | 0.750 | 10 | 1.000 | 1.000 | 1.000 | limited |
| `org.ent.pressagency.ddp-dapd` | 19 | 7 | 0.923 | 10 | 1.000 | 0.900 | 0.947 | limited |
| `org.ent.pressagency.dnb` | 29 | 10 | 0.667 | 10 | 1.000 | 0.700 | 0.824 | limited |
| `org.ent.pressagency.domei` | 25 | 10 | 1.000 | 10 | 1.000 | 1.000 | 1.000 | limited |
| `org.ent.pressagency.dpa` | 66 | 12 | 1.000 | 12 | 0.923 | 1.000 | 0.960 | limited |
| `org.ent.pressagency.europapress` | 20 | 10 | 1.000 | 10 | 0.900 | 0.900 | 0.900 | limited |
| `org.ent.pressagency.extel` | 30 | 7 | 0.571 | 6 | 0.714 | 0.833 | 0.769 | insufficient |
| `org.ent.pressagency.havas` | 334 | 32 | 0.938 | 50 | 0.938 | 0.900 | 0.918 | adequate |
| `org.ent.pressagency.keystone` | 8 | 10 | 0.889 | 9 | 0.800 | 0.444 | 0.571 | insufficient |
| `org.ent.pressagency.kipa` | 26 | 11 | 0.737 | 11 | 1.000 | 0.545 | 0.706 | limited |
| `org.ent.pressagency.kyodo` | 0 | 4 | 0.000 | 10 | 0.000 | 0.000 | 0.000 | limited |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.pressagency.reuters` | 287 | 44 | 0.929 | 47 | 1.000 | 0.936 | 0.967 | adequate |
| `org.ent.pressagency.spk-smp` | 34 | 12 | 0.880 | 10 | 0.667 | 0.800 | 0.727 | limited |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | 4 | 0.857 | 2 | 1.000 | 0.500 | 0.667 | insufficient |
| `org.ent.pressagency.stefani` | 23 | 8 | 0.933 | 10 | 1.000 | 1.000 | 1.000 | limited |
| `org.ent.pressagency.tanjug` | 25 | 10 | 1.000 | 10 | 1.000 | 1.000 | 1.000 | limited |
| `org.ent.pressagency.tass` | 19 | 7 | 0.857 | 10 | 0.750 | 0.600 | 0.667 | limited |
| `org.ent.pressagency.telegraphen-union` | 18 | 8 | 0.700 | 10 | 0.455 | 0.500 | 0.476 | limited |
| `org.ent.pressagency.up-upi` | 117 | 11 | 0.952 | 22 | 0.850 | 0.773 | 0.810 | adequate |
| `org.ent.pressagency.wolff` | 63 | 10 | 0.947 | 14 | 0.800 | 0.571 | 0.667 | limited |
| `org.ent.pressagency.xinhua` | 25 | 8 | 0.667 | 10 | 0.538 | 0.700 | 0.609 | limited |
| `org.ent.radiostation.bbc` | 50 | 11 | 0.778 | 14 | 0.545 | 0.429 | 0.480 | limited |
| `org.ent.radiostation.china-radio-international` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.deutsche-welle` | 13 | 9 | 0.900 | 10 | 1.000 | 0.900 | 0.947 | limited |
| `org.ent.radiostation.deutschlandfunk` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 0.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 0.667 | 10 | 0.667 | 0.600 | 0.632 | limited |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-free-europe` | 58 | 10 | 0.762 | 14 | 0.750 | 0.857 | 0.800 | limited |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 0.526 | 10 | 0.556 | 0.500 | 0.526 | limited |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 6 | 0.714 | 0.833 | 0.769 | insufficient |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 1.000 | 10 | 0.778 | 0.700 | 0.737 | limited |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 0.909 | 11 | 0.455 | 0.455 | 0.455 | limited |
| `org.ent.radiostation.rfi` | 0 | 0 | 0.000 | 3 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.rtl` | 31 | 9 | 0.875 | 10 | 0.750 | 0.600 | 0.667 | limited |
| `org.ent.radiostation.rts` | 21 | 6 | 0.286 | 8 | 0.500 | 0.500 | 0.500 | insufficient |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 1.000 | 10 | 0.636 | 0.700 | 0.667 | limited |
| `org.ent.radiostation.voice-of-america` | 40 | 10 | 0.667 | 11 | 0.692 | 0.818 | 0.750 | limited |
