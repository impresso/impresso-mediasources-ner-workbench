# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 1,905 | 1,374 | 856,287 | 2,241 | 68 | 1840-01-04 to 2000-12-04 |
| validation | 241 | 176 | 105,856 | 260 | 37 | 1841-09-28 to 1999-06-03 |
| test | 254 | 193 | 95,745 | 321 | 33 | 1840-06-16 to 1999-02-26 |
| **Total** | **2,400** | **1,743** | **1,057,888** | **2,822** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 652 | 76 | 83 | 811 |
| `en` | 71 | 8 | 5 | 84 |
| `fr` | 1,174 | 156 | 161 | 1,491 |
| `it` | 1 | 0 | 1 | 2 |
| `lb` | 7 | 1 | 4 | 12 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,830 | 206 | 260 | 2,296 |
| `radio station` | 411 | 54 | 61 | 526 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 273 | 29 | 26 | 328 |
| `org.ent.pressagency.agence-radio` | 16 | 3 | 5 | 24 |
| `org.ent.pressagency.ansa` | 20 | 2 | 3 | 25 |
| `org.ent.pressagency.ap` | 78 | 13 | 13 | 104 |
| `org.ent.pressagency.apa` | 16 | 2 | 4 | 22 |
| `org.ent.pressagency.ata` | 20 | 2 | 3 | 25 |
| `org.ent.pressagency.ats-sda` | 247 | 30 | 27 | 304 |
| `org.ent.pressagency.belga` | 18 | 4 | 3 | 25 |
| `org.ent.pressagency.ctk` | 23 | 3 | 1 | 27 |
| `org.ent.pressagency.ddp-dapd` | 19 | 3 | 3 | 25 |
| `org.ent.pressagency.dnb` | 27 | 5 | 7 | 39 |
| `org.ent.pressagency.domei` | 23 | 3 | 4 | 30 |
| `org.ent.pressagency.dpa` | 51 | 3 | 4 | 58 |
| `org.ent.pressagency.europapress` | 19 | 3 | 3 | 25 |
| `org.ent.pressagency.extel` | 27 | 3 | 4 | 34 |
| `org.ent.pressagency.havas` | 329 | 31 | 49 | 409 |
| `org.ent.pressagency.kipa` | 20 | 1 | 6 | 27 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 279 | 33 | 40 | 352 |
| `org.ent.pressagency.spk-smp` | 22 | 0 | 0 | 22 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 1 | 18 |
| `org.ent.pressagency.stefani` | 23 | 1 | 4 | 28 |
| `org.ent.pressagency.tanjug` | 23 | 5 | 4 | 32 |
| `org.ent.pressagency.tass` | 23 | 3 | 4 | 30 |
| `org.ent.pressagency.telegraphen-union` | 16 | 2 | 2 | 20 |
| `org.ent.pressagency.up-upi` | 117 | 10 | 20 | 147 |
| `org.ent.pressagency.wolff` | 57 | 4 | 11 | 72 |
| `org.ent.pressagency.xinhua` | 21 | 3 | 6 | 30 |
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
