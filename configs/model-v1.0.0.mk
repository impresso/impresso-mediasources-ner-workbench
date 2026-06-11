# Published v1.0.0 press-agency baseline config.

include configs/common.mk

MODEL = models.d/newsagency_radiostation_modernbert_v1.0.0
TRAIN_JSONL = data/curated/legacy-import/train.jsonl
VALIDATION_JSONL = data/curated/legacy-import/validation.jsonl
TEST_JSONL = data/curated/legacy-import/test.jsonl
LABEL_MAP = data/curated/legacy-import/label_map.json
DATASET_REVISION = v1.0.0
DATASET_SOURCE_DIR = data/releases/dataset-v1.0.0
EMPTY_TRAIN_SOURCE_JSONL = data/releases/dataset-v1.0.0/data/train.jsonl
EMPTY_TRAIN_LABEL_MAP = data/releases/dataset-v1.0.0/label_map.json
EMPTY_TRAIN_AUDIT_DIR = audit.d/empty-training-docs/dataset-v1.0.0
SPAN_PATCH_AUDIT_ID = empty-training-docs-v1.0.0
