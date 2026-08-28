# Decoder/supervision experiment for released dataset v2.0.0.
#
# This config inherits the released HF-verification setup and defines a small
# factorial validation-only experiment:
#   2 supervision regimes x 3 seeds x 3 decoders

include configs/model-v2.0.0-4layers-hf-verification.mk

EXPERIMENT_ID = decoding-v2.0.0
EXPERIMENT_SEEDS = 17 42 73
EXPERIMENT_SUPERVISION = first_subtoken all_subtokens_b_to_i
EXPERIMENT_DECODERS = first_subtoken first_subtoken_viterbi all_subtoken_viterbi
EXPERIMENT_TRAIN_DECODER = first_subtoken_viterbi
EXPERIMENT_BASELINE_DECODER = first_subtoken_viterbi
EXPERIMENT_ROOT = models.d/experiments/$(EXPERIMENT_ID)
EXPERIMENT_REPORT_DIR = reports.d/experiments/$(EXPERIMENT_ID)
