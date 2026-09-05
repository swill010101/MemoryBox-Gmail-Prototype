"""Read/hash an explicit 22-source selection on FlightSim. No media decoding or models.

Input JSON: {"manifest_id":..., "version":..., "sources":[{"path":...,
"provider_key":..., "video_external_id":..., "duration_sec":...,
"owner_truth_ref":null, "owner_confirmed":false, "coverage_tags":[...], "truth":[...]}]}.
Owner truth may be empty for evidence generation; when supplied it is never inferred by this script. No directory scan or substitutions.
Output remains local until founder reviews permission to commit identity/truth references.
"""
import argparse
import hashlib
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection",required=True)
    args=parser.parse_args()
    selection=json.loads(Path(args.selection).read_text(encoding="utf-8-sig"))
    rows=selection["sources"]
    if len(rows)!=22:raise SystemExit("Exactly 22 explicit selected sources required")
    seen=set();out=[]
    for row in rows:
        path=Path(row["path"]).resolve(strict=True)
        if path in seen:raise SystemExit("Duplicate source path")
        seen.add(path)
        before=path.stat()
        with path.open("rb") as fh:sha=hashlib.file_digest(fh,"sha256").hexdigest()
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise SystemExit("Source changed while hashing; retry when quiescent")
        entry={k:v for k,v in row.items() if k!="path"}
        entry["source_sha256"]=sha
        out.append(entry)
    print(json.dumps({"id":selection["manifest_id"],"version":selection["version"],"sources":out},indent=2))

if __name__=="__main__":main()
