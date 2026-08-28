# Context-length experiment for released dataset v2.0.0.
#
# This config fixes the best decoder-experiment protocol and varies only the
# coherent context/window setup:
#   ctx512  -> 512 / 256 / 32, reused from decoding-v2.0.0 baseline
#   ctx1024 -> 1024 / 512 / 64
#   ctx2048 -> 2048 / 1024 / 128

include configs/model-v2.0.0-4layers-hf-verification.mk

CONTEXT_EXPERIMENT_ID = context-v2.0.0
CONTEXT_EXPERIMENT_SEEDS = 17 42 73
CONTEXT_EXPERIMENT_CONTEXTS = ctx512 ctx1024 ctx2048
CONTEXT_EXPERIMENT_DECODER = first_subtoken_viterbi
CONTEXT_EXPERIMENT_SUPERVISION = all_subtokens_b_to_i
CONTEXT_EXPERIMENT_ROOT = models.d/experiments/$(CONTEXT_EXPERIMENT_ID)
CONTEXT_EXPERIMENT_REPORT_DIR = reports.d/experiments/$(CONTEXT_EXPERIMENT_ID)
CONTEXT_EXPERIMENT_REUSED_ROOT = models.d/experiments/decoding-v2.0.0/all_subtokens_b_to_i
CONTEXT_EXPERIMENT_BASELINE_RESULTS_TSV = reports.d/experiments/decoding-v2.0.0/results.tsv
