# FlightSim voice-pilot clone rehearsal

This is the next development validation step, not production deployment. `rehearse-voice-pg16.py` has two modes: default read-only prerequisite inspection, or explicit `--rehearse` for backup and isolated clone validation. Tom's standing authorization includes clone migration rehearsal. No service stop, model install, recognition, Learn unlock or production migration occurs.

The helper verifies the FlightSim hostname, expected clean Git release, PostgreSQL 16, current migration 031, absent 032/pilot tables, matching pg_dump major version and available disk capacity. It makes a consistent custom-format live backup using read-only pg_dump, copies it to a fresh `C:/MemoryBox-backups/i13-pre032-<random>` directory and checks host/container SHA256 agreement. The Windows copy is copied back and restored to a new `mb_i13_pre032_restore_<random>` database, never to `memorybox`.

Only the clone receives migration 032. The first application rolls back; the second commits and records 032 in the clone's ledger. Both compare counts and content fingerprints for transcript words, immutable transcript versions, annotations, recognition/speech queues and Historian Capture campaigns/items. A final read-only live check confirms 032 remains absent. The backup, proof JSON and clone remain available. There is no cleanup or automatic retry on failure.

Local validation: eight tests passed on the isolated PostgreSQL 17 fixture, including generated-name rejection, migration rollback/commit and deliberate existing-data corruption rejection (plus five existing pilot database tests). This verifies SQL/control logic, not FlightSim's PostgreSQL 16 restoration. Only the FlightSim script output can establish that result.

Run from the exact detached release with `python -B docs/implementation/p2-i13-stage-a/rehearse-voice-pg16.py --expected-sha <exact release SHA> --rehearse`. The supplied operator command will contain the actual SHA, not this placeholder. Existing app/worker services may remain up; the backup is transactionally consistent. Backup/restore consumes disk and I/O, but does not drain or process runtime queues.

Paste the final JSON summary. Do not send the backup or model/media files. Then finalize the FlightSim encoder environment and threshold protocol. Only after all prerequisites are concrete will the consolidated production deployment report request its one approval.
