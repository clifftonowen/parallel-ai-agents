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
from contextlib import asynccontextmanager
import threading
import uuid
import zipfile
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import auth_db
import routes_auth
from run_state import RunState, infer_phase
from security import current_user, user_from_header_or_query
import prompt_cache

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

from paths import OUTPUT_ROOT, PROJECT_ROOT, PYTHON  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create the schema on startup rather than at import.

    Doing this at import meant any importer -- including a test collector --
    created a database file as a side effect.
    """
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    auth_db.init_db()
    yield


app = FastAPI(title="parallel-ai-agents dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(routes_auth.router)

# ---------------------------------------------------------------------------
# In-memory run registry
# ---------------------------------------------------------------------------

_runs: dict[str, RunState] = {}
_runs_lock = threading.Lock()


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


def _persist_run_result(state: RunState) -> None:
    """If the run belongs to a signed-in user, save its final state to the DB so it
    appears in their history and survives a server restart. No-op for anonymous runs."""
    if state.user_id is None:
        return
    try:
        auth_db.set_run_result(state.run_id, state.status, state.run_dir, state.outputs)
    except Exception as exc:  # never let a DB hiccup break the run
        state.append_log(f"[api] Warning: could not save run to history: {exc}")


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
        with state._lock:
            state._proc = proc

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            state.append_log(line)
            infer_phase(state, line)

        proc.wait()
        return_code = proc.returncode

        # A cancel request killed the process — report it as cancelled, not an error.
        if state._cancelled:
            with state._lock:
                state.status = "cancelled"
                state.phase = "error"
            _persist_run_result(state)
            state._push_sse({"log": "[api] Run cancelled.", "phase": "error", "progress_pct": state.progress_pct})
            return

        if return_code != 0:
            with state._lock:
                state.status = "error"
                state.error = f"Process exited with code {return_code}"
            state.set_phase("error", state.progress_pct)
            _persist_run_result(state)
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

        _persist_run_result(state)
        # Record this fresh generation so a future similar prompt can reuse it.
        try:
            prompt_cache.remember(state.topic, state.run_dir, state.outputs)
        except Exception as exc:
            state.append_log(f"[api] Warning: could not cache this run: {exc}")
        state._push_sse({"log": "[api] Run complete.", "phase": "done", "progress_pct": 100})

    except Exception as exc:
        with state._lock:
            state.status = "error"
            state.error = str(exc)
        _persist_run_result(state)
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
async def start_run(req: StartRunRequest, authorization: str | None = Header(default=None)):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    if req.mode not in ("both", "original", "adk", "async", "all"):
        raise HTTPException(status_code=400, detail="mode must be 'both', 'original', 'adk', 'async', or 'all'")

    user = current_user(authorization)
    topic = req.topic.strip()
    run_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()

    # ── Semantic cache (learner path only) ────────────────────────────────────
    # A close-enough earlier prompt reuses its already-generated materials instantly:
    # no subprocess, no wait, no cost. Benchmark modes never short-circuit.
    if req.mode == "async":
        try:
            hit = prompt_cache.find_similar(topic)
        except Exception:
            hit = None
        if hit:
            state = RunState(
                run_id=run_id, topic=topic, mode=req.mode, _loop=loop,
                user_id=(user["id"] if user else None),
                status="complete", phase="done", progress_pct=100,
                run_dir=hit["run_dir"], outputs=hit["outputs"],
                from_cache=True, cached_topic=hit["cached_topic"],
            )
            with _runs_lock:
                _runs[run_id] = state
            if user:
                try:
                    auth_db.upsert_run(run_id, user["id"], topic, "complete", state.started_at)
                    auth_db.set_run_result(run_id, "complete", hit["run_dir"], hit["outputs"])
                except Exception:
                    pass
            return {"run_id": run_id, "status": "complete", "from_cache": True}

    state = RunState(
        run_id=run_id,
        topic=topic,
        mode=req.mode,
        _loop=loop,
        user_id=(user["id"] if user else None),
    )

    with _runs_lock:
        _runs[run_id] = state

    # Record the run against the user immediately so it shows in history while running.
    if user:
        try:
            auth_db.upsert_run(run_id, user["id"], state.topic, "running", state.started_at)
        except Exception:
            pass

    thread = threading.Thread(target=_run_worker, args=(state,), daemon=True)
    thread.start()

    return {"run_id": run_id, "status": "running"}


@app.get("/run/{run_id}")
async def get_run(run_id: str, authorization: str | None = Header(default=None)):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is not None:
        # A run owned by a user is only served to that user; anonymous in-memory runs stay open.
        if state.user_id is not None:
            user = current_user(authorization)
            if not user or user["id"] != state.user_id:
                raise HTTPException(status_code=404, detail="run not found")
        return state.to_dict()

    # Not in memory (e.g. after a restart) — fall back to the DB for the owner.
    persisted = auth_db.get_run(run_id)
    if persisted is None:
        raise HTTPException(status_code=404, detail="run not found")
    user = current_user(authorization)
    if not user or user["id"] != persisted["user_id"]:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": persisted["run_id"],
        "topic": persisted["topic"],
        "mode": "async",
        "started_at": persisted["started_at"],
        "status": persisted["status"],
        "phase": "done" if persisted["status"] == "complete" else "error",
        "progress_pct": 100 if persisted["status"] == "complete" else 0,
        "log_lines": [],
        "benchmark": {},
        "outputs": persisted["outputs"],
        "run_dir": persisted["run_dir"],
        "error": None,
    }


@app.post("/run/{run_id}/cancel")
async def cancel_run(run_id: str):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    if state.status != "running":
        # Already finished, failed, or cancelled — nothing to stop.
        return {"run_id": run_id, "status": state.status, "cancelled": False}
    signalled = state.cancel()
    return {"run_id": run_id, "status": "cancelled", "cancelled": signalled}


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
async def download_run(
    run_id: str,
    authorization: str | None = Header(default=None),
    token: str | None = None,
):
    with _runs_lock:
        state = _runs.get(run_id)

    if state is not None:
        if state.user_id is not None:
            user = user_from_header_or_query(authorization, token)
            if not user or user["id"] != state.user_id:
                raise HTTPException(status_code=404, detail="run not found")
        if state.status != "complete":
            raise HTTPException(status_code=409, detail="run is not complete yet")
        outputs = state.outputs
    else:
        # Not in memory — a persisted, completed run for its owner.
        persisted = auth_db.get_run(run_id)
        if persisted is None:
            raise HTTPException(status_code=404, detail="run not found")
        user = user_from_header_or_query(authorization, token)
        if not user or user["id"] != persisted["user_id"]:
            raise HTTPException(status_code=404, detail="run not found")
        if persisted["status"] != "complete":
            raise HTTPException(status_code=409, detail="run is not complete yet")
        outputs = persisted["outputs"]

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
    topic_str = state.topic if state is not None else persisted["topic"]
    topic_slug = re.sub(r"[^a-z0-9]+", "_", topic_str.lower()).strip("_")[:30]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{topic_slug}_{ts}.zip"

    return StreamingResponse(
        io.BytesIO(buf.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/runs")
async def list_runs(authorization: str | None = Header(default=None)):
    user = current_user(authorization)

    with _runs_lock:
        live = {s.run_id: s for s in _runs.values()}

    if user:
        # A signed-in user sees only their own runs, from the DB, with live progress
        # overlaid for any that are currently running.
        out = []
        for r in auth_db.runs_for_user(user["id"]):
            s = live.get(r["run_id"])
            if s is not None:
                out.append({
                    "run_id": s.run_id, "topic": s.topic, "mode": s.mode,
                    "status": s.status, "started_at": s.started_at,
                    "progress_pct": s.progress_pct, "phase": s.phase,
                })
            else:
                out.append({
                    "run_id": r["run_id"], "topic": r["topic"], "mode": "async",
                    "status": r["status"], "started_at": r["started_at"],
                    "progress_pct": 100 if r["status"] == "complete" else 0,
                    "phase": "done" if r["status"] == "complete" else "error",
                })
        return out

    # Anonymous: current behavior — the in-memory list, minus runs owned by a user.
    return [
        {
            "run_id": s.run_id, "topic": s.topic, "mode": s.mode,
            "status": s.status, "started_at": s.started_at,
            "progress_pct": s.progress_pct, "phase": s.phase,
        }
        for s in reversed(list(live.values()))
        if s.user_id is None
    ]


@app.get("/file/{run_id}/{filename}")
async def serve_file(
    run_id: str,
    filename: str,
    authorization: str | None = Header(default=None),
    token: str | None = None,
):
    # Sanitize filename — no path traversal
    filename = os.path.basename(filename)
    with _runs_lock:
        state = _runs.get(run_id)

    outputs: dict = {}
    run_dir = ""
    if state is not None:
        if state.user_id is not None:
            user = user_from_header_or_query(authorization, token)
            if not user or user["id"] != state.user_id:
                raise HTTPException(status_code=404, detail="run not found")
        outputs, run_dir = state.outputs, state.run_dir
    else:
        # Not in memory — serve a persisted run's files to its owner.
        persisted = auth_db.get_run(run_id)
        if persisted is None:
            raise HTTPException(status_code=404, detail="run not found")
        user = user_from_header_or_query(authorization, token)
        if not user or user["id"] != persisted["user_id"]:
            raise HTTPException(status_code=404, detail="run not found")
        outputs, run_dir = persisted["outputs"], persisted["run_dir"]

    # Check outputs dict first
    for path in outputs.values():
        if os.path.basename(path) == filename and os.path.isfile(path):
            return FileResponse(path)

    # Fallback: search run_dir
    if run_dir:
        candidate = os.path.join(run_dir, filename)
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
