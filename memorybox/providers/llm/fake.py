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
    bits: list[str] = []
    for u in pack.get("units") or []:
        text = str(u.get("content") or u.get("authored_text") or u.get("subject") or "").strip()
        if text:
            bits.append(text[:280])
        if len(bits) >= 10:
            break
    body = " ".join(bits) if bits else "No citable excerpts were in the prepared pack."
    kinds = {str(u.get("kind") or "") for u in (pack.get("units") or [])}
    if kinds == {"calendar"} or (kinds and kinds <= {"calendar"}):
        body = (
            "The prepared pack has calendar rows for this window. "
            "Those are scheduled or recorded, not proof the events occurred. "
            + body
        )
    used = pack.get("evidence_used") or {}
    footer_bits = [f"{k} {v}" for k, v in used.items() if v]
    footer = "Family evidence used: " + (", ".join(footer_bits) if footer_bits else "none") + "."
    return body + "\n\n" + footer


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
