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
    label = pack.get("period") or pack.get("temporal_label") or "this period"
    unc = pack.get("uncertainty") if isinstance(pack.get("uncertainty"), dict) else {}
    incomplete = bool(unc.get("incomplete_coverage"))
    disc = str(unc.get("note") or "").strip()
    episodes = [x for x in (pack.get("episodes") or []) if isinstance(x, dict)]

    paras: list[str] = [
        f"During {label}, this is what stands out from family life in the archive, "
        "without pasting the original messages."
    ]
    if incomplete:
        paras.append(
            "Coverage of the archive for this period is incomplete"
            + (f" ({disc})" if disc else "")
            + "."
        )
    story_lines: list[str] = []
    for ep in episodes:
        claims = [str(c).strip() for c in (ep.get("claims") or []) if str(c).strip()]
        theme = str(ep.get("theme_or_episode") or "").strip()
        text = claims[0] if claims else theme
        t = re.sub(r"\s+", " ", text).strip()
        t = re.split(
            r"(?i)\nOn .+ wrote:|-----Original Message-----|Begin forwarded message:",
            t,
            maxsplit=1,
        )[0].strip()
        if not t or _VOLUME_NOISE.search(t):
            continue
        if _TXN_NOISE.search(t) and not re.search(r"(?i)\b(trip|visit|dinner|family|journal)\b", t):
            continue
        span = ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {}
        when = str((span or {}).get("start") or "").strip()
        people = [str(p) for p in (ep.get("people") or []) if str(p).strip()]
        if people:
            t = f"{t} — {', '.join(people[:3])}"
        if len(when) >= 10:
            story_lines.append(f"On {when[:10]}, {t.rstrip('.')}.")
        else:
            story_lines.append(t if t.endswith(".") else f"{t}.")
    if story_lines:
        chunk = max(1, (len(story_lines) + 1) // 2)
        paras.append(" ".join(story_lines[:chunk]))
        if story_lines[chunk:]:
            paras.append(" ".join(story_lines[chunk:]))
    else:
        paras.append(
            f"Nothing in the prepared outline rose above ordinary correspondence for {label}."
        )
    paras.append(f"That is the shape of {label} as the meaningful episodes tell it.")
    return "\n\n".join(p for p in paras if p)


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
