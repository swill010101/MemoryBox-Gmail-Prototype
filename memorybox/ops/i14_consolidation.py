"""Deterministic prepared-layer consolidation. Never merges or deletes evidence.

Identity keys only: complete content_hash and RFC-own. Similar text with a
different hash and RFC stays two communications. Quoted/forwarded overlap is
handled later by prepared-text omission, not by dropping evidence.
"""
from __future__ import annotations

import re
from typing import Any

from memorybox.ops.i14_thread_review import message_sort_key

HASH_SHAPE = re.compile(r"^[a-f0-9]{64}$")

RULE_ID = "i14-household-email-consolidate-v1"

# Survivor among an identity group is the earliest UTC instant, then evidence_id.
# Extras are omitted from the prepared generation and keep their original evidence
# rows untouched. Map-neither remains the production *evidence* policy; this rule
# only chooses which row is *displayed* in prepared communications.


def hash_status(raw: Any) -> tuple[str, str]:
    value = str(raw or "").strip().lower()
    if not value:
        return "", "missing"
    if HASH_SHAPE.fullmatch(value):
        return value, "ok"
    return value, "invalid"


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self.parent.setdefault(key, key)

    def find(self, key: str) -> str:
        self.add(key)
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != key:
            nxt = self.parent[key]
            self.parent[key] = root
            key = nxt
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def identity_tokens(msg: dict[str, Any]) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    digest, status = hash_status(msg.get("content_hash"))
    if status == "ok":
        tokens.append(("exact_bytes", f"hash:{digest}"))
    rfc = str(msg.get("rfc_message_id") or "").strip().lower()
    if rfc:
        tokens.append(("rfc_own", f"rfc:{rfc}"))
    if not tokens:
        tokens.append(("singleton", f"row:{msg.get('evidence_id')}"))
    return tokens


def identity_key(msg: dict[str, Any]) -> tuple[str, str]:
    return identity_tokens(msg)[0]


def classify_pair(*, same_hash: bool, same_rfc: bool, same_source: bool) -> str:
    """Map identity overlap onto the four founder-required classes."""
    if same_hash and same_source:
        return "exact_duplicate_evidence"
    if same_hash or same_rfc:
        return "same_communication_multiple_extracts"
    return "distinct_evidence"


def consolidate_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    excluded: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("spam_or_trash"):
            excluded.append({**msg, "exclude_reason": "spam_or_trash"})
        elif not msg.get("evidence_id"):
            excluded.append({**msg, "exclude_reason": "malformed"})
        else:
            eligible.append(msg)

    uf = _UnionFind()
    for msg in eligible:
        mid = f"msg:{msg.get('evidence_id')}"
        tokens = identity_tokens(msg)
        uf.union(mid, tokens[0][1])
        for _kind, token in tokens[1:]:
            uf.union(mid, token)

    groups: dict[str, list[dict[str, Any]]] = {}
    for msg in eligible:
        root = uf.find(f"msg:{msg.get('evidence_id')}")
        groups.setdefault(root, []).append(msg)

    displayed: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    class_counts = {
        "exact_duplicate_evidence": 0,
        "same_communication_multiple_extracts": 0,
        "quoted_or_forwarded_not_duplicate_evidence": 0,
        "distinct_evidence": 0,
    }
    for group in groups.values():
        ordered = sorted(group, key=message_sort_key)
        displayed.append(ordered[0])
        if len(ordered) == 1:
            class_counts["distinct_evidence"] += 1
            continue
        sources = {str(m.get("source_id") or "") for m in ordered}
        hashes = {hash_status(m.get("content_hash"))[0] for m in ordered}
        hashes.discard("")
        rfcs = {str(m.get("rfc_message_id") or "").strip().lower() for m in ordered}
        rfcs.discard("")
        same_hash = len(hashes) == 1 and bool(hashes)
        same_rfc = len(rfcs) == 1 and bool(rfcs)
        same_source = len(sources) == 1
        bucket = classify_pair(same_hash=same_hash, same_rfc=same_rfc, same_source=same_source)
        class_counts[bucket] += len(ordered) - 1
        dupe_kind = "exact_bytes" if same_hash else "rfc_own"
        for extra in ordered[1:]:
            duplicates.append(
                {
                    **extra,
                    "duplicate_of": ordered[0]["evidence_id"],
                    "consolidation_class": bucket,
                    "dupe_key_class": dupe_kind,
                }
            )
    unexplained = len(eligible) - len(displayed) - len(duplicates)
    return {
        "rule_id": RULE_ID,
        "excluded": excluded,
        "eligible": eligible,
        "displayed": displayed,
        "duplicates": duplicates,
        "unexplained": unexplained,
        "class_extra_rows": class_counts,
        "never_merge_similar_text": True,
    }
