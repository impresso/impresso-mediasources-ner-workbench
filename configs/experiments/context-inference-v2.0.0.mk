# Inference-context matrix for released dataset v2.0.0.
#
# This is a validation-only evaluation experiment. It reuses already trained
# all_subtokens_b_to_i checkpoints and varies only the inference window:
#
#   train ctx512  -> infer ctx512 / ctx1024 / ctx2048
#   train ctx1024 -> infer ctx512 / ctx1024 / ctx2048
#   train ctx2048 -> infer ctx512 / ctx1024 / ctx2048

include configs/model-v2.0.0-4layers-hf-verification.mk

CONTEXT_EXPERIMENT_ID = context-inference-v2.0.0
CONTEXT_EXPERIMENT_SEEDS = 17 42 73
CONTEXT_EXPERIMENT_CONTEXTS = ctx512 ctx1024 ctx2048
CONTEXT_EXPERIMENT_INFER_CONTEXTS = ctx512 ctx1024 ctx2048
CONTEXT_EXPERIMENT_FULL_MATRIX = true
CONTEXT_EXPERIMENT_DECODER = first_subtoken_viterbi
CONTEXT_EXPERIMENT_SUPERVISION = all_subtokens_b_to_i
CONTEXT_EXPERIMENT_ROOT = models.d/experiments/$(CONTEXT_EXPERIMENT_ID)
CONTEXT_EXPERIMENT_TRAINED_ROOT = models.d/experiments/context-v2.0.0
CONTEXT_EXPERIMENT_REPORT_DIR = reports.d/experiments/$(CONTEXT_EXPERIMENT_ID)
CONTEXT_EXPERIMENT_REUSED_ROOT = models.d/experiments/decoding-v2.0.0/all_subtokens_b_to_i
CONTEXT_EXPERIMENT_BASELINE_RESULTS_TSV = reports.d/experiments/decoding-v2.0.0/results.tsv
