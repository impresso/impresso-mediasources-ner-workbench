# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 1,994 | 1,460 | 861,586 | 2,357 | 69 | 1840-01-04 to 2000-12-04 |
| validation | 333 | 266 | 111,276 | 375 | 41 | 1841-09-28 to 2000-12-23 |
| test | 337 | 276 | 100,792 | 462 | 36 | 1840-06-16 to 2000-08-22 |
| **Total** | **2,664** | **2,002** | **1,073,654** | **3,194** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 696 | 112 | 112 | 920 |
| `en` | 85 | 19 | 11 | 115 |
| `fr` | 1,202 | 201 | 209 | 1,612 |
| `it` | 2 | 0 | 1 | 3 |
| `lb` | 9 | 1 | 4 | 14 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,902 | 252 | 316 | 2,470 |
| `radio station` | 455 | 123 | 146 | 724 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 276 | 29 | 31 | 336 |
| `org.ent.pressagency.agence-radio` | 16 | 5 | 5 | 26 |
| `org.ent.pressagency.akp` | 0 | 1 | 5 | 6 |
| `org.ent.pressagency.ansa` | 21 | 5 | 5 | 31 |
| `org.ent.pressagency.ap` | 84 | 14 | 14 | 112 |
| `org.ent.pressagency.apa` | 17 | 3 | 5 | 25 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 253 | 32 | 29 | 314 |
| `org.ent.pressagency.belga` | 22 | 5 | 5 | 32 |
| `org.ent.pressagency.cip` | 0 | 0 | 1 | 1 |
| `org.ent.pressagency.ctk` | 25 | 4 | 5 | 34 |
| `org.ent.pressagency.ddp-dapd` | 19 | 4 | 5 | 28 |
| `org.ent.pressagency.dnb` | 27 | 6 | 7 | 40 |
| `org.ent.pressagency.domei` | 26 | 5 | 5 | 36 |
| `org.ent.pressagency.dpa` | 56 | 5 | 6 | 67 |
| `org.ent.pressagency.europapress` | 19 | 5 | 5 | 29 |
| `org.ent.pressagency.extel` | 29 | 5 | 5 | 39 |
| `org.ent.pressagency.havas` | 333 | 31 | 50 | 414 |
| `org.ent.pressagency.keystone` | 0 | 0 | 2 | 2 |
| `org.ent.pressagency.kipa` | 21 | 5 | 6 | 32 |
| `org.ent.pressagency.kyodo` | 0 | 0 | 2 | 2 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 285 | 36 | 43 | 364 |
| `org.ent.pressagency.spk-smp` | 32 | 6 | 5 | 43 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 2 | 19 |
| `org.ent.pressagency.stefani` | 23 | 4 | 5 | 32 |
| `org.ent.pressagency.tanjug` | 24 | 5 | 5 | 34 |
| `org.ent.pressagency.tass` | 25 | 5 | 6 | 36 |
| `org.ent.pressagency.telegraphen-union` | 18 | 5 | 5 | 28 |
| `org.ent.pressagency.up-upi` | 117 | 10 | 22 | 149 |
| `org.ent.pressagency.wolff` | 62 | 5 | 11 | 78 |
| `org.ent.pressagency.xinhua` | 25 | 5 | 7 | 37 |
| `org.ent.radiostation.bbc` | 59 | 11 | 13 | 83 |
| `org.ent.radiostation.china-radio-international` | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.deutsche-welle` | 14 | 10 | 10 | 34 |
| `org.ent.radiostation.deutschlandfunk` | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.kol-yisrael` | 0 | 0 | 2 | 2 |
| `org.ent.radiostation.polskie-radio` | 27 | 10 | 10 | 47 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 60 | 10 | 14 | 84 |
| `org.ent.radiostation.radio-liberty` | 17 | 10 | 10 | 37 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 5 | 47 |
| `org.ent.radiostation.radio-paris` | 25 | 8 | 10 | 43 |
| `org.ent.radiostation.radio-prague` | 30 | 6 | 10 | 46 |
| `org.ent.radiostation.rfi` | 9 | 10 | 10 | 29 |
| `org.ent.radiostation.rtl` | 33 | 10 | 10 | 53 |
| `org.ent.radiostation.rts` | 22 | 10 | 10 | 42 |
| `org.ent.radiostation.vatican-radio` | 29 | 8 | 10 | 47 |
| `org.ent.radiostation.voice-of-america` | 40 | 10 | 11 | 61 |
