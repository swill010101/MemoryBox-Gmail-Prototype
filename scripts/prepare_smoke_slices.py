"""Prepare small real-data smoke slices under working/ (gitignored).

Does not modify archive originals. Does not print message/event content.
Outputs only paths, counts, and hashes to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


def slice_mbox(src: Path, dest: Path, *, limit: int) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    buf = bytearray()
    written = 0
    count = 0
    with src.open("rb") as fin, dest.open("wb") as fout:
        for line in fin:
            if line.startswith(b"From ") and buf:
                fout.write(buf)
                count += 1
                written += len(buf)
                buf = bytearray()
                if count >= limit:
                    break
            buf.extend(line)
        if count < limit and buf:
            fout.write(buf)
            count += 1
            written += len(buf)
    h = hashlib.sha256(dest.read_bytes()).hexdigest()
    return {
        "ok": True,
        "kind": "mbox_slice",
        "dest": str(dest),
        "messages": count,
        "bytes": written,
        "content_sha256": h,
        "source_bytes": src.stat().st_size,
    }


def extract_ics_from_takeout_zip(zip_path: Path, dest_dir: Path) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".ics"):
                continue
            if "Calendar" not in name.replace("\\", "/"):
                # still allow any ics in takeout
                pass
            target = dest_dir / Path(name).name
            with zf.open(name) as src, target.open("wb") as out:
                data = src.read()
                out.write(data)
            extracted.append(
                {
                    "file": target.name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    return {
        "ok": bool(extracted),
        "kind": "ics_extract",
        "dest_dir": str(dest_dir),
        "files": extracted,
        "count": len(extracted),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Prepare gitignored real-data smoke slices")
    p.add_argument(
        "--mbox",
        type=Path,
        help="Path to real mbox (archive; left untouched)",
    )
    p.add_argument("--mbox-limit", type=int, default=5)
    p.add_argument(
        "--mbox-out",
        type=Path,
        default=Path("working/smoke/email_slice.mbox"),
    )
    p.add_argument(
        "--takeout-zip",
        type=Path,
        help="Takeout zip containing Calendar/*.ics",
    )
    p.add_argument(
        "--ics-out-dir",
        type=Path,
        default=Path("working/smoke/calendar"),
    )
    args = p.parse_args()
    import json

    results = []
    if args.mbox:
        if not args.mbox.is_file():
            print(json.dumps({"ok": False, "error": f"mbox missing: {args.mbox}"}))
            return 1
        results.append(slice_mbox(args.mbox, args.mbox_out, limit=args.mbox_limit))
    if args.takeout_zip:
        if not args.takeout_zip.is_file():
            print(json.dumps({"ok": False, "error": f"zip missing: {args.takeout_zip}"}))
            return 1
        results.append(extract_ics_from_takeout_zip(args.takeout_zip, args.ics_out_dir))
    if not results:
        print(json.dumps({"ok": False, "error": "provide --mbox and/or --takeout-zip"}))
        return 2
    print(json.dumps({"ok": all(r.get("ok") for r in results), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
