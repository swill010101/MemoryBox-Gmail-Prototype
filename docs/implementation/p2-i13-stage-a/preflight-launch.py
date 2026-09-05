"""Inspect launch paths without importing MB, opening databases or starting services."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root",required=True)
    args=parser.parse_args()
    runtime=Path(args.runtime_root).resolve(strict=True)
    release=Path(__file__).resolve().parents[3]
    effective=dict(os.environ)
    loaded=[]
    for name in ["memorybox_app.env","video_worker.env","memorybox_sources.env"]:
        p=runtime/"config"/name
        if not p.is_file():continue
        loaded.append(name)
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:continue
            key,value=line.split("=",1);value=value.strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in {chr(34),chr(39)}:value=value[1:-1]
            effective[key.strip()]=value
    # Values below are file paths only. Never print database URLs, tokens, or config contents.
    defaults={
        "MEMORYBOX_IMMICH_ENV":runtime/"config/immich.env",
        "MEMORYBOX_HC_CONFIG":runtime/"config/historian_capture.json",
        "MEMORYBOX_HC_GMAIL_CREDENTIALS":runtime/"config/historian_capture_gmail_credentials.json",
        "MEMORYBOX_HC_GMAIL_TOKEN":runtime/"config/historian_capture_gmail_token.json",
        "MEMORYBOX_HC_MAIL_DIR":runtime/".memorybox_hc_mail",
    }
    paths={}
    for key,default in defaults.items():
        p=Path(effective.get(key) or default)
        if not p.is_absolute():p=runtime/p
        paths[key]={"path":str(p),"exists":p.exists()}
    for key in ["MEMORYBOX_VIDEO_MEDIA_ROOT","MEMORYBOX_VIDEO_DERIVED_DIR"]:
        value=effective.get(key)
        p=Path(value) if value else None
        if p is not None and not p.is_absolute():p=runtime/p
        paths[key]={"path":str(p) if p else None,"exists":p.exists() if p else None,"needs_explicit_review":not bool(value)}
    files=["__init__.py","gmail_client.py","plus_address.py","reply_extract.py"]
    print(json.dumps({"release_root":str(release),"runtime_root":str(runtime),
        "optional_env_files_present":loaded,"paths":paths,
        "capture_modules":{n:(runtime/"application/marvin_capture"/n).is_file() for n in files},
        "inherited_or_file_setting_present":{k:bool(effective.get(k)) for k in ["MEMORYBOX_DATABASE_URL","MEMORYBOX_QDRANT_URL","MEMORYBOX_VIDEO_WORKER_URL","MEMORYBOX_P1_RUNTIME_HOST"]},
        "proposed_locks":{"MEMORYBOX_RECOGNITION_DRAIN":"0","MEMORYBOX_SPEECH_DRAIN":"0","MEMORYBOX_I13_ADMISSION_ID":"unset"},
        "limits":"Read-only path inspection, not import validation or deployment approval. Current shell settings may differ from running startmb child processes."},indent=2))

if __name__=="__main__":main()
