"""
api_server.py
-------------
FastAPI backend for the profiling dashboard.

Endpoints:
  POST /run                    — start a pipeline run (spawns subprocess)
  GET  /run/{run_id}           — poll run state (status, progress, benchmark)
  GET  /run/{run_id}/stream    — SSE live log stream
  GET  /run/{run_id}/download  — ZIP of all output files
  GET  /runs                   — list all past runs
  GET  /file/{run_id}/{filename} — serve individual output file

Run with:
  uvicorn api_server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import glob
import io
import json
import os
import re
import subprocess
import sys
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Prefer the project venv python; fall back to sys.executable
_VENV_PYTHON = os.path.join(PROJECT_ROOT, "..", ".venv", "Scripts", "python.exe")
PYTHON = os.path.abspath(_VENV_PYTHON) if os.path.isfile(os.path.abspath(_VENV_PYTHON)) else sys.executable

app = FastAPI(title="parallel-ai-agents dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory run registry
# ---------------------------------------------------------------------------

_runs: dict[str, "RunState"] = {}
_runs_lock = threading.Lock()


@dataclass
class RunState:
    run_id: str
    topic: str
    mode: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "running"       # running | complete | error
    phase: str = "starting"
    progress_pct: int = 0
    log_lines: list[str] = field(default_factory=list)
    benchmark: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    run_dir: str = ""
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
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
            }


# ---------------------------------------------------------------------------
# Phase detection from stdout lines
# ---------------------------------------------------------------------------

# Maps regex patterns in stdout to (phase_name, progress_pct)
_PHASE_PATTERNS: list[tuple[re.Pattern, str, int]] = [
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


def _infer_phase(state: RunState, line: str) -> None:
    for pattern, phase, pct in _PHASE_PATTERNS:
        if pattern.search(line):
            if pct > state.progress_pct:
                state.set_phase(phase, pct)
            break


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _build_cmd(topic: str, mode: str) -> list[str]:
    cmd = [PYTHON, "benchmark_profile.py", "--topic", topic, "--no-cprofile"]
    if mode == "adk":
        cmd.append("--adk-only")
    elif mode == "original":
        cmd.append("--original-only")
    elif mode == "async":
        cmd.append("--async-only")
    # "both" and "all" run all paths — no extra flag needed
    return cmd


def _find_benchmark_json() -> str | None:
    pattern = os.path.join(PROJECT_ROOT, "profiling_results_*.json")
    matches = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return matches[0] if matches else None


def _collect_outputs(run_dir: str) -> dict[str, str]:
    mapping = {
        "notes_md": "notes.md",
        "flashcards_md": "flashcards.md",
        "notes_pdf": "notes.pdf",
        "flashcards_pdf": "flashcards.pdf",
        "video": "study_video.mp4",
    }
    result: dict[str, str] = {}
    if not run_dir or not os.path.isdir(run_dir):
        return result
    for key, filename in mapping.items():
        path = os.path.join(run_dir, filename)
        if os.path.isfile(path):
            result[key] = path
    return result


def _run_worker(state: RunState) -> None:
    cmd = _build_cmd(state.topic, state.mode)
    state.append_log(f"[api] Launching: {' '.join(cmd)}")
    state.set_phase("starting", 2)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT,
        )

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            state.append_log(line)
            _infer_phase(state, line)

        proc.wait()
        return_code = proc.returncode

        if return_code != 0:
            with state._lock:
                state.status = "error"
                state.error = f"Process exited with code {return_code}"
            state.set_phase("error", state.progress_pct)
            state._push_sse({"log": state.error, "phase": "error", "progress_pct": state.progress_pct})
            return

        # Read benchmark JSON produced by benchmark_profile.py
        bench_path = _find_benchmark_json()
        if bench_path:
            try:
                with open(bench_path, encoding="utf-8") as f:
                    bench = json.load(f)
                with state._lock:
                    state.benchmark = bench
                state.append_log(f"[api] Benchmark JSON loaded: {bench_path}")
            except Exception as exc:
                state.append_log(f"[api] Warning: could not load benchmark JSON: {exc}")

        # Locate most-recently-modified subdir in output/ as the run directory
        run_dir = ""
        output_root = os.path.join(PROJECT_ROOT, "output")
        if os.path.isdir(output_root):
            subdirs = [
                os.path.join(output_root, d)
                for d in os.listdir(output_root)
                if os.path.isdir(os.path.join(output_root, d))
            ]
            if subdirs:
                run_dir = max(subdirs, key=os.path.getmtime)

        with state._lock:
            state.run_dir = run_dir
            state.outputs = _collect_outputs(run_dir)
            state.status = "complete"
            state.progress_pct = 100
            state.phase = "done"

        state._push_sse({"log": "[api] Run complete.", "phase": "done", "progress_pct": 100})

    except Exception as exc:
        with state._lock:
            state.status = "error"
            state.error = str(exc)
        state._push_sse({"log": f"[api] ERROR: {exc}", "phase": "error", "progress_pct": state.progress_pct})

    finally:
        # Signal all SSE subscribers that the stream is done
        sentinel = json.dumps({"done": True})
        for q in list(state._queues):
            try:
                if state._loop:
                    state._loop.call_soon_threadsafe(q.put_nowait, sentinel)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartRunRequest(BaseModel):
    topic: str
    mode: str = "both"   # both | original | adk


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/run")
async def start_run(req: StartRunRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    if req.mode not in ("both", "original", "adk", "async", "all"):
        raise HTTPException(status_code=400, detail="mode must be 'both', 'original', 'adk', 'async', or 'all'")

    run_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    state = RunState(run_id=run_id, topic=req.topic.strip(), mode=req.mode, _loop=loop)

    with _runs_lock:
        _runs[run_id] = state

    thread = threading.Thread(target=_run_worker, args=(state,), daemon=True)
    thread.start()

    return {"run_id": run_id, "status": "running"}


@app.get("/run/{run_id}")
async def get_run(run_id: str):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return state.to_dict()


@app.get("/run/{run_id}/stream")
async def stream_run(run_id: str):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")

    q: asyncio.Queue = asyncio.Queue()
    with state._lock:
        # Replay existing log lines to new subscriber (use current phase/pct as best-effort snapshot)
        current_phase = state.phase
        current_pct = state.progress_pct
        for line in state.log_lines:
            q.put_nowait(json.dumps({"log": line, "phase": current_phase, "progress_pct": current_pct}))
        # If already done, send sentinel immediately
        if state.status in ("complete", "error"):
            q.put_nowait(json.dumps({"done": True}))
        else:
            state._queues.append(q)

    async def event_generator():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
                    continue
                event_data = json.loads(payload)
                yield f"data: {json.dumps(event_data)}\n\n"
                if event_data.get("done"):
                    break
        finally:
            with state._lock:
                if q in state._queues:
                    state._queues.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/run/{run_id}/download")
async def download_run(run_id: str):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    if state.status != "complete":
        raise HTTPException(status_code=409, detail="run is not complete yet")

    outputs = state.outputs
    if not outputs:
        raise HTTPException(status_code=404, detail="no output files found for this run")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, path in outputs.items():
            if os.path.isfile(path):
                zf.write(path, arcname=os.path.basename(path))

        # Include benchmark JSON if available
        bench_path = _find_benchmark_json()
        if bench_path and os.path.isfile(bench_path):
            zf.write(bench_path, arcname=os.path.basename(bench_path))

    buf.seek(0)
    topic_slug = re.sub(r"[^a-z0-9]+", "_", state.topic.lower()).strip("_")[:30]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{topic_slug}_{ts}.zip"

    return StreamingResponse(
        io.BytesIO(buf.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/runs")
async def list_runs():
    with _runs_lock:
        snapshot = list(_runs.values())
    return [
        {
            "run_id": s.run_id,
            "topic": s.topic,
            "mode": s.mode,
            "status": s.status,
            "started_at": s.started_at,
            "progress_pct": s.progress_pct,
            "phase": s.phase,
        }
        for s in reversed(snapshot)
    ]


@app.get("/file/{run_id}/{filename}")
async def serve_file(run_id: str, filename: str):
    # Sanitize filename — no path traversal
    filename = os.path.basename(filename)
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")

    # Check outputs dict first
    for path in state.outputs.values():
        if os.path.basename(path) == filename and os.path.isfile(path):
            return FileResponse(path)

    # Fallback: search run_dir
    if state.run_dir:
        candidate = os.path.join(state.run_dir, filename)
        if os.path.isfile(candidate):
            return FileResponse(candidate)

    raise HTTPException(status_code=404, detail=f"file '{filename}' not found for this run")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "runs": len(_runs)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
