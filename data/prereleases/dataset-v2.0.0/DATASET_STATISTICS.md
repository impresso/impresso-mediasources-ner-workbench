# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 2,041 | 1,470 | 871,623 | 2,386 | 69 | 1840-01-04 to 2000-12-04 |
| validation | 442 | 343 | 119,568 | 482 | 44 | 1841-09-28 to 2000-12-23 |
| test | 432 | 355 | 107,695 | 576 | 39 | 1840-06-16 to 2000-08-22 |
| **Total** | **2,915** | **2,168** | **1,098,886** | **3,444** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 716 | 159 | 151 | 1,026 |
| `en` | 98 | 29 | 20 | 147 |
| `fr` | 1,216 | 253 | 256 | 1,725 |
| `it` | 2 | 0 | 1 | 3 |
| `lb` | 9 | 1 | 4 | 14 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,955 | 375 | 436 | 2,766 |
| `radio station` | 431 | 107 | 140 | 678 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 278 | 34 | 35 | 347 |
| `org.ent.pressagency.agence-radio` | 16 | 9 | 10 | 35 |
| `org.ent.pressagency.akp` | 0 | 10 | 11 | 21 |
| `org.ent.pressagency.ansa` | 22 | 10 | 9 | 41 |
| `org.ent.pressagency.ap` | 81 | 14 | 14 | 109 |
| `org.ent.pressagency.apa` | 29 | 3 | 10 | 42 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 265 | 39 | 34 | 338 |
| `org.ent.pressagency.belga` | 23 | 8 | 10 | 41 |
| `org.ent.pressagency.cip` | 0 | 0 | 3 | 3 |
| `org.ent.pressagency.ctk` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.ddp-dapd` | 19 | 7 | 10 | 36 |
| `org.ent.pressagency.dnb` | 29 | 10 | 10 | 49 |
| `org.ent.pressagency.domei` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.dpa` | 66 | 12 | 12 | 90 |
| `org.ent.pressagency.europapress` | 20 | 10 | 10 | 40 |
| `org.ent.pressagency.extel` | 30 | 7 | 6 | 43 |
| `org.ent.pressagency.havas` | 334 | 32 | 50 | 416 |
| `org.ent.pressagency.keystone` | 8 | 10 | 9 | 27 |
| `org.ent.pressagency.kipa` | 26 | 11 | 11 | 48 |
| `org.ent.pressagency.kyodo` | 0 | 4 | 10 | 14 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 287 | 44 | 47 | 378 |
| `org.ent.pressagency.spk-smp` | 34 | 12 | 10 | 56 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 14 | 4 | 2 | 20 |
| `org.ent.pressagency.stefani` | 23 | 8 | 10 | 41 |
| `org.ent.pressagency.tanjug` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.tass` | 19 | 7 | 10 | 36 |
| `org.ent.pressagency.telegraphen-union` | 18 | 8 | 10 | 36 |
| `org.ent.pressagency.up-upi` | 117 | 11 | 22 | 150 |
| `org.ent.pressagency.wolff` | 63 | 10 | 14 | 87 |
| `org.ent.pressagency.xinhua` | 25 | 8 | 10 | 43 |
| `org.ent.radiostation.bbc` | 50 | 11 | 14 | 75 |
| `org.ent.radiostation.china-radio-international` | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.deutsche-welle` | 13 | 9 | 10 | 32 |
| `org.ent.radiostation.deutschlandfunk` | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 2 | 2 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 10 | 47 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 58 | 10 | 14 | 82 |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 10 | 37 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 6 | 48 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 10 | 43 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 11 | 47 |
| `org.ent.radiostation.rfi` | 0 | 0 | 3 | 3 |
| `org.ent.radiostation.rtl` | 31 | 9 | 10 | 50 |
| `org.ent.radiostation.rts` | 21 | 6 | 8 | 35 |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 10 | 47 |
| `org.ent.radiostation.voice-of-america` | 40 | 10 | 11 | 61 |
