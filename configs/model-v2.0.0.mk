# Released dataset config for dataset-v2.0.0.
#
# v2.x.x is self-contained: it uses the immutable v2 release dataset, v2 model
# artifact, and v2 checker label map.

include configs/common.mk

MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0
SELECTED_MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0/best
DATASET_REVISION = v2.0.0
DATASET_TSV_COMPARE_VERSION = v1.0.0
DATASET_SOURCE_DIR = data/releases/dataset-v2.0.0
TRAIN_JSONL = $(DATASET_SOURCE_DIR)/train.jsonl
VALIDATION_JSONL = $(DATASET_SOURCE_DIR)/validation.jsonl
TEST_JSONL = $(DATASET_SOURCE_DIR)/test.jsonl
LABEL_MAP = $(DATASET_SOURCE_DIR)/label_map.json
TRAIN_SYNC_LABEL_MAP = false
HF_MODEL = $(SELECTED_MODEL)
HF_MODEL_REPO = impresso-project/mmbert-impresso-mediasources-ner
HF_MODEL_REVISION = v2.0.0
CURATION_MODEL = $(SELECTED_MODEL)
CURATION_LABEL_MAP = $(LABEL_MAP)
CURATION_INPUT_DIR = $(DATASET_SOURCE_DIR)
CURATION_APPLIED_DIR = $(DATASET_SOURCE_DIR)

# Supervise every model subtoken and convert B-X continuation labels to I-X.
# Validation and test comparisons against first-subtoken-only training favored B.
LABEL_ALL_TOKENS = true

EMPTY_DOC_AUDIT_ROOT = audit.d/empty-docs/dataset-v2.0.0
