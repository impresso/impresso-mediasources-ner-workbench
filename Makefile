.DEFAULT_GOAL := help

PYTHON ?= python3
ARGS ?=
CFG ?= configs/model-v0.1.0.mk

include $(CFG)

export HF_HOME

.PHONY: help smoke validate-labels sample-newsagencies sample-radiostations curate import-legacy-hipe export-dataset download-mlm-sources build-mlm-data pretrain-mlm push-mlm-model publish-dataset publish-testset train test test-official curation-eval curation-review curate-legacy-eval push-model

help:
	@echo "Impresso media sources NER workbench"
	@echo ""
	@echo "Targets:"
	@echo "  make smoke                         Run lightweight contract checks"
	@echo "  make validate-labels               Validate canonical label metadata"
	@echo "  make sample-newsagencies ARGS=...  Sample news-agency candidates"
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
	@echo "  make push-model CFG=...            Push model payload to Hugging Face"

smoke:
	$(PYTHON) -m py_compile lib/*.py hf_model/pipeline.py
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

validate-labels:
	$(PYTHON) -m lib.validate_labels --newsagencies resources/newsagency_seeds.json --radiostations resources/radiostation_seeds.json

sample-newsagencies:
	$(PYTHON) -m lib.sample_newsagencies $(ARGS)

sample-radiostations:
	$(PYTHON) -m lib.sample_radiostations $(ARGS)

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
	$(PYTHON) -m lib.publish_dataset $(ARGS)

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

curation-review:
	$(PYTHON) -m lib.build_curation_review --validation-jsonl "$(VALIDATION_JSONL)" --validation-predictions "$(CURATION_OUTPUT_DIR)/eval/validation_predictions.jsonl" --test-jsonl "$(TEST_JSONL)" --test-predictions "$(CURATION_OUTPUT_DIR)/eval/test_predictions.jsonl" --output-dir "$(CURATION_OUTPUT_DIR)/review" --languages "$(CURATION_LANGS)" --context-radius "$(CURATION_CONTEXT_RADIUS)" $(ARGS)

curate-legacy-eval: curation-eval curation-review

push-model:
	$(PYTHON) -m lib.push_model_to_hub --repo-id "$(HF_MODEL)" --model "$(MODEL)" --card hf_model/README.md $(ARGS)
