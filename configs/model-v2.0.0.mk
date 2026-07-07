# Active prerelease config for dataset-v2.0.0.
#
# v2.x.x is self-contained: it uses the v2 prerelease dataset, v2 model
# artifact, and v2 checker label map. It is not the published HF revision yet.

include configs/common.mk

MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0
SELECTED_MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0-label-all-tokens/best
DATASET_SOURCE_DIR = data/prereleases/dataset-v2.0.0
DATASET_REVISION = v2.0.0
DATASET_TSV_COMPARE_VERSION = v1.0.0
TRAIN_JSONL = data/prereleases/dataset-v2.0.0/train.jsonl
VALIDATION_JSONL = data/prereleases/dataset-v2.0.0/validation.jsonl
TEST_JSONL = data/prereleases/dataset-v2.0.0/test.jsonl
LABEL_MAP = data/prereleases/dataset-v2.0.0/label_map.json
HF_MODEL = $(SELECTED_MODEL)
CURATION_MODEL = $(SELECTED_MODEL)
CURATION_LABEL_MAP = $(LABEL_MAP)
CURATION_INPUT_DIR = $(DATASET_SOURCE_DIR)
CURATION_APPLIED_DIR = $(DATASET_SOURCE_DIR)

# Supervise every model subtoken and convert B-X continuation labels to I-X.
# Validation and test comparisons against first-subtoken-only training favored B.
LABEL_ALL_TOKENS = true

EMPTY_DOC_AUDIT_ROOT = audit.d/empty-docs/dataset-v2.0.0
