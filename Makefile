.DEFAULT_GOAL := help

PYTHON ?= python3
ARGS ?=
CFG ?= configs/model-v2.0.0.mk

include $(CFG)

export HF_HOME

.PHONY: help help-review smoke clean clean-dry-run clean-all-data validate-labels annotation-stats curation-state curation-state-json snippet-state dataset-state legacy-curation-state audit-empty-training-docs review-span-patches apply-span-patches sample-newsagencies sample-needed-newsagencies sample-radiostations curate import-legacy-hipe export-dataset download-mlm-sources build-mlm-data pretrain-mlm push-mlm-model publish-dataset publish-testset train test test-official curation-eval curation-eval-validation curation-eval-test curation-review curation-review-validation curation-review-test curate-legacy-eval curate-legacy-validation curate-legacy-test build-newsagency-snippets-from-legacy score-newsagency-snippets review-newsagency-snippets export-newsagency-snippets score-radiostation-snippets review-radiostation-spans export-radiostation-snippets review-curation validate-curation apply-curation push-model

help:
	@echo "Impresso media sources NER workbench"
	@echo ""
	@echo "Targets:"
	@echo "  make smoke                         Run lightweight contract checks"
	@echo "  make clean-dry-run                 Show ignored/generated local data that clean would remove"
	@echo "  make clean                         Remove ignored/generated local data; keep data/releases"
	@echo "  make clean-all-data                Alias for clean; release snapshots are still preserved"
	@echo "  make validate-labels               Validate canonical label metadata"
	@echo "  make annotation-stats              Summarize annotation coverage by label/language"
	@echo "  make curation-state                Summarize curation, snippets, and dataset state"
	@echo "  make snippet-state                 Summarize sampled/scored/reviewed/exported snippets"
	@echo "  make dataset-state                 Summarize staging and configured published dataset state"
	@echo "  make audit-empty-training-docs     Score training docs with no gold entities for missing mentions"
	@echo "  make review-span-patches           Review audit-suggested span patches"
	@echo "  make apply-span-patches            Apply accepted audit span patch decisions to JSONL"
	@echo "  make sample-newsagencies ARGS=...  Sample real news-agency search snippets"
	@echo "  make sample-needed-newsagencies    Sample news-agency label/language buckets below target"
	@echo "  make sample-radiostations ARGS=... Sample radio-station candidates"
	@echo "  make curate ARGS=...               Curate candidate JSONL"
	@echo "  make import-legacy-hipe ARGS=...   Convert legacy HIPE TSV annotations to JSONL"
	@echo "  make export-dataset                Export curated JSONL training data"
	@echo "  make download-mlm-sources          Download compiled Impresso MLM source files"
	@echo "  make build-mlm-data                Build balanced multilingual Impresso MLM data"
	@echo "  make pretrain-mlm                  Continue MLM pretraining for multilingual Impresso BERT"
	@echo "  make push-mlm-model                Push continued MLM model payload to Hugging Face"
	@echo "  make publish-dataset ARGS=...      Publish or dry-run training dataset"
	@echo "  make publish-testset ARGS=...      Publish or dry-run testset"
	@echo "  make train CFG=...                 Train via training submodule"
	@echo "  make test CFG=...                  Evaluate via training submodule"
	@echo "  make test-official CFG=...         Evaluate and record official metrics"
	@echo "  make curate-legacy-eval CFG=...    Evaluate dev/test and build curation review JSONL"
	@echo "  make curate-legacy-validation CFG=... Evaluate only legacy dev/validation for curation"
	@echo "  make curate-legacy-test CFG=...    Evaluate only legacy test for curation"
	@echo "  make build-newsagency-snippets-from-legacy Build bootstrap snippet candidates from legacy JSONL"
	@echo "  make score-newsagency-snippets     Score sampled news-agency snippets with current model"
	@echo "  make review-newsagency-snippets REVIEWER=... Review uncertain news-agency snippets"
	@echo "  make export-newsagency-snippets    Export accepted news-agency snippets to training JSONL"
	@echo "  make score-radiostation-snippets   Score sampled radio-station snippets with alias matching"
	@echo "  make review-radiostation-spans     Review radio-station span suggestions"
	@echo "  make export-radiostation-snippets  Export accepted radio-station snippets to training JSONL"
	@echo "  make review-curation REVIEWER=...  Review pending curation disagreements in terminal"
	@echo "  make validate-curation CFG=...     Validate reviewed curation decisions"
	@echo "  make apply-curation CFG=...        Apply reviewed decisions to JSONL annotations"
	@echo "  make push-model CFG=...            Push model payload to Hugging Face"

help-review:
	@echo "Review and curation targets"
	@echo ""
	@echo "HIPE-derived dev/test correction:"
	@echo "  make curate-legacy-eval CURATION_MODEL=...   Score validation+test and build review queue"
	@echo "  make curate-legacy-validation CURATION_MODEL=... Score validation only"
	@echo "  make curate-legacy-test CURATION_MODEL=...   Score test only"
	@echo "  make review-curation                         Review pending gold/prediction disagreements"
	@echo "  make validate-curation                       Validate curation decisions"
	@echo "  make apply-curation                          Write curated JSONL folds"
	@echo ""
	@echo "Audit-driven span patches:"
	@echo "  make audit-empty-training-docs                Score empty-gold training docs for suspicious missed spans"
	@echo "  make review-span-patches                      Review audit-suggested span patches"
	@echo "  make apply-span-patches                       Apply accepted/corrected span patches to JSONL"
	@echo ""
	@echo "News-agency snippet review:"
	@echo "  make sample-newsagencies                    Sample real Impresso search snippets"
	@echo "  make sample-needed-newsagencies             Sample label/language buckets below target"
	@echo "  make build-newsagency-snippets-from-legacy   Bootstrap snippet candidates from legacy JSONL"
	@echo "  make score-newsagency-snippets               Score sampled snippets with HF_MODEL"
	@echo "  make review-newsagency-snippets              Review uncertain snippets; press i for label info"
	@echo "  make export-newsagency-snippets              Export accepted snippets to training JSONL"
	@echo ""
	@echo "Radio-station snippet review:"
	@echo "  make score-radiostation-snippets             Score existing sampled radio snippets by alias"
	@echo "  make review-radiostation-spans               Review radio-station span suggestions"
	@echo "  make export-radiostation-snippets            Export accepted spans to training JSONL"
	@echo ""
	@echo "State summaries:"
	@echo "  make curation-state                          Summarize all curation and dataset state"
	@echo "  make snippet-state                           Summarize snippet sampling/review/export state"
	@echo "  make legacy-curation-state                   Summarize HIPE-derived disagreement curation state"
	@echo "  make dataset-state                           Summarize staging and published dataset config"
	@echo "  make curation-state-json                     Write $(CURATION_STATE_JSON)"
	@echo ""
	@echo "Useful overrides:"
	@echo "  REVIEWER=$$USER, REVIEW_MAX_ITEMS=20, NEWSAGENCY_SNIPPETS=..., NEWSAGENCY_LEGACY_SNIPPETS=..., RADIOSTATION_SNIPPETS=..."
	@echo "  REVIEW_COVERAGE_JSON=$(ANNOTATION_STATS_JSON), REVIEW_ONLY_UNDER_TARGET=true"
	@echo "  ANNOTATION_MAIN_LANGS='$(ANNOTATION_MAIN_LANGS)', ANNOTATION_SIDE_LANGS='$(ANNOTATION_SIDE_LANGS)'"
	@echo "  ANNOTATION_MAIN_TARGET_PER_LABEL_LANG=$(ANNOTATION_MAIN_TARGET_PER_LABEL_LANG), ANNOTATION_SIDE_TARGET_PER_LABEL_LANG=$(ANNOTATION_SIDE_TARGET_PER_LABEL_LANG)"
	@echo "  AUTO_ACCEPT_MIN_CONFIDENCE=0.99, AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE=\$$(AUTO_ACCEPT_MIN_CONFIDENCE), AUTO_ACCEPT_MIN_MARGIN=0.30"
	@echo "  CURATION_STATE_JSON=$(CURATION_STATE_JSON)"

smoke:
	$(PYTHON) -m py_compile lib/*.py hf_model/pipeline.py
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

clean:
	$(PYTHON) -m lib.clean_workbench

clean-dry-run:
	$(PYTHON) -m lib.clean_workbench --dry-run

clean-all-data: clean

validate-labels:
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

annotation-stats:
	$(PYTHON) -m lib.annotation_stats --target-per-label "$(ANNOTATION_TARGET_PER_LABEL)" --main-languages $(ANNOTATION_MAIN_LANGS) --side-languages $(ANNOTATION_SIDE_LANGS) --main-target-per-label-language "$(ANNOTATION_MAIN_TARGET_PER_LABEL_LANG)" --side-target-per-label-language "$(ANNOTATION_SIDE_TARGET_PER_LABEL_LANG)" $(foreach target,$(ANNOTATION_LANGUAGE_TARGETS),--language-target "$(target)") --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --legacy-jsonl "$(TRAIN_JSONL)" --legacy-jsonl "$(VALIDATION_JSONL)" --legacy-jsonl "$(TEST_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" --newsagency-reviewed-jsonl "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --radiostation-reviewed-jsonl "$(RADIOSTATION_REVIEWED_SNIPPETS)" --json-output "$(ANNOTATION_STATS_JSON)" --tsv-output "$(ANNOTATION_STATS_TSV)" $(ARGS)

curation-state:
	$(PYTHON) -m lib.curation_state --section all --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

curation-state-json:
	$(PYTHON) -m lib.curation_state --section all --json-output "$(CURATION_STATE_JSON)" --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

snippet-state:
	$(PYTHON) -m lib.curation_state --section snippets --newsagency-snippets "$(NEWSAGENCY_SNIPPETS)" --newsagency-snippet-summary "$(NEWSAGENCY_SNIPPET_SUMMARY)" --newsagency-scored-snippets "$(NEWSAGENCY_SCORED_SNIPPETS)" --newsagency-reviewed-snippets "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --newsagency-snippet-decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --newsagency-snippet-train-jsonl "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --newsagency-snippet-test-jsonl "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --radiostation-snippets "$(RADIOSTATION_SNIPPETS)" --radiostation-snippet-summary "$(RADIOSTATION_SNIPPET_SUMMARY)" --radiostation-scored-snippets "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostation-reviewed-snippets "$(RADIOSTATION_REVIEWED_SNIPPETS)" --radiostation-snippet-decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --radiostation-snippet-train-jsonl "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --radiostation-snippet-test-jsonl "$(RADIOSTATION_SNIPPET_TEST_JSONL)" $(ARGS)

dataset-state:
	$(PYTHON) -m lib.curation_state --section dataset --dataset "$(DATASET)" --dataset-revision "$(DATASET_REVISION)" --dataset-source-dir "$(DATASET_SOURCE_DIR)" --dataset-output-dir "$(DATASET_OUTPUT_DIR)" $(ARGS)

legacy-curation-state:
	$(PYTHON) -m lib.curation_state --section legacy --curation-output-dir "$(CURATION_OUTPUT_DIR)" --curation-input-dir "$(CURATION_INPUT_DIR)" --curation-applied-dir "$(CURATION_APPLIED_DIR)" $(ARGS)

audit-empty-training-docs:
	$(PYTHON) -m lib.audit_empty_training_docs prepare --input-jsonl "$(EMPTY_TRAIN_SOURCE_JSONL)" --label-map "$(EMPTY_TRAIN_LABEL_MAP)" --output-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_eval_input.jsonl" --summary-json "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prepare_summary.json"
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(EMPTY_TRAIN_MODEL)" --eval-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_eval_input.jsonl" --label-map "$(EMPTY_TRAIN_LABEL_MAP)" --output-dir "$(EMPTY_TRAIN_AUDIT_DIR)/eval" --split-name empty_train --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)
	$(PYTHON) -m lib.audit_empty_training_docs summarize --source-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_eval_input.jsonl" --predictions-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/eval/empty_train_predictions.jsonl" --candidates-jsonl "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_candidates.jsonl" --candidates-tsv "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_candidates.tsv" --summary-json "$(EMPTY_TRAIN_AUDIT_DIR)/empty_train_prediction_summary.json"

review-span-patches:
	$(PYTHON) -m lib.span_patch_review --candidates "$(SPAN_PATCH_CANDIDATES)" --decisions "$(SPAN_PATCH_DECISIONS)" --audit-id "$(SPAN_PATCH_AUDIT_ID)" --reviewer "$(REVIEWER)" --target-label "$(SPAN_PATCH_TARGET_LABEL)" --limit "$(REVIEW_MAX_ITEMS)" --summary-json "$(SPAN_PATCH_SUMMARY_JSON)" --queue-jsonl "$(SPAN_PATCH_QUEUE_JSONL)" $(ARGS)

apply-span-patches:
	$(PYTHON) -m lib.apply_span_patch_decisions --input-jsonl "$(SPAN_PATCH_SOURCE_JSONL)" --output-jsonl "$(SPAN_PATCH_OUTPUT_JSONL)" --candidates "$(SPAN_PATCH_CANDIDATES)" --decisions "$(SPAN_PATCH_DECISIONS)" --audit-id "$(SPAN_PATCH_AUDIT_ID)" --target-label "$(SPAN_PATCH_TARGET_LABEL)" --changes-jsonl "$(SPAN_PATCH_CHANGES_JSONL)" --changes-tsv "$(SPAN_PATCH_CHANGES_TSV)" --summary-json "$(SPAN_PATCH_APPLY_SUMMARY_JSON)" $(ARGS)

sample-newsagencies:
	$(PYTHON) -m lib.sample_newsagencies --seeds "$(NEWSAGENCY_LABEL_METADATA)" --out "$(NEWSAGENCY_SNIPPETS)" --summary-out "$(NEWSAGENCY_SNIPPET_SUMMARY)" --languages $(NEWSAGENCY_SAMPLE_LANGS) --target-per-query-lang "$(NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(NEWSAGENCY_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(NEWSAGENCY_SAMPLE_YEAR_START)" --year-end "$(NEWSAGENCY_SAMPLE_YEAR_END)" --context-source "$(NEWSAGENCY_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(NEWSAGENCY_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" $(ARGS)

sample-needed-newsagencies:
	$(PYTHON) -m lib.sample_newsagencies --seeds "$(NEWSAGENCY_LABEL_METADATA)" --out "$(NEWSAGENCY_SNIPPETS)" --summary-out "$(NEWSAGENCY_SNIPPET_SUMMARY)" --languages $(NEWSAGENCY_SAMPLE_LANGS) --target-per-query-lang "$(NEWSAGENCY_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(NEWSAGENCY_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(NEWSAGENCY_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(NEWSAGENCY_SAMPLE_YEAR_START)" --year-end "$(NEWSAGENCY_SAMPLE_YEAR_END)" --context-source "$(NEWSAGENCY_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(NEWSAGENCY_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --coverage-json "$(ANNOTATION_STATS_JSON)" --only-under-target $(ARGS)

sample-radiostations:
	$(PYTHON) -m lib.sample_radiostations --seeds "$(RADIOSTATION_LABEL_METADATA)" --out "$(RADIOSTATION_SNIPPETS)" --summary-out "$(RADIOSTATION_SNIPPET_SUMMARY)" --languages $(RADIOSTATION_SAMPLE_LANGS) --target-per-query-lang "$(RADIOSTATION_SAMPLE_TARGET_PER_QUERY_LANG)" --max-per-label "$(RADIOSTATION_SAMPLE_MAX_PER_LABEL)" --max-queries-per-label "$(RADIOSTATION_SAMPLE_MAX_QUERIES_PER_LABEL)" --year-start "$(RADIOSTATION_SAMPLE_YEAR_START)" --year-end "$(RADIOSTATION_SAMPLE_YEAR_END)" --context-source "$(RADIOSTATION_SAMPLE_CONTEXT_SOURCE)" --context-chars "$(RADIOSTATION_SAMPLE_CONTEXT_CHARS)" --sample-registry "$(SAMPLE_ENTITY_REGISTRY)" --coverage-json "$(ANNOTATION_STATS_JSON)" $(if $(filter true,$(RADIOSTATION_SAMPLE_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)

curate:
	$(PYTHON) -m lib.curate_candidates $(ARGS)

import-legacy-hipe:
	$(PYTHON) -m lib.import_legacy_hipe_tsv $(ARGS)

export-dataset:
	$(PYTHON) -m lib.export_training_data $(ARGS)

download-mlm-sources:
	$(PYTHON) -m lib.download_mlm_sources --output-dir "$(MLM_DATASET_DIR)" $(foreach source,$(MLM_SOURCE_URLS),--source "$(source)") $(ARGS)

build-mlm-data:
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.mlm_data --dataset-dir "$(MLM_DATASET_DIR)" --output-dir "$(MLM_DATA_DIR)" --languages "$(MLM_LANGS)" $(if $(filter-out 0,$(MLM_MAX_PER_LANGUAGE)),--max-per-language "$(MLM_MAX_PER_LANGUAGE)",--target-total "$(MLM_TARGET_TOTAL)") --validation-fraction "$(MLM_VAL_FRACTION)" --ocr-min "$(MLM_OCR_MIN)" --min-chars "$(MLM_MIN_CHARS)" --progress-interval "$(MLM_PROGRESS_INTERVAL)" --seed "$(SEED)" $(ARGS)

pretrain-mlm:
	$(PYTHON) -m py_compile training/newsagency-radiostation-modernbert-classifier/src/mediaagency_modernbert/*.py
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.mlm --model-name-or-path "$(MLM_BASE_MODEL)" --train-file "$(MLM_DATA_DIR)/train.json" --validation-file "$(MLM_DATA_DIR)/validation.json" --output-dir "$(MLM_OUTPUT_DIR)" --max-sequence-len "$(MLM_MAX_LEN)" $(if $(filter true,$(MLM_PAD_TO_MAX_LENGTH)),--pad-to-max-length,--no-pad-to-max-length) --tokenized-cache-dir "$(MLM_TOKENIZED_CACHE_DIR)" --preprocessing-num-workers "$(MLM_PREPROCESSING_NUM_WORKERS)" --map-batch-size "$(MLM_MAP_BATCH_SIZE)" --max-train-samples "$(MLM_MAX_TRAIN_SAMPLES)" --max-eval-samples "$(MLM_MAX_EVAL_SAMPLES)" --mlm-probability "$(MLM_PROBABILITY)" --epochs "$(MLM_EPOCHS)" --train-batch-size "$(MLM_BATCH)" --eval-batch-size "$(MLM_EVAL_BATCH)" --gradient-accumulation-steps "$(MLM_GRADIENT_ACCUMULATION_STEPS)" $(if $(filter true,$(MLM_GRADIENT_CHECKPOINTING)),--gradient-checkpointing,--no-gradient-checkpointing) --learning-rate "$(MLM_LEARNING_RATE)" --weight-decay "$(MLM_WEIGHT_DECAY)" --warmup-steps "$(MLM_WARMUP_STEPS)" --warmup-fraction "$(MLM_WARMUP_FRACTION)" --evals-per-epoch "$(MLM_EVALS_PER_EPOCH)" --save-strategy "$(MLM_SAVE_STRATEGY)" --save-steps "$(MLM_SAVE_STEPS)" --save-total-limit "$(MLM_SAVE_TOTAL_LIMIT)" --logging-steps "$(MLM_LOGGING_STEPS)" --seed "$(SEED)" $(ARGS)

push-mlm-model:
	$(PYTHON) -m lib.push_mlm_model_to_hub --repo-id "$(MLM_HF_MODEL)" --model-dir "$(MLM_OUTPUT_DIR)/final" --card hf_mlm_model/README.md $(ARGS)

publish-dataset:
	$(PYTHON) -m lib.publish_dataset --input-dir "$(DATASET_SOURCE_DIR)" --output-dir "$(DATASET_OUTPUT_DIR)" --repo-id "$(DATASET)" --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json $(ARGS)

publish-testset:
	$(PYTHON) -m lib.publish_testset $(ARGS)

train:
	$(PYTHON) -m py_compile training/newsagency-radiostation-modernbert-classifier/src/mediaagency_modernbert/*.py
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-train --model-name-or-path "$(BASE_MODEL)" $(if $(CHECKPOINT),--checkpoint "$(CHECKPOINT)",) --train-jsonl "$(TRAIN_JSONL)" --validation-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)" --epochs "$(EPOCHS)" --train-batch-size "$(BATCH)" --eval-batch-size "$(EVAL_BATCH)" --gradient-accumulation-steps "$(GRADIENT_ACCUMULATION_STEPS)" $(if $(filter true,$(GRADIENT_CHECKPOINTING)),--gradient-checkpointing,--no-gradient-checkpointing) $(if $(filter true,$(FREEZE_BASE_MODEL)),--freeze-base-model,--no-freeze-base-model) --unfreeze-top-layers "$(UNFREEZE_TOP_LAYERS)" --optimizer "$(OPTIMIZER)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --learning-rate "$(LEARNING_RATE)" --weight-decay "$(WEIGHT_DECAY)" --warmup-steps "$(WARMUP_STEPS)" --logging-steps "$(LOGGING_STEPS)" --early-stopping-patience "$(EARLY_STOPPING_PATIENCE)" --early-stopping-metric "$(EARLY_STOPPING_METRIC)" --early-stopping-mode "$(EARLY_STOPPING_MODE)" --early-stopping-min-delta "$(EARLY_STOPPING_MIN_DELTA)" --seed "$(SEED)" --device "$(DEVICE)" $(ARGS)

test:
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

test-official:
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(MODEL)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval:
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval-validation:
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(VALIDATION_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name validation --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-eval-test:
	PYTHONPATH=$(TRAINING_PKG):$$PYTHONPATH $(PYTHON) -m mediaagency_modernbert.train --do-eval --checkpoint "$(CURATION_MODEL)" --eval-jsonl "$(TEST_JSONL)" --label-map "$(LABEL_MAP)" --output-dir "$(CURATION_OUTPUT_DIR)/eval" --split-name test --eval-batch-size "$(EVAL_BATCH)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --max-words-per-window "$(MAX_WORDS_PER_WINDOW)" --stride-words "$(STRIDE_WORDS)" --device "$(DEVICE)" $(ARGS)

curation-review:
	$(PYTHON) -m lib.build_curation_review --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "validation test" $(ARGS)

curation-review-validation:
	$(PYTHON) -m lib.build_curation_review --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "validation" $(ARGS)

curation-review-test:
	$(PYTHON) -m lib.build_curation_review --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --decisions-jsonl "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" --splits "test" $(ARGS)

curate-legacy-eval: curation-eval curation-review

curate-legacy-validation: curation-eval-validation curation-review-validation

curate-legacy-test: curation-eval-test curation-review-test

build-newsagency-snippets-from-legacy:
	$(PYTHON) -m lib.build_newsagency_snippets --input "$(NEWSAGENCY_SNIPPET_SOURCE_DIR)/train.jsonl" --input "$(NEWSAGENCY_SNIPPET_SOURCE_DIR)/validation.jsonl" --input "$(NEWSAGENCY_SNIPPET_SOURCE_DIR)/test.jsonl" --output "$(NEWSAGENCY_LEGACY_SNIPPETS)" --context-radius "$(NEWSAGENCY_SNIPPET_CONTEXT_RADIUS)" --limit "$(NEWSAGENCY_SNIPPET_LIMIT)" $(ARGS)

score-newsagency-snippets:
	$(PYTHON) -m lib.score_newsagency_snippets --input "$(NEWSAGENCY_SNIPPETS)" --output "$(NEWSAGENCY_SCORED_SNIPPETS)" --model "$(HF_MODEL)" --device "$(DEVICE)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" --auto-accept-min-confidence "$(AUTO_ACCEPT_MIN_CONFIDENCE)" --auto-accept-min-margin "$(AUTO_ACCEPT_MIN_MARGIN)" --auto-accept-multiple-min-confidence "$(AUTO_ACCEPT_MULTIPLE_MIN_CONFIDENCE)" $(ARGS)

review-newsagency-snippets:
	$(PYTHON) -m lib.review_newsagency_snippets --input "$(NEWSAGENCY_SCORED_SNIPPETS)" --output "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --decisions "$(NEWSAGENCY_SNIPPET_DECISIONS)" --reviewer "$(REVIEWER)" --limit "$(REVIEW_MAX_ITEMS)" --label-metadata "$(NEWSAGENCY_LABEL_METADATA)" --coverage-json "$(REVIEW_COVERAGE_JSON)" $(if $(filter true,$(REVIEW_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)

export-newsagency-snippets:
	$(PYTHON) -m lib.export_snippet_training_data --input "$(NEWSAGENCY_REVIEWED_SNIPPETS)" --output "$(NEWSAGENCY_SNIPPET_TRAIN_JSONL)" --test-output "$(NEWSAGENCY_SNIPPET_TEST_JSONL)" --validation-fraction "$(SNIPPET_VALIDATION_FRACTION)" --test-fraction "$(SNIPPET_TEST_FRACTION)" --split-seed "$(SNIPPET_SPLIT_SEED)" --label-map "$(LABEL_MAP)" --extra-label-metadata "$(NEWSAGENCY_LABEL_METADATA)" $(ARGS)

score-radiostation-snippets:
	$(PYTHON) -m lib.score_radiostation_snippets --input "$(RADIOSTATION_SNIPPETS)" --output "$(RADIOSTATION_SCORED_SNIPPETS)" --radiostations "$(RADIOSTATION_LABEL_METADATA)" --newsagencies "$(NEWSAGENCY_LABEL_METADATA)" --model "$(HF_MODEL)" --device "$(DEVICE)" --max-sequence-len "$(MAX_SEQUENCE_LEN)" $(ARGS)

review-radiostation-spans:
	$(PYTHON) -m lib.review_newsagency_snippets --input "$(RADIOSTATION_SCORED_SNIPPETS)" --output "$(RADIOSTATION_REVIEWED_SNIPPETS)" --decisions "$(RADIOSTATION_SNIPPET_DECISIONS)" --reviewer "$(REVIEWER)" --limit "$(REVIEW_MAX_ITEMS)" --label-metadata "$(RADIOSTATION_LABEL_METADATA)" --review-prefix "radiostation-span" --coverage-json "$(REVIEW_COVERAGE_JSON)" $(if $(filter true,$(REVIEW_ONLY_UNDER_TARGET)),--only-under-target,) $(ARGS)

export-radiostation-snippets:
	$(PYTHON) -m lib.export_snippet_training_data --input "$(RADIOSTATION_REVIEWED_SNIPPETS)" --output "$(RADIOSTATION_SNIPPET_TRAIN_JSONL)" --test-output "$(RADIOSTATION_SNIPPET_TEST_JSONL)" --validation-fraction "$(SNIPPET_VALIDATION_FRACTION)" --test-fraction "$(SNIPPET_TEST_FRACTION)" --split-seed "$(SNIPPET_SPLIT_SEED)" --label-map "$(LABEL_MAP)" --extra-label-metadata "$(RADIOSTATION_LABEL_METADATA)" --extra-label-metadata "$(NEWSAGENCY_LABEL_METADATA)" $(ARGS)

review-curation:
	$(PYTHON) -m lib.review_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/todo_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --reviewer "$(REVIEWER)" $(ARGS)

validate-curation:
	$(PYTHON) -m lib.validate_curation --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --require-complete $(ARGS)

apply-curation:
	$(PYTHON) -m lib.apply_curation_decisions --input-dir "$(CURATION_INPUT_DIR)" --output-dir "$(CURATION_APPLIED_DIR)" --disagreements "$(CURATION_OUTPUT_DIR)/review/all_disagreements.jsonl" --decisions "$(CURATION_OUTPUT_DIR)/review/decisions.jsonl" --splits "validation test" --require-complete $(ARGS)

push-model:
	$(PYTHON) -m lib.push_model_to_hub --repo-id "$(HF_MODEL)" --model "$(MODEL)" --card hf_model/README.md $(ARGS)
