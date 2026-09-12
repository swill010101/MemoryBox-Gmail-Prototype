"""Isolated tests for startmb Python selection and -Restart lifecycle. Not FlightSim."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTMB_CMD = ROOT / "startmb.cmd"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _has_serve_deps(exe: Path) -> bool:
    proc = subprocess.run(
        [
            str(exe),
            "-c",
            "import importlib.util; print(importlib.util.find_spec('uvicorn') is not None); print(importlib.util.find_spec('psycopg') is not None)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return proc.returncode == 0 and len(lines) >= 2 and lines[-2:] == ["True", "True"]


def _make_venv(path: Path, *, system_site: bool) -> Path:
    args = [sys.executable, "-m", "venv", str(path)]
    if system_site:
        args.append("--system-site-packages")
    subprocess.run(args, check=True, capture_output=True, text=True)
    exe = path / "Scripts" / "python.exe"
    if not exe.is_file():
        raise RuntimeError("venv_python_missing:" + str(exe))
    return exe


def _clean_path(extra: Path) -> str:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    return os.pathsep.join(
        [
            str(extra),
            str(Path(windir) / "System32" / "WindowsPowerShell" / "v1.0"),
            str(Path(windir) / "System32"),
            windir,
        ]
    )


def _run_startmb(args: list[str], *, path: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = path
    env.pop("PYTHONHOME", None)
    cmd = ["cmd.exe", "/d", "/c", str(STARTMB_CMD), *args, "-RepoRoot", str(repo_root)]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
        timeout=60,
    )


def _json_from_proc(proc: subprocess.CompletedProcess[str]) -> dict:
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise AssertionError("no_json_output:" + text[:800])


class StartmbPythonAndRestart(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.name != "nt":
            raise unittest.SkipTest("startmb is Windows")
        if not STARTMB_CMD.is_file():
            raise unittest.SkipTest("startmb.cmd missing")
        if not _has_serve_deps(Path(sys.executable)):
            raise unittest.SkipTest("host python lacks uvicorn+psycopg")
        cls.tmp = tempfile.TemporaryDirectory(prefix="startmb-py-")
        base = Path(cls.tmp.name)
        cls.good_root = base / "good-root"
        cls.good_py = _make_venv(cls.good_root / ".venv", system_site=True)
        if not _has_serve_deps(cls.good_py):
            raise unittest.SkipTest("system-site venv lacks uvicorn+psycopg")
        cls.bare_py = _make_venv(base / "bare-venv", system_site=False)
        if _has_serve_deps(cls.bare_py):
            raise AssertionError("bare venv unexpectedly has uvicorn/psycopg")
        cls.broken_root = base / "broken-root"
        cls.broken_venv_py = _make_venv(cls.broken_root / ".venv", system_site=False)
        if _has_serve_deps(cls.broken_venv_py):
            raise AssertionError("broken venv unexpectedly has uvicorn/psycopg")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_prefers_venv_when_path_python_lacks_uvicorn(self) -> None:
        path = _clean_path(self.bare_py.parent)
        proc = _run_startmb(["-ProbePython"], path=path, repo_root=self.good_root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = _json_from_proc(proc)
        self.assertTrue(payload["ok"])
        selected = Path(payload["python"]).resolve()
        self.assertEqual(selected, self.good_py.resolve())
        self.assertNotEqual(selected, self.bare_py.resolve())

    def test_fails_closed_when_venv_missing_required_packages(self) -> None:
        path = _clean_path(self.bare_py.parent)
        proc = _run_startmb(["-ProbePython"], path=path, repo_root=self.broken_root)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        blob = ((proc.stdout or "") + (proc.stderr or "")).lower()
        self.assertIn("missing uvicorn+psycopg", blob)
        self.assertIn("refusing path python", blob)

    def test_startmb_cmd_restart_stops_isolated_listener(self) -> None:
        serve_port = _free_port()
        worker_port = _free_port()
        self.assertNotIn(serve_port, (8790, 8791))
        self.assertNotIn(worker_port, (8790, 8791))
        listener = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(serve_port), "--bind", "127.0.0.1"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 8
            ready = False
            while time.time() < deadline:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.3)
                    if sock.connect_ex(("127.0.0.1", serve_port)) == 0:
                        ready = True
                        break
                time.sleep(0.1)
            self.assertTrue(ready, "dummy listener did not bind")
            path = _clean_path(self.bare_py.parent)
            proc = _run_startmb(
                [
                    "-Restart",
                    "-IsolatedRestart",
                    "-ServePort",
                    str(serve_port),
                    "-WorkerPort",
                    str(worker_port),
                    "-SkipChrome",
                ],
                path=path,
                repo_root=self.good_root,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = _json_from_proc(proc)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["skipped_docker"])
            self.assertTrue(payload["skipped_start"])
            self.assertFalse(payload["serve_listening"])
            self.assertEqual(Path(payload["python"]).resolve(), self.good_py.resolve())
            deadline = time.time() + 8
            closed = False
            while time.time() < deadline:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.3)
                    if sock.connect_ex(("127.0.0.1", serve_port)) != 0:
                        closed = True
                        break
                time.sleep(0.1)
            self.assertTrue(closed, "dummy listener still bound after IsolatedRestart")
            self.assertIsNotNone(listener.poll())
        finally:
            if listener.poll() is None:
                listener.terminate()
                try:
                    listener.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    listener.kill()


if __name__ == "__main__":
    unittest.main()
