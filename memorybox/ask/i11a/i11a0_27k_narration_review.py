"""Assemble a read-only 27K narration-quality review. Does not call Ollama."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_SERIES = (
    Path(r"\\flightsim\FlightSim User\MemoryBox\docs\test-output\i11a0-benchmark\gate3-b-i14-full-prompt-v5")
)
EXECUTIONS = (
    ("A", "d22f720fd063b6befe09fe02f5ca96f4a5f9693252b8868570f8ee310ec747d9", "coarse"),
    ("B", "8e2c493bc89c96f1ad92fb97a87b471456e3660f213e36e0e3671ad761ab0960", "repeat_1"),
    ("C", "ddaefaeb5da8826d79f732d49045085d3b7439eb8da7154561d84d30786e4f72", "repeat_2"),
    ("D", "b65bf2af63a1b952721b9b484c41907851313187d93510e9da7a86c33077b55b", "repeat_3"),
)
EXPECTED_PACKET = "ae0fcbb738dd956282aef23188fd53e703adefed7ba2ee1630a0a653b6ce20d7"
EXPECTED_PROMPT = "c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b"
EXPECTED_DIGEST = "304bf7349c71ad37a07eec8be67212b3f05b0f243f4a6f7c98e90dd2f3009f48"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def count_units(text: str) -> dict[str, int]:
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    sentences = split_sentences(text)
    words = re.findall(r"\b[\w']+\b", text)
    return {
        "characters": len(text),
        "words": len(words),
        "sentences": len(sentences),
        "paragraphs": len(paras),
    }


def split_sentences(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    chunks = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    return [c.strip() for c in chunks if c.strip()]


def citation_ids(text: str) -> list[str]:
    found = re.findall(
        r"\[email_[^\]]+\]|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        text,
        flags=re.I,
    )
    return found


def load_run(series: Path, eid: str) -> dict:
    folder = series / "runs" / eid
    rec = json.loads((folder / "run_record.json").read_text(encoding="utf-8"))
    cap = json.loads((folder / "request_capture.json").read_text(encoding="utf-8"))
    man = json.loads((folder / "packet_manifest.json").read_text(encoding="utf-8"))
    nar = (folder / "narration.txt").read_bytes()
    pkt = (folder / "evidence_packet.txt").read_bytes()
    return {
        "folder": folder,
        "record": rec,
        "capture": cap,
        "manifest": man,
        "narration_bytes": nar,
        "packet_bytes": pkt,
        "narration_text": nar.decode("utf-8"),
        "complete": (folder / "COMPLETE").is_file(),
    }


def verify_identity(series: Path) -> dict:
    rows = []
    for label, eid, role in EXECUTIONS:
        run = load_run(series, eid)
        man = run["manifest"]
        cap = run["capture"]
        rec = run["record"]
        rj = cap.get("request_json") or {}
        opt = rj.get("options") or {}
        row = {
            "candidate": label,
            "role": role,
            "execution_id": eid,
            "phase": rec.get("phase"),
            "packet_sha256": rec.get("packet_sha256") or man.get("packet_sha256"),
            "evidence_file_sha256": sha256_bytes(run["packet_bytes"]),
            "prompt_sha256": rec.get("prompt_sha256"),
            "system_sha256": cap.get("system_sha256"),
            "user_sha256": cap.get("user_sha256"),
            "digest": cap.get("digest"),
            "tag": cap.get("model_tag"),
            "estimated_evidence_tokens": man.get("estimated_evidence_tokens"),
            "evidence_bytes": man.get("evidence_bytes"),
            "message_count": man.get("message_count"),
            "thread_count": man.get("conversation_count"),
            "actual_complete_prompt_tokens": rec.get("actual_prompt_tokens"),
            "num_ctx": rec.get("configured_num_ctx"),
            "time_start": man.get("time_start"),
            "time_end": man.get("time_end"),
            "manifest_partial_context": man.get("partial_context"),
            "user_partial_context": None,
            "think": rj.get("think"),
            "truncate": rj.get("truncate"),
            "shift": rj.get("shift"),
            "temperature": opt.get("temperature"),
            "seed": opt.get("seed"),
            "packet_id": None,
            "evidence_ids": list(man.get("evidence_ids") or []),
            "narration_sha256": sha256_bytes(run["narration_bytes"]),
            "done_reason": (rec.get("last_event") or {}).get("done_reason"),
            "eval_count": (rec.get("last_event") or {}).get("eval_count"),
            "complete_marker": run["complete"],
        }
        user = next((m.get("content") or "" for m in rj.get("messages") or [] if m.get("role") == "user"), "")
        for line in user.splitlines():
            if line.startswith("partial_context:"):
                row["user_partial_context"] = line.split(":", 1)[1].strip()
            if line.startswith("packet_id:"):
                row["packet_id"] = line.split(":", 1)[1].strip()
        rows.append(row)
    problems = []
    for key in (
        "packet_sha256",
        "evidence_file_sha256",
        "prompt_sha256",
        "digest",
        "estimated_evidence_tokens",
        "evidence_bytes",
        "message_count",
        "thread_count",
        "actual_complete_prompt_tokens",
        "num_ctx",
        "evidence_ids",
    ):
        vals = {json.dumps(r[key], sort_keys=True) if key == "evidence_ids" else r[key] for r in rows}
        if len(vals) != 1:
            problems.append(f"{key} mismatch: {vals}")
    first = rows[0]
    if first["packet_sha256"] != EXPECTED_PACKET:
        problems.append("packet_sha256 is not the expected 27K packet")
    if first["prompt_sha256"] != EXPECTED_PROMPT:
        problems.append("prompt_sha256 is not i11a0-narration-v0.2-draft")
    if first["digest"] != EXPECTED_DIGEST:
        problems.append("digest is not pinned Qwen B")
    return {"ok": not problems, "problems": problems, "rows": rows}


CLAIM_AUDIT_A = [
    {
        "sentence_number": 1,
        "exact_text": "In the late autumn of 2006, as the chill of winter began to settle in, Peg Legg found herself immersed in the flurry of holiday preparations.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg emails from 2006-11-07 onward discuss Christmas lists and shopping (e.g. T-0333 / 54e1bfd3…). The packet also begins 2005-12-10.",
        "date_accuracy": "partial — holiday prep in Nov 2006 is in the packet; 'late autumn of 2006' as the opening frame omits 2005 and 2007 dates",
        "person_attribution_accuracy": "Peg Legg is the usual author of the shopping emails",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "preparations are ongoing plans, not a completed holiday",
        "emotion_motive_significance": "inferred — 'chill of winter', 'immersed', 'flurry' are not stated as weather/mood facts in that sentence's implied sources",
        "chronological_placement": "compresses a 2005–2007 packet into late 2006",
        "notes": "No citation. Atmosphere invented.",
        "severity": "high",
    },
    {
        "sentence_number": 2,
        "exact_text": "Her emails reveal a meticulous and affectionate approach to the season, as she meticulously curated gift lists for her family, ensuring that each person received something thoughtful and personal.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg tracks lists and purchases (wallet for Lars, sweater for Matt, DVDs, etc.).",
        "date_accuracy": "not dated in the sentence",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "unsupported completed outcome — 'ensuring that each person received' treats planned/purchased gifts as received",
        "emotion_motive_significance": "inferred meticulous/affectionate/thoughtful/personal",
        "chronological_placement": "generic holiday season",
        "notes": "Gift-list work is in the packet; completed receipt and personality claims are not.",
        "severity": "high",
    },
    {
        "sentence_number": 3,
        "exact_text": "Peg’s correspondence with Tom Will, her brother, highlights the collaborative effort involved in selecting gifts, with Tom providing a master list that detailed who was giving what to whom.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "supported",
        "supporting_excerpt": "Tom Will, 2006-11-07, 'xmas list - your eyes only!' (0e7dc382… / 6f1b61ef…): 'OK, here's the master list with the name of the person, the gift and who is giving it.' Peg calls him 'little brother' in T-0448 (e17a1c58…).",
        "date_accuracy": "undated in sentence; list is 7 Nov 2006",
        "person_attribution_accuracy": "Tom authored the master list; Peg authored brother address",
        "quoted_forwarded_accuracy": "does not confuse Tom's list with Peg's words",
        "plan_versus_completed": "list is a plan, correctly treated as selecting gifts",
        "emotion_motive_significance": "none beyond 'collaborative'",
        "chronological_placement": "ok if remaining in Nov 2006",
        "notes": "Strongest factual sentence. Still uncited.",
        "severity": "medium",
    },
    {
        "sentence_number": 4,
        "exact_text": "This shared responsibility reflected the close-knit nature of their family, where even the smallest gestures were appreciated.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "unsupported",
        "supporting_excerpt": "None states 'close-knit' or that smallest gestures were appreciated as a family fact.",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "family as a unit invented as character",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "n/a",
        "emotion_motive_significance": "invented significance",
        "chronological_placement": "n/a",
        "notes": "Prompt forbids stating significance as fact without evidence.",
        "severity": "high",
    },
    {
        "sentence_number": 5,
        "exact_text": "Peg’s enthusiasm for the holiday season was palpable, as she eagerly awaited the arrival of Christmas and the opportunity to reunite with her loved ones.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg writes she looks forward to everyone being together (e.g. T-0416 / cc531354… 'That's is what I treasure most').",
        "date_accuracy": "not specified",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "awaiting Christmas is a plan/anticipation",
        "emotion_motive_significance": "overstates 'palpable enthusiasm' and 'eagerly' as narrator fact",
        "chronological_placement": "pre-Christmas",
        "notes": "Some looking-forward language exists; 'palpable' is invented atmosphere.",
        "severity": "high",
    },
    {
        "sentence_number": 6,
        "exact_text": "Her emails often included updates on her shopping progress, from ordering DVDs and books to searching for the perfect gifts for her family members.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg orders DVDs (Giant, Gypsy, African Queen, Twin Towers) and books (Southern Living, Grisham).",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "ordering is in progress; 'perfect gifts' is inferred",
        "emotion_motive_significance": "'perfect' inferred",
        "chronological_placement": "shopping sequence exists across November–December 2006",
        "notes": "DVD/book shopping is real. Uncited.",
        "severity": "medium",
    },
    {
        "sentence_number": 7,
        "exact_text": "She was particularly excited about the prospect of giving her father a new DVD player, a gift that would allow him to enjoy his favorite movies in comfort.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg, planning shopping: 'Ange and I are going to T later to fetch the DVD/VCR player they have on sale for $90 for us to give to Dad. Is alright?' That is a plan, not a completed gift. The packet also discusses DVD movies as gifts.",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "father/Dad is correct",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "treats a planned Target run as a settled gift purpose; does not prove the player was purchased or given",
        "emotion_motive_significance": "invented 'particularly excited' and 'enjoy his favorite movies in comfort'",
        "chronological_placement": "n/a",
        "notes": "Object is in the packet as a planned DVD/VCR player, not invented. Emotion and completed-purpose language remain unsupported.",
        "severity": "high",
    },
    {
        "sentence_number": 8,
        "exact_text": "Peg also expressed her desire to give her brother, Tom, a gift that would be meaningful to him, showing her deep understanding of his interests and preferences.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg asks Tom for his list ('I'm missing YOUR list!!' T-0407 / 2bf9eacd…). She does not spell out a single chosen gift for Tom in the audited sentences.",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "brother Tom is supportable",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "desire/list request is a plan",
        "emotion_motive_significance": "'meaningful' and 'deep understanding' inferred",
        "chronological_placement": "n/a",
        "notes": "Asking for Tom's list is real; mind-reading is not.",
        "severity": "high",
    },
    {
        "sentence_number": 9,
        "exact_text": "The holiday season was not without its challenges, as Peg faced the inconvenience of a malfunctioning car, which threatened to disrupt her plans.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "supported",
        "supporting_excerpt": "Check-engine light, AutoZone/dealer, throttle-module software (T-0445 / T-0451). Peg feared missing shopping and travel.",
        "date_accuracy": "mid-December 2006 in the packet, not stated",
        "person_attribution_accuracy": "Peg's car",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "malfunction occurred; disruption of plans is feared more than proven as a missed gathering",
        "emotion_motive_significance": "'inconvenience' is milder than Peg's 'driving me crazy' but not invented",
        "chronological_placement": "ok among December events",
        "notes": "Car trouble is in the packet. Uncited.",
        "severity": "medium",
    },
    {
        "sentence_number": 10,
        "exact_text": "Despite this, she remained optimistic and determined, ensuring that she would be able to complete her shopping and make it to the family gatherings.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "unsupported",
        "supporting_excerpt": "Optimism/determination are narrator labels. Completing all shopping and attending gatherings is not established as a finished outcome by this sentence.",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "treats plans as ensured completed events",
        "emotion_motive_significance": "invented inner states",
        "chronological_placement": "n/a",
        "notes": "Saturday at Dad's later occurs in other messages; this sentence still overclaims.",
        "severity": "high",
    },
    {
        "sentence_number": 11,
        "exact_text": "Her emails reveal a sense of urgency and excitement as she worked to finalize her lists and make sure that everyone received something they would cherish.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg is often last-minute and chasing lists. 'Everyone received something they would cherish' is a completed-outcome claim.",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "received/cherish is unsupported completion",
        "emotion_motive_significance": "urgency/excitement inferred",
        "chronological_placement": "n/a",
        "notes": None,
        "severity": "high",
    },
    {
        "sentence_number": 12,
        "exact_text": "As the days leading up to Christmas approached, Peg’s emails reflected a growing sense of anticipation and joy.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "unsupported",
        "supporting_excerpt": "No packet line says her emails 'reflected growing anticipation and joy' as a measured change.",
        "date_accuracy": "pre-Christmas window exists",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "n/a",
        "emotion_motive_significance": "invented emotional arc",
        "chronological_placement": "pre-Christmas only; omits May 2007 and Dec 2007 packet tail",
        "notes": None,
        "severity": "high",
    },
    {
        "sentence_number": 13,
        "exact_text": "She was looking forward to the family gatherings, the shared meals, and the warmth of being together.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg looks forward to being together and putting dinner together at Dad's (T-0445 / T-0448).",
        "date_accuracy": "not specified",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "looking forward is a plan; 'warmth' is inferred",
        "emotion_motive_significance": "warmth inferred",
        "chronological_placement": "Christmas 2006 gatherings",
        "notes": None,
        "severity": "medium",
    },
    {
        "sentence_number": 14,
        "exact_text": "Her correspondence with Tom and the rest of her family was filled with affection and a deep sense of gratitude for the time they had together.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "partially_supported",
        "supporting_excerpt": "Peg writes 'My love to all' often and thanks Tom after Saturday (T-0448). 'Filled with' and 'deep sense of gratitude for the time they had together' overgeneralize.",
        "date_accuracy": "n/a",
        "person_attribution_accuracy": "does not steal Tom's MS-150 words",
        "quoted_forwarded_accuracy": "ok",
        "plan_versus_completed": "gratitude after an event is later in packet; here it is a blanket trait",
        "emotion_motive_significance": "overstated",
        "chronological_placement": "n/a",
        "notes": None,
        "severity": "medium",
    },
    {
        "sentence_number": 15,
        "exact_text": "Peg’s holiday season was a time of love, preparation, and the joy of giving, all of which were evident in her heartfelt messages to her family.",
        "cited_evidence_ids": [],
        "every_cited_id_exists_in_packet": True,
        "support": "unsupported",
        "supporting_excerpt": "Theme sentence. Packet also contains flu, power outage, missed graduation, car repair, ice storm — not summarized.",
        "date_accuracy": "reduces 2005–2007 to one holiday season",
        "person_attribution_accuracy": "Peg",
        "quoted_forwarded_accuracy": "n/a",
        "plan_versus_completed": "treats the season as a completed moral",
        "emotion_motive_significance": "invented summary significance",
        "chronological_placement": "wrong grain for the packet span",
        "notes": "Closing moralizes. No partial-context disclosure.",
        "severity": "critical",
    },
]


def write_bundle(series: Path, dest: Path) -> dict:
    ident = verify_identity(series)
    if not ident["ok"]:
        raise SystemExit("IDENTITY_FAILURE " + "; ".join(ident["problems"]))
    dest.mkdir(parents=True, exist_ok=True)
    cand_dir = dest / "candidates"
    cand_dir.mkdir(exist_ok=True)
    hashes = {}
    orig_hashes = {}
    stats_rows = []
    narrations = {}
    for label, eid, role in EXECUTIONS:
        run = load_run(series, eid)
        blind = cand_dir / f"candidate_{label}.txt"
        blind.write_bytes(run["narration_bytes"])
        orig_hashes[f"original_narration_{eid}"] = sha256_bytes(run["narration_bytes"])
        orig_hashes[f"original_packet_{eid}"] = sha256_bytes(run["packet_bytes"])
        orig_hashes[f"original_COMPLETE_{eid}"] = sha256_file(run["folder"] / "COMPLETE")
        counts = count_units(run["narration_text"])
        cites = citation_ids(run["narration_text"])
        narrations[label] = run["narration_text"]
        stats_rows.append(
            {
                "candidate": label,
                "execution_id": eid,
                "role": role,
                "narration_sha256": sha256_bytes(run["narration_bytes"]),
                "word_count": counts["words"],
                "sentence_count": counts["sentences"],
                "paragraph_count": counts["paragraphs"],
                "citation_count": len(cites),
                "citations": cites,
                "done_reason": (run["record"].get("last_event") or {}).get("done_reason"),
                "eval_count": (run["record"].get("last_event") or {}).get("eval_count"),
                "output_limit_termination": False,
            }
        )
    packet_bytes = load_run(series, EXECUTIONS[0][1])["packet_bytes"]
    packet_text = packet_bytes.decode("utf-8")
    header = (
        "---\n"
        f"packet_sha256: {EXPECTED_PACKET}\n"
        "source_file: evidence_packet.txt (COMPLETE run directory; not rewritten)\n"
        "note: Accepted I14 cleaned household email only. Header above the first evidence line is review metadata, not model input.\n"
        "---\n\n"
    )
    (dest / "evidence_packet.md").write_text(header + packet_text, encoding="utf-8", newline="\n")
    (dest / "canonical_narration.md").write_text(
        "---\n"
        "audit_copy: Candidate A\n"
        "reason: proposed-point coarse execution; byte-identical to Candidate B; not identical to C or D\n"
        f"execution_id: {EXECUTIONS[0][1]}\n"
        f"narration_sha256: {stats_rows[0]['narration_sha256']}\n"
        "do_not_treat_as_the_only_output: true\n"
        "---\n\n"
        + narrations["A"].rstrip()
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha_set = {r["narration_sha256"] for r in stats_rows}
    exact_pairs = []
    for i, a in enumerate(stats_rows):
        for b in stats_rows[i + 1 :]:
            exact_pairs.append(
                {
                    "left": a["candidate"],
                    "right": b["candidate"],
                    "exact_match": a["narration_sha256"] == b["narration_sha256"],
                    "normalized_match": normalize_text(narrations[a["candidate"]])
                    == normalize_text(narrations[b["candidate"]]),
                }
            )
    repeatability = {
        "series": "gate3-b-i14-full-prompt-v5",
        "all_four_byte_identical": len(sha_set) == 1,
        "canonical_identical_copy": None,
        "repeatability_confirmations": [],
        "differing_outputs": True,
        "blinded_candidates": "candidates/candidate_A.txt through candidate_D.txt",
        "identity": ident["rows"],
        "user_wrapper_note": (
            "evidence_packet SHA and prompt_sha256 match. user_sha256 differs only because "
            "packet_id is qwen3:14b-q8_0-27000-cold-1/2/3. That is not a different evidence packet."
        ),
        "manifest_partial_context": True,
        "user_message_partial_context": ident["rows"][0]["user_partial_context"],
        "controller_partial_context_mismatch": ident["rows"][0]["user_partial_context"] != "yes",
        "pairwise": exact_pairs,
        "per_execution": stats_rows,
        "byte_identical_pair": ["A", "B"],
    }
    (dest / "repeatability.json").write_text(json.dumps(repeatability, indent=2) + "\n", encoding="utf-8", newline="\n")
    audit_path = dest / "claim_audit.json"
    audit_doc = {
        "audited_candidate": "A",
        "execution_id": EXECUTIONS[0][1],
        "note": "Candidates C and D are different texts; their extra defects are in narration_quality_assessment.md.",
        "rows": CLAIM_AUDIT_A,
    }
    audit_path.write_text(json.dumps(audit_doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (dest / "claim_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = list(CLAIM_AUDIT_A[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(CLAIM_AUDIT_A)
    (dest / "_original_run_hashes.json").write_text(
        json.dumps(orig_hashes, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return {
        "dest": str(dest),
        "repeatability": repeatability,
        "orig_hashes": orig_hashes,
        "ident": ident,
    }


def write_hashes(dest: Path) -> Path:
    lines = [
        "# SHA-256 of every file in this review bundle (except this HASHES.txt).",
        "# Original COMPLETE run directories were not written by this assembler.",
        "",
    ]
    for path in sorted(p for p in dest.rglob("*") if p.is_file() and p.name != "HASHES.txt"):
        rel = path.relative_to(dest).as_posix()
        lines.append(f"{sha256_file(path)}  {rel}")
    orig = dest / "_original_run_hashes.json"
    if orig.is_file():
        lines.append("")
        lines.append("# Hashes of the four original narrations, packets, and COMPLETE markers")
        payload = json.loads(orig.read_text(encoding="utf-8"))
        for key, value in sorted(payload.items()):
            lines.append(f"{value}  {key}")
    out = dest / "HASHES.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    series = DEFAULT_SERIES
    dest = series / "narration-quality-review"
    if "--hash-only" in sys.argv:
        path = write_hashes(dest)
        print(json.dumps({"ok": True, "hashes": str(path)}, indent=2))
    else:
        payload = write_bundle(series, dest)
        print(json.dumps({"ok": True, "dest": payload["dest"], "models_called": False}, indent=2))
