.DEFAULT_GOAL := help

PYTHON ?= python3
ARGS ?=
CFG ?= configs/model-v2.0.0.mk

include $(CFG)

RELEASE_AUDIT_S3_PREFIX ?=

ifneq ($(wildcard $(LOCAL_CONFIG)),)
$(info Loading local config overrides from $(LOCAL_CONFIG))
include $(LOCAL_CONFIG)
endif

export HF_HOME

.PHONY: plan-holdout-gaps sample-holdout-gaps
.PHONY: help help-anno help-data help-model help-pretrain help-finetune smoke clean clean-dry-run anno-housekeeping data-housekeeping prepare-dataset-release finalize-dataset-release promote-dataset-release download-hf-dataset compare-hf-dataset-release audit-tokenization audit-predicted-iob audit-subtokens migrate-tokenization semantic-search validate-labels validate-jsonl-format validate-dataset-splits sync-label-map maybe-sync-label-map dataset-statistics dataset-quality-analysis dataset-subword-stats materialize-dataset-tsv materialize-dataset-tsv-quiet annotation-stats mention-profiles entity-surface-frequencies audit-seed-alias-matches curation-state curation-state-json snippet-state dataset-state eval-disagreement-state audit-empty-training-docs audit-empty-docs-split audit-missing-spans review-missing-spans apply-missing-spans missing-span-status promote-missing-spans integrate-missing-spans audit-existing-spans review-existing-spans apply-existing-spans existing-span-status promote-existing-spans integrate-existing-spans audit-agency-word-boundaries apply-agency-word-boundaries agency-word-boundary-status promote-agency-word-boundaries integrate-agency-word-boundaries review-span-patches apply-span-patches span-patch-status promote-span-patches integrate-span-patches search-tsv review-tsv-search replace-tsv-segment create-tsv-span-patch create-tsv-span-patches apply-tsv-span-patches tsv-span-patch-status promote-tsv-span-patches integrate-tsv-span-patches check-curation-checker plan-media-sampling sample-media-snippets sample-all-aliases-media-snippets sample-freely-media-snippets curate import-hipe export-dataset download-mlm-sources build-mlm-data pretrain-mlm push-mlm-model publish-dataset publish-testset train train-fresh stamp-model-inference-metadata evaluate-validation evaluate-test test test-official curation-eval curation-eval-train curation-eval-validation curation-eval-test curation-review curation-review-train curation-review-validation curation-review-test suggest-eval-disagreements suggest-eval-disagreements-train suggest-eval-disagreements-validation suggest-eval-disagreements-test suggest-media-snippet-spans review-media-snippet-spans review-auto-media-snippet-spans split-media-snippets preview-promote-snippets promote-snippets integrate-snippets curation-dashboard review-curation validate-curation apply-curation push-model

help:
	@echo "Impresso media sources NER workbench"
	@echo ""
	@echo "Housekeeping:"
	@echo "  make anno-housekeeping  Refresh annotation checks, coverage, profiles, and curation state"
	@echo "  make data-housekeeping  Refresh dataset checks, TSV views, statistics, and quality reports"
	@echo "  make prepare-dataset-release  Refresh release metadata for the configured dataset prerelease"
	@echo "  make finalize-dataset-release  Record HF publication metadata after upload"
	@echo "  make promote-dataset-release  Project a published prerelease into immutable data/releases"
	@echo "  make download-hf-dataset      Materialize the pinned HF dataset locally"
	@echo "  make compare-hf-dataset-release  Compare local HF materialization with Git release"
	@echo ""
	@echo "Main help groups:"
	@echo "  make help-anno               Annotation sampling, review, audit, and promotion"
	@echo "  make help-data               Dataset validation, state, export, and publishing"
	@echo "  make help-model              Model evaluation, curation eval, and Hub push"
	@echo "  make help-pretrain           MLM source download, data build, pretraining, and push"
	@echo "  make help-finetune           Token-classifier training and evaluation"
	@echo ""
	@echo "Common utilities:"
	@echo "  make smoke                   Run lightweight contract checks"
	@echo "  make clean-dry-run           Preview ignored/generated local data cleanup"
	@echo "  make clean                   Remove ignored/generated local data; keep data/releases"
	@echo ""
	@echo "Defaults:"
	@echo "  CFG=$(CFG)"
	@echo "  PYTHON=$(PYTHON)"
	@echo "  ARGS=$(ARGS)"

help-anno:
	@echo "Annotation and curation targets"
	@echo ""
	@echo "Use this group for curator work: inspect state, sample or audit evidence, suggest spans, review decisions, split/apply reviewed material, and promote it into dataset splits."
	@echo ""
	@echo "State and diagnostics:"
	@echo "  make anno-housekeeping  Refresh all annotation checks, statistics, profiles, and state reports"
	@echo ""
	@echo "  make curation-dashboard       Run all read-only state/stats targets in sequence"
	@echo "  make annotation-stats         Summarize annotation coverage by label/language"
	@echo "  make mention-profiles         Generate empirical entity mention-surface profiles"
	@echo "  make audit-seed-alias-matches Apply seed alias matchers to annotated data and report TP/FP-style hit quality"
	@echo "  make entity-surface-frequencies ENTITY_LABEL=org.ent.pressagency.havas"
	@echo "                                Print case-insensitive surface frequencies by language"
	@echo "  make semantic-search ARGS='--environment normal --language de --query \"Telegraphen Union\"'"
	@echo "                                Explore embedding search and recursively narrow result passages"
	@echo "  make curation-state           Summarize all curation and dataset state"
	@echo "  make snippet-state            Summarize snippet sampling/suggestion/review/split state"
	@echo "  make eval-disagreement-state  Summarize evaluation disagreement curation state"
	@echo ""
	@echo "Audit-driven span patches:"
	@echo "  make audit-empty-training-docs                Score empty-gold train/validation/test docs for missed spans"
	@echo "  make audit-missing-spans MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata"
	@echo "                                             Suggest missing spans for one label in one split"
	@echo "  make review-missing-spans                     Review target-specific missing-span suggestions"
	@echo "  make integrate-missing-spans                  Apply reviewed missing-span decisions, then promote"
	@echo "  make audit-existing-spans                     Build target-label boundary review from existing annotations"
	@echo "  make review-existing-spans                    Verify/correct/remove existing span boundaries"
	@echo "  make apply-existing-spans                     Apply existing-span boundary decisions to a patched split"
	@echo "  make promote-existing-spans                   Promote existing-span patched output into the source split"
	@echo "  make integrate-existing-spans                 Apply existing-span decisions, then promote the patched split"
	@echo "  make audit-agency-word-boundaries             Build accepted patches for the agency-word boundary migration"
	@echo "  make integrate-agency-word-boundaries         Apply and promote agency-word boundary migration patches"
	@echo "  make review-span-patches                      Review audit-suggested span patches"
	@echo "  make apply-span-patches                       Apply accepted/corrected span patches to JSONL"
	@echo "  make span-patch-status                        Compare patched output with the configured promotion target"
	@echo "  make promote-span-patches                     Promote patched output into the prerelease/source split"
	@echo "  make integrate-span-patches                   Apply span-patch decisions, then promote the patched split"
	@echo "  make create-tsv-span-patch TSV_PATCH_SPLIT=test"
	@echo "                                             Paste one TSV patch block and create accepted manual span patches"
	@echo "  make create-tsv-span-patches TSV_PATCH_SPLIT=test"
	@echo "                                             Paste one or more TSV patch blocks in an interactive loop"
	@echo "  make search-tsv TSV_SEARCH=\"Radio London\""
	@echo "                                             Page through token/tag TSV hits in all splits unless TSV_PATCH_SPLIT is set"
	@echo "                                             Tag searches show audited hits; token searches hide them unless TSV_SEARCH_INCLUDE_AUDITED=true"
	@echo "  make review-tsv-search TSV_SEARCH=tan TSV_PATCH_LABEL=org.ent.pressagency.tanjug REVIEWER=\"$$USER\""
	@echo "                                             Page through TSV hits; annotate with TSV lines or verify the current hit"
	@echo "  make replace-tsv-segment TSV_SEGMENT_SPLIT=train TSV_SEGMENT_OLD=/tmp/old.tsv TSV_SEGMENT_NEW=/tmp/new.tsv"
	@echo "                                             Replace an exact TOKEN/NERTAG segment with a clean TOKEN/NERTAG block"
	@echo "  make integrate-tsv-span-patches               Apply and promote accepted TSV-derived patches in all splits unless TSV_PATCH_SPLIT is set"
	@echo ""
	@echo "Evaluation disagreement annotation:"
	@echo "  make suggest-eval-disagreements               Score train/validation/test and build review queue"
	@echo "  make suggest-eval-disagreements-train         Score train only"
	@echo "  make suggest-eval-disagreements-validation    Score validation only"
	@echo "  make suggest-eval-disagreements-test          Score test only"
	@echo "  make review-curation                          Review pending gold/prediction disagreements"
	@echo "  make validate-curation                        Validate curation decisions"
	@echo "  make apply-curation                           Write curated JSONL folds"
	@echo ""
	@echo "Media-source snippet annotation:"
	@echo "  make plan-media-sampling MEDIA_FAMILY=pressagency"
	@echo "                                             Plan focused sampling from coverage, pending work, and mention surfaces"
	@echo "  make sample-holdout-gaps MEDIA_FAMILY=pressagency HOLDOUT_MIN_PER_LABEL=10"
	@echo "                                             Sample labels below validation/test positive-count targets"
	@echo "  make sample-media-snippets MEDIA_FAMILY=pressagency"
	@echo "                                             Focused sample press-agency label/language/surface gaps"
	@echo "  make sample-all-aliases-media-snippets MEDIA_FAMILY=pressagency MEDIA_LABELS=org.ent.pressagency.cip"
	@echo "                                             Search every configured alias for under-target labels"
	@echo "  make sample-media-snippets MEDIA_FAMILY=radiostation MEDIA_LABELS=org.ent.radiostation.rtl"
	@echo "                                             Sample one radio-station label below target"
	@echo "  make suggest-media-snippet-spans MEDIA_FAMILY=pressagency"
	@echo "                                             Suggest spans: model plus known entity metadata matchers"
	@echo "  make review-media-snippet-spans MEDIA_FAMILY=pressagency REVIEWER=\"$$USER\""
	@echo "                                             Review uncertain snippet spans; press i for label info"
	@echo "  make review-auto-media-snippet-spans MEDIA_FAMILY=pressagency REVIEWER=\"$$USER\""
	@echo "                                             Audit auto-accepted snippet spans manually"
	@echo "  make split-media-snippets MEDIA_FAMILY=pressagency"
	@echo "                                             Split accepted snippets into train/validation/test JSONL"
	@echo "  make preview-promote-snippets                Preview promotion into configured dataset splits"
	@echo "  make promote-snippets                        Promote split snippets into configured dataset splits"
	@echo "  make integrate-snippets                      Split, preview, then promote reviewed snippets"
	@echo ""
	@echo "Useful overrides:"
	@echo "  MEDIA_FAMILY=pressagency|radiostation, REVIEWER=$$USER, SNIPPET_REVIEW_MAX_ITEMS=0 (all), MEDIA_SNIPPETS=..."
	@echo "  MEDIA_LABELS='org.ent.pressagency.reuters', MEDIA_SAMPLE_MODE=focused|coverage|surface"
	@echo "  REVIEW_COVERAGE_JSON=$(ANNOTATION_STATS_JSON), REVIEW_ONLY_UNDER_TARGET=false (set true for coverage-only review)"
	@echo "  ENTITY_LABEL=org.ent.pressagency.havas, ENTITY_SURFACE_FREQUENCIES_EXAMPLES=0"
	@echo "  MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata, MISSING_SPAN_SPLIT=train|validation|test"
	@echo "  SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.tass, SPAN_BOUNDARY_SPLIT=train|validation|dev|test"
	@echo "  CURATION_MODEL=$(CURATION_MODEL), CURATION_LABEL_MAP=$(CURATION_LABEL_MAP)"
	@echo "  EMPTY_DOC_MODEL=$(EMPTY_DOC_MODEL) (defaults to CURATION_MODEL)"
	@echo "  ANNOTATION_MAIN_LANGS='$(ANNOTATION_MAIN_LANGS)', ANNOTATION_SIDE_LANGS='$(ANNOTATION_SIDE_LANGS)'"
	@echo "  ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=$(ANNOTATION_MAIN_TARGET_PER_LABEL_LANG), ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=$(ANNOTATION_SIDE_TARGET_PER_LABEL_LANG)"
	@echo "  SUGGEST_NON_O_MIN_CONFIDENCE=0.33 (suggest best non-O label even when O wins)"
	@echo "  AUTO_ACCEPT_ENABLED=false|true (default false), AUTO_ACCEPT_MIN_CONFIDENCE=0.99, AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE=\$$(AUTO_ACCEPT_MIN_CONFIDENCE), AUTO_ACCEPT_MIN_MARGIN=0.30"
	@echo "  CURATION_STATE_JSON=$(CURATION_STATE_JSON)"

help-data:
	@echo "Dataset targets"
	@echo ""
	@echo "Use this group for dataset integrity, state snapshots, exports, and publishing. Promotion targets integrate reviewed local curation artifacts into the configured prerelease/source splits."
	@echo ""
	@echo "Validation and state:"
	@echo "  make data-housekeeping                     Run all dataset checks and refresh inspection reports"
	@echo ""
	@echo "  make validate-labels                       Validate canonical label metadata"
	@echo "  make validate-jsonl-format                 Validate token/offset/BIO/entity consistency"
	@echo "  make validate-dataset-splits               Check train/validation/test split integrity"
	@echo "  make audit-tokenization                    Verify canonical punctuation tokenization and boundaries"
	@echo "  make migrate-tokenization                  Stage canonicalized train/validation/test JSONL"
	@echo "  make sync-label-map                        Derive label_map.json from minimal train/validation/test"
	@echo "  make dataset-statistics                    Generate the release Markdown statistics report"
	@echo "  make dataset-quality-analysis              Refresh validation/test evaluation and quality report"
	@echo "  make audit-predicted-iob                   Audit illegal BIO transitions in predicted token tags"
	@echo "  make audit-subtokens                       Audit subtoken prediction consistency within words"
	@echo "  make dataset-subword-stats                 Measure tokenizer expansion and window coverage"
	@echo "  make materialize-dataset-tsv               Write ignored TOKEN/NERTAG TSV views for diffing"
	@echo "  make prepare-dataset-release               Refresh release metadata for the configured dataset prerelease"
	@echo "  make finalize-dataset-release              Record HF publication metadata after upload"
	@echo "  make promote-dataset-release               Project a published prerelease into immutable data/releases"
	@echo "  make download-hf-dataset                   Materialize the pinned HF dataset locally"
	@echo "  make compare-hf-dataset-release            Compare local HF materialization with Git release"
	@echo "  make dataset-state                         Summarize staging and configured published dataset state"
	@echo "  make curation-state-json                   Write $(CURATION_STATE_JSON)"
	@echo ""
	@echo "Import, export, publish:"
	@echo "  make import-hipe ARGS=...                  Convert HIPE TSV annotations to JSONL"
	@echo "  make export-dataset                        Export curated JSONL training data"
	@echo "  make publish-dataset ARGS=...              Publish or dry-run training dataset"
	@echo "  make publish-testset ARGS=...              Publish or dry-run testset"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean-dry-run                         Preview ignored/generated local data cleanup"
	@echo "  make clean                                 Remove ignored/generated local data; keep data/releases"

help-model:
	@echo "Model targets"
	@echo ""
	@echo "Use this group for model-side checks, evaluation, curation evaluation output, and pushing trained model artifacts."
	@echo ""
	@echo "Checks:"
	@echo "  make smoke                                 Run lightweight contract checks"
	@echo ""
	@echo "Evaluation:"
	@echo "  make evaluate-validation CFG=...           Evaluate the selected checkpoint on validation"
	@echo "  make evaluate-test CFG=...                 Evaluate the selected checkpoint on held-out test"
	@echo "  make test CFG=...                          Compatibility alias for evaluate-validation"
	@echo "  make test-official CFG=...                 Compatibility alias for evaluate-test"
	@echo "  make curation-eval                         Evaluate train/validation/test for disagreement review"
	@echo "  make curation-eval-train                   Evaluate train for disagreement review"
	@echo "  make curation-eval-validation              Evaluate validation for disagreement review"
	@echo "  make curation-eval-test                    Evaluate test for disagreement review"
	@echo ""
	@echo "Publishing:"
	@echo "  make push-model CFG=...                    Push model payload to Hugging Face"

help-pretrain:
	@echo "Pretraining targets"
	@echo ""
	@echo "Use this group for continued MLM pretraining before token-classifier fine-tuning."
	@echo ""
	@echo "  make download-mlm-sources                  Download compiled Impresso MLM source files"
	@echo "  make build-mlm-data                        Build balanced multilingual Impresso MLM data"
	@echo "  make pretrain-mlm                          Continue MLM pretraining for multilingual Impresso BERT"
	@echo "  make push-mlm-model                        Push continued MLM model payload to Hugging Face"

help-finetune:
	@echo "Fine-tuning targets"
	@echo ""
	@echo "Use this group for training and evaluating the token-classification NER model with the configured v2 dataset splits."
	@echo ""
	@echo "  make train CFG=...                         Train via training submodule"
	@echo "  make train-fresh CFG=...                   Remove the configured MODEL directory, then train from the base model"
	@echo "    LABEL_ALL_TOKENS=true                    B: all subtokens supervised; continuation B-X becomes I-X (v2 default)"
	@echo "    LABEL_ALL_TOKENS=false                   A: first subtoken supervised; continuations use -100"
	@echo "  make stamp-model-inference-metadata       Stamp tokenization/training/decoding policy into config.json"
	@echo "  make test CFG=...                          Evaluate validation via training submodule"
	@echo "  make test-official CFG=...                 Evaluate test and record official metrics"

smoke:
	@echo "Running lightweight syntax and metadata contract checks."
	$(PYTHON) -m py_compile lib/*.py hf_model/pipeline.py
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

semantic-search:
	@echo "Exploring semantic nearest-neighbor results and their most similar text passages."
	$(PYTHON) -m lib.semantic_search_explorer $(ARGS)

clean:
	@echo "Removing ignored/generated local workbench data while preserving release snapshots."
	$(PYTHON) -m lib.clean_workbench

clean-dry-run:
	@echo "Previewing ignored/generated local data that clean would remove."
	$(PYTHON) -m lib.clean_workbench --dry-run

validate-labels:
	@echo "Validating canonical news-agency and radio-station label metadata."
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

audit-tokenization:
	@echo "Auditing train/validation/test against the canonical v2 punctuation tokenization profile without changing data."
	$(PYTHON) -m lib.migrate_tokenization --split train="$(TRAIN_JSONL)" --split validation="$(VALIDATION_JSONL)" --split test="$(TEST_JSONL)" --summary-json "$(TOKENIZATION_AUDIT_JSON)" --changes-jsonl "$(TOKENIZATION_CHANGES_JSONL)" --report-md "$(TOKENIZATION_AUDIT_MD)"
	@echo "Reports:"
	@echo "  $(TOKENIZATION_AUDIT_MD)"
	@echo "  $(TOKENIZATION_CHANGES_JSONL)"

migrate-tokenization:
	@echo "Materializing canonical v2 punctuation-tokenized train/validation/test files in the migration staging directory."
	$(PYTHON) -m lib.migrate_tokenization --split train="$(TRAIN_JSONL)" --split validation="$(VALIDATION_JSONL)" --split test="$(TEST_JSONL)" --output-dir "$(TOKENIZATION_MIGRATION_DIR)" --summary-json "$(TOKENIZATION_AUDIT_JSON)" --changes-jsonl "$(TOKENIZATION_CHANGES_JSONL)" --report-md "$(TOKENIZATION_AUDIT_MD)"
	@echo "Staged migrated splits: $(TOKENIZATION_MIGRATION_DIR)"

data-housekeeping:
	@echo "Running complete housekeeping for the configured dataset and checker model."
	$(MAKE) audit-tokenization
	$(MAKE) validate-jsonl-format
	$(MAKE) sync-label-map
	$(MAKE) validate-labels
	$(MAKE) validate-dataset-splits
	$(MAKE) materialize-dataset-tsv-quiet
	$(MAKE) curation-state-json
	$(MAKE) dataset-subword-stats
	$(MAKE) dataset-quality-analysis
	$(MAKE) dataset-state
	@echo "Dataset housekeeping complete."
	@echo "Reports:"
	@echo "  $(DATASET_STATISTICS_MD)"
	@echo "  $(DATASET_QUALITY_MD)"
	@echo "  $(DATASET_SUBWORD_STATS_JSON)"
	@echo "  $(CURATION_STATE_JSON)"
	@echo "  $(DATASET_TSV_DIR)/"

prepare-dataset-release: sync-label-map validate-labels validate-jsonl-format validate-dataset-splits dataset-statistics materialize-dataset-tsv-quiet
	@echo "Preparing release metadata for $(DATASET_RELEASE_ID) from $(DATASET_SOURCE_DIR)."
	$(PYTHON) -m lib.prepare_dataset_release --dataset-source-dir "$(DATASET_SOURCE_DIR)" --release-id "$(DATASET_RELEASE_ID)" --version "$(DATASET_REVISION)" --repo-id "$(DATASET)" --status "$(DATASET_RELEASE_STATUS)" --hf-release-files "$(HF_RELEASE_FILES)" --git-release-files "$(GIT_RELEASE_FILES)" $(ARGS)
	@echo "Next step:"
	@echo "  # Inspect the release metadata and staged dataset payload."
	@echo "  make publish-dataset ARGS=\"--dry-run\""

finalize-dataset-release:
	@echo "Recording Hugging Face publication metadata for $(DATASET_RELEASE_ID)."
	$(if $(strip $(HF_COMMIT_SHA)),,$(error HF_COMMIT_SHA is required, e.g. make finalize-dataset-release HF_COMMIT_SHA=<40-character-hf-commit-sha>))
	$(PYTHON) -m lib.finalize_dataset_release --dataset-source-dir "$(DATASET_SOURCE_DIR)" --release-id "$(DATASET_RELEASE_ID)" --version "$(DATASET_REVISION)" --repo-id "$(DATASET)" --hf-revision "$(DATASET_REVISION)" --hf-release-files "$(HF_RELEASE_FILES)" --git-release-files "$(GIT_RELEASE_FILES)" --hf-commit-sha "$(HF_COMMIT_SHA)" $(if $(strip $(RELEASE_AUDIT_S3_PREFIX)),--audit-s3-prefix "$(RELEASE_AUDIT_S3_PREFIX)",) $(ARGS)
	@echo "Next step:"
	@echo "  # Promote the published release metadata into the immutable Git release projection."
	@echo "  make promote-dataset-release"

promote-dataset-release:
	@echo "Projecting published prerelease $(DATASET_SOURCE_DIR) into immutable $(DATASET_RELEASE_DIR)."
	$(PYTHON) -m lib.promote_dataset_release --source-dir "$(DATASET_SOURCE_DIR)" --release-dir "$(DATASET_RELEASE_DIR)" --release-files "$(GIT_RELEASE_FILES)" $(ARGS)
	@echo "Next step:"
	@echo "  # Commit the immutable final release snapshot."
	@echo "  git add $(DATASET_RELEASE_DIR)"

download-hf-dataset:
	@echo "Materializing pinned Hugging Face dataset $(DATASET) into $(HF_DATASET_LOCAL_DIR)."
	$(if $(strip $(HF_DATASET_COMMIT)),,$(error HF_DATASET_COMMIT is required; set it to the published dataset commit SHA))
	hf download "$(DATASET)" --type dataset --revision "$(HF_DATASET_COMMIT)" --local-dir "$(HF_DATASET_LOCAL_DIR)" --include "data/train.jsonl" --include "data/validation.jsonl" --include "data/test.jsonl" --include "label_map.json" --include "DATASET_STATISTICS.md" --include "README.md"
	@echo "Next step:"
	@echo "  # Compare the pinned HF materialization with the immutable Git release."
	@echo "  make compare-hf-dataset-release"

compare-hf-dataset-release:
	@echo "Comparing pinned HF dataset materialization with $(DATASET_RELEASE_DIR)."
	$(PYTHON) -m lib.compare_dataset_projection --hf-dir "$(HF_DATASET_LOCAL_DIR)" --git-dir "$(DATASET_RELEASE_DIR)" --summary-json "$(HF_DATASET_COMPARE_SUMMARY_JSON)" $(ARGS)
	@echo "Comparison summary: $(HF_DATASET_COMPARE_SUMMARY_JSON)"

validate-dataset-splits:
	@echo "Checking train/validation/test split integrity, including promoted snippet rows."
	$(PYTHON) -m lib.validate_dataset_splits --train "$(TRAIN_JSONL)" --validation "$(VALIDATION_JSONL)" --test "$(TEST_JSONL)" --snippet train="$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --snippet train="$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --snippet validation="$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --snippet validation="$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --snippet test="$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --snippet test="$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

validate-jsonl-format:
	@echo "Validating JSONL token, offset, BIO, and entity consistency."
	$(PYTHON) -m lib.validate_jsonl_format $(if $(strip $(JSONL_FORMAT_JSONL)),$(foreach input,$(JSONL_FORMAT_JSONL),--jsonl "$(input)"),--jsonl "$(TRAIN_JSONL)" --jsonl "$(VALIDATION_JSONL)" --jsonl "$(TEST_JSONL)") --summary-json "$(JSONL_FORMAT_SUMMARY_JSON)" $(if $(filter true,$(JSONL_FORMAT_ALLOW_TOKEN_LABEL_IDS)),--allow-token-label-ids,) $(ARGS)
	@echo "Summary: $(JSONL_FORMAT_SUMMARY_JSON)"

sync-label-map:
	@echo "Deriving label_map.json from minimal train/validation/test token_labels."
	$(PYTHON) -m lib.sync_label_map --input-jsonl "$(TRAIN_JSONL)" --input-jsonl "$(VALIDATION_JSONL)" --input-jsonl "$(TEST_JSONL)" --output "$(LABEL_MAP)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --label-metadata "$(NEWSPAPER_LABEL_METADATA)" $(ARGS)

maybe-sync-label-map:
	$(if $(filter true,$(TRAIN_SYNC_LABEL_MAP)),$(MAKE) sync-label-map,)

dataset-statistics:
	@echo "Generating the Markdown dataset statistics report from train/validation/test."
	$(PYTHON) -m lib.dataset_statistics --train "$(TRAIN_JSONL)" --validation "$(VALIDATION_JSONL)" --test "$(TEST_JSONL)" --output "$(DATASET_STATISTICS_MD)" --release "$(DATASET_REVISION)" $(ARGS)
	@echo "Report: $(DATASET_STATISTICS_MD)"

dataset-quality-analysis: dataset-statistics curation-eval-validation curation-eval-test
	@echo "Analyzing current validation/test quality and per-entity test coverage."
	$(PYTHON) -m lib.dataset_quality_report --train "$(TRAIN_JSONL)" --validation "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --validation-metrics "$(CURATION_OUTPUT_DIR)/eval/validation_metrics.json" --test "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --test-metrics "$(CURATION_OUTPUT_DIR)/eval/test_metrics.json" --output "$(DATASET_QUALITY_MD)" --test-entity-predictions-tsv "$(DATASET_ENTITY_PREDICTIONS_TSV)" --release "$(DATASET_REVISION)" --model "$(CURATION_MODEL)" $(ARGS)
	@echo "Report: $(DATASET_QUALITY_MD)"
	@echo "Detailed test entity predictions: $(DATASET_ENTITY_PREDICTIONS_TSV)"

audit-predicted-iob:
	@echo "Auditing illegal BIO transitions in $(PREDICTED_IOB_SPLIT) word-level predictions."
	@test -f "$(PREDICTED_IOB_TOKEN_PREDICTIONS)" || { echo "Missing token prediction TSV: $(PREDICTED_IOB_TOKEN_PREDICTIONS)"; echo "Next step:"; echo "  # Generate token diagnostics for this split."; echo "  make curation-eval-$(PREDICTED_IOB_SPLIT)"; exit 1; }
	$(PYTHON) -m lib.audit_predicted_iob --token-predictions "$(PREDICTED_IOB_TOKEN_PREDICTIONS)" --summary-json "$(PREDICTED_IOB_SUMMARY_JSON)" --violations-tsv "$(PREDICTED_IOB_VIOLATIONS_TSV)" $(ARGS)
	@echo "Summary: $(PREDICTED_IOB_SUMMARY_JSON)"
	@echo "Violations: $(PREDICTED_IOB_VIOLATIONS_TSV)"

audit-subtokens:
	@echo "Auditing subtoken prediction consistency in $(SUBTOKEN_AUDIT_SPLIT) diagnostics."
	@test -f "$(SUBTOKEN_AUDIT_PREDICTIONS)" || { echo "Missing subtoken prediction TSV: $(SUBTOKEN_AUDIT_PREDICTIONS)"; echo "Next step:"; echo "  # Generate subtoken diagnostics for this split."; echo "  make curation-eval-$(SUBTOKEN_AUDIT_SPLIT)"; exit 1; }
	$(PYTHON) -m lib.audit_subtoken_predictions --subtoken-predictions "$(SUBTOKEN_AUDIT_PREDICTIONS)" --summary-json "$(SUBTOKEN_AUDIT_SUMMARY_JSON)" --details-tsv "$(SUBTOKEN_AUDIT_DETAILS_TSV)" $(ARGS)
	@echo "Summary: $(SUBTOKEN_AUDIT_SUMMARY_JSON)"
	@echo "Details: $(SUBTOKEN_AUDIT_DETAILS_TSV)"

dataset-subword-stats:
	@echo "Collecting tokenizer subword and fixed-window coverage statistics for train/validation/test."
	$(PYTHON) -m lib.dataset_subword_stats --tokenizer "$(DATASET_SUBWORD_STATS_TOKENIZER)" --split train="$(TRAIN_JSONL)" --split validation="$(VALIDATION_JSONL)" --split test="$(TEST_JSONL)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" $(foreach length,$(DATASET_SUBWORD_STATS_SEQUENCE_LENGTHS),--sequence-length "$(length)") --output-json "$(DATASET_SUBWORD_STATS_JSON)" $(ARGS)
	@echo "Report: $(DATASET_SUBWORD_STATS_JSON)"

materialize-dataset-tsv-quiet:
	@$(PYTHON) -m lib.materialize_dataset_tsv --input "$(TRAIN_JSONL)" --output "$(DATASET_TSV_TRAIN)" --split train >/dev/null
	@$(PYTHON) -m lib.materialize_dataset_tsv --input "$(VALIDATION_JSONL)" --output "$(DATASET_TSV_VALIDATION)" --split validation >/dev/null
	@$(PYTHON) -m lib.materialize_dataset_tsv --input "$(TEST_JSONL)" --output "$(DATASET_TSV_TEST)" --split test >/dev/null

materialize-dataset-tsv: materialize-dataset-tsv-quiet
	@echo "Materialized CoNLL-style TSV views under $(DATASET_TSV_DIR)."
	@echo "Next step: compare against $(DATASET_TSV_COMPARE_VERSION)."
	@echo "  diff -u $(DATASET_TSV_COMPARE_TRAIN) $(DATASET_TSV_TRAIN)"
	@echo "  diff -u $(DATASET_TSV_COMPARE_VALIDATION) $(DATASET_TSV_VALIDATION)"
	@echo "  diff -u $(DATASET_TSV_COMPARE_TEST) $(DATASET_TSV_TEST)"

$(DATASET_TSV_TRAIN): $(TRAIN_JSONL)
	@echo "Materializing train JSONL as TOKEN/NERTAG TSV."
	$(PYTHON) -m lib.materialize_dataset_tsv --input "$<" --output "$@" --split train

$(DATASET_TSV_VALIDATION): $(VALIDATION_JSONL)
	@echo "Materializing validation JSONL as TOKEN/NERTAG TSV."
	$(PYTHON) -m lib.materialize_dataset_tsv --input "$<" --output "$@" --split validation

$(DATASET_TSV_TEST): $(TEST_JSONL)
	@echo "Materializing test JSONL as TOKEN/NERTAG TSV."
	$(PYTHON) -m lib.materialize_dataset_tsv --input "$<" --output "$@" --split test

annotation-stats:
	@echo "Summarizing annotation coverage by label and language across train/validation/test and snippet splits."
	$(PYTHON) -m lib.annotation_stats --target-per-label "$(ANNOTATION_TARGET_PER_LABEL)" --main-languages $(ANNOTATION_MAIN_LANGS) --side-languages $(ANNOTATION_SIDE_LANGS) --main-target-per-label-language "$(ANNOTATION_MAIN_TARGET_PER_LABEL_LANG)" --side-target-per-label-language "$(ANNOTATION_SIDE_TARGET_PER_LABEL_LANG)" $(foreach target,$(ANNOTATION_LANGUAGE_TARGETS),--language-target "$(target)") --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --dataset-jsonl "$(TRAIN_JSONL)" --dataset-jsonl "$(VALIDATION_JSONL)" --dataset-jsonl "$(TEST_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" --newsagency-reviewed-jsonl "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --radiostation-reviewed-jsonl "$(RADIOSTATION_REVIEWED_SNIPPETS)" --json-output "$(ANNOTATION_STATS_JSON)" --tsv-output "$(ANNOTATION_STATS_TSV)" $(ARGS)

mention-profiles:
	@echo "Building empirical mention-surface profiles for canonical entity labels."
	$(PYTHON) -m lib.entity_mention_profiles $(foreach input,$(MENTION_PROFILE_JSONL),--input-jsonl "$(input)") --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --top-n "$(MENTION_PROFILE_TOP_N)" --json-output "$(MENTION_PROFILE_JSON)" --tsv-output "$(MENTION_PROFILE_TSV)" --md-output "$(MENTION_PROFILE_MD)" $(ARGS)
	$(PYTHON) -m lib.entity_mention_profiles --input-jsonl "train=$(TRAIN_JSONL)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --top-n "$(MENTION_PROFILE_TOP_N)" --md-output "$(MENTION_PROFILE_TRAIN_MD)" $(ARGS)
	$(PYTHON) -m lib.entity_mention_profiles --input-jsonl "validation=$(VALIDATION_JSONL)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --top-n "$(MENTION_PROFILE_TOP_N)" --md-output "$(MENTION_PROFILE_VALIDATION_MD)" $(ARGS)
	$(PYTHON) -m lib.entity_mention_profiles --input-jsonl "test=$(TEST_JSONL)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --top-n "$(MENTION_PROFILE_TOP_N)" --md-output "$(MENTION_PROFILE_TEST_MD)" $(ARGS)

entity-surface-frequencies:
	@test -n "$(ENTITY_LABEL)" || { echo "ENTITY_LABEL is required, e.g. ENTITY_LABEL=org.ent.pressagency.havas"; exit 1; }
	@$(PYTHON) -m lib.entity_surface_frequencies --label "$(ENTITY_LABEL)" $(foreach input,$(MENTION_PROFILE_JSONL),--input-jsonl "$(input)") --include-examples "$(ENTITY_SURFACE_FREQUENCIES_EXAMPLES)" $(ARGS)

audit-seed-alias-matches:
	@echo "Auditing seed alias matcher hits against current train/validation/test annotations."
	$(PYTHON) -m lib.audit_seed_alias_matches --split train="$(TRAIN_JSONL)" --split validation="$(VALIDATION_JSONL)" --split test="$(TEST_JSONL)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --details-tsv "$(SEED_ALIAS_AUDIT_DETAILS_TSV)" --summary-json "$(SEED_ALIAS_AUDIT_SUMMARY_JSON)" --report-md "$(SEED_ALIAS_AUDIT_MD)" --context-chars "$(SEED_ALIAS_AUDIT_CONTEXT_CHARS)" --example-limit "$(SEED_ALIAS_AUDIT_EXAMPLE_LIMIT)" $(ARGS)

curation-dashboard:
	@echo "Running the read-only curation dashboard: coverage, profiles, curation state, snippet state, disagreement state, and dataset state."
	$(MAKE) annotation-stats
	$(MAKE) mention-profiles
	$(MAKE) curation-state
	$(MAKE) snippet-state
	$(MAKE) eval-disagreement-state
	$(MAKE) dataset-state

anno-housekeeping:
	@echo "Running complete non-interactive housekeeping for annotation and curation state."
	$(MAKE) validate-labels
	$(MAKE) annotation-stats
	$(MAKE) mention-profiles
	@if [ -f "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" ] && [ -f "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" ]; then \
		$(PYTHON) -m lib.validate_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --no-require-complete; \
	else \
		echo "Disagreement decision validation: skipped (no complete queue/decision file pair)."; \
	fi
	$(MAKE) curation-state-json
	$(MAKE) curation-state
	@echo "Annotation housekeeping complete."
	@echo "Reports:"
	@echo "  $(ANNOTATION_STATS_JSON)"
	@echo "  $(ANNOTATION_STATS_TSV)"
	@echo "  $(MENTION_PROFILE_MD)"
	@echo "  $(MENTION_PROFILE_TRAIN_MD)"
	@echo "  $(MENTION_PROFILE_VALIDATION_MD)"
	@echo "  $(MENTION_PROFILE_TEST_MD)"
	@echo "  $(MENTION_PROFILE_JSON)"
	@echo "  $(MENTION_PROFILE_TSV)"
	@echo "  $(CURATION_STATE_JSON)"

curation-state:
	@echo "Summarizing all curation, snippet, and dataset state."
	$(PYTHON) -m lib.curation_state --section all --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-validation-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-validation-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

curation-state-json:
	@echo "Writing a JSON snapshot of all curation, snippet, and dataset state."
	$(PYTHON) -m lib.curation_state --section all --json-output "$(CURATION_STATE_JSON)" --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-validation-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-validation-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

snippet-state:
	@echo "Summarizing sampled, suggested, reviewed, and split snippet curation state."
	$(PYTHON) -m lib.curation_state --section snippets --dataset-source-dir "$(DATASET_SOURCE_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-validation-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-validation-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

dataset-state:
	@echo "Summarizing configured dataset source, staging, and publication state."
	$(PYTHON) -m lib.curation_state --section dataset --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" $(ARGS)

eval-disagreement-state:
	@echo "Summarizing HIPE-derived evaluation disagreement curation state."
	$(PYTHON) -m lib.curation_state --section legacy --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" $(ARGS)

audit-empty-training-docs:
	@echo "Auditing train, validation, and test documents with no gold entities using $(EMPTY_DOC_MODEL)."
	$(MAKE) audit-empty-docs-split EMPTY_DOC_SPLIT=train
	$(MAKE) audit-empty-docs-split EMPTY_DOC_SPLIT=validation
	$(MAKE) audit-empty-docs-split EMPTY_DOC_SPLIT=test
	@echo "Next step:"
	@echo "  # Review one split's concrete span patches."
	@echo "  make review-span-patches EMPTY_DOC_SPLIT=train REVIEWER=\"$$USER\""

audit-empty-docs-split:
	@echo "Auditing empty-gold $(EMPTY_DOC_SPLIT) documents for suspicious missed media-source mentions."
	$(PYTHON) -m lib.audit_empty_training_docs prepare --input-jsonl "$(EMPTY_DOC_SOURCE_JSONL)" --label-map "$(EMPTY_DOC_LABEL_MAP)" --output-jsonl "$(EMPTY_DOC_AUDIT_DIR)/eval_input.jsonl" --summary-json "$(EMPTY_DOC_AUDIT_DIR)/prepare_summary.json"
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(EMPTY_DOC_MODEL)" --use-checkpoint-label-map --eval-jsonl "$(EMPTY_DOC_AUDIT_DIR)/eval_input.jsonl" --label-map "$(EMPTY_DOC_LABEL_MAP)" --output-dir "$(EMPTY_DOC_AUDIT_DIR)/eval" --split-name empty_docs --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	$(PYTHON) -m lib.audit_empty_training_docs summarize --source-jsonl "$(EMPTY_DOC_AUDIT_DIR)/eval_input.jsonl" --predictions-jsonl "$(EMPTY_DOC_AUDIT_DIR)/eval/empty_docs_predictions.jsonl" --candidates-jsonl "$(EMPTY_DOC_AUDIT_DIR)/prediction_candidates.jsonl" --candidates-tsv "$(EMPTY_DOC_AUDIT_DIR)/prediction_candidates.tsv" --summary-json "$(EMPTY_DOC_AUDIT_DIR)/prediction_summary.json"

audit-missing-spans:
	@echo "Building a target-specific missing-span audit queue for $(MISSING_SPAN_TARGET_LABEL) in $(MISSING_SPAN_SPLIT)."
	@test -n "$(MISSING_SPAN_TARGET_LABEL)" || { echo "MISSING_SPAN_TARGET_LABEL is required, e.g. MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata"; exit 1; }
	$(PYTHON) -m lib.audit_missing_spans --input-jsonl "$(MISSING_SPAN_SOURCE_JSONL)" --predictions-jsonl "$(MISSING_SPAN_PREDICTIONS_JSONL)" --target-label "$(MISSING_SPAN_TARGET_LABEL)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --audit-id "$(MISSING_SPAN_AUDIT_ID)" --split "$(MISSING_SPAN_SPLIT)" --candidates-jsonl "$(MISSING_SPAN_CANDIDATES)" --candidates-tsv "$(MISSING_SPAN_CANDIDATES_TSV)" --summary-json "$(MISSING_SPAN_SUMMARY_JSON)" $(ARGS)
	@echo "Next step:"
	@echo "  # Review the missing-span queue."
	@echo "  make review-missing-spans MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT) REVIEWER=\"$$USER\""

review-missing-spans:
	@echo "Reviewing target-specific missing-span suggestions and writing append-only decisions."
	@test -n "$(MISSING_SPAN_TARGET_LABEL)" || { echo "MISSING_SPAN_TARGET_LABEL is required, e.g. MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata"; exit 1; }
	$(PYTHON) -m lib.span_patch_review --candidates "$(MISSING_SPAN_CANDIDATES)" --decisions "$(MISSING_SPAN_DECISIONS)" --audit-id "$(MISSING_SPAN_AUDIT_ID)" --reviewer "$(REVIEWER)" --target-label "$(MISSING_SPAN_TARGET_LABEL)" --limit "$(REVIEW_MAX_ITEMS)" --summary-json "$(MISSING_SPAN_REVIEW_SUMMARY_JSON)" --queue-jsonl "$(MISSING_SPAN_QUEUE_JSONL)" $(ARGS)
	@echo "Next steps:"
	@echo "  # Apply accepted missing-span decisions to a patched split."
	@echo "  make apply-missing-spans MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT)"
	@echo "  # Apply accepted decisions and promote the patched split directly."
	@echo "  make integrate-missing-spans MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT)"

apply-missing-spans:
	@echo "Applying reviewed missing-span decisions to the configured split."
	@test -n "$(MISSING_SPAN_TARGET_LABEL)" || { echo "MISSING_SPAN_TARGET_LABEL is required, e.g. MISSING_SPAN_TARGET_LABEL=org.ent.pressagency.ata"; exit 1; }
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(MISSING_SPAN_SOURCE_JSONL)" --output-jsonl "$(MISSING_SPAN_OUTPUT_JSONL)" --candidates "$(MISSING_SPAN_CANDIDATES)" --decisions "$(MISSING_SPAN_DECISIONS)" --audit-id "$(MISSING_SPAN_AUDIT_ID)" --target-label "$(MISSING_SPAN_TARGET_LABEL)" --changes-jsonl "$(MISSING_SPAN_CHANGES_JSONL)" --changes-tsv "$(MISSING_SPAN_CHANGES_TSV)" --summary-json "$(MISSING_SPAN_APPLY_SUMMARY_JSON)" $(ARGS)
	@echo "Next steps:"
	@echo "  # Check whether the patched split is ready for promotion."
	@echo "  make missing-span-status MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT)"
	@echo "  # Promote the patched split."
	@echo "  make promote-missing-spans MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT)"

missing-span-status:
	@echo "Checking whether the missing-span patched output is ready for promotion."
	@echo "audit id:        $(MISSING_SPAN_AUDIT_ID)"
	@echo "target label:    $(MISSING_SPAN_TARGET_LABEL)"
	@echo "source split:    $(MISSING_SPAN_SOURCE_JSONL)"
	@echo "patched output:  $(MISSING_SPAN_OUTPUT_JSONL)"
	@echo "promote target:  $(MISSING_SPAN_PROMOTE_JSONL)"
	@test -f "$(MISSING_SPAN_OUTPUT_JSONL)" || { echo "patched output:  missing; run make apply-missing-spans first"; exit 1; }
	@test -f "$(MISSING_SPAN_PROMOTE_JSONL)" || { echo "promote target:  missing"; exit 1; }
	@if cmp -s "$(MISSING_SPAN_OUTPUT_JSONL)" "$(MISSING_SPAN_PROMOTE_JSONL)"; then \
		echo "state:           promoted target is up to date"; \
	else \
		echo "state:           patched output differs from promote target"; \
		echo "Next step:"; \
		echo "  # Promote the patched split."; \
		echo "  make promote-missing-spans MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT)"; \
		echo "  # Or apply reviewed decisions and promote in one command."; \
		echo "  make integrate-missing-spans MISSING_SPAN_TARGET_LABEL=$(MISSING_SPAN_TARGET_LABEL) MISSING_SPAN_SPLIT=$(MISSING_SPAN_SPLIT)"; \
	fi

promote-missing-spans:
	@echo "Promoting the missing-span patched split into the configured source split."
	@test -f "$(MISSING_SPAN_OUTPUT_JSONL)" || { echo "Missing patched output: $(MISSING_SPAN_OUTPUT_JSONL). Run make apply-missing-spans first."; exit 1; }
	@echo "Promoting $(MISSING_SPAN_OUTPUT_JSONL) -> $(MISSING_SPAN_PROMOTE_JSONL)"
	cp "$(MISSING_SPAN_OUTPUT_JSONL)" "$(MISSING_SPAN_PROMOTE_JSONL)"
	$(MAKE) validate-dataset-splits

integrate-missing-spans: apply-missing-spans promote-missing-spans
	@echo "Missing-span integration complete."

audit-existing-spans:
	@echo "Building a boundary/label/removal audit queue for existing spans of $(SPAN_BOUNDARY_TARGET_LABEL) in $(SPAN_BOUNDARY_SPLIT_KEY)."
	@test -n "$(SPAN_BOUNDARY_TARGET_LABEL)" || { echo "SPAN_BOUNDARY_TARGET_LABEL is required, e.g. SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas"; exit 1; }
	@test "$(SPAN_BOUNDARY_SPLIT_KEY)" = "train" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "validation" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "test" || { echo "SPAN_BOUNDARY_SPLIT must be train, validation/dev, or test"; exit 1; }
	$(PYTHON) -m lib.audit_existing_spans --input-jsonl "$(SPAN_BOUNDARY_SOURCE_JSONL)" --target-label "$(SPAN_BOUNDARY_TARGET_LABEL)" --audit-id "$(SPAN_BOUNDARY_AUDIT_ID)" --candidates-jsonl "$(SPAN_BOUNDARY_CANDIDATES)" --candidates-tsv "$(SPAN_BOUNDARY_CANDIDATES_TSV)" --summary-json "$(SPAN_BOUNDARY_SUMMARY_JSON)" --limit "$(SPAN_BOUNDARY_AUDIT_LIMIT)" $(ARGS)
	@echo "Next step:"
	@echo "  # Review existing-span boundary candidates."
	@echo "  make review-existing-spans SPAN_BOUNDARY_TARGET_LABEL=$(SPAN_BOUNDARY_TARGET_LABEL) SPAN_BOUNDARY_SPLIT=$(SPAN_BOUNDARY_SPLIT_KEY) REVIEWER=\"$$USER\""

review-existing-spans:
	@echo "Reviewing existing-span audit candidates and writing append-only decisions."
	@test -n "$(SPAN_BOUNDARY_TARGET_LABEL)" || { echo "SPAN_BOUNDARY_TARGET_LABEL is required, e.g. SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas"; exit 1; }
	@test "$(SPAN_BOUNDARY_SPLIT_KEY)" = "train" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "validation" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "test" || { echo "SPAN_BOUNDARY_SPLIT must be train, validation/dev, or test"; exit 1; }
	$(PYTHON) -m lib.span_patch_review --candidates "$(SPAN_BOUNDARY_CANDIDATES)" --decisions "$(SPAN_BOUNDARY_DECISIONS)" --audit-id "$(SPAN_BOUNDARY_AUDIT_ID)" --reviewer "$(REVIEWER)" --target-label "$(SPAN_BOUNDARY_TARGET_LABEL)" --limit "$(REVIEW_MAX_ITEMS)" --summary-json "$(SPAN_BOUNDARY_REVIEW_SUMMARY_JSON)" --queue-jsonl "$(SPAN_BOUNDARY_QUEUE_JSONL)" $(ARGS)
	@echo "Next step:"
	@echo "  # Apply reviewed existing-span decisions."
	@echo "  make apply-existing-spans SPAN_BOUNDARY_TARGET_LABEL=$(SPAN_BOUNDARY_TARGET_LABEL) SPAN_BOUNDARY_SPLIT=$(SPAN_BOUNDARY_SPLIT_KEY)"

apply-existing-spans:
	@echo "Applying reviewed existing-span decisions to a patched split."
	@test -n "$(SPAN_BOUNDARY_TARGET_LABEL)" || { echo "SPAN_BOUNDARY_TARGET_LABEL is required, e.g. SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas"; exit 1; }
	@test "$(SPAN_BOUNDARY_SPLIT_KEY)" = "train" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "validation" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "test" || { echo "SPAN_BOUNDARY_SPLIT must be train, validation/dev, or test"; exit 1; }
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(SPAN_BOUNDARY_SOURCE_JSONL)" --output-jsonl "$(SPAN_BOUNDARY_OUTPUT_JSONL)" --candidates "$(SPAN_BOUNDARY_CANDIDATES)" --decisions "$(SPAN_BOUNDARY_DECISIONS)" --audit-id "$(SPAN_BOUNDARY_AUDIT_ID)" --target-label "$(SPAN_BOUNDARY_TARGET_LABEL)" --changes-jsonl "$(SPAN_BOUNDARY_CHANGES_JSONL)" --changes-tsv "$(SPAN_BOUNDARY_CHANGES_TSV)" --summary-json "$(SPAN_BOUNDARY_APPLY_SUMMARY_JSON)" --replace-overlaps $(ARGS)
	@echo "Next step:"
	@echo "  # Check whether the patched split is ready for promotion."
	@echo "  make existing-span-status SPAN_BOUNDARY_TARGET_LABEL=$(SPAN_BOUNDARY_TARGET_LABEL) SPAN_BOUNDARY_SPLIT=$(SPAN_BOUNDARY_SPLIT_KEY)"

existing-span-status:
	@echo "Checking whether the existing-span patched output is ready for promotion."
	@test "$(SPAN_BOUNDARY_SPLIT_KEY)" = "train" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "validation" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "test" || { echo "SPAN_BOUNDARY_SPLIT must be train, validation/dev, or test"; exit 1; }
	@echo "audit id:        $(SPAN_BOUNDARY_AUDIT_ID)"
	@echo "target label:    $(SPAN_BOUNDARY_TARGET_LABEL)"
	@echo "split:           $(SPAN_BOUNDARY_SPLIT_KEY)"
	@echo "source split:    $(SPAN_BOUNDARY_SOURCE_JSONL)"
	@echo "patched output:  $(SPAN_BOUNDARY_OUTPUT_JSONL)"
	@echo "promote target:  $(SPAN_BOUNDARY_PROMOTE_JSONL)"
	@test -f "$(SPAN_BOUNDARY_OUTPUT_JSONL)" || { echo "patched output:  missing; run make apply-existing-spans first"; exit 1; }
	@test -f "$(SPAN_BOUNDARY_PROMOTE_JSONL)" || { echo "promote target:  missing"; exit 1; }
	@if cmp -s "$(SPAN_BOUNDARY_OUTPUT_JSONL)" "$(SPAN_BOUNDARY_PROMOTE_JSONL)"; then \
		echo "state:           promoted target is up to date"; \
	else \
		echo "state:           patched output differs from promote target"; \
		echo "Next step:"; \
		echo "  # Promote the patched split."; \
		echo "  make promote-existing-spans SPAN_BOUNDARY_TARGET_LABEL=$(SPAN_BOUNDARY_TARGET_LABEL) SPAN_BOUNDARY_SPLIT=$(SPAN_BOUNDARY_SPLIT_KEY)"; \
		echo "  # Or apply reviewed decisions and promote in one command."; \
		echo "  make integrate-existing-spans SPAN_BOUNDARY_TARGET_LABEL=$(SPAN_BOUNDARY_TARGET_LABEL) SPAN_BOUNDARY_SPLIT=$(SPAN_BOUNDARY_SPLIT_KEY)"; \
	fi

promote-existing-spans:
	@echo "Promoting the existing-span patched split into the configured source split."
	@test "$(SPAN_BOUNDARY_SPLIT_KEY)" = "train" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "validation" -o "$(SPAN_BOUNDARY_SPLIT_KEY)" = "test" || { echo "SPAN_BOUNDARY_SPLIT must be train, validation/dev, or test"; exit 1; }
	@test -f "$(SPAN_BOUNDARY_OUTPUT_JSONL)" || { echo "Missing patched output: $(SPAN_BOUNDARY_OUTPUT_JSONL). Run make apply-existing-spans first."; exit 1; }
	@echo "Promoting $(SPAN_BOUNDARY_OUTPUT_JSONL) -> $(SPAN_BOUNDARY_PROMOTE_JSONL)"
	cp "$(SPAN_BOUNDARY_OUTPUT_JSONL)" "$(SPAN_BOUNDARY_PROMOTE_JSONL)"
	$(MAKE) validate-dataset-splits

integrate-existing-spans: apply-existing-spans promote-existing-spans
	@echo "Existing-span integration complete."

audit-agency-word-boundaries:
	@echo "Building accepted agency-word boundary migration patches for $(AGENCY_WORD_SPLIT_KEY)."
	@test "$(AGENCY_WORD_SPLIT_KEY)" = "train" -o "$(AGENCY_WORD_SPLIT_KEY)" = "validation" -o "$(AGENCY_WORD_SPLIT_KEY)" = "test" || { echo "AGENCY_WORD_SPLIT must be train, validation/dev, or test"; exit 1; }
	@test -n "$(REVIEWER)" || { echo "REVIEWER is required, e.g. REVIEWER=\"$$USER\""; exit 1; }
	$(PYTHON) -m lib.audit_agency_word_boundaries --input-jsonl "$(AGENCY_WORD_SOURCE_JSONL)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --audit-id "$(AGENCY_WORD_AUDIT_ID)" --split "$(AGENCY_WORD_SPLIT_KEY)" --reviewer "$(REVIEWER)" --candidates-jsonl "$(AGENCY_WORD_CANDIDATES)" --decisions-jsonl "$(AGENCY_WORD_DECISIONS)" --changes-jsonl "$(AGENCY_WORD_PREVIEW_JSONL)" --changes-tsv "$(AGENCY_WORD_PREVIEW_TSV)" --summary-json "$(AGENCY_WORD_SUMMARY_JSON)" $(ARGS)
	@echo "Next step:"
	@echo "  # Inspect proposed boundary changes before applying."
	@echo "  less $(AGENCY_WORD_PREVIEW_TSV)"
	@echo "  # Apply accepted migration patches to a patched split."
	@echo "  make apply-agency-word-boundaries AGENCY_WORD_SPLIT=$(AGENCY_WORD_SPLIT_KEY)"

apply-agency-word-boundaries:
	@echo "Applying agency-word boundary migration patches to $(AGENCY_WORD_SPLIT_KEY)."
	@test "$(AGENCY_WORD_SPLIT_KEY)" = "train" -o "$(AGENCY_WORD_SPLIT_KEY)" = "validation" -o "$(AGENCY_WORD_SPLIT_KEY)" = "test" || { echo "AGENCY_WORD_SPLIT must be train, validation/dev, or test"; exit 1; }
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(AGENCY_WORD_SOURCE_JSONL)" --output-jsonl "$(AGENCY_WORD_OUTPUT_JSONL)" --candidates "$(AGENCY_WORD_CANDIDATES)" --decisions "$(AGENCY_WORD_DECISIONS)" --audit-id "$(AGENCY_WORD_AUDIT_ID)" --target-label "" --changes-jsonl "$(AGENCY_WORD_CHANGES_JSONL)" --changes-tsv "$(AGENCY_WORD_CHANGES_TSV)" --summary-json "$(AGENCY_WORD_APPLY_SUMMARY_JSON)" --replace-overlaps $(ARGS)
	@echo "Next step:"
	@echo "  # Check whether the patched split is ready for promotion."
	@echo "  make agency-word-boundary-status AGENCY_WORD_SPLIT=$(AGENCY_WORD_SPLIT_KEY)"

agency-word-boundary-status:
	@echo "Checking whether agency-word boundary migration output is ready for promotion."
	@test "$(AGENCY_WORD_SPLIT_KEY)" = "train" -o "$(AGENCY_WORD_SPLIT_KEY)" = "validation" -o "$(AGENCY_WORD_SPLIT_KEY)" = "test" || { echo "AGENCY_WORD_SPLIT must be train, validation/dev, or test"; exit 1; }
	@echo "audit id:        $(AGENCY_WORD_AUDIT_ID)"
	@echo "split:           $(AGENCY_WORD_SPLIT_KEY)"
	@echo "source split:    $(AGENCY_WORD_SOURCE_JSONL)"
	@echo "patched output:  $(AGENCY_WORD_OUTPUT_JSONL)"
	@echo "promote target:  $(AGENCY_WORD_PROMOTE_JSONL)"
	@test -f "$(AGENCY_WORD_OUTPUT_JSONL)" || { echo "patched output:  missing; run make apply-agency-word-boundaries first"; exit 1; }
	@test -f "$(AGENCY_WORD_PROMOTE_JSONL)" || { echo "promote target:  missing"; exit 1; }
	@if cmp -s "$(AGENCY_WORD_OUTPUT_JSONL)" "$(AGENCY_WORD_PROMOTE_JSONL)"; then \
		echo "state:           promoted target is up to date"; \
	else \
		echo "state:           patched output differs from promote target"; \
		echo "Next step:"; \
		echo "  # Promote the patched split."; \
		echo "  make promote-agency-word-boundaries AGENCY_WORD_SPLIT=$(AGENCY_WORD_SPLIT_KEY)"; \
	fi

promote-agency-word-boundaries:
	@echo "Promoting agency-word boundary migration output into $(AGENCY_WORD_SPLIT_KEY)."
	@test "$(AGENCY_WORD_SPLIT_KEY)" = "train" -o "$(AGENCY_WORD_SPLIT_KEY)" = "validation" -o "$(AGENCY_WORD_SPLIT_KEY)" = "test" || { echo "AGENCY_WORD_SPLIT must be train, validation/dev, or test"; exit 1; }
	@test -f "$(AGENCY_WORD_OUTPUT_JSONL)" || { echo "Missing patched output: $(AGENCY_WORD_OUTPUT_JSONL). Run make apply-agency-word-boundaries first."; exit 1; }
	@echo "Promoting $(AGENCY_WORD_OUTPUT_JSONL) -> $(AGENCY_WORD_PROMOTE_JSONL)"
	cp "$(AGENCY_WORD_OUTPUT_JSONL)" "$(AGENCY_WORD_PROMOTE_JSONL)"
	$(MAKE) validate-dataset-splits

integrate-agency-word-boundaries: apply-agency-word-boundaries promote-agency-word-boundaries
	@echo "Agency-word boundary migration complete for $(AGENCY_WORD_SPLIT_KEY)."

review-span-patches:
	@echo "Reviewing audit-suggested span patches and writing append-only decisions."
	$(PYTHON) -m lib.span_patch_review --candidates "$(SPAN_PATCH_CANDIDATES)" --decisions "$(SPAN_PATCH_DECISIONS)" --audit-id "$(SPAN_PATCH_AUDIT_ID)" --reviewer "$(REVIEWER)" --target-label "$(SPAN_PATCH_TARGET_LABEL)" --limit "$(REVIEW_MAX_ITEMS)" --summary-json "$(SPAN_PATCH_SUMMARY_JSON)" --queue-jsonl "$(SPAN_PATCH_QUEUE_JSONL)" $(ARGS)
	@echo "Next step:"
	@echo "  # Apply accepted or corrected span patches."
	@echo "  make apply-span-patches EMPTY_DOC_SPLIT=$(EMPTY_DOC_SPLIT)"

apply-span-patches:
	@echo "Applying accepted or corrected span-patch decisions to a patched JSONL split."
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(SPAN_PATCH_SOURCE_JSONL)" --output-jsonl "$(SPAN_PATCH_OUTPUT_JSONL)" --candidates "$(SPAN_PATCH_CANDIDATES)" --decisions "$(SPAN_PATCH_DECISIONS)" --audit-id "$(SPAN_PATCH_AUDIT_ID)" --target-label "$(SPAN_PATCH_TARGET_LABEL)" --changes-jsonl "$(SPAN_PATCH_CHANGES_JSONL)" --changes-tsv "$(SPAN_PATCH_CHANGES_TSV)" --summary-json "$(SPAN_PATCH_APPLY_SUMMARY_JSON)" $(ARGS)
	@echo "Next step:"
	@echo "  # Check whether the patched split is ready for promotion."
	@echo "  make span-patch-status EMPTY_DOC_SPLIT=$(EMPTY_DOC_SPLIT)"

span-patch-status:
	@echo "Checking whether the span-patch output is ready for promotion."
	@echo "audit id:        $(SPAN_PATCH_AUDIT_ID)"
	@echo "source split:    $(SPAN_PATCH_SOURCE_JSONL)"
	@echo "patched output:  $(SPAN_PATCH_OUTPUT_JSONL)"
	@echo "promote target:  $(SPAN_PATCH_PROMOTE_JSONL)"
	@test -f "$(SPAN_PATCH_OUTPUT_JSONL)" || { echo "patched output:  missing; run make apply-span-patches first"; exit 1; }
	@test -f "$(SPAN_PATCH_PROMOTE_JSONL)" || { echo "promote target:  missing"; exit 1; }
	@if cmp -s "$(SPAN_PATCH_OUTPUT_JSONL)" "$(SPAN_PATCH_PROMOTE_JSONL)"; then echo "state:           promoted target is up to date"; else echo "state:           patched output differs from promote target"; fi

promote-span-patches:
	@echo "Promoting the span-patch output into the configured prerelease/source split."
	@test -f "$(SPAN_PATCH_OUTPUT_JSONL)" || { echo "Missing patched output: $(SPAN_PATCH_OUTPUT_JSONL). Run make apply-span-patches first."; exit 1; }
	@test -n "$(SPAN_PATCH_PROMOTE_JSONL)" || { echo "SPAN_PATCH_PROMOTE_JSONL is empty"; exit 1; }
	@echo "Promoting $(SPAN_PATCH_OUTPUT_JSONL) -> $(SPAN_PATCH_PROMOTE_JSONL)"
	cp "$(SPAN_PATCH_OUTPUT_JSONL)" "$(SPAN_PATCH_PROMOTE_JSONL)"
	$(MAKE) validate-dataset-splits

integrate-span-patches: apply-span-patches promote-span-patches
	@echo "Span-patch integration complete for $(EMPTY_DOC_SPLIT)."

search-tsv: materialize-dataset-tsv-quiet
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@for split in $(TSV_PATCH_SPLITS); do $(MAKE) $@ TSV_PATCH_SPLIT=$$split || exit $$?; done
else
	@echo "Searching TOKEN/NERTAG TSV for $(if $(strip $(TSV_SEARCH_TAG)),tag $(TSV_SEARCH_TAG),$(TSV_SEARCH)) in $(TSV_SEARCH_TSV)."
	@test -n "$(TSV_SEARCH)$(TSV_SEARCH_TAG)" || { echo "TSV_SEARCH or TSV_SEARCH_TAG is required, e.g. TSV_SEARCH=tan, TSV_SEARCH=\"Radio London\", or TSV_SEARCH_TAG=org.ent.radiostation.deutsche-welle"; exit 1; }
	@set -- "$(TSV_SEARCH)"; $(PYTHON) -m lib.tsv_hit_pager "$(TSV_SEARCH_TSV)" "$$@" $(if $(strip $(TSV_SEARCH_TAG)),--tag "$(TSV_SEARCH_TAG)",) --context "$(TSV_SEARCH_CONTEXT)" --source-jsonl "$(TSV_PATCH_SOURCE_JSONL)" $(if $(filter true,$(TSV_SEARCH_ONLY_O)),--only-O,) $(if $(filter true,$(TSV_SEARCH_NO_PAGER)),--no-pager,) $(if $(filter true,$(TSV_SEARCH_INCLUDE_AUDITED)),--include-audited,)
endif

review-tsv-search: materialize-dataset-tsv-quiet
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@for split in $(TSV_PATCH_SPLITS); do $(MAKE) $@ TSV_PATCH_SPLIT=$$split || exit $$?; done
else
	@echo "Reviewing TOKEN/NERTAG TSV search hits for $(TSV_SEARCH) and creating accepted span patches."
	@test -n "$(TSV_SEARCH)" || { echo "TSV_SEARCH is required, e.g. TSV_SEARCH=tan or TSV_SEARCH=\"Radio London\""; exit 1; }
	@test -n "$(TSV_PATCH_LABEL)" || { echo "TSV_PATCH_LABEL is required, e.g. TSV_PATCH_LABEL=org.ent.pressagency.tanjug"; exit 1; }
	@test -n "$(REVIEWER)" || { echo "REVIEWER is required, e.g. REVIEWER=\"$$USER\""; exit 1; }
	$(PYTHON) -m lib.review_tsv_search --input-jsonl "$(TSV_PATCH_SOURCE_JSONL)" --tsv "$(TSV_SEARCH_TSV)" --candidates "$(TSV_PATCH_CANDIDATES)" --decisions "$(TSV_PATCH_DECISIONS)" --audit-id "$(TSV_PATCH_AUDIT_ID)" --label "$(TSV_PATCH_LABEL)" --reviewer "$(REVIEWER)" --search "$(word 1,$(TSV_SEARCH))" $(if $(word 2,$(TSV_SEARCH)),--search2 "$(word 2,$(TSV_SEARCH))",) --context "$(TSV_SEARCH_CONTEXT)" $(if $(filter true,$(TSV_SEARCH_ONLY_O)),--only-O,) $(if $(filter true,$(TSV_SEARCH_INCLUDE_AUDITED)),--include-audited,) --summary-json "$(TSV_PATCH_SUMMARY_JSON)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --label-metadata "$(NEWSPAPER_LABEL_METADATA)" $(ARGS)
	@echo "Next step:"
	@echo "  # Preview applying and promoting accepted TSV search span patches."
	@echo "  make -n integrate-tsv-span-patches"
endif

replace-tsv-segment:
	@echo "Replacing an exact TOKEN/NERTAG segment in $(TSV_SEGMENT_SPLIT) JSONL."
	@echo "Replacement TSV may use optional '_' as third column to suppress the default following space."
	@test -n "$(TSV_SEGMENT_OLD)" || { echo "TSV_SEGMENT_OLD is required, e.g. TSV_SEGMENT_OLD=/tmp/old.tsv"; exit 1; }
	@test -n "$(TSV_SEGMENT_NEW)" || { echo "TSV_SEGMENT_NEW is required, e.g. TSV_SEGMENT_NEW=/tmp/new.tsv"; exit 1; }
	$(PYTHON) -m lib.replace_tsv_segment --input-jsonl "$(TSV_SEGMENT_SOURCE_JSONL)" --output-jsonl "$(TSV_SEGMENT_OUTPUT_JSONL)" --old-tsv "$(TSV_SEGMENT_OLD)" --new-tsv "$(TSV_SEGMENT_NEW)" $(if $(strip $(TSV_SEGMENT_MATCH_INDEX)),--match-index "$(TSV_SEGMENT_MATCH_INDEX)",) $(if $(filter true,$(TSV_SEGMENT_ALL_MATCHES)),--all-matches,) $(ARGS)
	@echo "Patched output: $(TSV_SEGMENT_OUTPUT_JSONL)"
	@echo "Inspect with:"
	@echo "  git diff --no-index $(TSV_SEGMENT_SOURCE_JSONL) $(TSV_SEGMENT_OUTPUT_JSONL)"

create-tsv-span-patch:
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@echo "Creating accepted manual span patches across $(TSV_PATCH_SPLITS) from one pasted TSV block."
	$(PYTHON) -m lib.create_span_patches_from_tsv --input-jsonl "$(TRAIN_JSONL)" --candidates "audit.d/manual-tsv/manual-tsv-detect/candidates.jsonl" --decisions "data/curated/span-patches/manual-tsv-detect/decisions.jsonl" --audit-id "manual-tsv-detect" --label "$(TSV_PATCH_LABEL)" --reviewer "$(REVIEWER)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --label-metadata "$(NEWSPAPER_LABEL_METADATA)" --allow-no-matches --split-input-jsonl train="$(TRAIN_JSONL)" --split-input-jsonl validation="$(VALIDATION_JSONL)" --split-input-jsonl test="$(TEST_JSONL)" --split-candidates train="audit.d/manual-tsv/manual-tsv-train/candidates.jsonl" --split-candidates validation="audit.d/manual-tsv/manual-tsv-validation/candidates.jsonl" --split-candidates test="audit.d/manual-tsv/manual-tsv-test/candidates.jsonl" --split-decisions train="data/curated/span-patches/manual-tsv-train/decisions.jsonl" --split-decisions validation="data/curated/span-patches/manual-tsv-validation/decisions.jsonl" --split-decisions test="data/curated/span-patches/manual-tsv-test/decisions.jsonl" --split-audit-id train="manual-tsv-train" --split-audit-id validation="manual-tsv-validation" --split-audit-id test="manual-tsv-test" --split-summary-json train="audit.d/manual-tsv/manual-tsv-train/summary.json" --split-summary-json validation="audit.d/manual-tsv/manual-tsv-validation/summary.json" --split-summary-json test="audit.d/manual-tsv/manual-tsv-test/summary.json" $(ARGS)
	@echo "Next step:"
	@echo "  # Apply accepted TSV-derived span patches."
	@echo "  make apply-tsv-span-patches"
else
	@echo "Creating accepted manual span patches from pasted TOKEN OLD [NEW] TSV lines."
	$(PYTHON) -m lib.create_span_patches_from_tsv --input-jsonl "$(TSV_PATCH_SOURCE_JSONL)" --candidates "$(TSV_PATCH_CANDIDATES)" --decisions "$(TSV_PATCH_DECISIONS)" --audit-id "$(TSV_PATCH_AUDIT_ID)" --label "$(TSV_PATCH_LABEL)" --reviewer "$(REVIEWER)" --summary-json "$(TSV_PATCH_SUMMARY_JSON)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --label-metadata "$(NEWSPAPER_LABEL_METADATA)" $(ARGS)
	@echo "Next step:"
	@echo "  # Apply accepted TSV-derived span patches."
	@echo "  make apply-tsv-span-patches TSV_PATCH_SPLIT=$(TSV_PATCH_SPLIT)"
endif

create-tsv-span-patches:
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@echo "Creating accepted manual span patches across $(TSV_PATCH_SPLITS) from pasted TSV blocks."
	$(PYTHON) -m lib.create_span_patches_from_tsv --input-jsonl "$(TRAIN_JSONL)" --candidates "audit.d/manual-tsv/manual-tsv-detect/candidates.jsonl" --decisions "data/curated/span-patches/manual-tsv-detect/decisions.jsonl" --audit-id "manual-tsv-detect" --label "$(TSV_PATCH_LABEL)" --reviewer "$(REVIEWER)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --label-metadata "$(NEWSPAPER_LABEL_METADATA)" --allow-no-matches --loop --split-input-jsonl train="$(TRAIN_JSONL)" --split-input-jsonl validation="$(VALIDATION_JSONL)" --split-input-jsonl test="$(TEST_JSONL)" --split-candidates train="audit.d/manual-tsv/manual-tsv-train/candidates.jsonl" --split-candidates validation="audit.d/manual-tsv/manual-tsv-validation/candidates.jsonl" --split-candidates test="audit.d/manual-tsv/manual-tsv-test/candidates.jsonl" --split-decisions train="data/curated/span-patches/manual-tsv-train/decisions.jsonl" --split-decisions validation="data/curated/span-patches/manual-tsv-validation/decisions.jsonl" --split-decisions test="data/curated/span-patches/manual-tsv-test/decisions.jsonl" --split-audit-id train="manual-tsv-train" --split-audit-id validation="manual-tsv-validation" --split-audit-id test="manual-tsv-test" --split-summary-json train="audit.d/manual-tsv/manual-tsv-train/summary.json" --split-summary-json validation="audit.d/manual-tsv/manual-tsv-validation/summary.json" --split-summary-json test="audit.d/manual-tsv/manual-tsv-test/summary.json" $(ARGS)
	@echo "Next step:"
	@echo "  # Apply accepted TSV-derived span patches."
	@echo "  make apply-tsv-span-patches"
else
	@echo "Creating accepted manual span patches from pasted TOKEN OLD [NEW] TSV blocks."
	$(PYTHON) -m lib.create_span_patches_from_tsv --input-jsonl "$(TSV_PATCH_SOURCE_JSONL)" --candidates "$(TSV_PATCH_CANDIDATES)" --decisions "$(TSV_PATCH_DECISIONS)" --audit-id "$(TSV_PATCH_AUDIT_ID)" --label "$(TSV_PATCH_LABEL)" --reviewer "$(REVIEWER)" --summary-json "$(TSV_PATCH_SUMMARY_JSON)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --label-metadata "$(NEWSPAPER_LABEL_METADATA)" --loop $(ARGS)
	@echo "Next step:"
	@echo "  # Apply accepted TSV-derived span patches."
	@echo "  make apply-tsv-span-patches TSV_PATCH_SPLIT=$(TSV_PATCH_SPLIT)"
endif

apply-tsv-span-patches:
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@for split in $(TSV_PATCH_SPLITS); do $(MAKE) $@ TSV_PATCH_SPLIT=$$split TSV_PATCH_SUPPRESS_NEXT=true || exit $$?; done
	@echo "Next step:"
	@echo "  # Check whether the patched train/validation/test splits are ready for promotion."
	@echo "  make tsv-span-patch-status"
else
	@echo "Applying accepted TSV-derived span patches to the configured split."
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(TSV_PATCH_SOURCE_JSONL)" --output-jsonl "$(TSV_PATCH_OUTPUT_JSONL)" --candidates "$(TSV_PATCH_CANDIDATES)" --decisions "$(TSV_PATCH_DECISIONS)" --audit-id "$(TSV_PATCH_AUDIT_ID)" --target-label "$(TSV_PATCH_LABEL)" --changes-jsonl "$(TSV_PATCH_CHANGES_JSONL)" --changes-tsv "$(TSV_PATCH_CHANGES_TSV)" --summary-json "$(TSV_PATCH_APPLY_SUMMARY_JSON)" $(ARGS)
ifeq ($(filter true,$(TSV_PATCH_SUPPRESS_NEXT)),)
	@echo "Next step:"
	@echo "  # Check whether the patched split is ready for promotion."
	@echo "  make tsv-span-patch-status TSV_PATCH_SPLIT=$(TSV_PATCH_SPLIT)"
endif
endif

tsv-span-patch-status:
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@for split in $(TSV_PATCH_SPLITS); do $(MAKE) $@ TSV_PATCH_SPLIT=$$split || exit $$?; done
else
	@echo "Checking whether the TSV-derived patched output is ready for promotion."
	@echo "audit id:        $(TSV_PATCH_AUDIT_ID)"
	@echo "target label:    $(TSV_PATCH_LABEL)"
	@echo "source split:    $(TSV_PATCH_SOURCE_JSONL)"
	@echo "patched output:  $(TSV_PATCH_OUTPUT_JSONL)"
	@echo "promote target:  $(TSV_PATCH_PROMOTE_JSONL)"
	@test -f "$(TSV_PATCH_OUTPUT_JSONL)" || { echo "patched output:  missing; run make apply-tsv-span-patches first"; exit 1; }
	@test -f "$(TSV_PATCH_PROMOTE_JSONL)" || { echo "promote target:  missing"; exit 1; }
	@if cmp -s "$(TSV_PATCH_OUTPUT_JSONL)" "$(TSV_PATCH_PROMOTE_JSONL)"; then echo "state:           promoted target is up to date"; else echo "state:           patched output differs from promote target"; fi
endif

promote-tsv-span-patches:
ifeq ($(strip $(TSV_PATCH_SPLIT)),)
	@for split in $(TSV_PATCH_SPLITS); do $(MAKE) $@ TSV_PATCH_SPLIT=$$split TSV_PATCH_SUPPRESS_NEXT=true || exit $$?; done
	@echo "Next step:"
	@echo "  # Regenerate TSV views for inspection."
	@echo "  make materialize-dataset-tsv"
else
	@echo "Promoting the TSV-derived patched split into the configured source split."
	@test -f "$(TSV_PATCH_OUTPUT_JSONL)" || { echo "Missing patched output: $(TSV_PATCH_OUTPUT_JSONL). Run make apply-tsv-span-patches first."; exit 1; }
	@echo "Promoting $(TSV_PATCH_OUTPUT_JSONL) -> $(TSV_PATCH_PROMOTE_JSONL)"
	cp "$(TSV_PATCH_OUTPUT_JSONL)" "$(TSV_PATCH_PROMOTE_JSONL)"
	$(MAKE) validate-dataset-splits
ifeq ($(filter true,$(TSV_PATCH_SUPPRESS_NEXT)),)
	@echo "Next step:"
	@echo "  # Regenerate TSV views for inspection."
	@echo "  make materialize-dataset-tsv"
endif
endif

integrate-tsv-span-patches: apply-tsv-span-patches promote-tsv-span-patches materialize-dataset-tsv-quiet
	@echo "TSV-derived span-patch integration complete."

plan-media-sampling:
	@echo "Planning focused $(MEDIA_FAMILY) sampling from coverage, pending work, and mention surfaces."
	$(PYTHON) -m lib.plan_media_sampling --family "$(MEDIA_FAMILY)" --seeds "$(MEDIA_LABEL_METADATA)" --coverage-json "$(ANNOTATION_STATS_JSON)" --profiles-json "$(MENTION_PROFILE_JSON)" --json-output "$(MEDIA_SAMPLING_PLAN_JSON)" --tsv-output "$(MEDIA_SAMPLING_PLAN_TSV)" --languages $(MEDIA_SAMPLE_LANGS) --target-per-bucket "$(MEDIA_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(MEDIA_SAMPLE_MAX_PER_LABEL)" --max-queries-per-bucket "$(MEDIA_SAMPLE_MAX_QUERIES_PER_LABEL)" --min-missing "$(MEDIA_SAMPLE_MIN_MISSING)" --surface-saturation "$(MEDIA_SAMPLE_SURFACE_SATURATION)" $(if $(MEDIA_SAMPLE_EFFECTIVE_LABELS),--labels "$(MEDIA_SAMPLE_EFFECTIVE_LABELS)",) --pending-jsonl "$(MEDIA_SNIPPETS)" --pending-jsonl "$(MEDIA_SCORED_SNIPPETS)" --pending-jsonl "$(MEDIA_REVIEWED_SNIPPETS)" --pending-jsonl "$(MEDIA_SNIPPET_TRAIN_JSONL)" --pending-jsonl "$(MEDIA_SNIPPET_VALIDATION_JSONL)" --pending-jsonl "$(MEDIA_SNIPPET_TEST_JSONL)"
	@echo "Next step:"
	@echo "  # Sample only the planned focused gaps."
	@echo "  make sample-media-snippets MEDIA_FAMILY=$(MEDIA_FAMILY)"

plan-holdout-gaps:
	@echo "Planning $(MEDIA_FAMILY) holdout gaps below $(HOLDOUT_MIN_PER_LABEL) positive mentions."
	$(PYTHON) -m lib.plan_holdout_gaps --family "$(MEDIA_FAMILY)" --seeds "$(MEDIA_LABEL_METADATA)" --validation "$(VALIDATION_JSONL)" --test "$(TEST_JSONL)" --minimum "$(HOLDOUT_MIN_PER_LABEL)" --sample-factor "$(HOLDOUT_SAMPLE_FACTOR)" --languages $(MEDIA_SAMPLE_LANGS) --max-queries "$(HOLDOUT_MAX_QUERIES_PER_LABEL)" --output "$(HOLDOUT_PLAN_JSON)"

sample-holdout-gaps: plan-holdout-gaps
	@echo "Sampling $(MEDIA_FAMILY) snippets for validation/test holdout gaps."
	$(PYTHON) -m lib.sample_media_snippets --family "$(MEDIA_FAMILY)" --seeds "$(MEDIA_LABEL_METADATA)" --out "$(MEDIA_SNIPPETS)" --summary-out "$(MEDIA_SNIPPET_SUMMARY)" --languages $(MEDIA_SAMPLE_LANGS) --target-per-query-lang "$(MEDIA_SAMPLE_TARGET_PER_QUERY_LANG)" --pool-factor "$(MEDIA_SAMPLE_POOL_FACTOR)" --max-per-label "0" --max-queries-per-label "$(HOLDOUT_MAX_QUERIES_PER_LABEL)" --year-start "$(MEDIA_SAMPLE_YEAR_START)" --year-end "$(MEDIA_SAMPLE_YEAR_END)" --context-source "$(MEDIA_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(MEDIA_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --existing-issue-jsonl "$(TRAIN_JSONL)" --existing-issue-jsonl "$(VALIDATION_JSONL)" --existing-issue-jsonl "$(TEST_JSONL)" --sampling-plan "$(HOLDOUT_PLAN_JSON)" $(ARGS)
	@echo "Next step:"
	@echo "  make suggest-media-snippet-spans MEDIA_FAMILY=$(MEDIA_FAMILY) # Suggest spans for holdout-gap samples"

sample-freely-media-snippets:
	@echo "Sampling $(MEDIA_FAMILY) snippets freely, without restricting to below-target coverage buckets."
	$(PYTHON) -m lib.sample_media_snippets --family "$(MEDIA_FAMILY)" --seeds "$(MEDIA_LABEL_METADATA)" --out "$(MEDIA_SNIPPETS)" --summary-out "$(MEDIA_SNIPPET_SUMMARY)" --languages $(MEDIA_SAMPLE_LANGS) --target-per-query-lang "$(MEDIA_SAMPLE_TARGET_PER_QUERY_LANG)" --pool-factor "$(MEDIA_SAMPLE_POOL_FACTOR)" --max-per-label "$(MEDIA_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(MEDIA_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(MEDIA_SAMPLE_YEAR_START)" --year-end "$(MEDIA_SAMPLE_YEAR_END)" --context-source "$(MEDIA_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(MEDIA_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --existing-issue-jsonl "$(TRAIN_JSONL)" --existing-issue-jsonl "$(VALIDATION_JSONL)" --existing-issue-jsonl "$(TEST_JSONL)" $(if $(MEDIA_SAMPLE_EFFECTIVE_LABELS),--labels "$(MEDIA_SAMPLE_EFFECTIVE_LABELS)",) $(ARGS)
	@echo "Next step:"
	@echo "  # Suggest spans for sampled media-source snippets."
	@echo "  make suggest-media-snippet-spans MEDIA_FAMILY=$(MEDIA_FAMILY)"

sample-all-aliases-media-snippets:
	@echo "Sampling $(MEDIA_FAMILY) snippets by trying every configured search alias for under-target labels."
	$(MAKE) sample-media-snippets MEDIA_FAMILY="$(MEDIA_FAMILY)" MEDIA_LABELS="$(MEDIA_SAMPLE_EFFECTIVE_LABELS)" MEDIA_SAMPLE_MODE=coverage MEDIA_SAMPLE_MAX_QUERIES_PER_LABEL=0

sample-media-snippets:
	@echo "Sampling $(MEDIA_FAMILY) snippets for focused label/language/surface gaps."
	@if [ -n "$(MEDIA_SAMPLE_PLAN)" ]; then $(MAKE) annotation-stats ARGS=""; $(MAKE) mention-profiles ARGS=""; $(MAKE) plan-media-sampling MEDIA_FAMILY="$(MEDIA_FAMILY)"; fi
	$(PYTHON) -m lib.sample_media_snippets --family "$(MEDIA_FAMILY)" --seeds "$(MEDIA_LABEL_METADATA)" --out "$(MEDIA_SNIPPETS)" --summary-out "$(MEDIA_SNIPPET_SUMMARY)" --languages $(MEDIA_SAMPLE_LANGS) --target-per-query-lang "$(MEDIA_SAMPLE_TARGET_PER_QUERY_LANG)" --pool-factor "$(MEDIA_SAMPLE_POOL_FACTOR)" --max-per-label "$(MEDIA_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(MEDIA_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(MEDIA_SAMPLE_YEAR_START)" --year-end "$(MEDIA_SAMPLE_YEAR_END)" --context-source "$(MEDIA_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(MEDIA_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --existing-issue-jsonl "$(TRAIN_JSONL)" --existing-issue-jsonl "$(VALIDATION_JSONL)" --existing-issue-jsonl "$(TEST_JSONL)" --coverage-json "$(ANNOTATION_STATS_JSON)" --only-under-target $(if $(MEDIA_SAMPLE_PLAN),--sampling-plan "$(MEDIA_SAMPLE_PLAN)",) $(if $(MEDIA_SAMPLE_EFFECTIVE_LABELS),--labels "$(MEDIA_SAMPLE_EFFECTIVE_LABELS)",) $(ARGS)
	@echo "Next step:"
	@echo "  # Suggest spans for sampled media-source snippets."
	@echo "  make suggest-media-snippet-spans MEDIA_FAMILY=$(MEDIA_FAMILY)"

curate:
	@echo "Running the generic candidate curation command with ARGS."
	$(PYTHON) -m lib.curate_candidates $(ARGS)

import-hipe:
	@echo "Converting HIPE TSV annotations into JSONL workbench data."
	$(PYTHON) -m lib.import_legacy_hipe_tsv $(ARGS)

export-dataset:
	@echo "Exporting curated JSONL training data."
	$(PYTHON) -m lib.export_training_data $(ARGS)

download-mlm-sources:
	@echo "Downloading compiled Impresso sources for continued MLM pretraining."
	$(PYTHON) -m lib.download_mlm_sources --output-dir "$(MLM_DATASET_DIR)" $(foreach source,$(MLM_SOURCE_URLS),--source "$(source)") $(ARGS)

build-mlm-data:
	@echo "Building balanced multilingual MLM train/validation data."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.mlm_data --dataset-dir "$(MLM_DATASET_DIR)" --output-dir "$(MLM_DATA_DIR)" --languages "$(MLM_LANGS)" $(if $(filter-out 0,$(MLM_MAX_PER_LANGUAGE)),--max-per-language "$(MLM_MAX_PER_LANGUAGE)",--target-total "$(MLM_TARGET_TOTAL)") --validation-fraction "$(MLM_VAL_FRACTION)" --ocr-min "$(MLM_OCR_MIN)" --min-chars "$(MLM_MIN_CHARS)" --progress-interval "$(MLM_PROGRESS_INTERVAL)" --seed "$(SEED)" $(ARGS)

pretrain-mlm:
	@echo "Continuing MLM pretraining for the configured multilingual Impresso base model."
	$(PYTHON) -m py_compile training/newsagency-radiostation-modernbert-classifier/src/mediaagency_modernbert/*.py
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.mlm --model-name-or-path "$(MLM_BASE_MODEL)" --train-file "$(MLM_DATA_DIR)/train.json" --validation-file "$(MLM_DATA_DIR)/validation.json" --output-dir "$(MLM_OUTPUT_DIR)" --max-sequence-len "$(MLM_MAX_LEN)" $(if $(filter true,$(MLM_PAD_TO_MAX_LENGTH)),--pad-to-max-length,--no-pad-to-max-length) --tokenized-cache-dir "$(MLM_TOKENIZED_CACHE_DIR)" --preprocessing-num-workers "$(MLM_PREPROCESSING_NUM_WORKERS)" --map-batch-size "$(MLM_MAP_BATCH_SIZE)" --max-train-samples "$(MLM_MAX_TRAIN_SAMPLES)" --max-eval-samples "$(MLM_MAX_EVAL_SAMPLES)" --mlm-probability "$(MLM_PROBABILITY)" --epochs "$(MLM_EPOCHS)" --train-batch-size "$(MLM_BATCH)" --eval-batch-size "$(MLM_EVAL_BATCH)" --gradient-accumulation-steps "$(MLM_GRADIENT_ACCUMULATION_STEPS)" $(if $(filter true,$(MLM_GRADIENT_CHECKPOINTING)),--gradient-checkpointing,--no-gradient-checkpointing) --learning-rate "$(MLM_LEARNING_RATE)" --weight-decay "$(MLM_WEIGHT_DECAY)" --warmup-steps "$(MLM_WARMUP_STEPS)" --warmup-fraction "$(MLM_WARMUP_FRACTION)" --evals-per-epoch "$(MLM_EVALS_PER_EPOCH)" --save-strategy "$(MLM_SAVE_STRATEGY)" --save-steps "$(MLM_SAVE_STEPS)" --save-total-limit "$(MLM_SAVE_TOTAL_LIMIT)" --logging-steps "$(MLM_LOGGING_STEPS)" --seed "$(SEED)" $(ARGS)

push-mlm-model:
	@echo "Pushing the continued MLM model payload to Hugging Face."
	$(PYTHON) -m lib.push_mlm_model_to_hub --repo-id "$(MLM_HF_MODEL)" --model-dir "$(MLM_OUTPUT_DIR)/final" --card hf_mlm_model/README.md $(ARGS)

publish-dataset:
	@echo "Publishing or dry-running publication of the training dataset."
	$(PYTHON) -m lib.publish_dataset --input-dir "$(DATASET_SOURCE_DIR)" --output-dir "$(DATASET_OUTPUT_DIR)" --repo-id "$(DATASET)" --release-files "$(HF_RELEASE_FILES)" --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json $(ARGS)

publish-testset:
	@echo "Publishing or dry-running publication of the testset."
	$(PYTHON) -m lib.publish_testset $(ARGS)

train:
	@echo "Fine-tuning the token-classification NER model on the configured train/validation splits."
	$(if $(filter true,$(TRAIN_SYNC_LABEL_MAP)),$(MAKE) sync-label-map,)
	$(PYTHON) -m py_compile training/newsagency-radiostation-modernbert-classifier/src/mediaagency_modernbert/*.py
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-train --model-name-or-path "$(BASE_MODEL)" $(if $(CHECKPOINT),--checkpoint "$(CHECKPOINT)",) --train-jsonl "$(TRAIN_JSONL)" --validation-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)" --epochs "$(EPOCHS)" --train-batch-size "$(BATCH)" --eval-batch-size "$(EVAL_BATCH)" --gradient-accumulation-steps "$(GRADIENT_ACCUMULATION_STEPS)" $(if $(filter true,$(GRADIENT_CHECKPOINTING)),--gradient-checkpointing,--no-gradient-checkpointing) $(if $(filter true,$(LABEL_ALL_TOKENS)),--label-all-tokens,--no-label-all-tokens) $(if $(filter true,$(FREEZE_BASE_MODEL)),--freeze-base-model,--no-freeze-base-model) --unfreeze-top-layers "$(UNFREEZE_TOP_LAYERS)" --optimizer "$(OPTIMIZER)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --learning-rate "$(LEARNING_RATE)" --weight-decay "$(WEIGHT_DECAY)" --warmup-steps "$(WARMUP_STEPS)" --logging-steps "$(LOGGING_STEPS)" --early-stopping-patience "$(EARLY_STOPPING_PATIENCE)" --early-stopping-metric "$(EARLY_STOPPING_METRIC)" --early-stopping-mode "$(EARLY_STOPPING_MODE)" --early-stopping-min-delta "$(EARLY_STOPPING_MIN_DELTA)" --seed "$(SEED)" --device "$(DEVICE)" $(ARGS)

train-fresh:
	@echo "Removing the configured model output directory before fresh training."
	@test -n "$(MODEL)" || { echo "MODEL is empty; refusing to remove anything"; exit 1; }
	@case "$(MODEL)" in models.d/*) ;; *) echo "MODEL must be under models.d/ for train-fresh: $(MODEL)"; exit 1;; esac
	@test "$(MODEL)" != "models.d" -a "$(MODEL)" != "models.d/" -a "$(MODEL)" != "." -a "$(MODEL)" != "/" || { echo "Unsafe MODEL value: $(MODEL)"; exit 1; }
	rm -rf "$(MODEL)"
	$(MAKE) train

stamp-model-inference-metadata:
	@echo "Stamping annotation tokenization and subtoken policies into the trained model config."
	$(PYTHON) -m lib.stamp_model_inference_metadata --model-dir "$(MODEL)" --dataset "$(TRAIN_JSONL)" --label-all-tokens "$(LABEL_ALL_TOKENS)"

evaluate-validation: maybe-sync-label-map
	@echo "Evaluating the selected checkpoint on the validation split."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(SELECTED_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)

evaluate-test: maybe-sync-label-map
	@echo "Evaluating the selected checkpoint on the held-out test split."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(SELECTED_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)

test: evaluate-validation

test-official: evaluate-test

check-curation-checker:
	@test -f "$(CURATION_LABEL_MAP)" || { echo "Missing curation checker label map: $(CURATION_LABEL_MAP)"; echo "Next step:"; echo "  # Train the configured model and write its label_map.json."; echo "  make train"; echo "Or pass both CURATION_MODEL=... and CURATION_LABEL_MAP=... for another checker."; exit 1; }

curation-eval: maybe-sync-label-map check-curation-checker
	@echo "Evaluating train/validation/test to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TRAIN_JSONL)" --label-map "$(CURATION_LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name train --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(CURATION_LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(CURATION_LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	@echo "Next step:"
	@echo "  # Build the train/validation/test disagreement review queue."
	@echo "  make curation-review"

curation-eval-train: maybe-sync-label-map check-curation-checker
	@echo "Evaluating train to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TRAIN_JSONL)" --label-map "$(CURATION_LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name train --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	@echo "Next step:"
	@echo "  # Build the train disagreement review queue."
	@echo "  make curation-review-train"

curation-eval-validation: maybe-sync-label-map check-curation-checker
	@echo "Evaluating validation to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(CURATION_LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	@echo "Next step:"
	@echo "  # Build the validation disagreement review queue."
	@echo "  make curation-review-validation"

curation-eval-test: maybe-sync-label-map check-curation-checker
	@echo "Evaluating test to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(CURATION_LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(EVAL_DECODER_ARGS) $(EVAL_PREDICTION_DIAGNOSTIC_ARGS) $(ARGS)
	@echo "Next step:"
	@echo "  # Build the test disagreement review queue."
	@echo "  make curation-review-test"

curation-review:
	@echo "Building the train/validation/test disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --train-jsonl "$(TRAIN_JSONL)" --train-predictions "$(CURATION_OUTPUT_DIR)/eval/train_predictions.jsonl" --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "train validation test" $(ARGS)
	@echo "Next step:"
	@echo "  # Review pending disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

curation-review-train:
	@echo "Building the train disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --train-jsonl "$(TRAIN_JSONL)" --train-predictions "$(CURATION_OUTPUT_DIR)/eval/train_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "train" $(ARGS)
	@echo "Next step:"
	@echo "  # Review pending train disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

curation-review-validation:
	@echo "Building the validation disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "validation" $(ARGS)
	@echo "Next step:"
	@echo "  # Review pending validation disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

curation-review-test:
	@echo "Building the test disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "test" $(ARGS)
	@echo "Next step:"
	@echo "  # Review pending test disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

suggest-eval-disagreements: curation-eval curation-review
	@echo "Next step:"
	@echo "  # Review pending disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

suggest-eval-disagreements-train: curation-eval-train curation-review-train
	@echo "Next step:"
	@echo "  # Review pending train disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

suggest-eval-disagreements-validation: curation-eval-validation curation-review-validation
	@echo "Next step:"
	@echo "  # Review pending validation disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

suggest-eval-disagreements-test: curation-eval-test curation-review-test
	@echo "Next step:"
	@echo "  # Review pending test disagreements."
	@echo "  make review-curation REVIEWER=\"$$USER\""

suggest-media-snippet-spans:
	@echo "Suggesting $(MEDIA_FAMILY) snippet spans: use the configured model and known entity metadata matchers."
	$(PYTHON) -m lib.score_media_snippets --family "$(MEDIA_FAMILY)" --input "$(MEDIA_SNIPPETS)" --output "$(MEDIA_SCORED_SNIPPETS)" --newsagencies "$(NEWSAGENCY_LABEL_METADATA)" --radiostations "$(RADIOSTATION_LABEL_METADATA)" --newspapers "$(NEWSPAPER_LABEL_METADATA)" --model "$(HF_MODEL)" --device "$(DEVICE)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --suggest-non-o-min-confidence "$(SUGGEST_NON_O_MIN_CONFIDENCE)" $(if $(filter true,$(AUTO_ACCEPT_ENABLED)),--auto-accept,--no-auto-accept) --auto-accept-min-confidence "$(AUTO_ACCEPT_MIN_CONFIDENCE)" --auto-accept-min-margin "$(AUTO_ACCEPT_MIN_MARGIN)" --auto-accept-multiple-min-confidence "$(AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE)" $(ARGS)
	@echo "Next step:"
	@echo "  # Review suggested media-source snippet spans."
	@echo "  make review-media-snippet-spans MEDIA_FAMILY=$(MEDIA_FAMILY) REVIEWER=\"$$USER\""

review-media-snippet-spans:
	@echo "Reviewing $(MEDIA_FAMILY) snippet span suggestions and writing append-only decisions."
	$(PYTHON) -m lib.review_media_snippets --family "$(MEDIA_FAMILY)" --input "$(MEDIA_SCORED_SNIPPETS)" --output "$(MEDIA_REVIEWED_SNIPPETS)" --decisions "$(MEDIA_SNIPPET_DECISIONS)" --reviewer "$(REVIEWER)" --limit "$(SNIPPET_REVIEW_MAX_ITEMS)" --label-metadata "$(MEDIA_LABEL_METADATA)" --review-prefix "$(MEDIA_REVIEW_PREFIX)" --coverage-json "$(REVIEW_COVERAGE_JSON)" $(if $(filter true,$(REVIEW_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)
	@echo "Next step:"
	@echo "  # Split accepted snippets into train/validation/test."
	@echo "  make split-media-snippets MEDIA_FAMILY=$(MEDIA_FAMILY)"

review-auto-media-snippet-spans:
	@echo "Auditing auto-accepted $(MEDIA_FAMILY) snippet spans and writing append-only decisions."
	$(PYTHON) -m lib.review_media_snippets --family "$(MEDIA_FAMILY)" --input "$(MEDIA_SCORED_SNIPPETS)" --output "$(MEDIA_REVIEWED_SNIPPETS)" --decisions "$(MEDIA_SNIPPET_DECISIONS)" --reviewer "$(REVIEWER)" --limit "$(SNIPPET_REVIEW_MAX_ITEMS)" --label-metadata "$(MEDIA_LABEL_METADATA)" --review-prefix "$(MEDIA_REVIEW_PREFIX)" --review-status auto_accepted $(ARGS)
	@echo "Next step:"
	@echo "  # Split accepted snippets into train/validation/test."
	@echo "  make split-media-snippets MEDIA_FAMILY=$(MEDIA_FAMILY)"

split-media-snippets:
	@echo "Splitting accepted $(MEDIA_FAMILY) snippet decisions into train/validation/test JSONL."
	$(PYTHON) -m lib.export_snippet_training_data --input "$(MEDIA_REVIEWED_SNIPPETS)" --output "$(MEDIA_SNIPPET_TRAIN_JSONL)" --validation-output "$(MEDIA_SNIPPET_VALIDATION_JSONL)" --test-output "$(MEDIA_SNIPPET_TEST_JSONL)" --validation-fraction "$(SNIPPET_VALIDATION_FRACTION)" --test-fraction "$(SNIPPET_TEST_FRACTION)" --split-seed "$(SNIPPET_SPLIT_SEED)" --label-map "$(LABEL_MAP)" --holdout-min-per-label "$(HOLDOUT_MIN_PER_LABEL)" --holdout-source train="$(TRAIN_JSONL)" --holdout-source validation="$(VALIDATION_JSONL)" --holdout-source test="$(TEST_JSONL)" --extra-label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --extra-label-metadata "$(RADIOSTATION_LABEL_METADATA)" --extra-label-metadata "$(NEWSPAPER_LABEL_METADATA)" $(ARGS)
	@echo "Next step:"
	@echo "  # Preview integration after snippet splits are up to date."
	@echo "  make preview-promote-snippets"

preview-promote-snippets:
	@echo "Previewing promotion of split snippet rows into the configured dataset splits."
	$(PYTHON) -m lib.promote_snippet_splits --dry-run --base train="$(SNIPPET_PROMOTE_TRAIN_JSONL)" --base validation="$(SNIPPET_PROMOTE_VALIDATION_JSONL)" --base test="$(SNIPPET_PROMOTE_TEST_JSONL)" --snippet train="$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --snippet train="$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --snippet validation="$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --snippet validation="$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --snippet test="$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --snippet test="$(RADIOSTATION_SNIPPET_TEST_JSONL)" --summary-json "$(SNIPPET_PROMOTE_SUMMARY_JSON)" $(ARGS)
	@echo "Next step:"
	@echo "  # Promote split snippets into configured dataset splits."
	@echo "  make promote-snippets"

promote-snippets:
	@echo "Promoting split snippet rows into the configured dataset splits."
	$(PYTHON) -m lib.promote_snippet_splits --base train="$(SNIPPET_PROMOTE_TRAIN_JSONL)" --base validation="$(SNIPPET_PROMOTE_VALIDATION_JSONL)" --base test="$(SNIPPET_PROMOTE_TEST_JSONL)" --snippet train="$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --snippet train="$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --snippet validation="$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --snippet validation="$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --snippet test="$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --snippet test="$(RADIOSTATION_SNIPPET_TEST_JSONL)" --summary-json "$(SNIPPET_PROMOTE_SUMMARY_JSON)" $(ARGS)
	$(MAKE) validate-dataset-splits
	@echo "Next step:"
	@echo "  # Refresh annotation state after promotion."
	@echo "  make anno-housekeeping"
	@echo "Shortcut for next time:"
	@echo "  # Split, preview, and promote snippets in one command."
	@echo "  make integrate-snippets"

integrate-snippets:
	@echo "Integrating reviewed snippets: split press-agency and radio-station decisions, preview promotion, then promote."
	$(MAKE) split-media-snippets MEDIA_FAMILY=pressagency
	$(MAKE) split-media-snippets MEDIA_FAMILY=radiostation
	$(MAKE) preview-promote-snippets
	$(MAKE) promote-snippets
	@echo "Snippet integration complete."

review-curation:
	@echo "Reviewing pending gold-vs-prediction disagreement items in the terminal."
	$(PYTHON) -m lib.review_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/todo_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --reviewer "$(REVIEWER)" $(ARGS)
	@echo "Next step:"
	@echo "  # Validate reviewed disagreement decisions."
	@echo "  make validate-curation"

validate-curation:
	@echo "Validating reviewed gold-vs-prediction disagreement decisions."
	$(PYTHON) -m lib.validate_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --require-complete $(ARGS)
	@echo "Next step:"
	@echo "  # Apply validated disagreement decisions."
	@echo "  make apply-curation"

apply-curation:
	@echo "Applying reviewed curation decisions to train/validation/test JSONL annotations."
	$(PYTHON) -m lib.apply_curation_decisions --input-dir "$(CURATION_INPUT_DIR)" --output-dir "$(CURATION_APPLIED_DIR)" --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --splits "train validation test" --require-complete $(ARGS)
	$(MAKE) validate-dataset-splits

push-model:
	@echo "Pushing the fine-tuned model payload to Hugging Face."
	$(PYTHON) -m lib.push_model_to_hub --repo-id "$(HF_MODEL_REPO)" --revision "$(HF_MODEL_REVISION)" --model "$(SELECTED_MODEL)" --run-dir "$(MODEL)" --card hf_model/README.md $(ARGS)
