"""Default: inspect only. --start requires prior operator deployment approval and schemas 030/031."""
import argparse
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys


def configuration(runtime, inherited, media, derived):
    env=dict(inherited)
    for name in ("memorybox_app.env","video_worker.env","memorybox_sources.env"):
        path=runtime/"config"/name
        if not path.is_file():continue
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:continue
            key,value=line.split("=",1);value=value.strip()
            if len(value)>1 and value[0]==value[-1] and value[0] in {chr(34),chr(39)}:value=value[1:-1]
            env[key.strip()]=value
    defaults={"MEMORYBOX_IMMICH_ENV":runtime/"config/immich.env",
        "MEMORYBOX_HC_CONFIG":runtime/"config/historian_capture.json",
        "MEMORYBOX_HC_GMAIL_CREDENTIALS":runtime/"config/historian_capture_gmail_credentials.json",
        "MEMORYBOX_HC_GMAIL_TOKEN":runtime/"config/historian_capture_gmail_token.json",
        "MEMORYBOX_HC_MAIL_DIR":runtime/".memorybox_hc_mail",
        "MEMORYBOX_VIDEO_MEDIA_ROOT":media,"MEMORYBOX_VIDEO_DERIVED_DIR":derived}
    for key,default in defaults.items():
        path=Path(env.get(key) or default)
        if not path.is_absolute():path=runtime/path
        env[key]=str(path.resolve())
    for key,value in {"MEMORYBOX_VIDEO_WORKER_URL":"http://127.0.0.1:8791",
        "MEMORYBOX_VIDEO_WORKER_HOST":"127.0.0.1","MEMORYBOX_VIDEO_WORKER_PORT":"8791",
        "MEMORYBOX_HOST":"127.0.0.1","MEMORYBOX_PORT":"8790",
        "MEMORYBOX_PHOTO_PROVIDER":"immich","MEMORYBOX_VIDEO_PROVIDER":"hvrt",
        "MEMORYBOX_P1_RUNTIME_HOST":"1"}.items():
        if not env.get(key):env[key]=value
    # Apply locks LAST, including after optional local env files.
    env.update(MEMORYBOX_RECOGNITION_DRAIN="0",MEMORYBOX_SPEECH_DRAIN="0",PYTHONDONTWRITEBYTECODE="1")
    env.pop("MEMORYBOX_I13_ADMISSION_ID",None)
    return env,defaults


def check_schema(dsn):
    import psycopg
    with psycopg.connect(dsn,connect_timeout=5,options="-c default_transaction_read_only=on -c statement_timeout=20000") as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        row=c.execute("SELECT filename FROM public.schema_migrations WHERE version='030'").fetchone()
        if not row or row[0]!="030_p2_i13_scope_admission.sql":raise RuntimeError("Reviewed migration 030 is not recorded; no service started.")
        row=c.execute("SELECT filename FROM public.schema_migrations WHERE version='031'").fetchone()
        if not row or row[0]!="031_p2_i13_transcript_annotations.sql":raise RuntimeError("Reviewed migration 031 is not recorded; no service started.")
        for name in ("i13_transcript_versions","i13_transcript_annotations","i13_current_transcripts","i13_effective_words","i13_effective_moments"):
            if not c.execute("SELECT to_regclass(%s) IS NOT NULL",("public."+name,)).fetchone()[0]:
                raise RuntimeError("Required annotation schema missing; no service started.")
        for name in ("i13_processing_admissions","i13_admission_events","i13_work_attempts","i13_queue_units"):
            if not c.execute("SELECT to_regclass(%s) IS NOT NULL",("public."+name,)).fetchone()[0]:
                raise RuntimeError("Required I13 table missing; no service started.")
        for table in ("recognition_queue_items","speech_queue_items"):
            if not c.execute("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name='i13_admission_id' AND data_type='uuid')",(table,)).fetchone()[0]:
                raise RuntimeError("Required queue admission stamp missing; no service started.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root",required=True)
    parser.add_argument("--expected-sha",required=True)
    parser.add_argument("--media-root",required=True)
    parser.add_argument("--derived-dir",required=True)
    parser.add_argument("--role",choices=["app","worker"],default="app")
    parser.add_argument("--start",action="store_true")
    parser.add_argument("--deployment-reference")
    args=parser.parse_args()
    release=Path(__file__).resolve().parents[3]
    runtime=Path(args.runtime_root).resolve(strict=True)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=release,text=True).strip()
    if head!=args.expected_sha:raise RuntimeError("Release SHA mismatch.")
    if subprocess.check_output(["git","status","--porcelain"],cwd=release,text=True).strip():
        raise RuntimeError("Release checkout is not clean; preserve work and review.")
    env,path_keys=configuration(runtime,os.environ,args.media_root,args.derived_dir)
    missing=[key for key in path_keys if not Path(env[key]).exists()]
    missing += [key for key in ("MEMORYBOX_DATABASE_URL","MEMORYBOX_QDRANT_URL") if not env.get(key)]
    # Locate without importing MB or the external Capture package.
    mb=importlib.machinery.PathFinder.find_spec("memorybox",[str(release)])
    application=importlib.machinery.PathFinder.find_spec("application",[str(release),str(runtime)])
    capture=importlib.machinery.PathFinder.find_spec("application.marvin_capture",list(application.submodule_search_locations or [])) if application else None
    if not mb or Path(mb.origin).resolve()!=release/"memorybox/__init__.py":raise RuntimeError("Unexpected MB code origin.")
    if not capture or Path(capture.origin).resolve()!=runtime/"application/marvin_capture/__init__.py":
        raise RuntimeError("Unexpected Capture dependency origin.")
    capture_files={}
    for name in ("__init__.py","gmail_client.py","config.py","plus_address.py","reply_extract.py"):
        path=runtime/"application/marvin_capture"/name
        if not path.is_file():missing.append("Capture:"+name)
        else:capture_files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    report={"release_sha":head,"memorybox_origin":mb.origin,"capture_origin":capture.origin,
        "runtime_working_directory":str(runtime),"paths":{key:env[key] for key in path_keys},
        "capture_code_sha256":capture_files,"missing":missing,
        "drains":"both off","admission":"unset","mode":"start requested" if args.start else "check only",
        "limits":"Checks paths and import origins without importing MB. Check-only opens no database and starts no service."}
    print(json.dumps(report,indent=2),flush=True)
    if missing:raise RuntimeError("Required launch configuration missing; no service started.")
    if not args.start:return 0
    if not (args.deployment_reference or "").strip():raise RuntimeError("Explicit deployment reference required for --start.")
    check_schema(env["MEMORYBOX_DATABASE_URL"])
    os.environ.clear();os.environ.update(env)
    os.chdir(runtime)
    sys.path[:0]=[str(release),str(runtime)]
    if args.role=="worker":
        from memorybox.video_worker import main as worker
        worker()
    else:
        import uvicorn
        # Deliberately bypass memorybox serve's migrate/trace-cleanup/owner-bootstrap.
        # Normal app startup hooks still run after explicit deployment approval.
        uvicorn.run("memorybox.app:app",host=env["MEMORYBOX_HOST"],port=int(env["MEMORYBOX_PORT"]),reload=False)
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        # Database/config exception messages can contain credentials; do not echo them.
        print(json.dumps({"ok":False,"error_type":type(exc).__name__,"message":"Launch check/start failed; inspect noncredential report above. No automatic retry."}))
        raise SystemExit(2)
