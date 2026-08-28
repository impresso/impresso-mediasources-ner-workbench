# Layer-adaptation experiment for released dataset v2.0.0.
#
# This config fixes the best 512-context protocol and varies only the number of
# unfrozen top ModernBERT layers:
#   supervision -> all_subtokens_b_to_i
#   decoder     -> first_subtoken_viterbi
#   window      -> 512 / 256 / 32
#   layers      -> 4, 8

include configs/model-v2.0.0-4layers-hf-verification.mk

LAYER_EXPERIMENT_ID = layers-v2.0.0
LAYER_EXPERIMENT_SEEDS = 17 42 73
LAYER_EXPERIMENT_LAYERS = 4 8
LAYER_EXPERIMENT_BASELINE_LAYERS = 4
LAYER_EXPERIMENT_DECODER = first_subtoken_viterbi
LAYER_EXPERIMENT_ROOT = models.d/experiments/$(LAYER_EXPERIMENT_ID)
LAYER_EXPERIMENT_REPORT_DIR = reports.d/experiments/$(LAYER_EXPERIMENT_ID)
LAYER_EXPERIMENT_REUSED_ROOT = models.d/experiments/decoding-v2.0.0/all_subtokens_b_to_i
LAYER_EXPERIMENT_BASELINE_RESULTS_TSV = reports.d/experiments/decoding-v2.0.0/results.tsv
