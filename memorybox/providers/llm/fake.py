"""Fake LLM for offline acceptance — token-hash embeddings so retrieval works."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from memorybox.providers.base import ProviderHealth
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto

_DIM = 32


def _fake_narrative(pack_json: str) -> str:
    try:
        pack = json.loads(pack_json)
    except Exception:
        return "The prepared pack could not be read. MemoryBox will not invent family facts."
    label = (
        pack.get("temporal_label")
        or ((pack.get("scope") or {}).get("time") or {}).get("label")
        or "this period"
    )
    outline = list(pack.get("outline") or pack.get("derived_summaries") or [])
    episodes = list(pack.get("episodes") or pack.get("units") or [])
    cov = pack.get("coverage") or {}
    incomplete = False
    if isinstance(cov, dict):
        incomplete = bool(cov.get("incomplete"))
        disc = str(cov.get("truncation_disclosure") or "").strip()
    else:
        disc = ""
    if not outline and not episodes:
        return (
            f"There is not enough prepared family evidence to narrate {label}."
            "\n\nFamily evidence considered: none."
        )
    paras: list[str] = [
        f"Here is a short account of {label} from the prepared family evidence, "
        "without pasting the original messages."
    ]
    if incomplete:
        paras.append(
            "Coverage is incomplete"
            + (f": {disc}" if disc else ".")
            + " MemoryBox did not silently sample the rest of the period."
        )
    weeks = sorted(
        outline,
        key=lambda s: str((s or {}).get("period") or "") if isinstance(s, dict) else "",
    )
    week_bits: list[str] = []
    for s in weeks:
        if not isinstance(s, dict):
            continue
        t = str(s.get("text") or s.get("period") or "").strip()
        if t:
            week_bits.append(t)
    if week_bits:
        paras.append(
            "Across the weeks that have evidence, "
            + " ".join(week_bits[:12])
        )

    def _ep_day(ep: dict) -> str:
        t = ep.get("time")
        if isinstance(t, dict):
            return str(t.get("value") or "")
        return str(t or "")

    dated = [e for e in episodes if isinstance(e, dict)]
    dated.sort(key=lambda e: _ep_day(e) or "9999")
    story_bits: list[str] = []
    for ep in dated[:16]:
        day = _ep_day(ep)[:10] or "an undated day"
        gist = re.split(
            r"(?i)\nOn .+ wrote:|-----Original Message-----|Begin forwarded message:",
            str(ep.get("content") or ep.get("subject") or ""),
            maxsplit=1,
        )[0].strip()
        gist = re.sub(r"\s+", " ", gist)[:180]
        if not gist:
            continue
        n = int(ep.get("member_n") or 1)
        if n > 1:
            story_bits.append(f"Around {day}, {gist}")
        else:
            story_bits.append(f"Around {day}, {gist}")
    if story_bits:
        # Continuous prose, not a record dump: fold into a couple of sentences.
        mid = max(1, len(story_bits) // 2)
        paras.append(". ".join(story_bits[:mid]) + ".")
        if story_bits[mid:]:
            paras.append(". ".join(story_bits[mid:]) + ".")
    used = pack.get("evidence_considered") or pack.get("evidence_used") or {}
    footer_bits = [f"{v} {k}" for k, v in used.items() if v]
    footer = (
        "Family evidence considered: "
        + (" · ".join(footer_bits) if footer_bits else "none")
        + "."
    )
    return "\n\n".join(paras) + "\n\n" + footer


def _token_vector(text: str) -> tuple[float, ...]:
    vec = [0.0] * _DIM
    tokens = re.findall(r"[a-z0-9_]+", (text or "").lower())
    if not tokens:
        tokens = ["empty"]
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % _DIM] += 1.0
    # L2 normalize
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return tuple(x / norm for x in vec)


class FakeLlmProvider:
    provider_key = "fake_llm"
    embed_model = "fake-embed"

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider_key=self.provider_key, ok=True, detail="fake")

    def embed(
        self, text: str, *, purpose: Literal["query", "document"] = "document"
    ) -> EmbeddingDto:
        return EmbeddingDto(
            model=self.embed_model,
            vector=_token_vector(text),
            purpose=purpose,
        )

    def chat(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> ChatResultDto:
        last = messages[-1].content if messages else ""
        system = next((m.content for m in messages if m.role == "system"), "")
        if json_mode:
            content = '{"ok":true}'
        elif "NARRATIVE_SYNTHESIS" in (system or ""):
            content = _fake_narrative(last)
        else:
            content = f"echo:{last[:200]}"
        return ChatResultDto(model="fake-chat", content=content)
