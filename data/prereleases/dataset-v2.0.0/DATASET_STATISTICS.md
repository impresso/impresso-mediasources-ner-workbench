# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 1,936 | 1,405 | 858,311 | 2,278 | 69 | 1840-01-04 to 2000-12-04 |
| validation | 244 | 179 | 105,993 | 264 | 38 | 1841-09-28 to 1999-06-03 |
| test | 259 | 198 | 96,181 | 330 | 33 | 1840-06-16 to 1999-02-26 |
| **Total** | **2,439** | **1,782** | **1,060,485** | **2,872** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 662 | 78 | 85 | 825 |
| `en` | 78 | 9 | 6 | 93 |
| `fr` | 1,185 | 156 | 163 | 1,504 |
| `it` | 2 | 0 | 1 | 3 |
| `lb` | 9 | 1 | 4 | 14 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,867 | 210 | 269 | 2,346 |
| `radio station` | 411 | 54 | 61 | 526 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 275 | 29 | 26 | 330 |
| `org.ent.pressagency.agence-radio` | 16 | 3 | 5 | 24 |
| `org.ent.pressagency.ansa` | 21 | 3 | 3 | 27 |
| `org.ent.pressagency.ap` | 80 | 14 | 13 | 107 |
| `org.ent.pressagency.apa` | 17 | 2 | 5 | 24 |
| `org.ent.pressagency.ata` | 24 | 2 | 3 | 29 |
| `org.ent.pressagency.ats-sda` | 248 | 30 | 28 | 306 |
| `org.ent.pressagency.belga` | 21 | 4 | 3 | 28 |
| `org.ent.pressagency.ctk` | 25 | 3 | 1 | 29 |
| `org.ent.pressagency.ddp-dapd` | 19 | 3 | 3 | 25 |
| `org.ent.pressagency.dnb` | 27 | 5 | 7 | 39 |
| `org.ent.pressagency.domei` | 26 | 4 | 4 | 34 |
| `org.ent.pressagency.dpa` | 51 | 3 | 5 | 59 |
| `org.ent.pressagency.europapress` | 19 | 3 | 3 | 25 |
| `org.ent.pressagency.extel` | 27 | 3 | 4 | 34 |
| `org.ent.pressagency.havas` | 333 | 31 | 49 | 413 |
| `org.ent.pressagency.kipa` | 20 | 1 | 6 | 27 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 282 | 33 | 41 | 356 |
| `org.ent.pressagency.spk-smp` | 23 | 0 | 1 | 24 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 2 | 19 |
| `org.ent.pressagency.stefani` | 23 | 1 | 4 | 28 |
| `org.ent.pressagency.tanjug` | 23 | 5 | 4 | 32 |
| `org.ent.pressagency.tass` | 25 | 5 | 6 | 36 |
| `org.ent.pressagency.telegraphen-union` | 18 | 2 | 2 | 22 |
| `org.ent.pressagency.up-upi` | 117 | 10 | 20 | 147 |
| `org.ent.pressagency.wolff` | 60 | 4 | 11 | 75 |
| `org.ent.pressagency.xinhua` | 24 | 2 | 7 | 33 |
| `org.ent.radiostation.bbc` | 45 | 3 | 2 | 50 |
| `org.ent.radiostation.deutsche-welle` | 14 | 3 | 4 | 21 |
| `org.ent.radiostation.polskie-radio` | 27 | 7 | 6 | 40 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 54 | 6 | 6 | 66 |
| `org.ent.radiostation.radio-liberty` | 15 | 6 | 2 | 23 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 5 | 47 |
| `org.ent.radiostation.radio-paris` | 24 | 2 | 2 | 28 |
| `org.ent.radiostation.radio-prague` | 30 | 3 | 2 | 35 |
| `org.ent.radiostation.rtl` | 29 | 4 | 6 | 39 |
| `org.ent.radiostation.rts` | 21 | 4 | 4 | 29 |
| `org.ent.radiostation.vatican-radio` | 29 | 5 | 6 | 40 |
| `org.ent.radiostation.voice-of-america` | 33 | 1 | 7 | 41 |
