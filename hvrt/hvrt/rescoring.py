"""Decision / rescoring model — Owner > User > AI; human supersedes AI."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

DEFAULT_RULES = {
    "ranks": {"owner": 3, "user": 2, "ai": 1},
    "human_confirm_confidence": 1.0,
    "human_supersedes_ai": True,
    "human_supersedes_human": True,
    "owner_is_king": True,
}


def load_rules(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        "SELECT rules_json FROM decision_model WHERE name='hvrt_rescoring' "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return dict(DEFAULT_RULES)
    return json.loads(row["rules_json"])


def actor_rank(rules: dict[str, Any], actor_key: str) -> int:
    return int(rules.get("ranks", {}).get(actor_key, 0))


def human_confidence(rules: dict[str, Any], actor_key: str, confidence: float) -> float:
    if actor_key in ("owner", "user"):
        return float(rules.get("human_confirm_confidence", 1.0))
    return float(confidence)


def rebuild_effective_evidence(conn: sqlite3.Connection) -> int:
    """Recompute evidence_effective from annotations using decision rules.

    Competing annotations (same video, kind, overlapping label target) resolve by:
    higher actor rank wins; if equal rank, newer annotation wins (human can supersede human).
    """
    rules = load_rules(conn)
    conn.execute("DELETE FROM evidence_effective")

    rows = conn.execute(
        """
        SELECT * FROM annotations
        WHERE revoked = 0 AND kind != 'setting_placeholder'
        ORDER BY video_id, kind, created_at ASC, id ASC
        """
    ).fetchall()

    # key → winning annotation row
    winners: dict[tuple, sqlite3.Row] = {}

    for r in rows:
        key = _conflict_key(r)
        cur = winners.get(key)
        if cur is None:
            winners[key] = r
            continue
        if _beats(r, cur, rules):
            winners[key] = r

    n = 0
    for r in winners.values():
        conf = human_confidence(rules, r["actor_key"], float(r["confidence"]))
        decision = {
            "model": "hvrt_rescoring",
            "version": "1.0",
            "actor_key": r["actor_key"],
            "actor_rank": actor_rank(rules, r["actor_key"]),
            "rule": "owner>user>ai; newer same-rank human supersedes; human_confirm=1.0",
            "annotation_id": r["id"],
        }
        conn.execute(
            """
            INSERT INTO evidence_effective (
                video_id, kind, start_sec, end_sec, label_text, place_id, person_id,
                annotation_id, actor_key, confidence, decision_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """,
            (
                r["video_id"],
                r["kind"],
                r["start_sec"],
                r["end_sec"],
                r["label_text"],
                r["place_id"],
                r["person_id"],
                r["id"],
                r["actor_key"],
                conf,
                json.dumps(decision),
            ),
        )
        n += 1
    conn.commit()
    return n


def _conflict_key(r: sqlite3.Row) -> tuple:
    # Overlap resolution grain: video + kind + target entity (place/person/label)
    return (
        int(r["video_id"]),
        r["kind"],
        r["place_id"],
        r["person_id"],
        (r["label_text"] or "").strip().lower(),
        # Bucket by coarse time so disjoint spans on same reel can coexist
        int(float(r["start_sec"]) // 5),
    )


def _beats(challenger: sqlite3.Row, incumbent: sqlite3.Row, rules: dict[str, Any]) -> bool:
    cr = actor_rank(rules, challenger["actor_key"])
    ir = actor_rank(rules, incumbent["actor_key"])
    if cr > ir:
        return True
    if cr < ir:
        return False
    # Same rank: newer wins (human supersedes human)
    return int(challenger["id"]) > int(incumbent["id"])
