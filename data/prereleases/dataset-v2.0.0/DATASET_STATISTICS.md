# Dataset Statistics: v2.0.0

This report is generated from the released train, validation, and test JSONL files.

## Overview

| Split | Documents | With mentions | Tokens | Mentions | Newspapers | Date range |
|---|---:|---:|---:|---:|---:|---|
| train | 1,962 | 1,431 | 859,790 | 2,318 | 69 | 1840-01-04 to 2000-12-04 |
| validation | 292 | 226 | 108,727 | 324 | 41 | 1841-09-28 to 2000-07-08 |
| test | 300 | 239 | 98,288 | 392 | 35 | 1840-06-16 to 1999-02-26 |
| **Total** | **2,554** | **1,896** | **1,066,805** | **3,034** | - | - |

## Split Integrity

No document IDs occur in more than one split.

## Documents by Language

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `de` | 679 | 99 | 100 | 878 |
| `en` | 80 | 14 | 8 | 102 |
| `fr` | 1,192 | 178 | 187 | 1,557 |
| `it` | 2 | 0 | 1 | 3 |
| `lb` | 9 | 1 | 4 | 14 |

## Mentions by Entity Family

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `press agency` | 1,898 | 251 | 307 | 2,456 |
| `radio station` | 420 | 73 | 85 | 578 |

## Mentions by Entity Label

| Value | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| `org.ent.pressagency.afp` | 276 | 29 | 28 | 333 |
| `org.ent.pressagency.agence-radio` | 16 | 5 | 5 | 26 |
| `org.ent.pressagency.akp` | 0 | 1 | 5 | 6 |
| `org.ent.pressagency.ansa` | 21 | 5 | 5 | 31 |
| `org.ent.pressagency.ap` | 83 | 14 | 14 | 111 |
| `org.ent.pressagency.apa` | 17 | 3 | 5 | 25 |
| `org.ent.pressagency.ata` | 24 | 2 | 4 | 30 |
| `org.ent.pressagency.ats-sda` | 251 | 32 | 28 | 311 |
| `org.ent.pressagency.belga` | 22 | 5 | 5 | 32 |
| `org.ent.pressagency.cip` | 0 | 0 | 1 | 1 |
| `org.ent.pressagency.ctk` | 25 | 4 | 5 | 34 |
| `org.ent.pressagency.ddp-dapd` | 19 | 4 | 5 | 28 |
| `org.ent.pressagency.dnb` | 27 | 6 | 7 | 40 |
| `org.ent.pressagency.domei` | 26 | 5 | 5 | 36 |
| `org.ent.pressagency.dpa` | 56 | 5 | 5 | 66 |
| `org.ent.pressagency.europapress` | 19 | 5 | 5 | 29 |
| `org.ent.pressagency.extel` | 29 | 5 | 5 | 39 |
| `org.ent.pressagency.havas` | 333 | 31 | 50 | 414 |
| `org.ent.pressagency.keystone` | 0 | 0 | 1 | 1 |
| `org.ent.pressagency.kipa` | 21 | 5 | 6 | 32 |
| `org.ent.pressagency.palach-press` | 10 | 1 | 3 | 14 |
| `org.ent.pressagency.reuters` | 284 | 35 | 42 | 361 |
| `org.ent.pressagency.spk-smp` | 32 | 6 | 5 | 43 |
| `org.ent.pressagency.st-petersburg-telegraph-agency` | 13 | 4 | 2 | 19 |
| `org.ent.pressagency.stefani` | 23 | 4 | 5 | 32 |
| `org.ent.pressagency.tanjug` | 24 | 5 | 5 | 34 |
| `org.ent.pressagency.tass` | 25 | 5 | 6 | 36 |
| `org.ent.pressagency.telegraphen-union` | 18 | 5 | 5 | 28 |
| `org.ent.pressagency.up-upi` | 117 | 10 | 22 | 149 |
| `org.ent.pressagency.wolff` | 62 | 5 | 11 | 78 |
| `org.ent.pressagency.xinhua` | 25 | 5 | 7 | 37 |
| `org.ent.radiostation.bbc` | 48 | 8 | 9 | 65 |
| `org.ent.radiostation.deutsche-welle` | 14 | 5 | 6 | 25 |
| `org.ent.radiostation.polskie-radio` | 27 | 7 | 6 | 40 |
| `org.ent.radiostation.radio-bucharest` | 52 | 6 | 9 | 67 |
| `org.ent.radiostation.radio-free-europe` | 55 | 6 | 8 | 69 |
| `org.ent.radiostation.radio-liberty` | 16 | 6 | 5 | 27 |
| `org.ent.radiostation.radio-moscow` | 38 | 4 | 5 | 47 |
| `org.ent.radiostation.radio-paris` | 25 | 5 | 5 | 35 |
| `org.ent.radiostation.radio-prague` | 30 | 5 | 5 | 40 |
| `org.ent.radiostation.rfi` | 0 | 0 | 1 | 1 |
| `org.ent.radiostation.rtl` | 30 | 6 | 6 | 42 |
| `org.ent.radiostation.rts` | 21 | 5 | 6 | 32 |
| `org.ent.radiostation.vatican-radio` | 29 | 5 | 6 | 40 |
| `org.ent.radiostation.voice-of-america` | 35 | 5 | 8 | 48 |
