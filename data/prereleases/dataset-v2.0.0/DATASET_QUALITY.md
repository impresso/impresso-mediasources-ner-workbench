# Validation and Test Quality: v2.0.0

Model: `models.d/newsagency_radiostation_modernbert_v2.0.0-label-all-tokens/best`

This report was generated only after verifying that evaluation predictions cover exactly the current validation and test document IDs.

Coverage levels: **adequate** = at least 20 gold mentions; **limited** = 10-19; **insufficient** = fewer than 10.

## Overall Quality

| Split | Documents | Gold mentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| train | 2,041 | 2,387 | - | - | - |
| validation | 442 | 481 | 0.813 | 0.786 | 0.799 |
| test | 432 | 572 | 0.785 | 0.717 | 0.750 |

## Quality by Entity

| Entity label | Train gold | Val gold | Val F1 | Test gold | Test precision | Test recall | Test F1 | Test coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `org.ent.pressagency.afp` | 278 | 34 | 0.941 | 35 | 0.892 | 0.943 | 0.917 | adequate |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 1.000 | 10 | 0.636 | 0.700 | 0.667 | limited |
| `org.ent.pressagency.akp` | 0 | 10 | 0.000 | 11 | 0.000 | 0.000 | 0.000 | limited |
| `org.ent.pressagency.ansa` | 22 | 10 | 0.889 | 9 | 0.857 | 0.667 | 0.750 | insufficient |
| `org.ent.pressagency.ap` | 89 | 15 | 0.690 | 16 | 0.889 | 1.000 | 0.941 | limited |
| `org.ent.pressagency.apa` | 17 | 3 | 0.500 | 7 | 0.667 | 0.286 | 0.400 | insufficient |
| `org.ent.pressagency.ata` | 24 | 2 | 1.000 | 4 | 0.400 | 0.500 | 0.444 | insufficient |
| `org.ent.pressagency.ats-sda` | 264 | 39 | 0.974 | 34 | 0.889 | 0.941 | 0.914 | adequate |
| `org.ent.pressagency.belga` | 23 | 8 | 0.714 | 10 | 1.000 | 0.800 | 0.889 | limited |
| `org.ent.pressagency.cip` | 0 | 0 | 0.000 | 3 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.ctk` | 25 | 10 | 0.364 | 10 | 0.231 | 0.300 | 0.261 | limited |
| `org.ent.pressagency.ddp-dapd` | 19 | 7 | 0.462 | 10 | 0.889 | 0.800 | 0.842 | limited |
| `org.ent.pressagency.dnb` | 29 | 10 | 0.824 | 10 | 0.889 | 0.800 | 0.842 | limited |
| `org.ent.pressagency.domei` | 26 | 10 | 0.857 | 10 | 0.900 | 0.900 | 0.900 | limited |
| `org.ent.pressagency.dpa` | 66 | 12 | 0.815 | 12 | 0.846 | 0.917 | 0.880 | limited |
| `org.ent.pressagency.europapress` | 20 | 10 | 0.900 | 10 | 0.889 | 0.800 | 0.842 | limited |
| `org.ent.pressagency.extel` | 30 | 7 | 0.615 | 7 | 0.600 | 0.857 | 0.706 | insufficient |
| `org.ent.pressagency.havas` | 334 | 32 | 0.925 | 50 | 0.935 | 0.860 | 0.896 | adequate |
| `org.ent.pressagency.keystone` | 8 | 10 | 0.000 | 9 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.pressagency.kipa` | 23 | 10 | 0.947 | 10 | 0.625 | 0.500 | 0.556 | limited |
| `org.ent.pressagency.kyodo` | 0 | 4 | 0.000 | 10 | 0.000 | 0.000 | 0.000 | limited |
| `org.ent.pressagency.palach-press` | 10 | 1 | 1.000 | 3 | 0.667 | 0.667 | 0.667 | insufficient |
| `org.ent.pressagency.reuters` | 287 | 44 | 0.940 | 45 | 0.930 | 0.889 | 0.909 | adequate |
| `org.ent.pressagency.spk-smp` | 34 | 12 | 0.815 | 10 | 0.727 | 0.800 | 0.762 | limited |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 0.857 | 2 | 1.000 | 0.500 | 0.667 | insufficient |
| `org.ent.pressagency.stefani` | 23 | 8 | 0.933 | 10 | 1.000 | 1.000 | 1.000 | limited |
| `org.ent.pressagency.tanjug` | 25 | 10 | 0.476 | 10 | 0.357 | 0.500 | 0.417 | limited |
| `org.ent.pressagency.tass` | 25 | 7 | 0.429 | 10 | 0.571 | 0.400 | 0.471 | limited |
| `org.ent.pressagency.telegraphen-union` | 18 | 8 | 0.444 | 10 | 0.300 | 0.300 | 0.300 | limited |
| `org.ent.pressagency.up-upi` | 117 | 11 | 0.909 | 22 | 0.947 | 0.818 | 0.878 | adequate |
| `org.ent.pressagency.wolff` | 64 | 10 | 0.947 | 14 | 0.800 | 0.571 | 0.667 | limited |
| `org.ent.pressagency.xinhua` | 25 | 8 | 0.235 | 10 | 0.222 | 0.200 | 0.211 | limited |
| `org.ent.radiostation.bbc` | 50 | 11 | 0.783 | 13 | 0.667 | 0.615 | 0.640 | limited |
| `org.ent.radiostation.china-radio-international` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.deutsche-welle` | 14 | 9 | 0.900 | 10 | 0.900 | 0.900 | 0.900 | limited |
| `org.ent.radiostation.deutschlandfunk` | 0 | 0 | 0.000 | 1 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 0.000 | 2 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 0.632 | 10 | 0.750 | 0.600 | 0.667 | limited |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 1.000 | 9 | 1.000 | 1.000 | 1.000 | insufficient |
| `org.ent.radiostation.radio-free-europe` | 59 | 10 | 0.857 | 14 | 0.875 | 1.000 | 0.933 | limited |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 0.857 | 10 | 0.667 | 0.800 | 0.727 | limited |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 1.000 | 6 | 0.833 | 0.833 | 0.833 | insufficient |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 0.941 | 10 | 0.667 | 0.600 | 0.632 | limited |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 0.909 | 11 | 0.778 | 0.636 | 0.700 | limited |
| `org.ent.radiostation.rfi` | 0 | 0 | 0.000 | 3 | 0.000 | 0.000 | 0.000 | insufficient |
| `org.ent.radiostation.rtl` | 31 | 9 | 1.000 | 10 | 0.857 | 0.600 | 0.706 | limited |
| `org.ent.radiostation.rts` | 21 | 5 | 0.600 | 8 | 0.714 | 0.625 | 0.667 | insufficient |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 0.842 | 10 | 0.750 | 0.900 | 0.818 | limited |
| `org.ent.radiostation.voice-of-america` | 40 | 10 | 0.762 | 11 | 0.769 | 0.909 | 0.833 | limited |
