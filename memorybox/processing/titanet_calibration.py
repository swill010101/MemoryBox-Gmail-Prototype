"""Public-audio-only TitaNet threshold policy; no model or runtime I/O at import."""
from __future__ import annotations

import math

PUBLIC_CORPUS_SHA256 = "76f87d090650617fca0cac8f88b9416e0ebf80350acb97b343a85fa903728ab3"
UNCERTAIN = 0.30
MATCH = 0.45


def decision(score: float) -> str:
    return "match" if score >= MATCH else "uncertain" if score >= UNCERTAIN else "no_match"


def report(positive: list[float], negative: list[float]) -> dict:
    if not positive or not negative or not all(math.isfinite(x) for x in positive + negative):
        raise ValueError("calibration_scores_required")
    labels = ("match", "uncertain", "no_match")
    return {
        "thresholds": {"uncertain": UNCERTAIN, "match": MATCH},
        "same_speaker_pairs": len(positive),
        "different_speaker_pairs": len(negative),
        "same_by_decision": {x: sum(decision(v) == x for v in positive) for x in labels},
        "different_by_decision": {x: sum(decision(v) == x for v in negative) for x in labels},
        "same_score_range": [min(positive), max(positive)],
        "different_score_range": [min(negative), max(negative)],
    }
