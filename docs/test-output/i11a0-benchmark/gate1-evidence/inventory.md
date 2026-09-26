# P2-I11A.0 Gate 1 evidence

Inference was not authorized. No model was pulled, loaded, or asked to generate. No Peggy packet body was written.

Code commit: `7be7745b6503af5a383c716b7dd9d1e2bf27b5a8`

Machine-readable inventory: `inventory.json`
SHA-256 of `inventory.json`: `dece673e37e0188237770884ba0e60fa0d04cdf1f2d56e84ea3e63f3b19373e5`

## Branch ancestry

| Item | Value |
| --- | --- |
| Branch | `cursor/p2-i11a0-offline-harness` |
| HEAD at this report | `7be7745b6503af5a383c716b7dd9d1e2bf27b5a8` |
| Accepted I14 baseline | `6500ef032fa038be6e5a34b6ed312c92160fdf91` |
| Accepted I14 subject | docs(p2-i14): record Phase B household-email activation closeout |
| Merge base | `6500ef032fa038be6e5a34b6ed312c92160fdf91` |
| Accepted I14 is an ancestor | yes |
| Branch rewritten | no |

The accepted Phase B closeout is an ancestor of this branch. Its parent, the FlightSim runtime commit `ecf3e6726456c40f64f8bc38ea5d59f46c164b31`, is also an ancestor. The branch was not rebased or merged for this gate.

FlightSim's working checkout, read from `\\flightsim\FlightSim User\MemoryBox\.git\HEAD`, is still `refs/heads/codex/p2-i14-communications`. The prove command below ran on the desktop working tree. It has not yet run on FlightSim.

## Offline proof

Command: `python -m memorybox prove-i11a0-benchmark`

| Result | Value |
| --- | --- |
| ok | true |
| checks | 44 |
| problems | none |
| warnings | none |
| prompt version | `i11a0-narration-v0.2-draft` |
| prompt SHA-256 | `c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b` |
| models called | false |

## Peggy review directory

Authoritative path on FlightSim: `C:\memorybox\docs\test-output\trusted-email-review\REVIEW_20260831T120929Z`

Inspected from the desktop over `\\flightsim\FlightSim User\MemoryBox\docs\test-output\trusted-email-review\REVIEW_20260831T120929Z`. The shorter UNC `\\flightsim\MemoryBox\...` is not a share on this network. No file was copied.

The directory contains exactly seven `CHUNK_00N_MODEL_PASTE.txt` files. That is the canonical set. There is no eighth chunk paste in this directory.

| Seq | Filename | Bytes | SHA-256 | Conversations | Messages | Earliest | Latest | Review status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `CHUNK_001_MODEL_PASTE.txt` | 721963 | `906f98963140f11d07ddeffac7fb1008a36c20f46fd09604955fe33f2b97efcf` | 72 | 325 | 2009-01-01 | 2009-09-08 | reviewed_manifest_match |
| 2 | `CHUNK_002_MODEL_PASTE.txt` | 733205 | `1014073be3e9f0ddb2ba579ad4662cdb23d9b2cd9ed45c49b7baaa30a2be66e6` | 97 | 331 | 2009-09-11 | 2010-05-13 | reviewed_manifest_match |
| 3 | `CHUNK_003_MODEL_PASTE.txt` | 730546 | `7ab2e6daed825f90610a30fe0c53a274e8fec26104a6cb6bebbc7485318818ac` | 108 | 485 | 2010-03-25 | 2010-12-14 | reviewed_manifest_match |
| 4 | `CHUNK_004_MODEL_PASTE.txt` | 729574 | `1c5764adfd21f5d3e8d8af0e18d37889c5741d99144cca2fcd8512b73a6214e1` | 126 | 613 | 2010-12-14 | 2011-12-24 | reviewed_manifest_match |
| 5 | `CHUNK_005_MODEL_PASTE.txt` | 733298 | `da2a80676fdb13b1bc2034649dd44d8680083dbbd957668ceda49b39f4189588` | 131 | 714 | 2011-12-15 | 2012-11-05 | reviewed_manifest_match |
| 6 | `CHUNK_006_MODEL_PASTE.txt` | 727591 | `e4f72f34b78dafe441c11e2ad41db56316f500adae585553484e1853c16c265b` | 133 | 688 | 2012-11-05 | 2013-07-13 | reviewed_manifest_match |
| 7 | `CHUNK_007_MODEL_PASTE.txt` | 462364 | `761a6d8b2281e49263c169f11bcfb6ef24c04aea1d8aefa02a767577fb1a4886` | 90 | 440 | 2013-06-26 | 2014-03-05 | reviewed_manifest_match |

Totals: 7 files, 4838541 bytes, 757 conversations, 3596 messages.

Review ID: `REVIEW_20260831T120929Z`
Source commit recorded in the review metadata: `08c92a00d713db85091d3b9078af1b1c6cfabdb3`
Frozen parent paste SHA-256: `68043b1e859b71187373600d4c9aa0eb6c084c621e10242250af949663e8614d`

Each on-disk chunk hash equals both `CHUNK_MANIFEST.json` `chunk_sha256` and the reviewed hash in `CHUNK_MANIFEST_RESYNC_REPORT.txt`. Each chunk also has a different predecessor hash from before that resync. No file in this directory compares the chunks with an I14 successor, so no I14 relationship was assigned.

Date ranges overlap between neighboring chunks. That overlap is in the review manifest. It does not change which seven files are the set.

A separate directory, `docs/test-output/c1t-benchmark/chunks/chunks-c1t-68043b1e859b7118-e42d15817eb90e25`, contains many more `CHUNK_*_MODEL_PASTE.txt` files. It was not inventoried as the Peggy set.

## Companion files

| Filename | Role | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `CHUNK_MANIFEST.json` | manifest | 266812 | `7d65ed7998a57e734dc5616868397a0879dd05643932d3c20aa9d20b9b59bbfd` |
| `CHUNK_MANIFEST_RESYNC_REPORT.txt` | hash_ledger | 1676 | `6cdc4ed430a0a31a00df1c0785b102378eefa87e566589fff8f820a38636a2c0` |
| `CHUNK_PREPARATION_REPORT.txt` | chunk_preparation_report | 1803 | `75bb93790f8bb8ddea9d19191882bb2e6d4fdd996bbf4dc40bc1f067364a540b` |
| `FREEZE_RESYNC_REPORT.txt` | freeze_report | 520 | `e162a03ecc3a5a3a3306fb5466e84a56da9327c8e2f86baec05bd5dbba87b886` |
| `LOCAL_MANIFEST.json` | generation_metadata | 783 | `a1f662db4faf4f4d3a44649c0c0222a3b62864a8e9bd1e931672c9fe0854b2e8` |
| `MODEL_PASTE.txt` | model_paste | 4811404 | `68043b1e859b71187373600d4c9aa0eb6c084c621e10242250af949663e8614d` |
| `PREPARATION_REPORT.txt` | preparation_report | 31044 | `aabae9e9fb9bd65253f797951cac98ef7db9cb93dbe4a9c56c6c328e46dcc1bc` |
| `SOURCE_MAP.json` | source_map | 4112491 | `67b320e82af751b78be05e82e91e88259fc30a14e023485b6b2aba7252208d07` |

`MODEL_PASTE.txt` hash equals the frozen parent paste hash. No I14 comparison file is present.

## Packet strategy

The benchmark pool is all seven reviewed chunk pastes. `CHUNK_001` is not the pool by itself.

The harness selects conversation-intact packets from that pool:

- early, middle, and later packets from date-ordered thirds of the same conversations;
- a capacity ladder that grows the token target over that same pool;
- stable evidence IDs and source-chunk provenance on each packet;
- an explicit partial-boundary note when one thread must be cut between complete turns;
- a SHA-256 of every materialized packet text;
- read-only use of the reviewed files.

Real Peggy packet text was not generated in this gate. The strategy is implemented and covered by the offline proof with synthetic evidence. Packet generation, when it happens, stays offline and is separate from any Ollama request.

## Ollama on FlightSim

| Item | Value |
| --- | --- |
| Endpoint | `http://flightsim:11434` |
| Version | 0.34.1 |
| Status | reachable |
| Desktop `127.0.0.1:11434` | connection refused |
| Loaded models | none |
| GPU | not observed |
| Total VRAM | not observed |
| Pulls or loads this gate | none |

Installed tags:

| Tag | Digest | Quantization | Size | Context | Screen status |
| --- | --- | --- | --- | --- | --- |
| `gemma4:26b` | `08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68` | Q4_K_M | 18604148513 | 262144 | configuration C, installed |
| `gemma4:latest` | `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` | Q4_K_M | 9608350718 | not read | 8.0B tag, not configuration C |
| `llama3.2:latest` | `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` | Q4_K_M | 2019393189 | not read | not a benchmark configuration |
| `nomic-embed-text:latest` | `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f` | F16 | 274302450 | not read | not a benchmark configuration |

`qwen3:30b` is not installed, so it cannot stand in for configuration A.

Missing, not installed:

- Configuration A: `ollama pull qwen3:30b-a3b-instruct-2507-q4_K_M`
- Configuration B: `ollama pull qwen3:14b-q8_0`

Those commands were not run.

## Revised draft prompt

Version: `i11a0-narration-v0.2-draft`
SHA-256: `c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b`
Accepted: no
Production narrator: no

Change from v0.1-draft: the ban on emotion, motive, atmosphere, and interpretation is replaced by a rule that allows a cautious, cited interpretation and forbids stating those qualities as fact unless the evidence says them. Chronology, attribution, forwarded material, citations, uncertainty, and partial context are unchanged.

```
I11A0_BENCHMARK_NARRATION
version: i11a0-narration-v0.2-draft
role: benchmark narration only. This is not a production narrator and not an evidence ledger.

You are writing a documentary family narrative for one bounded evidence packet.
Write continuous prose a family member could read. Stay inside the supplied evidence.
Do not return JSON. Do not return a structured ledger of events, patterns, and conflicts.

Required narrative format:
- Plain prose paragraphs. No title, no JSON, and no bullet outline.
- When the packet can support it, write about 4 to 8 short paragraphs. If the packet is small, write fewer. Do not pad to reach a length.
- Begin with the account. Do not describe these instructions, and do not announce that you are a model.
- Do not add a provenance appendix, a count of messages, or a list of archive totals.
- If the user message says partial_context is yes, close with one short paragraph in ordinary language stating that this account covers only the supplied segment, that earlier or later context was not in the packet, and naming the partial_boundary evidence IDs from the user message. If partial_context is no, do not invent a missing-context apology.

Evidence citation:
- Every sentence that states a date, person, place, or event must be supportable by an evidence ID that appears in the packet.
- Use the ID form the packet already uses, such as [email_N].
- Put the citation at the end of the sentence it supports.
- Do not invent an evidence ID. Do not cite an ID that is not in the packet.
- If several sentences depend on the same source, cite that source on each of those sentences.

Chronology:
- Tell events in time order using the dates written in the evidence.
- When two items share a date, keep the order in which they appear in the packet.
- Do not move an event to a different date because it would make a smoother story.
- If a date is missing, incomplete, or contradicted by another passage in the packet, say that the date is uncertain and do not choose one.

Attribution and forwarded or quoted content:
- Name the author when the packet shows who wrote the message.
- Words inside a quoted reply, a forwarded chain, or an earlier message are not the outer author's own words unless the packet shows that the outer author wrote them.
- Keep these distinct: the person wrote this; the person quoted someone else; the person forwarded something written by someone else.
- Do not turn an advertisement, receipt, boilerplate notice, or signature block into a personal or family event.

Prohibited invention, and the line between fact and interpretation:
- Do not invent people, places, dates, relationships, or events.
- Do not state emotion, motive, personality, atmosphere, or significance as fact unless it is directly expressed in the evidence. You may offer a cautious interpretation when multiple cited passages support it, using language such as "the exchange suggests" or "the repeated messages indicate." Clearly distinguish interpretation from observable fact. Do not invent inner thoughts, emotions, motives, or conclusions merely to make the account more dramatic.
- Do not treat being mentioned, copied, photographed, or present as purpose, companionship, or meaning.
- A plan, an invitation, or a discussion is not proof that the event happened.
- If the evidence is thin or ambiguous, say what is known and what is uncertain. Do not fill the gap.

Output length:
- Stay inside the output budget. Finish the sentence you are writing rather than stopping mid-word.
- Do not start a new episode you cannot finish inside that budget.
```

User template:

```
PACKET
packet_id: {packet_id}
packet_role: {packet_role}
prompt_version: {prompt_version}
time_range: {time_start} to {time_end}
partial_context: {partial_context}
partial_boundary_note: {partial_boundary_note}
evidence_ids_in_packet: {evidence_ids}

Write the documentary narrative for this packet only. Use no evidence from outside it.

===== EVIDENCE =====
{evidence_text}
```

## Code changes for this inventory

Commit `7be7745b6503af5a383c716b7dd9d1e2bf27b5a8` teaches the inventory to walk the review directory, read `paste_file` / `chunk_sha256` / `date_range`, and record companion files. It also stores prompt `i11a0-narration-v0.2-draft`. The offline proof was re-run after that change: 44 checks, no problems.

## Smoke command, still blocked

```
python -m memorybox i11a0-benchmark --config docs/ops/i11a0_benchmark.example.json --stage smoke
```

The command refuses with exit 2 and `inference_not_authorized`. It was not run.
