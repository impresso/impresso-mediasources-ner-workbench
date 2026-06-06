# Active prerelease config for dataset-v2.0.0.
#
# v2.x.x extends the published v1 press-agency baseline with radio stations and
# corrected HIPE-derived agency data. It is not the published HF revision yet.

include configs/model-v1.0.0.mk

MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0
DATASET_SOURCE_DIR = data/prereleases/dataset-v2.0.0
DATASET_REVISION = v1.0.0
TRAIN_JSONL = data/prereleases/dataset-v2.0.0/train.jsonl
VALIDATION_JSONL = data/prereleases/dataset-v2.0.0/validation.jsonl
TEST_JSONL = data/prereleases/dataset-v2.0.0/test.jsonl
LABEL_MAP = data/prereleases/dataset-v2.0.0/label_map.json

EMPTY_TRAIN_SOURCE_JSONL = data/prereleases/dataset-v2.0.0/train.jsonl
EMPTY_TRAIN_LABEL_MAP = data/prereleases/dataset-v2.0.0/label_map.json
EMPTY_TRAIN_AUDIT_DIR = audit.d/empty-training-docs/dataset-v2.0.0
SPAN_PATCH_AUDIT_ID = empty-training-docs-v2.0.0
SPAN_PATCH_CANDIDATES = $(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_candidates.jsonl
SPAN_PATCH_DECISIONS = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/decisions.jsonl
SPAN_PATCH_QUEUE_JSONL = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/queue.jsonl
SPAN_PATCH_SUMMARY_JSON = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/summary.json
SPAN_PATCH_SOURCE_JSONL = $(EMPTY_TRAIN_SOURCE_JSONL)
SPAN_PATCH_OUTPUT_JSONL = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/patched.jsonl
SPAN_PATCH_CHANGES_JSONL = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/changes.jsonl
SPAN_PATCH_CHANGES_TSV = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/changes.tsv
SPAN_PATCH_APPLY_SUMMARY_JSON = data/curated/span-patches/$(SPAN_PATCH_AUDIT_ID)/apply_summary.json
