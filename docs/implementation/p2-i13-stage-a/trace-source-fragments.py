"""Read-only one-source lineage export. No MB imports, media decoding or writes."""
import json
import os
from pathlib import Path
from collections import Counter
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

VID = "vid-c57dbd21f993f6d1"
LIMIT = 200
DERIVED = Path(r"C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived\detections.json")
COLUMNS = ("id", "person_id", "video_provider_key", "video_external_id", "t_sec",
           "start_sec", "end_sec", "face_external_id", "external_face_id", "external_person_id",
           "source_asset_id", "method", "confidence", "match_score", "review_state", "status",
           "evidence_lineage", "confirmation_state", "authority", "exemplar_id", "withdrawn",
           "processing_run_id", "observation_ids", "model_version", "embedding_model", "created_at", "updated_at",
           "reason", "enqueue_reason", "attempts", "i13_admission_id")


def temporal_summary(rows):
    groups = {}
    for row in rows:
        key = str(row.get("person_id") or "unassigned")
        groups.setdefault(key, []).append(row)
    out = {}
    for key, items in groups.items():
        points = sorted(float(r["t_sec"]) for r in items if r.get("t_sec") is not None)
        gaps = [round(b-a, 6) for a,b in zip(points, points[1:])]
        durations = [round(float(r["end_sec"])-float(r["start_sec"]),6) for r in items
                     if r.get("start_sec") is not None and r.get("end_sec") is not None]
        out[key] = {"exported_rows":len(items), "observation_gap_counts":dict(Counter(map(str,gaps))),
                    "duration_counts":dict(Counter(map(str,durations))),
                    "durations_at_most_2_sec":sum(0 <= d <= 2 for d in durations),
                    "distinct_face_ids":len({r.get("face_external_id") for r in items if r.get("face_external_id")})}
    return out


def derived_trace(path):
    if not path.is_file():
        return {"exists":False}
    before = path.stat()
    if before.st_size > 64*1024*1024:
        return {"exists":True,"bytes":before.st_size,"skipped":"file exceeds 64 MiB read limit"}
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
        return {"exists":True,"unstable":True,"skipped":"file changed during read"}
    data = json.loads(raw)
    rows = [r for r in data.get("detections",[]) if isinstance(r,dict) and r.get("video_external_id")==VID]
    exported = [{k:r[k] for k in ("video_external_id","face_external_id","candidate_id","t_sec","end_sec") if k in r}
                for r in rows[:LIMIT]]
    return {"exists":True,"mtime_ns":after.st_mtime_ns,"source_rows":len(rows),
            "truncated":len(rows)>LIMIT,"rows":exported,
            "limits":"Filesystem snapshot is separate from the database transaction; no labels or embeddings exported"}


def main():
    report={"source_id":VID,"row_limit_per_table":LIMIT,"tables":{}}
    with psycopg.connect(os.environ["MEMORYBOX_DATABASE_URL"],connect_timeout=5,
            options="-c default_transaction_read_only=on -c statement_timeout=20000 -c lock_timeout=3000",
            row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        report["snapshot"]=conn.execute("SELECT current_database() AS database, transaction_timestamp() AS captured_at, current_setting('transaction_read_only') AS read_only, current_setting('transaction_isolation') AS isolation").fetchone()
        for table in ("video_face_observations","face_appearance_moments","face_evidence","identity_withdrawals","recognition_queue_items","pending_review_face_crops"):
            available={r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,)).fetchall()}
            if not available:
                report["tables"][table]={"missing":True};continue
            if table=="face_evidence":
                if "source_asset_id" not in available:
                    report["tables"][table]={"skipped":"source scope column missing"};continue
                where=sql.SQL("source_asset_id=%s"); params=[VID]
                if "exemplar_meta_json" in available:
                    where=sql.SQL("(source_asset_id=%s OR exemplar_meta_json->>'video_external_id'=%s)");params=[VID,VID]
            else:
                if "video_external_id" not in available:
                    report["tables"][table]={"skipped":"source scope column missing"};continue
                where=sql.SQL("video_external_id=%s");params=[VID]
                if "video_provider_key" in available:
                    where+=sql.SQL(" AND video_provider_key=%s");params.append("hvrt")
            table_sql=sql.Identifier("public",table)
            count=conn.execute(sql.SQL("SELECT count(*) AS n FROM {} WHERE {}").format(table_sql,where),params).fetchone()["n"]
            selected=[c for c in COLUMNS if c in available]
            expressions=list(map(sql.Identifier, selected))
            if table=="face_evidence" and "exemplar_meta_json" in available:
                expressions.append(sql.SQL("exemplar_meta_json->>'t_sec' AS exemplar_t_sec"))
            ordering=[c for c in ("person_id","t_sec","start_sec","created_at","id") if c in available]
            query=sql.SQL("SELECT {} FROM {} WHERE {} ORDER BY {} LIMIT %s").format(
                sql.SQL(",").join(expressions),table_sql,where,
                sql.SQL(",").join(map(sql.Identifier,ordering)))
            rows=conn.execute(query,params+[LIMIT]).fetchall()
            report["tables"][table]={"source_rows":count,"truncated":count>LIMIT,"rows":rows,"temporal_summary":temporal_summary(rows)}
        # Only runs referenced by observations in this exact source scope.
        if not report["tables"]["video_face_observations"].get("missing"):
            cols={r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='recognition_processing_runs'").fetchall()}
            picked=[c for c in ("id","person_id","run_kind","trigger","status","candidate_count","accepted_count","uncertain_count","range_count","started_at","finished_at") if c in cols]
            if picked and "processing_run_id" in {r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='video_face_observations'").fetchall()}:
                query=sql.SQL("SELECT {} FROM public.recognition_processing_runs WHERE id IN (SELECT processing_run_id FROM public.video_face_observations WHERE video_external_id=%s AND video_provider_key=%s) ORDER BY id LIMIT %s").format(sql.SQL(",").join(map(sql.Identifier,picked)))
                report["linked_runs"]=conn.execute(query,(VID,"hvrt",LIMIT)).fetchall()
                report["linked_runs_limit_note"]="Run counters may cover other sources; the selected run IDs are linked to this source only"
    report["derived"]=derived_trace(DERIVED)
    report["limits"]=["Only source-linked metadata, IDs and times; no vectors, names, transcripts or media", "Exported summaries reflect capped rows; inspect truncated flags", "Does not call Ask or rebuild Gallery; compare results with the 15 owner-observed entries"]
    print(json.dumps(report,default=str,indent=2))


if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(json.dumps({"ok":False,"error_type":type(exc).__name__,"message":"Read-only trace failed; no automatic retry. Check database environment and schema without sharing credentials."}))
        raise SystemExit(2)
