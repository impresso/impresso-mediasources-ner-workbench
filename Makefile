.DEFAULT_GOAL := help

PYTHON ?= python3
ARGS ?=
CFG ?= configs/model-v2.0.0.mk

include $(CFG)

export HF_HOME

.PHONY: help help-annotation help-dataset help-model help-pretraining help-finetuning help-review smoke clean clean-dry-run clean-all-data validate-labels validate-dataset-splits annotation-stats mention-profiles curation-state curation-state-json snippet-state dataset-state legacy-curation-state audit-empty-training-docs audit-existing-spans review-existing-spans apply-existing-spans existing-span-status promote-existing-spans refresh-existing-spans review-span-patches apply-span-patches span-patch-status promote-span-patches refresh-span-patches sample-newsagency-snippets sample-newsagencies sample-needed-newsagency-snippets sample-needed-newsagencies sample-radio-snippets sample-radio sample-radiostations curate import-legacy-hipe export-dataset download-mlm-sources build-mlm-data pretrain-mlm push-mlm-model publish-dataset publish-testset train test test-official curation-eval curation-eval-train curation-eval-validation curation-eval-test curation-review curation-review-train curation-review-validation curation-review-test curate-legacy-eval curate-legacy-train curate-legacy-validation curate-legacy-test build-newsagency-snippets-from-legacy suggest-newsagency-snippet-spans score-newsagency-snippets review-newsagency-snippet-spans review-newsagency-snippets split-newsagency-snippets export-newsagency-snippets suggest-radio-snippet-spans suggest-radiostation-snippet-spans score-radiostation-snippets review-radio-snippet-spans review-radiostation-snippet-spans review-radiostation-spans split-radio-snippets split-radiostation-snippets export-radiostation-snippets preview-promote-snippets preview-snippet-merge snippet-promotion-status promote-snippets merge-snippets refresh-snippet-dataset refresh-snippets curation-dashboard review-curation validate-curation apply-curation push-model

help:
	@echo "Impresso media sources NER workbench"
	@echo ""
	@echo "Main help groups:"
	@echo "  make help-annotation               Annotation sampling, review, audit, and promotion"
	@echo "  make help-dataset                  Dataset validation, state, export, and publishing"
	@echo "  make help-model                    Model evaluation, curation eval, and Hub push"
	@echo "  make help-pretraining              MLM source download, data build, pretraining, and push"
	@echo "  make help-finetuning               Token-classifier training and evaluation"
	@echo ""
	@echo "Common utilities:"
	@echo "  make smoke                         Run lightweight contract checks"
	@echo "  make clean-dry-run                 Preview ignored/generated local data cleanup"
	@echo "  make clean                         Remove ignored/generated local data; keep data/releases"
	@echo ""
	@echo "Defaults:"
	@echo "  CFG=$(CFG)"
	@echo "  PYTHON=$(PYTHON)"
	@echo "  ARGS=$(ARGS)"

help-annotation help-review:
	@echo "Annotation and curation targets"
	@echo ""
	@echo "Use this group for curator work: inspect state, sample or audit evidence, suggest spans, review decisions, split/apply reviewed material, and promote it into dataset splits."
	@echo ""
	@echo "State and diagnostics:"
	@echo "  make curation-dashboard                      Run all read-only state/stats targets in sequence"
	@echo "  make annotation-stats                        Summarize annotation coverage by label/language"
	@echo "  make mention-profiles                        Generate empirical entity mention-surface profiles"
	@echo "  make curation-state                          Summarize all curation and dataset state"
	@echo "  make snippet-state                           Summarize snippet sampling/suggestion/review/split state"
	@echo "  make legacy-curation-state                   Summarize HIPE-derived disagreement curation state"
	@echo ""
	@echo "Audit-driven span patches:"
	@echo "  make audit-empty-training-docs                Score empty-gold training docs for suspicious missed spans"
	@echo "  make audit-existing-spans                     Build target-label boundary review from existing annotations"
	@echo "  make review-existing-spans                    Verify/correct/remove existing span boundaries"
	@echo "  make apply-existing-spans                     Apply existing-span boundary decisions to a patched split"
	@echo "  make promote-existing-spans                   Promote existing-span patched output into the source split"
	@echo "  make refresh-existing-spans                   Apply existing-span decisions, then promote the patched split"
	@echo "  make review-span-patches                      Review audit-suggested span patches"
	@echo "  make apply-span-patches                       Apply accepted/corrected span patches to JSONL"
	@echo "  make span-patch-status                        Compare patched output with the configured promotion target"
	@echo "  make promote-span-patches                     Promote patched output into the prerelease/source split"
	@echo "  make refresh-span-patches                     Apply span-patch decisions, then promote the patched split"
	@echo ""
	@echo "Evaluation disagreement annotation:"
	@echo "  make curate-legacy-eval                       Score train/dev/test and build review queue"
	@echo "  make curate-legacy-train                      Score train only"
	@echo "  make curate-legacy-validation                 Score validation only"
	@echo "  make curate-legacy-test                       Score test only"
	@echo "  make review-curation                          Review pending gold/prediction disagreements"
	@echo "  make validate-curation                        Validate curation decisions"
	@echo "  make apply-curation                           Write curated JSONL folds"
	@echo ""
	@echo "News-agency snippet annotation:"
	@echo "  make sample-newsagency-snippets             Sample real Impresso search snippets"
	@echo "  make sample-needed-newsagency-snippets      Sample label/language buckets below target"
	@echo "  make build-newsagency-snippets-from-legacy   Bootstrap snippet candidates from legacy JSONL"
	@echo "  make suggest-newsagency-snippet-spans        Score sampled snippets with HF_MODEL"
	@echo "  make review-newsagency-snippet-spans         Review uncertain snippet spans; press i for label info"
	@echo "  make split-newsagency-snippets               Split accepted snippets into train/validation/test JSONL"
	@echo "  make preview-promote-snippets                Preview promotion into configured dataset splits"
	@echo "  make promote-snippets                        Promote split snippets into configured dataset splits"
	@echo "  make refresh-snippet-dataset                 Split reviewed snippets, then promote them into dataset splits"
	@echo ""
	@echo "Radio snippet annotation:"
	@echo "  make sample-radio-snippets                   Sample real Impresso radio snippets"
	@echo "  make suggest-radio-snippet-spans             Score existing sampled radio snippets by alias"
	@echo "  make review-radio-snippet-spans              Review radio span suggestions"
	@echo "  make split-radio-snippets                    Split accepted radio spans into train/validation/test JSONL"
	@echo ""
	@echo "Useful overrides:"
	@echo "  REVIEWER=$$USER, REVIEW_MAX_ITEMS=20, NEWSAGENCY_SNIPPETS=..., NEWSAGENCY_LEGACY_SNIPPETS=..., RADIOSTATION_SNIPPETS=..."
	@echo "  REVIEW_COVERAGE_JSON=$(ANNOTATION_STATS_JSON), REVIEW_ONLY_UNDER_TARGET=true"
	@echo "  ANNOTATION_MAIN_LANGS='$(ANNOTATION_MAIN_LANGS)', ANNOTATION_SIDE_LANGS='$(ANNOTATION_SIDE_LANGS)'"
	@echo "  ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=$(ANNOTATION_MAIN_TARGET_PER_LABEL_LANG), ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=$(ANNOTATION_SIDE_TARGET_PER_LABEL_LANG)"
	@echo "  AUTO_ACCEPT_MIN_CONFIDENCE=0.99, AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE=\$$(AUTO_ACCEPT_MIN_CONFIDENCE), AUTO_ACCEPT_MIN_MARGIN=0.30"
	@echo "  CURATION_STATE_JSON=$(CURATION_STATE_JSON)"

help-dataset:
	@echo "Dataset targets"
	@echo ""
	@echo "Use this group for dataset integrity, state snapshots, exports, and publishing. Promotion targets integrate reviewed local curation artifacts into the configured prerelease/source splits."
	@echo ""
	@echo "Validation and state:"
	@echo "  make validate-labels                       Validate canonical label metadata"
	@echo "  make validate-dataset-splits               Check train/validation/test split integrity"
	@echo "  make dataset-state                         Summarize staging and configured published dataset state"
	@echo "  make curation-state-json                   Write $(CURATION_STATE_JSON)"
	@echo ""
	@echo "Import, export, publish:"
	@echo "  make import-legacy-hipe ARGS=...           Convert legacy HIPE TSV annotations to JSONL"
	@echo "  make export-dataset                        Export curated JSONL training data"
	@echo "  make publish-dataset ARGS=...              Publish or dry-run training dataset"
	@echo "  make publish-testset ARGS=...              Publish or dry-run testset"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean-dry-run                         Preview ignored/generated local data cleanup"
	@echo "  make clean                                 Remove ignored/generated local data; keep data/releases"
	@echo "  make clean-all-data                        Alias for clean; release snapshots are still preserved"

help-model:
	@echo "Model targets"
	@echo ""
	@echo "Use this group for model-side checks, evaluation, curation evaluation output, and pushing trained model artifacts."
	@echo ""
	@echo "Checks:"
	@echo "  make smoke                                 Run lightweight contract checks"
	@echo ""
	@echo "Evaluation:"
	@echo "  make test CFG=...                          Evaluate the configured model on validation"
	@echo "  make test-official CFG=...                 Evaluate the configured model on test"
	@echo "  make curation-eval                         Evaluate train/validation/test for disagreement review"
	@echo "  make curation-eval-train                   Evaluate train for disagreement review"
	@echo "  make curation-eval-validation              Evaluate validation for disagreement review"
	@echo "  make curation-eval-test                    Evaluate test for disagreement review"
	@echo ""
	@echo "Publishing:"
	@echo "  make push-model CFG=...                    Push model payload to Hugging Face"

help-pretraining:
	@echo "Pretraining targets"
	@echo ""
	@echo "Use this group for continued MLM pretraining before token-classifier fine-tuning."
	@echo ""
	@echo "  make download-mlm-sources                  Download compiled Impresso MLM source files"
	@echo "  make build-mlm-data                        Build balanced multilingual Impresso MLM data"
	@echo "  make pretrain-mlm                          Continue MLM pretraining for multilingual Impresso BERT"
	@echo "  make push-mlm-model                        Push continued MLM model payload to Hugging Face"

help-finetuning:
	@echo "Fine-tuning targets"
	@echo ""
	@echo "Use this group for training and evaluating the token-classification NER model with the configured v2 dataset splits."
	@echo ""
	@echo "  make train CFG=...                         Train via training submodule"
	@echo "  make test CFG=...                          Evaluate validation via training submodule"
	@echo "  make test-official CFG=...                 Evaluate test and record official metrics"

smoke:
	@echo "Running lightweight syntax and metadata contract checks."
	$(PYTHON) -m py_compile lib/*.py hf_model/pipeline.py
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

clean:
	@echo "Removing ignored/generated local workbench data while preserving release snapshots."
	$(PYTHON) -m lib.clean_workbench

clean-dry-run:
	@echo "Previewing ignored/generated local data that clean would remove."
	$(PYTHON) -m lib.clean_workbench --dry-run

clean-all-data: clean

validate-labels:
	@echo "Validating canonical news-agency and radio-station label metadata."
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

validate-dataset-splits:
	@echo "Checking train/validation/test split integrity, including promoted snippet rows."
	$(PYTHON) -m lib.validate_dataset_splits --train "$(TRAIN_JSONL)" --validation "$(VALIDATION_JSONL)" --test "$(TEST_JSONL)" --snippet train="$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --snippet train="$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --snippet validation="$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --snippet validation="$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --snippet test="$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --snippet test="$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

annotation-stats:
	@echo "Summarizing annotation coverage by label and language across train/validation/test and snippet splits."
	$(PYTHON) -m lib.annotation_stats --target-per-label "$(ANNOTATION_TARGET_PER_LABEL)" --main-languages $(ANNOTATION_MAIN_LANGS) --side-languages $(ANNOTATION_SIDE_LANGS) --main-target-per-label-language "$(ANNOTATION_MAIN_TARGET_PER_LABEL_LANG)" --side-target-per-label-language "$(ANNOTATION_SIDE_TARGET_PER_LABEL_LANG)" $(foreach target,$(ANNOTATION_LANGUAGE_TARGETS),--language-target "$(target)") --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --legacy-jsonl "$(TRAIN_JSONL)" --legacy-jsonl "$(VALIDATION_JSONL)" --legacy-jsonl "$(TEST_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" --newsagency-reviewed-jsonl "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --radiostation-reviewed-jsonl "$(RADIOSTATION_REVIEWED_SNIPPETS)" --json-output "$(ANNOTATION_STATS_JSON)" --tsv-output "$(ANNOTATION_STATS_TSV)" $(ARGS)

mention-profiles:
	@echo "Building empirical mention-surface profiles for canonical entity labels."
	$(PYTHON) -m lib.entity_mention_profiles $(foreach input,$(MENTION_PROFILE_JSONL),--input-jsonl "$(input)") --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --top-n "$(MENTION_PROFILE_TOP_N)" --json-output "$(MENTION_PROFILE_JSON)" --tsv-output "$(MENTION_PROFILE_TSV)" --md-output "$(MENTION_PROFILE_MD)" $(ARGS)

curation-dashboard:
	@echo "Running the read-only curation dashboard: coverage, profiles, curation state, snippet state, legacy state, and dataset state."
	$(MAKE) annotation-stats
	$(MAKE) mention-profiles
	$(MAKE) curation-state
	$(MAKE) snippet-state
	$(MAKE) legacy-curation-state
	$(MAKE) dataset-state

curation-state:
	@echo "Summarizing all curation, snippet, and dataset state."
	$(PYTHON) -m lib.curation_state --section all --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-validation-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-validation-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

curation-state-json:
	@echo "Writing a JSON snapshot of all curation, snippet, and dataset state."
	$(PYTHON) -m lib.curation_state --section all --json-output "$(CURATION_STATE_JSON)" --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-validation-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-validation-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

snippet-state:
	@echo "Summarizing sampled, suggested, reviewed, and split snippet curation state."
	$(PYTHON) -m lib.curation_state --section snippets --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-validation-jsonl "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-validation-jsonl "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

dataset-state:
	@echo "Summarizing configured dataset source, staging, and publication state."
	$(PYTHON) -m lib.curation_state --section dataset --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" $(ARGS)

legacy-curation-state:
	@echo "Summarizing HIPE-derived evaluation disagreement curation state."
	$(PYTHON) -m lib.curation_state --section legacy --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" $(ARGS)

audit-empty-training-docs:
	@echo "Auditing training documents with no gold entities for suspicious missed media-source mentions."
	$(PYTHON) -m lib.audit_empty_training_docs prepare --input-jsonl "$(EMPTY_TRAIN_SOURCE_JSONL)" --label-map "$(EMPTY_TRAIN_LABEL_MAP)" --output-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_eval_input.jsonl" --summary-json "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prepare_summary.json"
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(EMPTY_TRAIN_MODEL)" --eval-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_eval_input.jsonl" --label-map "$(EMPTY_TRAIN_LABEL_MAP)" --output-dir "$(EMPTY_TRAIN_AUDIT_DIR)/eval" --split-name empty_train --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)
	$(PYTHON) -m lib.audit_empty_training_docs summarize --source-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_eval_input.jsonl" --predictions-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/eval/empty_train_predictions.jsonl" --candidates-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_candidates.jsonl" --candidates-tsv "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_candidates.tsv" --summary-json "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_summary.json"

audit-existing-spans:
	@echo "Building a boundary/label/removal audit queue for existing spans of $(SPAN_BOUNDARY_TARGET_LABEL)."
	@test -n "$(SPAN_BOUNDARY_TARGET_LABEL)" || { echo "SPAN_BOUNDARY_TARGET_LABEL is required, e.g. SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas"; exit 1; }
	$(PYTHON) -m lib.audit_existing_spans --input-jsonl "$(TRAIN_JSONL)" --target-label "$(SPAN_BOUNDARY_TARGET_LABEL)" --audit-id "$(SPAN_BOUNDARY_AUDIT_ID)" --candidates-jsonl "$(SPAN_BOUNDARY_CANDIDATES)" --candidates-tsv "$(SPAN_BOUNDARY_CANDIDATES_TSV)" --summary-json "$(SPAN_BOUNDARY_SUMMARY_JSON)" $(ARGS)

review-existing-spans:
	@echo "Reviewing existing-span audit candidates and writing append-only decisions."
	@test -n "$(SPAN_BOUNDARY_TARGET_LABEL)" || { echo "SPAN_BOUNDARY_TARGET_LABEL is required, e.g. SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas"; exit 1; }
	$(PYTHON) -m lib.span_patch_review --candidates "$(SPAN_BOUNDARY_CANDIDATES)" --decisions "$(SPAN_BOUNDARY_DECISIONS)" --audit-id "$(SPAN_BOUNDARY_AUDIT_ID)" --reviewer "$(REVIEWER)" --target-label "$(SPAN_BOUNDARY_TARGET_LABEL)" --limit "$(REVIEW_MAX_ITEMS)" --summary-json "$(SPAN_BOUNDARY_REVIEW_SUMMARY_JSON)" --queue-jsonl "$(SPAN_BOUNDARY_QUEUE_JSONL)" $(ARGS)

apply-existing-spans:
	@echo "Applying reviewed existing-span decisions to a patched split."
	@test -n "$(SPAN_BOUNDARY_TARGET_LABEL)" || { echo "SPAN_BOUNDARY_TARGET_LABEL is required, e.g. SPAN_BOUNDARY_TARGET_LABEL=org.ent.pressagency.havas"; exit 1; }
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(TRAIN_JSONL)" --output-jsonl "$(SPAN_BOUNDARY_OUTPUT_JSONL)" --candidates "$(SPAN_BOUNDARY_CANDIDATES)" --decisions "$(SPAN_BOUNDARY_DECISIONS)" --audit-id "$(SPAN_BOUNDARY_AUDIT_ID)" --target-label "$(SPAN_BOUNDARY_TARGET_LABEL)" --changes-jsonl "$(SPAN_BOUNDARY_CHANGES_JSONL)" --changes-tsv "$(SPAN_BOUNDARY_CHANGES_TSV)" --summary-json "$(SPAN_BOUNDARY_APPLY_SUMMARY_JSON)" --replace-overlaps $(ARGS)

existing-span-status:
	@echo "Checking whether the existing-span patched output is ready for promotion."
	@echo "audit id:        $(SPAN_BOUNDARY_AUDIT_ID)"
	@echo "target label:    $(SPAN_BOUNDARY_TARGET_LABEL)"
	@echo "source split:    $(TRAIN_JSONL)"
	@echo "patched output:  $(SPAN_BOUNDARY_OUTPUT_JSONL)"
	@echo "promote target:  $(SPAN_BOUNDARY_PROMOTE_JSONL)"
	@test -f "$(SPAN_BOUNDARY_OUTPUT_JSONL)" || { echo "patched output:  missing; run make apply-existing-spans first"; exit 1; }
	@test -f "$(SPAN_BOUNDARY_PROMOTE_JSONL)" || { echo "promote target:  missing"; exit 1; }
	@if cmp -s "$(SPAN_BOUNDARY_OUTPUT_JSONL)" "$(SPAN_BOUNDARY_PROMOTE_JSONL)"; then echo "state:           promoted target is up to date"; else echo "state:           patched output differs from promote target"; fi

promote-existing-spans:
	@echo "Promoting the existing-span patched split into the configured source split."
	@test -f "$(SPAN_BOUNDARY_OUTPUT_JSONL)" || { echo "Missing patched output: $(SPAN_BOUNDARY_OUTPUT_JSONL). Run make apply-existing-spans first."; exit 1; }
	@echo "Promoting $(SPAN_BOUNDARY_OUTPUT_JSONL) -> $(SPAN_BOUNDARY_PROMOTE_JSONL)"
	cp "$(SPAN_BOUNDARY_OUTPUT_JSONL)" "$(SPAN_BOUNDARY_PROMOTE_JSONL)"

refresh-existing-spans: apply-existing-spans promote-existing-spans

review-span-patches:
	@echo "Reviewing audit-suggested span patches and writing append-only decisions."
	$(PYTHON) -m lib.span_patch_review --candidates "$(SPAN_PATCH_CANDIDATES)" --decisions "$(SPAN_PATCH_DECISIONS)" --audit-id "$(SPAN_PATCH_AUDIT_ID)" --reviewer "$(REVIEWER)" --target-label "$(SPAN_PATCH_TARGET_LABEL)" --limit "$(REVIEW_MAX_ITEMS)" --summary-json "$(SPAN_PATCH_SUMMARY_JSON)" --queue-jsonl "$(SPAN_PATCH_QUEUE_JSONL)" $(ARGS)

apply-span-patches:
	@echo "Applying accepted or corrected span-patch decisions to a patched JSONL split."
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(SPAN_PATCH_SOURCE_JSONL)" --output-jsonl "$(SPAN_PATCH_OUTPUT_JSONL)" --candidates "$(SPAN_PATCH_CANDIDATES)" --decisions "$(SPAN_PATCH_DECISIONS)" --audit-id "$(SPAN_PATCH_AUDIT_ID)" --target-label "$(SPAN_PATCH_TARGET_LABEL)" --changes-jsonl "$(SPAN_PATCH_CHANGES_JSONL)" --changes-tsv "$(SPAN_PATCH_CHANGES_TSV)" --summary-json "$(SPAN_PATCH_APPLY_SUMMARY_JSON)" $(ARGS)

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

refresh-span-patches: apply-span-patches promote-span-patches

sample-newsagency-snippets sample-newsagencies:
	@echo "Sampling real Impresso search snippets for news-agency annotation."
	$(PYTHON) -m lib.sample_newsagencies --seeds "$(NEWSAGENCY_LABEL_METADATA)" --out "$(NEWSAGENCY_SNIPPETS)" --summary-out "$(NEWSAGENCY_SNIPPET_SUMMARY)" --languages $(NEWSAGENCY_SAMPLE_LANGS) --target-per-query-lang "$(NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(NEWSAGENCY_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(NEWSAGENCY_SAMPLE_YEAR_START)" --year-end "$(NEWSAGENCY_SAMPLE_YEAR_END)" --context-source "$(NEWSAGENCY_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(NEWSAGENCY_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --existing-issue-jsonl "$(TRAIN_JSONL)" --existing-issue-jsonl "$(VALIDATION_JSONL)" --existing-issue-jsonl "$(TEST_JSONL)" $(ARGS)

sample-needed-newsagency-snippets sample-needed-newsagencies:
	@echo "Sampling news-agency snippets for label/language coverage buckets below target."
	$(PYTHON) -m lib.sample_newsagencies --seeds "$(NEWSAGENCY_LABEL_METADATA)" --out "$(NEWSAGENCY_SNIPPETS)" --summary-out "$(NEWSAGENCY_SNIPPET_SUMMARY)" --languages $(NEWSAGENCY_SAMPLE_LANGS) --target-per-query-lang "$(NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(NEWSAGENCY_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(NEWSAGENCY_SAMPLE_YEAR_START)" --year-end "$(NEWSAGENCY_SAMPLE_YEAR_END)" --context-source "$(NEWSAGENCY_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(NEWSAGENCY_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --existing-issue-jsonl "$(TRAIN_JSONL)" --existing-issue-jsonl "$(VALIDATION_JSONL)" --existing-issue-jsonl "$(TEST_JSONL)" --coverage-json "$(ANNOTATION_STATS_JSON)" --only-under-target $(ARGS)

sample-radio-snippets sample-radio sample-radiostations:
	@echo "Sampling real Impresso search snippets for radio-station annotation."
	$(PYTHON) -m lib.sample_radiostations --seeds "$(RADIOSTATION_LABEL_METADATA)" --out "$(RADIOSTATION_SNIPPETS)" --summary-out "$(RADIOSTATION_SNIPPET_SUMMARY)" --languages $(RADIOSTATION_SAMPLE_LANGS) --target-per-query-lang "$(RADIOSTATION_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(RADIOSTATION_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(RADIOSTATION_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(RADIOSTATION_SAMPLE_YEAR_START)" --year-end "$(RADIOSTATION_SAMPLE_YEAR_END)" --context-source "$(RADIOSTATION_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(RADIOSTATION_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --existing-issue-jsonl "$(TRAIN_JSONL)" --existing-issue-jsonl "$(VALIDATION_JSONL)" --existing-issue-jsonl "$(TEST_JSONL)" --coverage-json "$(ANNOTATION_STATS_JSON)" $(if $(filter true,$(RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)

curate:
	@echo "Running the generic candidate curation command with ARGS."
	$(PYTHON) -m lib.curate_candidates $(ARGS)

import-legacy-hipe:
	@echo "Converting legacy HIPE TSV annotations into JSONL workbench data."
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
	$(PYTHON) -m lib.publish_dataset --input-dir "$(DATASET_SOURCE_DIR)" --output-dir "$(DATASET_OUTPUT_DIR)" --repo-id "$(DATASET)" --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json $(ARGS)

publish-testset:
	@echo "Publishing or dry-running publication of the testset."
	$(PYTHON) -m lib.publish_testset $(ARGS)

train:
	@echo "Fine-tuning the token-classification NER model on the configured train/validation splits."
	$(PYTHON) -m py_compile training/newsagency-radiostation-modernbert-classifier/src/mediaagency_modernbert/*.py
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-train --model-name-or-path "$(BASE_MODEL)" $(if $(CHECKPOINT),--checkpoint "$(CHECKPOINT)",) --train-jsonl "$(TRAIN_JSONL)" --validation-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)" --epochs "$(EPOCHS)" --train-batch-size "$(BATCH)" --eval-batch-size "$(EVAL_BATCH)" --gradient-accumulation-steps "$(GRADIENT_ACCUMULATION_STEPS)" $(if $(filter true,$(GRADIENT_CHECKPOINTING)),--gradient-checkpointing,--no-gradient-checkpointing) $(if $(filter true,$(FREEZE_BASE_MODEL)),--freeze-base-model,--no-freeze-base-model) --unfreeze-top-layers "$(UNFREEZE_TOP_LAYERS)" --optimizer "$(OPTIMIZER)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --learning-rate "$(LEARNING_RATE)" --weight-decay "$(WEIGHT_DECAY)" --warmup-steps "$(WARMUP_STEPS)" --logging-steps "$(LOGGING_STEPS)" --early-stopping-patience "$(EARLY_STOPPING_PATIENCE)" --early-stopping-metric "$(EARLY_STOPPING_METRIC)" --early-stopping-mode "$(EARLY_STOPPING_MODE)" --early-stopping-min-delta "$(EARLY_STOPPING_MIN_DELTA)" --seed "$(SEED)" --device "$(DEVICE)" $(ARGS)

test:
	@echo "Evaluating the configured model on the validation split."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

test-official:
	@echo "Evaluating the configured model on the test split for official metrics."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval:
	@echo "Evaluating train/validation/test to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TRAIN_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name train --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval-train:
	@echo "Evaluating train to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TRAIN_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name train --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval-validation:
	@echo "Evaluating validation to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval-test:
	@echo "Evaluating test to build gold-vs-prediction disagreement inputs."
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-review:
	@echo "Building the train/validation/test disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --train-jsonl "$(TRAIN_JSONL)" --train-predictions "$(CURATION_OUTPUT_DIR)/eval/train_predictions.jsonl" --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "train validation test" $(ARGS)

curation-review-train:
	@echo "Building the train disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --train-jsonl "$(TRAIN_JSONL)" --train-predictions "$(CURATION_OUTPUT_DIR)/eval/train_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "train" $(ARGS)

curation-review-validation:
	@echo "Building the validation disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "validation" $(ARGS)

curation-review-test:
	@echo "Building the test disagreement review queue from evaluation predictions."
	$(PYTHON) -m lib.build_curation_review --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "test" $(ARGS)

curate-legacy-eval: curation-eval curation-review

curate-legacy-train: curation-eval-train curation-review-train

curate-legacy-validation: curation-eval-validation curation-review-validation

curate-legacy-test: curation-eval-test curation-review-test

build-newsagency-snippets-from-legacy:
	@echo "Building bootstrap news-agency snippet candidates from existing JSONL splits."
	$(PYTHON) -m lib.build_newsagency_snippets --input "$(NEWSAGENCY_SNIPPET_SOURCE_DIR)/train.jsonl" --input "$(NEWSAGENCY_SNIPPET_SOURCE_DIR)/validation.jsonl" --input "$(NEWSAGENCY_SNIPPET_SOURCE_DIR)/test.jsonl" --output "$(NEWSAGENCY_LEGACY_SNIPPETS)" --context-radius "$(NEWSAGENCY_SNIPPET_CONTEXT_RADIUS)" --limit "$(NEWSAGENCY_SNIPPET_LIMIT)" $(ARGS)

suggest-newsagency-snippet-spans score-newsagency-snippets:
	@echo "Suggesting news-agency spans for sampled snippets with the configured model."
	$(PYTHON) -m lib.score_newsagency_snippets --input "$(NEWSAGENCY_SNIPPETS)" --output "$(NEWSAGENCY_SCORED_SNIPPETS)" --model "$(HF_MODEL)" --device "$(DEVICE)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --auto-accept-min-confidence "$(AUTO_ACCEPT_MIN_CONFIDENCE)" --auto-accept-min-margin "$(AUTO_ACCEPT_MIN_MARGIN)" --auto-accept-multiple-min-confidence "$(AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE)" $(ARGS)

review-newsagency-snippet-spans review-newsagency-snippets:
	@echo "Reviewing news-agency snippet span suggestions and writing append-only decisions."
	$(PYTHON) -m lib.review_newsagency_snippets --input "$(NEWSAGENCY_SCORED_SNIPPETS)" --output "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --reviewer "$(REVIEWER)" --limit "$(REVIEW_MAX_ITEMS)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --coverage-json "$(REVIEW_COVERAGE_JSON)" $(if $(filter true,$(REVIEW_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)

split-newsagency-snippets export-newsagency-snippets:
	@echo "Splitting accepted news-agency snippet decisions into train/validation/test JSONL."
	$(PYTHON) -m lib.export_snippet_training_data --input "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --output "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --validation-output "$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --test-output "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --validation-fraction "$(SNIPPET_VALIDATION_FRACTION)" --test-fraction "$(SNIPPET_TEST_FRACTION)" --split-seed "$(SNIPPET_SPLIT_SEED)" --label-map "$(LABEL_MAP)" --extra-label-metadata "$(NEWSAGENCY_LABEL_METADATA)" $(ARGS)

suggest-radio-snippet-spans suggest-radiostation-snippet-spans score-radiostation-snippets:
	@echo "Suggesting radio-station spans for sampled snippets with alias matching and the configured model."
	$(PYTHON) -m lib.score_radiostation_snippets --input "$(RADIOSTATION_SNIPPETS)" --output "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostations "$(RADIOSTATION_LABEL_METADATA)" --newsagencies "$(NEWSAGENCY_LABEL_METADATA)" --model "$(HF_MODEL)" --device "$(DEVICE)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" $(ARGS)

review-radio-snippet-spans review-radiostation-snippet-spans review-radiostation-spans:
	@echo "Reviewing radio-station snippet span suggestions and writing append-only decisions."
	$(PYTHON) -m lib.review_newsagency_snippets --input "$(RADIOSTATION_SCORED_SNIPPETS)" --output "$(RADIOSTATION_REVIEWED_SNIPPETS)" --decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --reviewer "$(REVIEWER)" --limit "$(REVIEW_MAX_ITEMS)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --review-prefix "radiostation-span" --coverage-json "$(REVIEW_COVERAGE_JSON)" $(if $(filter true,$(REVIEW_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)

split-radio-snippets split-radiostation-snippets export-radiostation-snippets:
	@echo "Splitting accepted radio-station snippet decisions into train/validation/test JSONL."
	$(PYTHON) -m lib.export_snippet_training_data --input "$(RADIOSTATION_REVIEWED_SNIPPETS)" --output "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --validation-output "$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --test-output "$(RADIOSTATION_SNIPPET_TEST_JSONL)" --validation-fraction "$(SNIPPET_VALIDATION_FRACTION)" --test-fraction "$(SNIPPET_TEST_FRACTION)" --split-seed "$(SNIPPET_SPLIT_SEED)" --label-map "$(LABEL_MAP)" --extra-label-metadata "$(RADIOSTATION_LABEL_METADATA)" --extra-label-metadata "$(NEWSAGENCY_LABEL_METADATA)" $(ARGS)

preview-promote-snippets preview-snippet-merge snippet-promotion-status:
	@echo "Previewing promotion of split snippet rows into the configured dataset splits."
	$(PYTHON) -m lib.promote_snippet_splits --dry-run --base train="$(SNIPPET_PROMOTE_TRAIN_JSONL)" --base validation="$(SNIPPET_PROMOTE_VALIDATION_JSONL)" --base test="$(SNIPPET_PROMOTE_TEST_JSONL)" --snippet train="$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --snippet train="$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --snippet validation="$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --snippet validation="$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --snippet test="$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --snippet test="$(RADIOSTATION_SNIPPET_TEST_JSONL)" --summary-json "$(SNIPPET_PROMOTE_SUMMARY_JSON)" $(ARGS)

promote-snippets merge-snippets:
	@echo "Promoting split snippet rows into the configured dataset splits."
	$(PYTHON) -m lib.promote_snippet_splits --base train="$(SNIPPET_PROMOTE_TRAIN_JSONL)" --base validation="$(SNIPPET_PROMOTE_VALIDATION_JSONL)" --base test="$(SNIPPET_PROMOTE_TEST_JSONL)" --snippet train="$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --snippet train="$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --snippet validation="$(NEWSAGENCY_SNIPPET_VALIDATION_JSONL)" --snippet validation="$(RADIOSTATION_SNIPPET_VALIDATION_JSONL)" --snippet test="$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --snippet test="$(RADIOSTATION_SNIPPET_TEST_JSONL)" --summary-json "$(SNIPPET_PROMOTE_SUMMARY_JSON)" $(ARGS)

refresh-snippet-dataset refresh-snippets: split-newsagency-snippets split-radio-snippets promote-snippets

review-curation:
	@echo "Reviewing pending gold-vs-prediction disagreement items in the terminal."
	$(PYTHON) -m lib.review_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/todo_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --reviewer "$(REVIEWER)" $(ARGS)

validate-curation:
	@echo "Validating reviewed gold-vs-prediction disagreement decisions."
	$(PYTHON) -m lib.validate_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --require-complete $(ARGS)

apply-curation:
	@echo "Applying reviewed curation decisions to train/validation/test JSONL annotations."
	$(PYTHON) -m lib.apply_curation_decisions --input-dir "$(CURATION_INPUT_DIR)" --output-dir "$(CURATION_APPLIED_DIR)" --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --splits "train validation test" --require-complete $(ARGS)

push-model:
	@echo "Pushing the fine-tuned model payload to Hugging Face."
	$(PYTHON) -m lib.push_model_to_hub --repo-id "$(HF_MODEL)" --model "$(MODEL)" --card hf_model/README.md $(ARGS)
