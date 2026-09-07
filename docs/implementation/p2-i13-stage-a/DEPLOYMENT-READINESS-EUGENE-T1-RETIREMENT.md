# FlightSim readiness: Eugene T1 lifecycle retirement

## Pending approval

This action retires one older training reference only: T1 annotation `d5a3d050-76d6-446e-91d4-ff89986856cb`, from stopped admission `1039c733-2149-40b2-b027-97058e032af3`. It preserves the annotation/history, prevents future pilot reuse, marks that admission's result stale, and starts no reprocessing.

T2 is excluded because it is shared by the current Tom and N1 pilots.

## Guarded execution

The script requires the read-only T1 preflight to remain current, verifies a new custom-format PostgreSQL backup with `pg_restore --list` and matching container/local SHA-256 on FlightSim C:, then writes exactly one immutable retirement record. It verifies the Eugene result is stale while Tom and N1 results remain current and legacy counts remain unchanged.

No private audio, model inference, media conversion, Learn, queue drain, migration, service restart, or reprocessing occurs. No planned downtime.

Rollback is logical: preserve retirement history and stale result; do not delete records or restore the database. Any future reprocessing requires a separate proposal and approval.
