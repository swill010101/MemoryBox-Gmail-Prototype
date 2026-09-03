"""Versioned C1T benchmark prompt schemas."""
from __future__ import annotations

import json
from typing import Any

HISTORIAN_EVIDENCE_LEDGER_V1 = "historian-evidence-ledger-v1"
TRUSTED_EMAIL_REVIEW_V1 = "trusted-email-review-v1"

_HISTORIAN_LEDGER_SCHEMA = {
    "chunk_id": "...",
    "scope": {
        "start": "...",
        "end": "...",
        "partial_context": False,
    },
    "events": [
        {
            "local_event_id": "...",
            "date_or_range": "...",
            "description": "...",
            "people": [],
            "event_type": "...",
            "local_significance": "high|medium|low|unknown",
            "significance_reason": "...",
            "evidence_ids": [],
            "evidence_basis": "direct|supported_inference",
            "confidence": "high|medium|low",
            "uncertainties": [],
            "connections_to_investigate": [],
        }
    ],
    "patterns": [],
    "conflicts": [],
    "potentially_meaningful_details": [],
    "segment_limits": [],
}

_HISTORIAN_SYSTEM = """You are a careful family historian reviewing one segment of a much larger evidence collection. Create a concise structured evidence ledger. Preserve every distinct event, milestone, relationship development, recurring pattern, conflict, uncertainty, and potentially meaningful detail that could matter when combined with other segments. Do not decide that something is globally unimportant merely because this segment provides limited context. Do not write the final life narrative. Do not infer beyond the supplied evidence. Cite every retained item using its supplied evidence ID. Distinguish direct evidence from supported interpretation, explain the support for any interpretation, and mark uncertainty explicitly. Return only the required structured result.

Keep descriptions concise. Do not produce a polished narrative. Do not discard a supported detail solely because it appears minor within this isolated chunk. Do not turn advertisements, boilerplate, automated notices, or signatures into personal events unless they directly establish a relevant fact. Preserve chronology. Preserve uncertainty. Every factual ledger entry must carry supported evidence IDs. Do not invent global significance that cannot be determined from one segment.

Return JSON matching this shape:
""" + json.dumps(_HISTORIAN_LEDGER_SCHEMA, indent=2)

_TRUSTED_EMAIL_SYSTEM = (
    "Return the existing trusted-email review JSON schema. "
    "Cite every claim with supplied [email_N] evidence IDs."
)

PROMPT_SCHEMAS: dict[str, dict[str, Any]] = {
    HISTORIAN_EVIDENCE_LEDGER_V1: {
        "schema_version": HISTORIAN_EVIDENCE_LEDGER_V1,
        "format": "json",
        "system": _HISTORIAN_SYSTEM,
        "citation_optional": False,
        "ledger_entry_lists": (
            "events",
            "patterns",
            "conflicts",
            "potentially_meaningful_details",
        ),
        "evidence_id_field": "evidence_ids",
    },
    TRUSTED_EMAIL_REVIEW_V1: {
        "schema_version": TRUSTED_EMAIL_REVIEW_V1,
        "format": "json",
        "system": _TRUSTED_EMAIL_SYSTEM,
        "citation_optional": False,
        "ledger_entry_lists": (),
        "evidence_id_field": "evidence_ids",
    },
}


def resolve_prompt_schema(version: str) -> dict[str, Any]:
    schema = PROMPT_SCHEMAS.get(version)
    if not schema:
        known = ", ".join(sorted(PROMPT_SCHEMAS))
        raise ValueError(f"unknown prompt schema {version!r}; known: {known}")
    return schema


def build_benchmark_messages(
    *,
    schema_version: str,
    chunk_text: str,
    chunk_metadata: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    schema = resolve_prompt_schema(schema_version)
    user = chunk_text
    if schema_version == HISTORIAN_EVIDENCE_LEDGER_V1 and chunk_metadata:
        chunk_id = str(chunk_metadata.get("chunk_id") or "")
        time_range = chunk_metadata.get("time_range") or {}
        prefix = (
            f"chunk_id: {chunk_id}\n"
            f"scope.start: {time_range.get('start') or ''}\n"
            f"scope.end: {time_range.get('end') or ''}\n"
            "partial_context: true when this segment is intentionally incomplete.\n\n"
        )
        user = prefix + chunk_text
    return [
        {"role": "system", "content": str(schema["system"])},
        {"role": "user", "content": user},
    ]
