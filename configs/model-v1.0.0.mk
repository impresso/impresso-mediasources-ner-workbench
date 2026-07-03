# Published v1.0.0 press-agency baseline config.

include configs/common.mk

MODEL = models.d/newsagency_radiostation_modernbert_v1.0.0
TRAIN_JSONL = data/curated/legacy-import/train.jsonl
VALIDATION_JSONL = data/curated/legacy-import/validation.jsonl
TEST_JSONL = data/curated/legacy-import/test.jsonl
LABEL_MAP = data/curated/legacy-import/label_map.json
DATASET_REVISION = v1.0.0
DATASET_SOURCE_DIR = data/releases/dataset-v1.0.0
EMPTY_DOC_SOURCE_JSONL = $(DATASET_SOURCE_DIR)/data/$(EMPTY_DOC_SPLIT).jsonl
EMPTY_DOC_LABEL_MAP = $(DATASET_SOURCE_DIR)/label_map.json
EMPTY_DOC_AUDIT_ROOT = audit.d/empty-docs/dataset-v1.0.0
