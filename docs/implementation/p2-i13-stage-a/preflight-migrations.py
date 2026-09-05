"""Read-only FlightSim migration/schema metadata. Never import application startup."""
import json
import os
import re
from pathlib import Path
import psycopg


def main():
    root = Path(__file__).resolve().parents[3]
    paths = sorted((root / "memorybox/migrations").glob("[0-9][0-9][0-9]_*.sql"))
    local = {p.name.split("_", 1)[0]: p.name for p in paths}
    if not paths or len(local) != len(paths) or local.get("030") != "030_p2_i13_scope_admission.sql":
        raise SystemExit("Missing or ambiguous release migration files; stop.")
    dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
    if not dsn:
        raise SystemExit("Load the existing database environment without printing credentials.")
    expected = []
    for p in paths:
        if p.name[:3] in {"009", "025", "030"}:
            expected.extend(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", p.read_text(encoding="utf-8"), re.I))
    with psycopg.connect(dsn, connect_timeout=5,
                          options="-c default_transaction_read_only=on -c statement_timeout=20000") as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = conn.execute("SELECT version,filename FROM public.schema_migrations ORDER BY version").fetchall()
        applied = dict(rows)
        report = {
            "read_only": conn.execute("SHOW transaction_read_only").fetchone()[0],
            "snapshot_time": str(conn.execute("SELECT transaction_timestamp()").fetchone()[0]),
            "runtime_migrations": rows,
            "pending": [name for v,name in local.items() if v not in applied],
            "filename_conflicts": [{"version":v,"runtime":f,"release":local[v]} for v,f in rows if v in local and local[v] != f],
            "expected_tables": {t:conn.execute("SELECT to_regclass(%s) IS NOT NULL",("public."+t,)).fetchone()[0] for t in expected},
            "columns": conn.execute("SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(%s) ORDER BY table_name,ordinal_position",(expected+["recognition_queue_items","speech_queue_items"],)).fetchall(),
            "constraints": conn.execute("SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=ANY(%s) ORDER BY 1,2",(expected+["recognition_queue_items","speech_queue_items"],)).fetchall(),
            "limits": "Metadata only; does not establish full schema or I12 workflow compatibility. No migration or processing authorized."
        }
    print(json.dumps(report,indent=2,default=str))
    if report["pending"] != ["030_p2_i13_scope_admission.sql"] or any(c["version"] not in {"009","025"} for c in report["filename_conflicts"]):
        raise SystemExit("Unexpected migration history; stop for reconciliation.")

if __name__ == "__main__":
    main()
