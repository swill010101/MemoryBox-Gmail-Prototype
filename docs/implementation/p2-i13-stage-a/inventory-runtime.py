"""Run on FlightSim with its existing MEMORYBOX_DATABASE_URL; stdout aggregates only."""
import json
import os
import psycopg
from psycopg import sql

def main():
    dsn=os.environ.get("MEMORYBOX_DATABASE_URL")
    if not dsn: raise SystemExit("Set MEMORYBOX_DATABASE_URL using the existing deployment environment; do not paste credentials into artifacts.")
    report={"kind":"consistent_read_only_native_inventory"}
    with psycopg.connect(dsn,connect_timeout=5,options="-c default_transaction_read_only=on -c statement_timeout=20000") as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        report["read_only"]=conn.execute("SHOW transaction_read_only").fetchone()[0]
        report["isolation"]=conn.execute("SHOW transaction_isolation").fetchone()[0]
        report["snapshot_time"]=str(conn.execute("SELECT transaction_timestamp()").fetchone()[0])
        tables=[r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE '%recognition%' OR tablename LIKE '%face%' OR tablename LIKE 'speech_%') ORDER BY 1")]
        report["table_counts"]={t:conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(t))).fetchone()[0] for t in tables}
        report["queue_groups"]=[dict(zip(["provider","reason","status","rows","people","sources"],r)) for r in conn.execute("SELECT video_provider_key,enqueue_reason,status,count(*),count(distinct person_id),count(distinct video_external_id) FROM recognition_queue_items GROUP BY 1,2,3 ORDER BY 1,2,3")]
        report["indexes"]=[dict(zip(["table","name","definition"],r)) for r in conn.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=ANY(%s) ORDER BY 1,2",(tables,))]
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
