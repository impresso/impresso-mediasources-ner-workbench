# v2.0.0 training variant that adapts the final 4 ModernBERT layers.
#
# The last 4 layers include the preceding full-attention layer plus the final
# sliding/sliding/full block. This keeps the v2 dataset, label-all-tokens setup,
# and default first_subtoken_viterbi evaluation decoder.

include configs/model-v2.0.0.mk

MODEL = models.d/newsagency_radiostation_modernbert_v2.0.0-label-all-tokens-4layers
SELECTED_MODEL = $(MODEL)/best
HF_MODEL = $(SELECTED_MODEL)
CURATION_MODEL = $(SELECTED_MODEL)

UNFREEZE_TOP_LAYERS = 4
