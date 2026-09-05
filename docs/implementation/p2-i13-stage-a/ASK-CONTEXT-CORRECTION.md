# Ask context and Person-result correction

Tom approved the Person-result correctness investigation and specified on 2026-09-05:
- `clear all` clears all active Ask context.
- `show me <MB person>` starts fresh, even for the same person.
- Subsequent `in Alaska`, `at Christmas`, and `in 2018` refine that person context.

Implementation: exact clear command bypasses planning/retrieval; clears the old server session and rotates to a new session. Complete MB name/alias resolution for `show me` uses existing read-only name resolution with lazy seeding disabled. Ambiguous names start fresh and proceed to existing clarification. Other queries retain normal parsing. The Gallery adopts the new session, drops presentation filters and selected results, and clears the active shell person on `clear all`. A clear on the Person surface returns to unscoped Explore. Ask history remains history; this command does not delete records, credentials, or historical queries.

Tests exposed and corrected missing person inheritance for bare place/event refinements. Page refresh previously reused `mb_ask_session`; refresh alone was not a context reset.

Separate verified code defects: photo cards and the People rail inferred names from query chips/title; Person timeline fallback invented a requested Person ID on assets lacking membership metadata; retrieval could assign the first mapped Person to an unmatched asset/segment. These fallbacks are removed. Person library cache version changes so prior synthesized membership is not reused; old files remain intact. Asset-level membership or an explicit provider face edge is required. Provider metadata can still be inaccurate: this change does not repair MB-to-provider mappings or legacy recognition data. Missing membership metadata can reduce results; low recall must not be interpreted as an empty personal archive. Rail association is no longer universally labelled owner-confirmed.

Validation: offline context, actual command boundary, planner and membership tests; existing Stage A suite; Node syntax; actual browser Ask-command/state and People-list component with synthetic responses (`browser-context-proof.json/png`). Browser proof is not full live Gallery acceptance. No FlightSim DB, recognition, transcription, provider identity writes, conversion, cleanup or migrations were run. I12 remains unchanged.

## FlightSim deployment and owner verification

1. Use the exact correction commit supplied in the review response. Fetch `origin codex/p2-i13-stage-a` from the current release checkout. Inspect `git show --stat` using that literal SHA.
2. Create a new, unused detached worktree under `C:\MemoryBox-releases`, at that exact SHA. Preserve existing release and `C:\MemoryBox` working trees. Do not pull into or clean the runtime tree.
3. Run `python -B -m unittest discover -s tests -p test_i13_stage_a.py -v` (33 tests), then `python -B -m unittest discover -s tests -p test_i13_ask_context.py -v` (15 tests). Node is required for the Stage A suite. Run `node --check memorybox/explore/static/explore.js`.
4. Use the existing approved `launch-locked.py` arrangement from the new release, updating the expected SHA to the correction SHA. Keep existing inherited database/Qdrant settings and reviewed source/derived/Capture paths. Run check-only first. No migration is needed.
5. Stop the two existing service windows with Ctrl-C; verify ports 8790/8791 clear. Start app and worker through that locked launcher with the reviewed deployment reference. Both drains remain off; admission remains unset. Do not run `startmb.cmd` or register an admission.
6. Confirm the loaded release SHA, Explore and Capture accessibility, and the same dummy recognition/speech probes returning 403 `processing_locked_no_admission`.
7. In Explore enter `clear all`: the Gallery, chips, date/place/media filters and current Person must clear. Enter `show me Eugene Will`: no old location/date/filter should return. Check whether the remaining assets actually contain Eugene; report counterexamples for read-only mapping investigation.
8. Independently run each follow-up from a fresh `show me Eugene Will`: `in Alaska`, `at Christmas`, `in 2018`. Confirm Eugene stays selected and the requested filter appears. Repeat the named search after applying filters; confirm it starts fresh. Also verify `clear all` from the Person surface returns to unscoped Ask.
9. Confirm existing playable source videos still seek correctly. Missing playable copies and legacy fragments remain unresolved; do not trigger conversion, Learn, reconciliation or deletion. Stop for owner review of results.

## Missing photos follow-up

Tom reported zero photos and 48 video moments after deploying 162b996 and using clear all. Code inspection confirms compact timeline assets lack membership, while the fallback metadata request did not ask for withPeople and a single feature-face hit prevented fallback. Corrected: compact-response rejection triggers the existing paginated metadata search with withPeople=true, retaining strict asset membership. Detailed verified rows enrich feature-face stubs. Existing timeout limits remain; a provider failure can still prevent photos returning. Old subset caches are excluded by a new cache version without deleting files. Offline response-shape regression tests are required; actual FlightSim results remain pending. No recognition or transcription is run by this correction.

Verification for this follow-up: 12 context/provider tests and 33 Stage A tests pass (45 total), including actual HTTP-client request/response flow with synthetic compact payloads, explicit metadata membership, feature-face enrichment, unrelated asset rejection and timeout. No live provider call was made.

## Place chip context correction

Tom's live verification: Tom then Alaska works; removing the Alaska chip then asking at Christmas restores Alaska and returns no Gallery. Combined fresh Christmas searches and Eugene/Florida work. Confirmed cause: clearPlaceFilter changed only browser state.

The Find POST now carries an optional context_place_names override. Omitted/null preserves normal inheritance; an empty list clears location and inherited trip labels. An explicit list re-enables/replaces location. The server applies the edit before Ask planning in a new context session, preserving Person, ordinary events and date scope while clearing stale selected results. Browser chip edits invalidate older displayed query results; successful payload adoption consumes the pending edit. This adds no extra HTTP round trip or provider request. It does not refresh the retrieved pool merely by toggling a chip; the next Ask retrieves against the edited context.

Verification: 15 context/provider tests plus 33 Stage A tests (48), Node syntax and rendered actual chip setters / Find request functions with synthetic server responses. Live acceptance remains pending. Retest: show me Tom Will -> in Alaska -> toggle Alaska off -> at Christmas; Alaska must remain absent and Tom must remain selected. Re-enable a place chip and verify the next Ask retains that place. No migration, runtime processing, conversion or I12 edits.
