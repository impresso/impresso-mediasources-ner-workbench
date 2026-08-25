# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 2,207 | 1,590 | 883,393 | 2,562 | 71 | 1840-01-04 to 2000-12-04 |
| validation | 471 | 366 | 121,518 | 532 | 44 | 1841-09-28 to 2000-12-23 |
| test | 446 | 361 | 108,642 | 602 | 39 | 1840-06-16 to 2000-08-22 |
| **Total** | **3,124** | **2,317** | **1,113,553** | **3,696** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 808 | 169 | 154 | 1,131 |
| `en` | 109 | 31 | 23 | 163 |
| `fr` | 1,260 | 267 | 261 | 1,788 |
| `it` | 5 | 1 | 1 | 7 |
| `lb` | 25 | 3 | 7 | 35 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 2,064 | 406 | 454 | 2,924 |
| `radio station` | 498 | 126 | 148 | 772 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 287 | 38 | 35 | 360 |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 10 | 35 |
| `org.ent.pressagency.akp` | 8 | 10 | 12 | 30 |
| `org.ent.pressagency.ansa` | 22 | 9 | 9 | 40 |
| `org.ent.pressagency.ap` | 87 | 16 | 15 | 118 |
| `org.ent.pressagency.apa` | 29 | 8 | 10 | 47 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 272 | 40 | 37 | 349 |
| `org.ent.pressagency.belga` | 23 | 11 | 10 | 44 |
| `org.ent.pressagency.cip` | 10 | 0 | 3 | 13 |
| `org.ent.pressagency.ctk` | 25 | 11 | 10 | 46 |
| `org.ent.pressagency.ddp-dapd` | 19 | 6 | 10 | 35 |
| `org.ent.pressagency.dnb` | 29 | 11 | 10 | 50 |
| `org.ent.pressagency.domei` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.dpa` | 76 | 12 | 12 | 100 |
| `org.ent.pressagency.europapress` | 20 | 10 | 10 | 40 |
| `org.ent.pressagency.extel` | 30 | 5 | 7 | 42 |
| `org.ent.pressagency.havas` | 334 | 33 | 50 | 417 |
| `org.ent.pressagency.keystone` | 11 | 12 | 11 | 34 |
| `org.ent.pressagency.kipa` | 34 | 11 | 11 | 56 |
| `org.ent.pressagency.kyodo` | 20 | 7 | 10 | 37 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 293 | 46 | 52 | 391 |
| `org.ent.pressagency.spk-smp` | 44 | 12 | 11 | 67 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | 4 | 3 | 21 |
| `org.ent.pressagency.stefani` | 23 | 8 | 10 | 41 |
| `org.ent.pressagency.tanjug` | 26 | 10 | 10 | 46 |
| `org.ent.pressagency.tass` | 28 | 10 | 13 | 51 |
| `org.ent.pressagency.telegraphen-union` | 17 | 12 | 9 | 38 |
| `org.ent.pressagency.up-upi` | 120 | 11 | 23 | 154 |
| `org.ent.pressagency.wolff` | 63 | 11 | 14 | 88 |
| `org.ent.pressagency.xinhua` | 25 | 10 | 10 | 45 |
| `org.ent.radiostation.bbc` | 51 | 14 | 14 | 79 |
| `org.ent.radiostation.china-radio-international` | 10 | 0 | 1 | 11 |
| `org.ent.radiostation.deutsche-welle` | 13 | 10 | 10 | 33 |
| `org.ent.radiostation.deutschlandfunk` | 16 | 2 | 1 | 19 |
| `org.ent.radiostation.kol-yisrael` | 21 | 0 | 2 | 23 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 10 | 47 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 58 | 10 | 15 | 83 |
| `org.ent.radiostation.radio-liberty` | 17 | 11 | 9 | 37 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 7 | 49 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 10 | 43 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 11 | 47 |
| `org.ent.radiostation.rfi` | 19 | 11 | 10 | 40 |
| `org.ent.radiostation.rtl` | 31 | 9 | 11 | 51 |
| `org.ent.radiostation.rts` | 21 | 5 | 7 | 33 |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 10 | 47 |
| `org.ent.radiostation.voice-of-america` | 40 | 12 | 11 | 63 |
