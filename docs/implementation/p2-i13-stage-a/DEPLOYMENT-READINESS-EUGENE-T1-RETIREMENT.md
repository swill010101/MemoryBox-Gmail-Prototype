# FlightSim readiness: Eugene T1 lifecycle retirement

## Completed stale-cascade verification

FlightSim read-only verification shows T1 annotation `d5a3d050-76d6-446e-91d4-ff89986856cb` is already retired. Its stopped admission `1039c733-2149-40b2-b027-97058e032af3` is stale; the stopped Tom, N1, and Eugene Patio admissions are current. Do not run this helper with `-Execute`: it is an obsolete duplicate-retirement package.

T2 is excluded because it is shared by the current Tom and N1 pilots.

## Historical guarded execution

The script uses the verified TitaNet tool release's Python environment, requires the read-only T1 preflight to remain current, verifies a new custom-format PostgreSQL backup with `pg_restore --list` and matching container/local SHA-256 on FlightSim C:, then writes exactly one immutable retirement record. It verifies the original Eugene result becomes stale while the current Tom, N1, and Eugene Patio results remain current, and legacy counts remain unchanged.

No private audio, model inference, media conversion, Learn, queue drain, migration, service restart, or reprocessing occurs. No planned downtime.

Rollback is logical: preserve retirement history and stale result; do not delete records or restore the database. Any future reprocessing requires a separate proposal and approval.
