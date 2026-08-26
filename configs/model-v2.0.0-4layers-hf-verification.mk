# v2.0.0 clean model-verification config trained from the published HF dataset.
#
# This config inherits the 4-layer v2 setup but reads train/validation/test from
# a local materialization of the exact Hugging Face dataset publication.

include configs/model-v2.0.0-4layers.mk

HF_DATASET_COMMIT = a7ac5dc1ec0dd92ae848dbccd258aa0361830da3
HF_DATASET_LOCAL_DIR = hf.d/dataset-v2.0.0

DATASET_SOURCE_DIR = $(HF_DATASET_LOCAL_DIR)
TRAIN_JSONL = $(DATASET_SOURCE_DIR)/data/train.jsonl
VALIDATION_JSONL = $(DATASET_SOURCE_DIR)/data/validation.jsonl
TEST_JSONL = $(DATASET_SOURCE_DIR)/data/test.jsonl
LABEL_MAP = $(DATASET_SOURCE_DIR)/label_map.json
TRAIN_SYNC_LABEL_MAP = false

MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0-hf-verification
SELECTED_MODEL = $(MODEL)/best
HF_MODEL = $(SELECTED_MODEL)
CURATION_MODEL = $(SELECTED_MODEL)
CURATION_LABEL_MAP = $(LABEL_MAP)
CURATION_INPUT_DIR = $(DATASET_SOURCE_DIR)
CURATION_APPLIED_DIR = $(DATASET_SOURCE_DIR)
