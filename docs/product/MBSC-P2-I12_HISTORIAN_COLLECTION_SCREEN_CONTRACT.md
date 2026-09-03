# MBSC-P2-I12 — Historian Collection Screen Contract

**Status:** Planning **LOCKED** 2026-09-03 · **BUILD NOT AUTHORIZED**  
**PRD:** [MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)  
**UX baseline:** [MBUX-001 v0.4](MBUX-001_v0.4.md) dark-theme MemoryBox shell — **not** a separate Marvin app visual system

---

## 1. Navigation placement

- Primary entry: **Review & Learn** area → **Historian Capture** (or **Collection Campaigns**)  
- Secondary: Person profile → “Campaigns involving this person” (read-only list link)  
- Badge: new Capture Items awaiting review (count)

Follow I10A-family chrome: left context panel, main canvas, evidence drawer patterns.

---

## 2. Screen map

| ID | Screen | Purpose |
|----|--------|---------|
| HC-01 | Campaign list | All campaigns with status, respondent count, new response badge |
| HC-02 | Create / edit campaign | Title, cadence, timezone; draft-only edits |
| HC-03 | Select respondents | Pick canonical MB People; confirm contact route per Person |
| HC-04 | Question editor | Ordered questions; starter templates; reorder while unsent |
| HC-05 | Campaign detail | Status, per-respondent progress matrix, delivery log |
| HC-06 | Response / review inbox | Filter: new · retained · rejected · unmatched |
| HC-07 | Capture Item viewer | **Read-only** immutable source: raw headers, body, attachments |
| HC-08 | Review Draft editor | Versioned working copy; notes; proposed links |
| HC-09 | Assessment & verdict | Private assessment control; explicit verdict buttons |
| HC-10 | Promotion flow | Choose Story (required V1) / Artifact / evidence; confirm |
| HC-11 | Unmatched resolution | Link to delivery, dismiss, or ad-hoc assign |
| HC-12 | Paused / stopped / completed states | Clear banners; explain what still accepts inbound |

Reference mockups: `codex/historian-capture-reference-screens-20260829` @ `fe913a4` (August 22 screens — **layout reference only**, not authoritative product spec).

---

## 3. Screen contracts

### HC-01 — Campaign list

- Columns: title, status pill, respondents (avatars/names), progress (e.g. 2/5 questions sent), new items count, updated  
- Actions: New campaign, open detail, pause/resume/stop from row menu (confirm destructive)  
- Empty state: explain historian capture purpose + CTA create  

### HC-02 — Create / edit campaign

- Fields: title (optional), cadence (days/hours), timezone, send mode (if enabled)  
- Save as draft only until Start  
- Cannot start without ≥1 respondent and ≥1 question  

### HC-03 — Select respondents

- Search MB People (I10A.1 picker)  
- For each Person: show profile email(s); owner **must confirm** one route (radio)  
- If no email on profile: block send until owner adds contact on Person or enters confirmed one-off with warning  
- **No** silent auto-pick on ambiguous email  
- Show duplicate-Person guard per campaign  

### HC-04 — Question editor

- Ordered list drag-reorder (unsent only)  
- “Add from starter questions” (config templates)  
- Skip question (pre-send) marks `skipped`  
- Sent questions: read-only text with “sent on …” badge  

### HC-05 — Campaign detail

- Header: status, cadence, started/stopped timestamps  
- **Per-respondent table:** question # · delivery status · capture received? · review state  
- Delivery log: expandable rows with correlation token, sent_at, fail_detail, retry  
- Actions: Pause, Resume, Stop (confirm), Add question (if policy allows)  

### HC-06 — Review inbox

- Tabs/filters: **Needs review** · Retained · Rejected · Unmatched  
- Row: respondent, question excerpt, received_at, assessment badge, verdict badge  
- Open → HC-07 + HC-08 side-by-side or tabbed (source | draft)  

### HC-07 — Immutable source viewer

- Show: From, Subject, Date, Message-ID, correlation match info  
- Body: original extracted text (label: “As received”)  
- Attachments: download/view only  
- Link: “View raw .eml” (preserved_raw_uri)  
- **No edit controls** on this pane  

### HC-08 — Review Draft editor

- Editable text area (owner cleanup/transcription)  
- Version dropdown: v1, v2, … current  
- Private notes field  
- Proposed links: People pills, Story/Artifact pickers  
- Save draft creates new version; prior versions read-only  

### HC-09 — Assessment & verdict

- **Owner assessment** (private): proposed 6-value select + optional note  
- History link: prior assessments  
- **Verdict** (explicit, separate step):  
  - **Keep in archive** (`retained`)  
  - **Reject as evidence** (`rejected`)  
  - **Promote to MemoryBox** (`promotion_authorized`) → opens HC-10  
- `believe_incorrect` assessment + reject: show warning that Ask will not use as affirmative evidence  

### HC-10 — Promotion flow

- If Story: new Story vs link existing; pre-fill from Review Draft; narrator = respondent  
- If Artifact (if in scope): create representation from attachment or body  
- Confirm screen: provenance chain summary  
- Success: deep link to created Story/Artifact  

### HC-11 — Unmatched resolution

- List unmatched/ambiguous Capture Items  
- Show subject, from, date, excerpt  
- Actions: search campaigns/deliveries to link; mark spam/dismiss  
- Resolution audit trail  

### HC-12 — State banners

| Campaign status | Banner |
|-----------------|--------|
| `paused` | “Outbound paused — inbound replies still accepted” |
| `stopped` | “Campaign stopped — no further questions will be sent” |
| `completed` | “All questions sent — awaiting or reviewing replies” |

---

## 4. Shared UX rules

1. Dark theme, MB shell components — reuse Journal/Story panel patterns.  
2. Immutable source always visually distinct (muted panel, lock icon).  
3. Never imply contributor text is verified fact.  
4. Assessment labels never shown to contributor (N/A in V1 — no contributor UI).  
5. Promotion never one-click from inbox row without review + verdict.  
6. Return navigation preserves campaign/inbox context (I1 context stack).  

---

## 5. Out of scope for V1 screens

- Curator-suggested questions UI  
- Contributor portal  
- Voice record on web  
- Multi-user permissions  
- Dynamic Views / Saved Views (I13)  

---

**PLANNING LOCKED 2026-09-03.**
