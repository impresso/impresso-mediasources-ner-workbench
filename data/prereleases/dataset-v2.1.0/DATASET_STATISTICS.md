# Dataset Statistics: v2.1.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 2,339 | 1,646 | 895,647 | 2,630 | 97 | 1840-01-04 to 2000-12-04 |
| validation | 483 | 371 | 122,219 | 545 | 44 | 1841-09-28 to 2000-12-23 |
| test | 458 | 369 | 109,374 | 612 | 39 | 1840-06-16 to 2000-08-22 |
| **Total** | **3,280** | **2,386** | **1,127,240** | **3,787** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 809 | 169 | 155 | 1,133 |
| `en` | 125 | 33 | 24 | 182 |
| `fr` | 1,268 | 276 | 269 | 1,813 |
| `it` | 9 | 1 | 2 | 12 |
| `lb` | 28 | 4 | 8 | 40 |
| `unknown` | 100 | 0 | 0 | 100 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 2,132 | 409 | 455 | 2,996 |
| `radio station` | 498 | 136 | 157 | 791 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 290 | 40 | 35 | 365 |
| `org.ent.pressagency.agence-radio` | 15 | 9 | 10 | 34 |
| `org.ent.pressagency.akp` | 8 | 10 | 14 | 32 |
| `org.ent.pressagency.ansa` | 22 | 9 | 9 | 40 |
| `org.ent.pressagency.ap` | 104 | 16 | 16 | 136 |
| `org.ent.pressagency.apa` | 29 | 8 | 10 | 47 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 272 | 41 | 37 | 350 |
| `org.ent.pressagency.belga` | 23 | 11 | 10 | 44 |
| `org.ent.pressagency.cip` | 10 | 0 | 3 | 13 |
| `org.ent.pressagency.ctk` | 25 | 11 | 10 | 46 |
| `org.ent.pressagency.ddp-dapd` | 19 | 6 | 10 | 35 |
| `org.ent.pressagency.dnb` | 29 | 12 | 10 | 51 |
| `org.ent.pressagency.domei` | 25 | 10 | 10 | 45 |
| `org.ent.pressagency.dpa` | 76 | 12 | 12 | 100 |
| `org.ent.pressagency.europapress` | 20 | 10 | 10 | 40 |
| `org.ent.pressagency.extel` | 33 | 6 | 7 | 46 |
| `org.ent.pressagency.havas` | 343 | 33 | 50 | 426 |
| `org.ent.pressagency.keystone` | 13 | 13 | 11 | 37 |
| `org.ent.pressagency.kipa` | 34 | 11 | 11 | 56 |
| `org.ent.pressagency.kyodo` | 20 | 7 | 10 | 37 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 319 | 46 | 52 | 417 |
| `org.ent.pressagency.spk-smp` | 44 | 12 | 10 | 66 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 8 | 2 | 2 | 12 |
| `org.ent.pressagency.stefani` | 24 | 8 | 10 | 42 |
| `org.ent.pressagency.tanjug` | 26 | 10 | 10 | 46 |
| `org.ent.pressagency.tass` | 32 | 10 | 13 | 55 |
| `org.ent.pressagency.telegraphen-union` | 17 | 12 | 9 | 38 |
| `org.ent.pressagency.up-upi` | 120 | 11 | 23 | 154 |
| `org.ent.pressagency.wolff` | 73 | 11 | 14 | 98 |
| `org.ent.pressagency.xinhua` | 25 | 9 | 10 | 44 |
| `org.ent.radiostation.bbc` | 51 | 14 | 14 | 79 |
| `org.ent.radiostation.china-radio-international` | 10 | 0 | 1 | 11 |
| `org.ent.radiostation.deutsche-welle` | 13 | 10 | 9 | 32 |
| `org.ent.radiostation.deutschlandfunk` | 16 | 10 | 10 | 36 |
| `org.ent.radiostation.kol-yisrael` | 21 | 0 | 2 | 23 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 10 | 47 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 58 | 11 | 15 | 84 |
| `org.ent.radiostation.radio-liberty` | 17 | 11 | 9 | 37 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 7 | 49 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 10 | 43 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 11 | 47 |
| `org.ent.radiostation.rfi` | 19 | 11 | 10 | 40 |
| `org.ent.radiostation.rtl` | 31 | 9 | 11 | 51 |
| `org.ent.radiostation.rts` | 21 | 5 | 7 | 33 |
| `org.ent.radiostation.vatican-radio` | 29 | 9 | 10 | 48 |
| `org.ent.radiostation.voice-of-america` | 40 | 12 | 12 | 64 |
