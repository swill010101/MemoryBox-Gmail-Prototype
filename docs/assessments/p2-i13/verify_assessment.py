"""Read-only baseline checks. No application imports, services, models, or databases."""
from pathlib import Path
import ast, json, subprocess, re
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
checks = []
def check(name, ok, detail):
    checks.append(dict(name=name, passed=bool(ok), detail=detail))
def extract(path, name, env=None):
    tree = ast.parse((ROOT/path).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = dict(env or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])), str(path), "exec"), ns)
    return ns[name]
# Execute only a pure range-grouping function, with synthetic non-personal observations.
f = extract("memorybox/recognition/observations.py", "group_assigned_into_ranges", {"RANGE_GAP_SEC":8.0})
rows=[dict(id=str(i),person_id="synthetic-person",review_state="assigned",t_sec=t,match_score=.8) for i,t in enumerate([0,4,8,30])]
r=f(rows)
check("same-person grouping",len(r)==2 and r[0]["end_sec"]==8 and r[1]["end_sec"]==30.5,"Four assigned observations group into two ranges at the baseline eight-second gap.")
# Run the actual baseline player binder against an in-memory media-element double.
js=(ROOT/"memorybox/explore/static/explore.js").read_text(encoding="utf-8")
a=js.index("  function appearanceViewBounds(");b=js.index("  function bindExploreVideoPlayer(",a)
harness=js[a:b]+"""
const events={};const player={currentTime:0,pauses:0,addEventListener(k,f){events[k]=f;},removeEventListener(){},pause(){this.pauses++;}};
bindAppearanceView(player,{start_sec:12,end_sec:14});const start=player.currentTime;
player.currentTime=15;events.timeupdate();
console.log(JSON.stringify({start,atEnd:player.currentTime,pauses:player.pauses}));
"""
v=json.loads(subprocess.run(["node","-e",harness],capture_output=True,text=True,check=True).stdout)
check("I13 playback violation reproduced",v==dict(start=12,atEnd=14,pauses=1),v)
obs=(ROOT/"memorybox/recognition/observations.py").read_text(encoding="utf-8")
node=next(n for n in ast.parse(obs).body if isinstance(n,ast.FunctionDef) and n.name=="delete_native_observations_for_video")
segment=ast.get_source_segment(obs,node)
check("provider deletion omission confirmed","video_provider_key =" not in segment,"Cleanup accepts a provider key but neither DELETE predicates on it; static evidence only.")
providers=[]
for p in (ROOT/"memorybox/providers/video").glob("*.py"):
    if "def i9_voice_vec_for_turn" in p.read_text(encoding="utf-8"): providers.append(p.name)
check("voice hook limited to fake provider",providers==["fake.py"],providers)
up=(ROOT/"memorybox/recognition/process.py").read_text(encoding="utf-8")
u=next(n for n in ast.parse(up).body if isinstance(n,ast.FunctionDef) and n.name=="upsert_appearance_moment")
s=ast.get_source_segment(up,u)
check("legacy moment insert lacks conflict handling","INSERT INTO face_appearance_moments" in s and "ON CONFLICT" not in s,"Not a live duplicate-count reproduction.")
# Execute only enqueue planning with all external reads/writes replaced by in-memory stubs.
planned=[]
people=[{"id":f"synthetic-{i}","display_name":"Synthetic"} for i in range(3)]
videos=[{"video_external_id":f"synthetic-video-{i}","video_provider_key":"synthetic"} for i in range(4)]
def capture_enqueue(**kw):
    planned.extend((kw["person_id"],v["video_external_id"]) for v in kw["videos"])
    return {"total_input":len(kw["videos"])}
fn=extract("memorybox/recognition/archive_pass.py","enqueue_known_people_archive",{
    "_ensure_watermark_table":lambda:None,
    "combined_eligible_videos":lambda **kw:videos,
    "list_people":lambda **kw:people,
    "face_scan_enabled":lambda pid:True,
    "resolve_immich_external_ids_for_person":lambda *a,**kw:[],
    "list_active_exemplars":lambda pid:[{"id":"synthetic-exemplar"}],
    "exemplar_fingerprint":lambda *a:"synthetic-fingerprint",
    "_video_ids_already_queued":lambda pid:set(v["video_external_id"] for v in videos),
    "enqueue_full_eligible_archive":capture_enqueue,
    "_save_watermark":lambda *a,**kw:None,
})
planned_result=fn(video_provider=object(),full=True)
check("full reconciliation Cartesian work expansion",len(planned)==12 and len(set(planned))==12,
      "Actual baseline planner with 3 synthetic People and 4 already-queued videos requests all 12 pairs under full=True. No database, queue, worker or model invoked. Historical 155K operands remain unknown.")

# Inventory committed schema declarations and API routes; no imports or DB execution.
lines=["# Schema and API inventory", "", "Generated from baseline source; declarations are not proof of deployed schema.", ""]
for p in sorted((ROOT/"memorybox/migrations").glob("*.sql")):
    if p.name[:3] not in {"008","011","012","013","018"}: continue
    lines += ["## "+str(p.relative_to(ROOT)).replace(chr(92),"/"), ""]
    for i,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
        if re.search(r"CREATE (?:UNIQUE )?(?:TABLE|INDEX)|ALTER TABLE",line): lines.append(f"- L{i}: `{line.strip()}`")
    lines.append("")
app=(ROOT/"memorybox/app.py").read_text(encoding="utf-8")
lines += ["## Pipeline API routes", ""]
for i,line in enumerate(app.splitlines(),1):
    if line.startswith("@app.") and any(x in line for x in ["/recognition/","/speech/","/review/","/people/sync","/library/media"]): lines.append(f"- L{i}: `{line}`")
(OUT/"schema-api-inventory.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
report={"baseline":"12fe18305f81350f28f8bcc0851c8a1091103f91","kind":"assessment checks, not product acceptance","checks":checks,"all_passed":all(x["passed"] for x in checks),"limits":["No runtime writes or recognition/transcription execution", "Media double is not rendered browser workflow proof", "Defect reproduction passing means baseline violation confirmed"]}
(OUT/"verification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["all_passed"] else 1)
