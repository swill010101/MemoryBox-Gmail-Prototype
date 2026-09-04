"""Operator-only release control. None of these commands starts a worker or model."""
from __future__ import annotations
import argparse
import getpass
import json
from pathlib import Path
from uuid import UUID
from .scope import ScopeDenied, digest, preview

def register(plan: dict, review_ref: str) -> dict:
    summary=preview(plan)
    if not review_ref.strip(): raise ScopeDenied("review_reference_required")
    from memorybox.db import connection
    with connection() as c:
        row=c.execute("INSERT INTO i13_processing_admissions(plan_json,plan_sha256,review_ref) VALUES(%s::jsonb,%s,%s) RETURNING id::text",(json.dumps(plan),digest(plan),review_ref)).fetchone()
        c.execute("INSERT INTO i13_admission_events(admission_id,action,actor,reference) VALUES(%s::uuid,'register',%s,%s)",(row["id"],getpass.getuser(),review_ref))
    return {"id":row["id"],"state":"registered","preview":summary,"processing_started":False}

def transition(admission_id: str, action: str, reference: str, acceptance_ref: str | None = None) -> dict:
    UUID(admission_id)
    if not reference.strip(): raise ScopeDenied("decision_reference_required")
    from memorybox.db import connection
    with connection() as c:
        row=c.execute("SELECT * FROM i13_processing_admissions WHERE id=%s::uuid FOR UPDATE",(admission_id,)).fetchone()
        if not row: raise ScopeDenied("admission_not_found")
        plan=row["plan_json"]
        if isinstance(plan,str): plan=json.loads(plan)
        preview(plan)
        if digest(plan)!=row["plan_sha256"]: raise ScopeDenied("scope_plan_changed")
        archive=plan["scope_kind"]=="archive"
        if action=="unlock":
            if not archive or row["state"]!="registered" or not (acceptance_ref or "").strip(): raise ScopeDenied("archive_acceptance_required")
            c.execute("UPDATE i13_processing_admissions SET state='unlocked',acceptance_ref=%s,unlock_ref=%s,updated_at=now() WHERE id=%s::uuid",(acceptance_ref,reference,admission_id))
            state="unlocked"
        elif action=="start":
            expected="unlocked" if archive else "registered"
            if row["state"]!=expected or (archive and not (row["acceptance_ref"] and row["unlock_ref"])): raise ScopeDenied("separate_unlock_required_or_already_started")
            c.execute("UPDATE i13_processing_admissions SET state='started',start_ref=%s,updated_at=now() WHERE id=%s::uuid",(reference,admission_id))
            state="started"
        elif action=="stop":
            c.execute("UPDATE i13_processing_admissions SET state='stopped',updated_at=now() WHERE id=%s::uuid",(admission_id,))
            state="stopped"
        else: raise ScopeDenied("invalid_release_action")
        c.execute("INSERT INTO i13_admission_events(admission_id,action,actor,reference) VALUES(%s::uuid,%s,%s,%s)",(admission_id,action,getpass.getuser(),reference))
    return {"id":admission_id,"state":state,"workers_launched":False,"enqueued":0}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    for action in ("preview","register"):
        cmd=sub.add_parser(action);cmd.add_argument("--plan",required=True)
        if action=="register": cmd.add_argument("--review-ref",required=True)
    for action in ("unlock","start","stop"):
        cmd=sub.add_parser(action);cmd.add_argument("--id",required=True);cmd.add_argument("--reference",required=True)
        if action=="unlock": cmd.add_argument("--acceptance-ref",required=True)
    args=parser.parse_args(argv)
    try:
        if args.action in ("preview","register"):
            plan=json.loads(Path(args.plan).read_text(encoding="utf-8"))
            result=preview(plan) if args.action=="preview" else register(plan,args.review_ref)
        else: result=transition(args.id,args.action,args.reference,getattr(args,"acceptance_ref",None))
        print(json.dumps(result,indent=2));return 0
    except (ScopeDenied,ValueError,OSError) as exc:
        print(json.dumps({"ok":False,"error":str(exc)}));return 2
