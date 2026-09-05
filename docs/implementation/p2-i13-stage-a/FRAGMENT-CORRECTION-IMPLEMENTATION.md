# Bounded fragment correction implementation - 2026-09-05

Tom approved implementation after the Gallery correlation. This delivery changes isolated code and tests, not runtime records. It does not run Learn, recognition, transcription, conversion, cleanup or a migration.

## Result and scope

The traced HVRT source/run's AI-associated face moments are now presented as one source card per compatible Person/model partition, with a Jump to a moment control in the existing viewer. Every query-returned moment, original interval, observation ID and authority is retained in the response. The card displays a moment count, not a half-second source duration. Selecting a moment changes only the existing player's currentTime: no new file, restart, artificial stop, context reset or autoplay is introduced.

The pilot source/run is explicitly allowlisted in recognition/source_moments.py. Other sources/runs, speech, owner-confirmed evidence and unknown lineage are not projected. No extra DB requests are added; list_appearance_moments selects existing run/observation columns and serializes IDs. Playback and Historian Capture remain unchanged. Data rollback is unnecessary: reverting to the preceding release restores presentation because no stored moments are changed.

Query membership takes precedence over the full-source preview. A result containing the seven verified pilot moments becomes one card with those seven seek points, not all 79 historical points. This prevents a filtered Ask from silently expanding. A result containing all 79 retains all 79. The earlier two provisional groups are not persisted as continuous appearance intervals; the jump list preserves the explicit 40.5-to-60.5 gap. Other Grandpa sources can still have fragments and require separate reviewed scope.

Future admitted scans now carry the sampler's planned interval into observation metadata. The grouper uses matching recorded cadence with a 0.011-second rounding allowance. Twenty-second gaps at ten-second cadence remain split; uncertainty, non-match points, withdrawals and partition changes block joining. Legacy observations without cadence retain conservative behavior. Positive sampling is not frame-level scene tracking, and the existing sampling cap still ends this source's samples at 790.5 seconds. No unobserved tail is claimed. Existing destructive rescan persistence is not repaired or exercised here; do not rerun Learn on the strength of this correction.

## Verification

- 10 focused tests: actual collector/grouper flow with synthetic frames; missing samples; explicit uncertainty/non-match/withdrawals; Person/source/run/model boundaries; legacy unknown cadence; source projection and every original lineage record; query subsets; other-source/speech/owner isolation; repeat projection; retrieval dedupe.
- 33 Stage A lock/playback tests, 4 legacy trace/reproduction tests, 18 Ask/context/provider/progress tests pass (65 total).
- browser_i13_fragments.py executes the actual card renderer, source seek binder and moment selector in headless Chromium with an in-memory synthetic video. Source seek 0.5s, chosen seek 1.5s, continues beyond 2s relevance end, keeps source URL and item unchanged, and disables navigation until metadata loads. JSON and screenshot proof accompany this report.
- JavaScript syntax and Git whitespace checks pass. Approved Video Detail / People reference inspected: existing dark source player and evidence navigation are retained; the added selector is a small extension, not a rebuilt People/Learn screen.
- This is not a live FlightSim acceptance test. Complete modal Previous/Next, Gallery return, transcript/owner overlays and the actual pilot playable copy require Tom's review after deployment. No performance recovery or face/voice accuracy is claimed.

## Deployment and rollback - Tom operates FlightSim

1. Review the code commit and this report. Keep the prior release available. No migration, backup replay or processing step is required for this code-only change.
2. Fetch the branch and create a new detached release at the exact reviewed commit, using the complete command block supplied with delivery. Never pull/switch/clean the dirty C:\MemoryBox checkout.
3. In a configured FlightSim PowerShell shell, invoke start-fragment-release.ps1 with the exact ExpectedSha. Default mode runs 65 offline tests and the locked launcher check only. It prints no credentials and starts nothing.
4. After review, stop the existing app and worker normally with Ctrl+C. Rerun the helper with -Start; it refuses occupied ports, uses the explicit Python 3.12 executable, preserves original runtime configuration/Capture dependency, and starts interactive app/worker consoles. Drains remain off and admission unset. Do not use startmb as a shortcut.
5. Verify app/worker startup. Refresh MB, submit a fresh named Ask, and inspect the pilot source: one card for its returned native face moments, original full-source playback, all returned seek points accessible, and no implied 0.5-second video length.
6. Select a later moment, play beyond its old half-second end, navigate Previous/Next and return to the same Gallery filters/sort/scroll. Confirm other sources and photo results remain available and transcript text/owner overlays persist. Do not select Learn.
7. Report results and stop for founder review. Do not enable processing or apply migrations.
8. Rollback: stop only these app/worker consoles, then use the prior release's locked launcher with its own exact SHA and existing configuration. No media, DB records, observations or credentials are restored/deleted because this deployment does not change them.

## FlightSim owner report - 2026-09-05

After the fa09ec646e669aefdbe6c747ba350650b1d857b3 release checks/start instructions, Tom reports that the previously counted 15 clips are now 9; one card is labeled 7 moments, plays correctly and jumps between moments. The supplied screenshot shows the 7-moments badge. Count reconciliation: replacing seven separate entries with one source card reduces the count by six (15 - 7 + 1 = 9). This is a presentation change, not deletion of six records or media files.

Record source-card consolidation, playback and moment navigation as passing by owner report. The remaining eight entries in that reported set are not established to be the same source; their exact provider/source/evidence lineage requires read-only correlation before extending projection. Similar thumbnails do not establish identical files. The screenshot's broader 57-visible Gallery count is not the same as the reported 15-to-9 subset.

This report does not independently confirm Gallery-return context, all modal navigation, transcript overlays, full I13 acceptance or face/voice accuracy. No additional processing, migration, deletion, conversion or broader projection is authorized/performed by this update. Keep the deployed code at fa09ec6 pending review; this documentation update needs no redeploy.

## Gallery return confirmed and next read-only lookup authorized

Tom subsequently reports that a remaining entry also plays beyond its old half-second end, and confirms closing the viewer preserves the Video filter and Gallery scroll position. Record these as owner-reported pilot passes; do not treat them as acceptance of all sources or full I13. Tom then directed proceeding with read-only source identification.

identify-gallery-sources.py resolves the exact 47 HVRT appearance IDs supplied in the earlier Gallery capture, including the seven known pilot controls. It uses one repeatable-read/read-only PostgreSQL transaction, fixed UUID parameters, provider predicate, 64-row cap and connection/statement/lock timeouts. Output is limited to source/Person/run IDs, intervals, status/authority/model, plus approved manifest filename/duration where matched. It does not import MB, scan media, request providers, start services, write files, or change database rows. It reports unmatched IDs instead of guessing source identity. The earlier snapshot may differ from current rendered membership.

Three offline tests pass: fixed-scope validation; source grouping with explicit unmatched/unknown-manifest results; rejection of unrequested IDs/providers. The helper has not been run against FlightSim by the agent. Await Tom's output before extending any Gallery projection. Raw runtime output should not automatically be committed. No redeployment or service restart is required to run this helper.

## Second-source extension implemented - review before deployment

Tom approved extending the projection to exactly source vid-da41273dbd9ac4bb and run bd94ab11-fb4f-4b8a-b993-339e535f84e6 (20111105_1530.MP4). The approved pairs are explicit; swapping runs between sources, an unknown run, or an off-manifest source cannot activate projection. Provider/source are now explicit grouping keys as well as Person/run/model. No other application behavior changes.

Twelve focused offline correction tests pass, including a two-source fixture that retains seven plus eight moments in two independent source cards and verifies immutable input, source URLs and cross-pair rejection. Existing browser navigation code and proof are unchanged; FlightSim review for this extension remains pending. The standard helper now discovers 67 tests because the focused suite grew by two.

Deployment: create a new detached release at this correction's exact published SHA and run start-fragment-release.ps1 with -ExpectedSha for check-only validation. Keep fa09ec6 available for rollback. After checks/review, close app and worker normally and run the same helper with -Start. Submit a fresh named Ask; for the previously captured fifteen-moment subset expect two cards with seven and eight moments, subject to current query membership. Check jumps, source playback and Gallery return on both. Do not merge sources, run Learn, migrate, delete records or enable drains. Other sources still remain outside this two-source correction.


## Video modal transcript fit correction

Tom reports both corrected source videos work as described on aec628644a983f5c471da627737b1b2637276a43. The remaining issue is modal clipping: the player and moment description push the transcript below the dialog. Tom authorized removing the description and keeping the complete transcript accessible within the modal.

The video dialog now reserves space for the player/jump selector and an independently scrolling transcript. Intrinsic media minimum height no longer expands the main panel beyond the dialog. The transcript accepts keyboard focus. The redundant evidence-count description is removed; the Gallery badge and Jump to a moment selector remain. Styling applies only while viewing video and is removed when viewing another media type. Playback bindings and transcript content are unchanged.

Verification: actual modal HTML, CSS and video/footer renderers reproduced clipping before the fix in all eight browser cases. After the correction, headless Chromium passes all eight cases (1208x832, 1024x640, 800x600, 640x480, each with/without moment navigation), including reaching the last transcript line. The rendered screenshot was visually inspected. All 33 Stage A tests pass. The existing synthetic-video browser test also passes: initial/source seek, chosen moment, playback past the evidence end, and unchanged source/item. Proof: browser-modal-fit-proof.json/png and refreshed browser-fragment-proof.png. These are synthetic browser checks, not live FlightSim acceptance.

Deployment uses the same start-fragment-release.ps1 helper from a new detached release at the exact delivered commit. Run check-only first, stop existing app/worker consoles normally, then run with -Start. No migration or processing is needed. On FlightSim verify both source videos, access the bottom of the transcript, select text, jump to a moment, resize the window and return to the Gallery. Keep aec6286 available for code rollback. Recognition/Learn remain locked; no runtime records or media were changed by this correction.
