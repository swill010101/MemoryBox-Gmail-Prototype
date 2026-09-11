# P2-I14 screen assets

Images in this folder are **separate PNG/JPG repository files**. Reference them from the PRD with **relative** Markdown only:

```markdown
![caption](p2-i14/assets/filename.png)
```

**Forbidden in Markdown and git for these assets:**

- base64 embeds
- `vscode-file://` URLs
- absolute `C:` / `E:` / FlightSim `C:\MemoryBox` paths
- upload, Library, or scratch paths
- I13 Learn / face / voice / transcript screenshots (unless a later implementation dependency is proven)
- fabricated / mocked “after I14” screenshots during Phase A
- committed images that expose private family email/SMS **bodies**, email **addresses**, telephone **numbers**, calendar **details**, credentials, tokens, or unrelated personal information

Prefer **controlled fixture/sample data**. If live FlightSim UI must be used, **crop or visibly redact** sensitive content before adding the file. Record **fixture** vs **sanitized live** in the table below.

## Naming

| Prefix | When | Overwrite? |
| --- | --- | --- |
| `baseline-*.png` | Accepted HC-2 “before” evidence (current behavior) | Never overwrite with acceptance shots |
| `acceptance-*.png` | Later I14 implemented behavior | Separate files only |

Absence of baseline PNG files **does not block** the Phase A documentation commit. Capturing them remains an **evidence item to complete before the affected UI is changed**.

## Baseline set (accepted HC-2 “before”)

Capture from the accepted HC-2 baseline (runtime SHA `743c767`) on `/explore/ui` and `/admin/jobs/ui` **before I14 implementation**, when practical. These document current behavior, **including communications hidden by default**.

| File | Subject | Data class (when captured) |
| --- | --- | --- |
| `baseline-explore-ask-gallery.png` | Ask/Gallery after a Person Ask (photos/videos visible) | *pending capture — fixture or sanitized live* |
| `baseline-explore-comms-chip-hidden.png` | Communications still hidden by default | *pending capture — fixture or sanitized live* |
| `baseline-explore-day-stack-email.png` | Day-stack Email tab / thread list | *pending capture — fixture or sanitized live* |
| `baseline-explore-email-detail-modal.png` | Email structured detail (quoted turns) | *pending capture — fixture or sanitized live* |
| `baseline-explore-sms-thread.png` | SMS conversation in day-stack | *pending capture — fixture or sanitized live* |
| `baseline-explore-calendar-card.png` | Calendar card / day-stack Calendar tab | *pending capture — fixture or sanitized live* |
| `baseline-explore-save-as-story.png` | Save as Story control on Explore | *pending capture — fixture or sanitized live* |
| `baseline-admin-jobs-scheduled-services.png` | Admin Scheduled Services (HC-2 pattern to extend; not I13 queues) | *pending capture — fixture or sanitized live* |

Planned PRD references (files not in git until captured):

![Ask/Gallery baseline](baseline-explore-ask-gallery.png)

![Communications chip hidden](baseline-explore-comms-chip-hidden.png)

![Day-stack email](baseline-explore-day-stack-email.png)

![Email detail modal](baseline-explore-email-detail-modal.png)

![SMS thread](baseline-explore-sms-thread.png)

![Calendar card](baseline-explore-calendar-card.png)

![Save as Story](baseline-explore-save-as-story.png)

![Admin Scheduled Services](baseline-admin-jobs-scheduled-services.png)

## Later acceptance set (do not capture in Phase A)

Separate files, **never** replacing `baseline-*`:

| File (examples) | Subject |
| --- | --- |
| `acceptance-explore-unified-gallery.png` | Implemented unified mixed-media Gallery |
| `acceptance-explore-comms-loading.png` | Photo-first loading / communications still loading |
| `acceptance-explore-comms-unavailable.png` | Source omitted / unavailable |
| `acceptance-explore-drill-down.png` | Communication drill-down |
| `acceptance-explore-story-return.png` | Return from Story to the same Ask |
| `acceptance-admin-comms-scheduled-service.png` | Communications ingest Scheduled Service status |
