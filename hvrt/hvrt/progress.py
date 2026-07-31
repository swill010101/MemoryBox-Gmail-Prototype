"""Console progress helpers for long HVRT jobs (no hard dependency on tqdm)."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator, TypeVar

T = TypeVar("T")


def _stderr(msg: str) -> None:
    sys.stderr.write(msg)
    sys.stderr.flush()


def log(msg: str) -> None:
    """Always-visible status line (stderr so it shows even if stdout is quiet)."""
    ts = time.strftime("%H:%M:%S")
    _stderr(f"[{ts}] {msg}\n")


@dataclass
class ProgressBar:
    total: int
    label: str = ""
    width: int = 28
    done: int = 0
    started: float = field(default_factory=time.time)
    _last_draw: float = 0.0

    def update(self, n: int = 1, *, status: str = "") -> None:
        self.done = min(self.total, self.done + n)
        now = time.time()
        # redraw at least every 0.2s or on completion
        if self.done < self.total and (now - self._last_draw) < 0.2:
            return
        self._last_draw = now
        self._draw(status)

    def set(self, done: int, *, status: str = "") -> None:
        self.done = max(0, min(self.total, done))
        self._last_draw = 0.0
        self.update(0, status=status)

    def _draw(self, status: str = "") -> None:
        if self.total <= 0:
            pct = 100.0
            filled = self.width
        else:
            pct = 100.0 * self.done / self.total
            filled = int(self.width * self.done / self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self.started
        rate = self.done / elapsed if elapsed > 0 else 0.0
        eta = (self.total - self.done) / rate if rate > 0 else 0.0
        label = f"{self.label} " if self.label else ""
        extra = f" · {status}" if status else ""
        _stderr(
            f"\r{label}|{bar}| {self.done}/{self.total} ({pct:5.1f}%) "
            f"elapsed {elapsed:5.0f}s eta {eta:5.0f}s{extra}   "
        )
        if self.done >= self.total:
            _stderr("\n")

    def close(self, status: str = "done") -> None:
        self.done = self.total
        self._draw(status)


def track(iterable: Iterable[T], *, total: int | None = None, label: str = "") -> Iterator[T]:
    items = list(iterable) if total is None else iterable
    n = total if total is not None else len(items)  # type: ignore[arg-type]
    bar = ProgressBar(total=max(1, n), label=label)
    i = 0
    for item in items:  # type: ignore[assignment]
        yield item  # type: ignore[misc]
        i += 1
        bar.set(i)
    if n == 0:
        bar.close()


class Heartbeat:
    """Print a heartbeat while a long blocking call runs (best-effort)."""

    def __init__(self, label: str, every_sec: float = 5.0) -> None:
        self.label = label
        self.every_sec = every_sec
        self._stop = False
        self._thread = None

    def __enter__(self) -> "Heartbeat":
        import threading

        self._started = time.time()

        def _run() -> None:
            while not self._stop:
                time.sleep(self.every_sec)
                if self._stop:
                    break
                elapsed = time.time() - self._started
                log(f"{self.label} … still working ({elapsed:.0f}s)")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        log(f"{self.label} … started")
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop = True
        elapsed = time.time() - self._started
        log(f"{self.label} … finished ({elapsed:.0f}s)")
