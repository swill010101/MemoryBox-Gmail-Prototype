# Owner annotation coverage checkpoint ? 2026-09-06

## Supplied read-only result

Tom supplied the deployed /annotations/transcript/coverage result. Manifest p2-i13-flightsim-22, version 0.2-membership-confirmed: 22 sources; zero sources without stored transcript words; 35,861 words; 20 reviewed words; 35,841 unreviewed words; one active assignment. The assignment is on vid-da41273dbd9ac4bb (4,087 words, 20 reviewed, 4,067 unreviewed). All other 21 sources have zero reviewed words and active assignments.

This independently corroborates the UI's saved-count result through an operator-supplied API inventory, not an agent database query. The aggregate report does not expose the assigned Person, text, exact interval or confidence. It does not verify model recognition, transcript completeness, word correctness, complete scenario coverage or unchanged queue counts. Existing words on all 22 sources do not justify a new transcription run or prove none will ever be needed. No target percentage or requirement to label all 35,861 words is established by this inventory.

The PowerShell prompt is in the older p2-i13-annotation-ui-2c2dd2d directory. A working directory does not identify the running server commit; the GET reached whichever app is serving port 8790. Preserve the prior owner acceptance of the reviewed release without claiming this output verifies its process SHA.

## Next review and bounded voice-proof preparation

Use MB's accepted annotation-only workflow to identify representative owner-confirmed speech within the exact manifest. Begin with the existing source and verify the intended Person and speech span. Add clearly attributable examples where available, with a separate passage reserved to evaluate future suggestions rather than also using it as the learning sample. Capture off-camera speech and unknown/no-matching-Person or poor-audio cases where they actually occur; do not invent labels or infer the speaker from the visible face.

The accepted PRD requires face-only, off-camera voice, simultaneous modalities, multiple people, poor audio, occlusion, short/long appearance and no-match scenarios. This speech review is only part of that matrix. Explicitly mark absent or not-yet-reviewed scenarios, retaining the 22-source scope.

Before any learning/recognition run, prepare a versioned plan specifying exact selected annotation IDs, Person/source/span/provenance, training versus evaluation allocation, model/threshold, bounded work cardinality and attempts, queue/exemplar side effects, expected evidence, and rollback/retirement behavior. The existing combined Learn action is not authorized by this checkpoint. Development and feature-branch publication may proceed under Tom's standing authorization; production changes require the consolidated readiness approval boundary. Do not equate owner assignments with actual voice recognition proof.

No runtime writes, migrations, transcription, recognition, cleanup, exemplar creation or archive activity occurred in recording this checkpoint.
