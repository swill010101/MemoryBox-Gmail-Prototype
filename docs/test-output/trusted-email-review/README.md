# Trusted email review (local only)

Human-inspection packets for date-bounded Peggy conversations.

`python -m memorybox prepare-trusted-email-review --person "Peggy George" --flightsim`

writes `REVIEW_<stamp>/MODEL_PASTE.txt`, `SOURCE_MAP.json`, and `PREPARATION_REPORT.txt`.

Do not commit those files. Do not upload them to GitHub. Do not paste message bodies into a cloud-agent chat.

Gemma is a later, explicit step against the approved hash:

`python -m memorybox run-trusted-email-review-gemma --paste-dir <REVIEW_dir> --require-hash <sha256>`

That command never calls Sol, never runs the paired pipeline, and never refreezes.
