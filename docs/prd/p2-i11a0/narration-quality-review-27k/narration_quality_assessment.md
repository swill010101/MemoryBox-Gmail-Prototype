# Narration quality assessment (Candidate A)

Audit copy: Candidate A (coarse), SHA-256 `9b0214c086a2ebf97c257b0a8a577a26c5b1ac3ba58e24c236dfcfe97326b512`, execution `d22f720f…ec747d9`. Byte-identical to Candidate B. Candidates C and D are different texts; extra defects are called out where they change a score.

This is a review of **this packet’s narration**, not of a hypothetical complete Peggy biography.

Scores are 1 (fail) to 5 (meets the prompt and the packet). A serious defect is not averaged away by fluent prose.

## Factual fidelity — **2**

Supportable core: Peg Legg and Tom Will coordinated 2006 Christmas lists; Tom sent a master list of who was giving what; Peg shopped (including DVDs and books); Peg called Tom “little brother”; a check-engine / car problem threatened December plans.

Serious defects in A/B:

- Atmosphere and character claims presented as fact (“chill of winter,” “immersed,” “meticulous and affectionate,” “close-knit,” “palpable” enthusiasm, “optimistic and determined,” “love, preparation, and the joy of giving”).
- Completed-gift language (“ensuring that each person received something thoughtful,” “everyone received something they would cherish”) is not established as a finished outcome in the cited sentences.
- Opening frame “late autumn of 2006” erases the packet’s 2005-12-10 start and 2007-12-04 end.

The DVD/VCR player for Dad is **in the packet as a plan** (“Ange and I are going to T later to fetch the DVD/VCR player… for us to give to Dad”). A does not invent the object. It does invent excitement and the purpose “enjoy his favorite movies in comfort,” and it does not mark the Target run as unconfirmed.

Candidate C adds a completed-holiday ending (“efforts paid off… everyone received the gifts they had hoped for… love and laughter”) that the packet does not prove. That is worse fidelity, not a second audit copy.

## Citation validity and sentence-level support — **1**

Zero citations in all four outputs. The prompt requires an in-packet ID, in the packet’s ID form, on every sentence that states a date, person, place, or event. Candidate A states people, events, and a season in every paragraph and cites nothing. No hallucinated IDs. Support for several sentences is only partial even if IDs had been attached (`claim_audit.csv`).

## Chronology — **2**

The packet is dated 2005-12-10 through 2007-12-04 and is ordered as packed: 2005 wish-list forward, October 2006 MS-150 thanks, November–December 2006 shopping and weather/car, then later 2007 fragments including a split T-0958.

A/B tells a single pre-Christmas 2006 arc. It does not walk the dates. Shared-date packet order is unused because most events are omitted.

## Authorship and attribution — **3**

A/B correctly treats the master list as Tom’s and the shopping updates as Peg’s, and it does not put the MS-150 ride in Peg’s mouth. It also never names Sue Will or the group recipients on Tom’s thanks letter.

Candidate C says Tom “shared his experience with Peg.” Peggy George is a recipient of a group letter, not the sole interlocutor. That is a relationship-narrowing error.

## Forwarded and quoted material handling — **3**

The packet opens with Peg forwarding a Christmas wish list (2005) and contains Tom’s MS-150 letter plus Sue’s quoted reply. A/B does not mis-attribute those bodies to the wrong person; it simply never handles them. That is omission, not a clean pass on the prompt’s forward/quote rules.

Candidate C mentions the ride without separating Tom’s letter, Sue’s reply, or the To/CC list.

## Plan versus completed event distinction — **2**

Repeated “ensuring / received / cherish” language treats plans as outcomes. The DVD/VCR player is a planned purchase. Saturday dinner at Dad’s and some pickups exist later in the packet, but A’s sentences claim a general completed holiday of received gifts. Candidate C’s last paragraph is an explicit completed-event invention.

## Unsupported emotion, motive or significance — **1**

This is the dominant failure mode. Examples from A: “affectionate approach,” “close-knit nature,” “smallest gestures were appreciated,” “enthusiasm… palpable,” “eagerly awaited,” “particularly excited,” “deep understanding of his interests,” “optimistic and determined,” “anticipation and joy,” “warmth of being together,” “deep sense of gratitude,” “time of love… joy of giving… heartfelt messages.”

Peg does write love-to-all closings and that being together is what she treasures. The prompt allows cautious interpretation with distinguishing language. A states inner life and moral significance as fact.

## Treatment of uncertainty — **2**

No “the date is uncertain,” no “the packet does not show whether,” no distinction between plan and confirmation. Gaps are filled with mood.

## Partial-context disclosure — **2**

Packet truth: `partial_context=true`, included `93a44b2a-…`, omitted `8c2b7377-…`, thread T-0958. A does not close with the required ordinary-language segment disclosure.

The user wrapper said `partial_context: no`, so the model followed the **user** instruction not to invent a missing-context apology. That is a **controller defect** (`packet_from_saved_row` zeros `partial_context`) as well as a failed disclosure relative to the evidence. Score 2, not 1, because the model was told the packet was complete.

## Narrative coherence — **4**

Four paragraphs, one season, consistent protagonists. Internally coherent as a Christmas-prep sketch. Coherence is not the same as coverage.

## Readability and prose quality — **4**

Readable family-adjacent prose, complete sentences, no JSON, no title, no mid-word cutoff. Dictionary-level repetition (“meticulously,” “emails reveal”) is a drag but not unreadable.

## Repetition or unnecessary detail — **3**

Little named-gift or dated detail. Much repeated mood (meticulous, affectionate, urgency, excitement, joy). Opposite of a ledger dump; still padded with synonyms rather than events.

## Family-documentary tone — **3**

Sounds like a sentimental recap, not a documentary that stays inside evidence. “Her emails reveal” is an archive-summary register.

## Whether the narrative centers people and events rather than archive mechanics — **3**

People are named (Peg Legg, Tom Will, father). Events are thin. “Her emails reveal / included / reflected” keeps the archive in the foreground.

## Whether the narrative ends naturally — **4**

`done_reason=stop`. The last sentence is a complete moral coda, not a truncated clause. The coda is unsupported significance, but it is a natural stop, not an output-limit stop.

## Whether output length was appropriate for the evidence — **2**

About 370 words, four short paragraphs, eval_count ~421. The prompt allows 4–8 paragraphs when the packet can support it. This packet is 62 messages / 42 threads, not a small packet. Length matches a mood essay, not the supplied evidence. Under-coverage is the problem, not verbosity.

## Evidence omitted or disproportionately emphasized — **2**

Emphasized: generic 2006 holiday prep and feelings.

Omitted or barely used, with enough weight to distort **this** bounded account:

- 2005-12-10 forwarded wish list (packet start)
- Tom’s October 2006 MS-150 thanks and Sue Will’s reply (A/B omit entirely; C compresses badly)
- Ice / winter-storm and power-loss stretch in the packet (A/B omit; D mentions a power outage but inflates duration/resilience)
- Named shopping (wallet for Lars, Matt’s sweater, towels, books, headsets, etc.)
- Car diagnosis/outcome beyond “malfunctioning”
- 2007 material and the T-0958 split

Disproportion: Christmas feeling over the actual mix of logistics, weather, health/work constraints, and Tom’s ride.

Candidate D’s power-outage paragraph is closer to a real thread than A, but “several days” and “resilience” still overclaim relative to “longer spell yesterday afternoon here without power.”

## Overall

Candidate A is fluent and the wrong kind of document: a Hallmark compression of a two-year email packet, with no citations, invented interiority, and plans written as outcomes. It is **not** good enough to use as the foundation for later MemoryBox narrative work without prompt and/or controller changes and a new confirmation run.

Recommended founder disposition from this auditor: **Reject** as a narrative foundation; **Accept with prompt and controller changes** only as a capacity-rung artifact that proved the model would finish. That disposition is for Tom; see `founder_score_sheet.md`.
