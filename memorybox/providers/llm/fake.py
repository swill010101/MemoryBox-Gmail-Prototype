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
    units = list(pack.get("units") or [])
    label = (
        pack.get("temporal_label")
        or ((pack.get("scope") or {}).get("time") or {}).get("label")
        or "this period"
    )
    if not units:
        return (
            f"There is not enough prepared family evidence to narrate {label}."
            "\n\nFamily evidence used: none."
        )
    kinds = {str(u.get("kind") or "") for u in units}
    paras: list[str] = [
        f"Here is a short account of {label} from the prepared family evidence, "
        "without pasting the original messages."
    ]
    if kinds and kinds <= {"calendar"}:
        paras.append(
            "The prepared pack has calendar rows for this window. "
            "Those are scheduled or recorded, not proof the events occurred."
        )
    by_day: dict[str, list[str]] = {}
    for u in units:
        day = str(u.get("time") or (u.get("time") or {}).get("value") or "").strip() or "an undated day"
        if isinstance(u.get("time"), dict):
            day = str((u.get("time") or {}).get("value") or day)
        kind = str(u.get("kind") or "evidence")
        subj = str(u.get("subject") or "").strip()
        gist = str(u.get("content") or u.get("authored_text") or "").strip()
        gist = re.split(
            r"(?i)\nOn .+ wrote:|-----Original Message-----|Begin forwarded message:",
            gist,
            maxsplit=1,
        )[0].strip()
        gist = re.sub(r"\s+", " ", gist)[:160]
        people = u.get("people") or []
        names = []
        for p in people:
            if isinstance(p, dict):
                n = str(p.get("name") or "").strip()
            else:
                n = str(p or "").strip()
            if n and n not in names:
                names.append(n)
        who = ", ".join(names[:4])
        if kind == "journal":
            bit = gist or subj or "a journal entry"
        elif kind == "calendar":
            bit = f"a calendar row{(' for ' + subj) if subj else ''}"
        elif kind == "travel":
            bit = gist or str(u.get("travel_kind") or "travel")
        elif subj:
            bit = f"{subj}" + (f" — {gist}" if gist else "")
        else:
            bit = gist or kind
        if who:
            bit = f"{who}: {bit}"
        by_day.setdefault(day[:10] if len(day) >= 10 else day, []).append(bit)
    for day, bits in list(by_day.items())[:10]:
        uniq: list[str] = []
        for b in bits:
            if b not in uniq:
                uniq.append(b)
        paras.append(f"On {day}, {'; '.join(uniq[:3])}.")
    used = pack.get("evidence_used") or {}
    footer_bits = [f"{k} {v}" for k, v in used.items() if v]
    footer = "Family evidence used: " + (", ".join(footer_bits) if footer_bits else "none") + "."
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
