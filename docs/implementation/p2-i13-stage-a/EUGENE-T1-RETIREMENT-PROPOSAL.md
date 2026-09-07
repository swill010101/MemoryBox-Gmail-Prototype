# Eugene T1 retirement proposal

## Selected lifecycle evidence

The read-only candidate inspection identified one safe older result: admission `1039c733-2149-40b2-b027-97058e032af3`, whose training annotation is `d5a3d050-76d6-446e-91d4-ff89986856cb` (T1, Eugene). The admission is stopped and current. Its dependent outcomes are `H1`, `O1`, and `U1-clear`.

T2 is explicitly excluded: its annotation is shared by the current Tom and N1 pilots, so retirement would stale both.

## Preflight

Run the read-only helper before any retirement:

```powershell
python -B docs/implementation/p2-i13-stage-a/prepare-eugene-t1-retirement.py
```

Expected: `mode: check_only`, T1, the three listed dependent outcomes, and no audio/database writes.

## Later action boundary

A separately approved retirement would append only the retirement record with a stated owner reason. It preserves T1 and its history, prevents future use of T1 as a pilot reference, and makes only admission `1039?` stale. It does not alter T2, Tom/N1 results, annotations, media, queues, or start reprocessing. A separate bounded reprocessing proposal remains required afterward.
