"""Fake LLM for offline acceptance — token-hash embeddings so retrieval works."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from memorybox.providers.base import ProviderHealth
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto

_DIM = 32
_VOLUME_NOISE = re.compile(
    r"(?i)evidence item\(s\)|\d{4}-W\d{2}:|\b\d+ email\b|\b\d+ sms\b|member_n"
)
_TXN_NOISE = re.compile(
    r"(?i)\b(tracking|shipment|shipped|order confirmation|survey invitation|"
    r"your receipt|invoice|fedex|usps)\b"
)


def _fake_narrative(pack_json: str) -> str:
    try:
        pack = json.loads(pack_json)
    except Exception:
        return "The prepared pack could not be read. MemoryBox will not invent family facts."
    pu = pack.get("period_understanding") if isinstance(pack.get("period_understanding"), dict) else {}
    label = (
        pu.get("label")
        or pack.get("temporal_label")
        or ((pack.get("scope") or {}).get("time") or {}).get("label")
        or "this period"
    )
    outline = [x for x in (pack.get("narrative_outline") or []) if isinstance(x, dict)]
    cov = pack.get("coverage") or {}
    incomplete = bool(isinstance(cov, dict) and cov.get("incomplete"))
    disc = str((cov.get("truncation_disclosure") if isinstance(cov, dict) else "") or "").strip()

    opening = next((x.get("text") for x in outline if x.get("role") == "opening"), None)
    closing = next((x.get("text") for x in outline if x.get("role") == "closing"), None)
    opening = opening or pu.get("opening") or (
        f"During {label}, this is what stands out from family life in the archive, "
        "without pasting the original messages."
    )
    closing = closing or pu.get("closing")

    beats = [x for x in outline if x.get("role") == "beat"]
    if not beats:
        for b in pu.get("beats") or []:
            if isinstance(b, dict):
                beats.append({"text": b.get("about") or b.get("text"), "time": b.get("time"), "when": b.get("when")})
    if not beats:
        for b in pack.get("significant_beats") or pack.get("episodes") or []:
            if not isinstance(b, dict):
                continue
            beats.append(
                {
                    "text": b.get("about") or b.get("title") or b.get("content") or b.get("subject"),
                    "time": b.get("time") if not isinstance(b.get("time"), dict) else (b.get("time") or {}).get("value"),
                }
            )

    paras: list[str] = [str(opening).strip()]
    if incomplete:
        paras.append(
            "Coverage of the archive for this period is incomplete"
            + (f" ({disc})" if disc else "")
            + "."
        )
    story_lines: list[str] = []
    for b in beats:
        t = re.sub(r"\s+", " ", str(b.get("text") or "").strip())
        t = re.split(
            r"(?i)\nOn .+ wrote:|-----Original Message-----|Begin forwarded message:",
            t,
            maxsplit=1,
        )[0].strip()
        if not t or _VOLUME_NOISE.search(t):
            continue
        if _TXN_NOISE.search(t) and not re.search(r"(?i)\b(trip|visit|dinner|family|journal)\b", t):
            continue
        when = str(b.get("time") or b.get("when") or "").strip()
        if len(when) >= 10:
            story_lines.append(f"On {when[:10]}, {t.rstrip('.')}.")
        elif when in {"early", "mid", "late", "during"}:
            story_lines.append(f"{when.capitalize()} in {label}, {t.rstrip('.')}.")
        else:
            story_lines.append(t if t.endswith(".") else f"{t}.")
    if story_lines:
        chunk = max(1, (len(story_lines) + 1) // 2)
        paras.append(" ".join(story_lines[:chunk]))
        if story_lines[chunk:]:
            paras.append(" ".join(story_lines[chunk:]))
    elif not pu.get("beats"):
        paras.append(
            f"Nothing in the prepared outline rose above ordinary correspondence for {label}."
        )
    if closing:
        paras.append(str(closing).strip())
    used = pack.get("evidence_considered") or pack.get("evidence_used") or {}
    footer_bits = [f"{v} {k}" for k, v in used.items() if v]
    footer = (
        "Family evidence considered: "
        + (" · ".join(footer_bits) if footer_bits else "none")
        + "."
    )
    return "\n\n".join(p for p in paras if p) + "\n\n" + footer


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
