# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 1,954 | 1,423 | 859,290 | 2,303 | 69 | 1840-01-04 to 2000-12-04 |
| validation | 278 | 212 | 107,929 | 302 | 41 | 1841-09-28 to 2000-03-24 |
| test | 286 | 225 | 97,405 | 364 | 35 | 1840-06-16 to 1999-02-26 |
| **Total** | **2,518** | **1,860** | **1,064,624** | **2,969** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 676 | 94 | 94 | 864 |
| `en` | 80 | 13 | 7 | 100 |
| `fr` | 1,187 | 170 | 180 | 1,537 |
| `it` | 2 | 0 | 1 | 3 |
| `lb` | 9 | 1 | 4 | 14 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,892 | 248 | 303 | 2,443 |
| `radio station` | 411 | 54 | 61 | 526 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 275 | 29 | 28 | 332 |
| `org.ent.pressagency.agence-radio` | 16 | 5 | 5 | 26 |
| `org.ent.pressagency.akp` | 0 | 1 | 5 | 6 |
| `org.ent.pressagency.ansa` | 21 | 5 | 5 | 31 |
| `org.ent.pressagency.ap` | 81 | 14 | 14 | 109 |
| `org.ent.pressagency.apa` | 17 | 3 | 5 | 25 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 250 | 31 | 28 | 309 |
| `org.ent.pressagency.belga` | 22 | 5 | 5 | 32 |
| `org.ent.pressagency.ctk` | 25 | 4 | 5 | 34 |
| `org.ent.pressagency.ddp-dapd` | 19 | 4 | 5 | 28 |
| `org.ent.pressagency.dnb` | 27 | 6 | 7 | 40 |
| `org.ent.pressagency.domei` | 26 | 5 | 5 | 36 |
| `org.ent.pressagency.dpa` | 55 | 5 | 5 | 65 |
| `org.ent.pressagency.europapress` | 19 | 5 | 5 | 29 |
| `org.ent.pressagency.extel` | 29 | 5 | 5 | 39 |
| `org.ent.pressagency.havas` | 333 | 31 | 50 | 414 |
| `org.ent.pressagency.kipa` | 21 | 5 | 6 | 32 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 283 | 33 | 41 | 357 |
| `org.ent.pressagency.spk-smp` | 32 | 6 | 5 | 43 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 2 | 19 |
| `org.ent.pressagency.stefani` | 23 | 4 | 5 | 32 |
| `org.ent.pressagency.tanjug` | 24 | 5 | 5 | 34 |
| `org.ent.pressagency.tass` | 25 | 5 | 6 | 36 |
| `org.ent.pressagency.telegraphen-union` | 18 | 5 | 5 | 28 |
| `org.ent.pressagency.up-upi` | 117 | 10 | 21 | 148 |
| `org.ent.pressagency.wolff` | 62 | 5 | 11 | 78 |
| `org.ent.pressagency.xinhua` | 25 | 5 | 7 | 37 |
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
