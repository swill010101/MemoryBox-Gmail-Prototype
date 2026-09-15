"""FlightSim custom-format dump before 039 / replacement load. Never migrates."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CONFIRM = "pre-039-replacement-generation-v1"


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def main() -> int:
    if not _env_on("MEMORYBOX_I14_BACKUP_ALLOW_FLIGHTSIM"):
        print(json.dumps({"ok": False, "error": "backup_flightsim_not_allowed"}))
        return 2
    if os.environ.get("MEMORYBOX_I14_BACKUP_CONFIRM", "").strip() != CONFIRM:
        print(json.dumps({"ok": False, "error": "backup_confirm_mismatch"}))
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    root = Path("E:/MemoryBox-backups") if Path("E:/MemoryBox-backups").exists() else Path("C:/MemoryBox-backups")
    folder = root / f"pre-i14-039-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    dump = folder / "memorybox.dump"
    docker = subprocess.run(
        [
            "docker",
            "exec",
            "memorybox-pg",
            "pg_dump",
            "-U",
            "memorybox",
            "-d",
            "memorybox",
            "-Fc",
            "-f",
            "/tmp/memorybox.dump",
        ],
        capture_output=True,
        text=True,
    )
    if docker.returncode != 0:
        print(json.dumps({"ok": False, "error": "pg_dump_failed", "stderr": (docker.stderr or "")[-400]}))
        return 2
    copy = subprocess.run(
        ["docker", "cp", "memorybox-pg:/tmp/memorybox.dump", str(dump)],
        capture_output=True,
        text=True,
    )
    if copy.returncode != 0 or not dump.exists():
        print(json.dumps({"ok": False, "error": "docker_cp_failed"}))
        return 2
    listing = subprocess.run(
        [
            "docker",
            "exec",
            "memorybox-pg",
            "pg_restore",
            "-l",
            "/tmp/memorybox.dump",
        ],
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        print(json.dumps({"ok": False, "error": "pg_restore_list_failed"}))
        return 2
    lines = [ln for ln in listing.stdout.splitlines() if ln.strip() and not ln.startswith(";")]
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    identity = {
        "ok": True,
        "bytes": dump.stat().st_size,
        "pg_restore_list_lines": len(lines),
        "sha256": digest,
        "stamp": stamp,
        "kind": "pre-039-replacement-generation",
    }
    (folder / "identity.json").write_text(json.dumps(identity, indent=2), encoding="utf-8")
    (folder / "pg_restore_l.txt").write_text(listing.stdout, encoding="utf-8")
    public = {k: v for k, v in identity.items() if k != "sha256"}
    public["sha256_prefix"] = digest[:12]
    print(json.dumps(public))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
