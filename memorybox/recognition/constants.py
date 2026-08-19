"""P2-I8B recognition constants (POC-promoted, not a research stack)."""

MODEL_ID = "insightface-buffalo_l"
METHOD_NATIVE = "mb_native_i8b"
METHOD_OWNER_LEARN = "owner_learn"
LINEAGE_NATIVE = "mb_native_i8b"
LINEAGE_LEGACY = "i1_hvrt"

# Cosine on buffalo_l — same threshold as hvrt/hvrt/face_learn.py
FACE_SIM_THRESHOLD = 0.38
UNCERTAIN_FLOOR = 0.28
RANGE_GAP_SEC = 8.0

MAX_EXEMPLARS = 16
MIN_CROP_PX = 24
NEAR_DUP_COSINE = 0.97

REQUEUE_REASONS = frozenset(
    {"exemplar_change", "correction", "owner_learn", "new_video"}
)

PRIORITY_CURRENT_VIDEO = 1
PRIORITY_OTHER_VIDEO = 50
