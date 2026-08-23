# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 2,115 | 1,522 | 876,598 | 2,464 | 70 | 1840-01-04 to 2000-12-04 |
| validation | 464 | 363 | 121,133 | 525 | 44 | 1841-09-28 to 2000-12-23 |
| test | 441 | 358 | 108,268 | 594 | 39 | 1840-06-16 to 2000-08-22 |
| **Total** | **3,020** | **2,243** | **1,105,999** | **3,583** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 774 | 167 | 154 | 1,095 |
| `en` | 102 | 30 | 21 | 153 |
| `fr` | 1,226 | 266 | 260 | 1,752 |
| `it` | 2 | 0 | 1 | 3 |
| `lb` | 11 | 1 | 5 | 17 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,995 | 404 | 448 | 2,847 |
| `radio station` | 469 | 121 | 146 | 736 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 280 | 38 | 35 | 353 |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 10 | 35 |
| `org.ent.pressagency.akp` | 0 | 10 | 11 | 21 |
| `org.ent.pressagency.ansa` | 22 | 9 | 9 | 40 |
| `org.ent.pressagency.ap` | 85 | 16 | 14 | 115 |
| `org.ent.pressagency.apa` | 29 | 8 | 10 | 47 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 268 | 40 | 37 | 345 |
| `org.ent.pressagency.belga` | 23 | 11 | 10 | 44 |
| `org.ent.pressagency.cip` | 10 | 0 | 3 | 13 |
| `org.ent.pressagency.ctk` | 25 | 11 | 10 | 46 |
| `org.ent.pressagency.ddp-dapd` | 19 | 6 | 10 | 35 |
| `org.ent.pressagency.dnb` | 29 | 11 | 10 | 50 |
| `org.ent.pressagency.domei` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.dpa` | 69 | 12 | 12 | 93 |
| `org.ent.pressagency.europapress` | 20 | 10 | 10 | 40 |
| `org.ent.pressagency.extel` | 30 | 5 | 7 | 42 |
| `org.ent.pressagency.havas` | 334 | 33 | 50 | 417 |
| `org.ent.pressagency.keystone` | 11 | 12 | 11 | 34 |
| `org.ent.pressagency.kipa` | 34 | 11 | 11 | 56 |
| `org.ent.pressagency.kyodo` | 0 | 7 | 10 | 17 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 290 | 45 | 51 | 386 |
| `org.ent.pressagency.spk-smp` | 36 | 12 | 11 | 59 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | 4 | 3 | 21 |
| `org.ent.pressagency.stefani` | 23 | 8 | 10 | 41 |
| `org.ent.pressagency.tanjug` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.tass` | 20 | 9 | 10 | 39 |
| `org.ent.pressagency.telegraphen-union` | 17 | 12 | 9 | 38 |
| `org.ent.pressagency.up-upi` | 119 | 11 | 23 | 153 |
| `org.ent.pressagency.wolff` | 63 | 11 | 14 | 88 |
| `org.ent.pressagency.xinhua` | 25 | 10 | 10 | 45 |
| `org.ent.radiostation.bbc` | 50 | 12 | 14 | 76 |
| `org.ent.radiostation.china-radio-international` | 10 | 0 | 1 | 11 |
| `org.ent.radiostation.deutsche-welle` | 13 | 9 | 10 | 32 |
| `org.ent.radiostation.deutschlandfunk` | 16 | 1 | 1 | 18 |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 2 | 2 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 10 | 47 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 58 | 10 | 15 | 83 |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 9 | 36 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 6 | 48 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 10 | 43 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 11 | 47 |
| `org.ent.radiostation.rfi` | 12 | 10 | 10 | 32 |
| `org.ent.radiostation.rtl` | 31 | 9 | 10 | 50 |
| `org.ent.radiostation.rts` | 21 | 5 | 7 | 33 |
| `org.ent.radiostation.vatican-radio` | 29 | 9 | 10 | 48 |
| `org.ent.radiostation.voice-of-america` | 40 | 12 | 11 | 63 |
