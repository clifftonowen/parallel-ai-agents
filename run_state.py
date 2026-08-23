"""
run_state.py

The per-run state object and the stdout-to-progress mapping.

Deliberately free of FastAPI imports so it can be exercised without standing up
a server -- `_infer_phase` in particular is pure string matching and is the
easiest useful thing in the backend to test.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

__all__ = ["RunState", "PHASE_PATTERNS", "infer_phase"]


@dataclass
class RunState:
    run_id: str
    topic: str
    mode: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "running"       # running | complete | error | cancelled
    phase: str = "starting"
    progress_pct: int = 0
    log_lines: list[str] = field(default_factory=list)
    benchmark: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    run_dir: str = ""
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # Handle to the generation subprocess, so a cancel request can terminate it.
    _proc: subprocess.Popen | None = None
    _cancelled: bool = False
    # Owner (if the run was started by a signed-in user), for persisted history.
    user_id: int | None = None
    # False runs the fast path: no video stage, ~2 minutes instead of ~10.
    include_video: bool = True
    # Set when this run's materials were reused from a similar earlier prompt.
    from_cache: bool = False
    cached_topic: str | None = None
    # SSE subscribers: list of asyncio.Queue (one per connected client)
    _queues: list[asyncio.Queue] = field(default_factory=list)
    _loop: asyncio.AbstractEventLoop | None = None

    def append_log(self, line: str) -> None:
        with self._lock:
            self.log_lines.append(line)
        self._push_sse({"log": line, "phase": self.phase, "progress_pct": self.progress_pct})

    def set_phase(self, phase: str, pct: int) -> None:
        with self._lock:
            self.phase = phase
            self.progress_pct = pct
        self._push_sse({"log": None, "phase": phase, "progress_pct": pct})

    def cancel(self) -> bool:
        """Stop the generation subprocess and everything it spawned.

        Returns True if a running process was signalled. Safe to call twice.

        The pipeline spawns Chromium, pandoc and ffmpeg as grandchildren. Killing
        only the immediate Python child leaves those orphaned and still burning
        CPU -- which on a small container is an out-of-memory kill, not just a
        leak. So both branches target the whole process group: a job-tree kill on
        Windows, and killpg on POSIX (which needs the start_new_session=True that
        run_manager passes to Popen).
        """
        with self._lock:
            proc = self._proc
            if self.status != "running":
                return False
            self._cancelled = True
        if proc is None or proc.poll() is not None:
            return False
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            else:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return True

    def _push_sse(self, event: dict) -> None:
        if self._loop is None:
            return
        payload = json.dumps(event)
        for q in list(self._queues):
            self._loop.call_soon_threadsafe(q.put_nowait, payload)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "run_id": self.run_id,
                "topic": self.topic,
                "mode": self.mode,
                "started_at": self.started_at,
                "status": self.status,
                "phase": self.phase,
                "progress_pct": self.progress_pct,
                "log_lines": list(self.log_lines),
                "benchmark": self.benchmark,
                "outputs": self.outputs,
                "run_dir": self.run_dir,
                "error": self.error,
                "from_cache": self.from_cache,
                "cached_topic": self.cached_topic,
            }


# ---------------------------------------------------------------------------
# Phase detection from stdout lines
# ---------------------------------------------------------------------------

# Progress is inferred by regex-matching the subprocess's print statements, so
# these patterns are coupled to log wording in the agents. Order matters: the
# first match wins.
PHASE_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (re.compile(r"ADK Pipeline|Original Pipeline|Starting|study_generator", re.I), "starting", 2),
    (re.compile(r"\[Notes\]|notes_agent|Phase 1|phase1|NotesAgent|Generating notes", re.I), "phase1", 10),
    (re.compile(r"NotesPost|timing|notes\.md saved|Notes saved", re.I), "phase1", 30),
    (re.compile(r"\[Flashcard\]|flashcard_agent|FlashcardAgent|Generating flashcard", re.I), "phase2", 40),
    (re.compile(r"\[Video\]|VideoAgent|video_agent|Stage A|Stage B", re.I), "phase2", 50),
    (re.compile(r"study_video|video.*saved|mp4", re.I), "phase2", 65),
    (re.compile(r"\[PDF\]|PDFAgent|notes_pdf|flashcards_pdf|pandoc", re.I), "phase3", 75),
    (re.compile(r"PDF.*saved|pdf_path", re.I), "phase3", 85),
    (re.compile(r"BENCHMARK RESULTS|profiling_results|Comparison", re.I), "profiling", 90),
    (re.compile(r"ADK Pipeline.*complete|Original Pipeline.*complete|Pipeline.*done", re.I), "done", 95),
]


def infer_phase(state: RunState, line: str) -> None:
    """Advance the run's phase/progress if this log line indicates a later stage.

    Monotonic on purpose: a late-arriving line from an earlier stage must not
    walk the progress bar backwards.
    """
    for pattern, phase, pct in PHASE_PATTERNS:
        if pattern.search(line):
            if pct > state.progress_pct:
                state.set_phase(phase, pct)
            break
