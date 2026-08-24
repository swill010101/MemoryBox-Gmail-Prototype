# P2-I10A.2 — Reusable Speech Input

**Status:** **ACCEPTED** 2026-08-24 (Tom: “i10A.2 is accepted”) · implementation `cursor/p2-i10a2-speech-build-49da` · `prove-i10a2`  
**PRD:** [MBPRD-P2-I10A2_SPEECH_INPUT.md](MBPRD-P2-I10A2_SPEECH_INPUT.md)  
**Contract:** [MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md](MBSC-P2-I10A2_SPEECH_SCREEN_CONTRACT.md)  
**Assessment:** [MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10A2_ASSESSMENT_RECONCILIATION.md)  
**Acceptance:** [MBAT-P2-I10A2_ACCEPTANCE.md](MBAT-P2-I10A2_ACCEPTANCE.md)  
**Depends:** I10A · I10A.1 · I10B **ACCEPTED** (Artifact-description dictation row **superseded** by I10A.2)  
**Does not start:** I10C product · I11 · I9 · spoken Ask · I10A.1 polish · Artifact `MediaRecorder`

## Intent

One narrative editor. Speech on that editor with two semantics: **authored-memory** (preserve audio + approved text on Save) and **convenience** (text durable, audio transient). Natural speech. Pause/Resume. Review before Save. No orphan files. No four mic forks.

## Build locks

See PRD Frozen rows. Shared component **first**. All four surfaces this increment. Journal POC replaced. Silence ~30s **pauses** and asks “Are you still there?” — not auto-stop.

## Prove

[MBAT-P2-I10A2_ACCEPTANCE.md](MBAT-P2-I10A2_ACCEPTANCE.md) · `prove-i10a2` remains the regression gate.

**ACCEPTED 2026-08-24. Do not reopen I10A.2. Next is I10C (not started).**
