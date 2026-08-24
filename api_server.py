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
  uvicorn api_server:app --reload --port 8010
"""

from __future__ import annotations

import asyncio
import io
import json
import os
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
import run_manager
from src.agents.run_context import slugify_topic
from run_manager import runs as _runs, runs_lock as _runs_lock
from run_state import RunState
import notify  # noqa: E402
from security import (  # noqa: E402
    cors_origins, current_user, is_admin, require_admin, require_owner,
    require_runner, require_signed_in, user_from_header_or_query,
)
import prompt_cache

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

from paths import OUTPUT_ROOT, PROJECT_ROOT  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create the schema on startup rather than at import.

    Doing this at import meant any importer -- including a test collector --
    created a database file as a side effect.
    """
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    auth_db.init_db()
    # Sessions expire by age, enforced on every lookup; this just stops the
    # table growing without bound.
    gone = auth_db.purge_expired_sessions()
    if gone:
        print(f"[api] purged {gone} expired session(s)")
    yield


app = FastAPI(title="parallel-ai-agents dashboard", lifespan=lifespan)

# Was allow_origins=["*"]. With a bearer token in localStorage that let any
# site a visitor happened to open call this API. Defaults to the local
# front-end; set CORS_ORIGINS to the deployed origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


app.include_router(routes_auth.router)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartRunRequest(BaseModel):
    topic: str
    mode: str = "both"   # both | original | adk | async | all
    # Async pipeline only. Skipping video cuts a run from ~10 minutes to ~2,
    # since ffmpeg assembly dominates wall time.
    include_video: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/run")
async def start_run(req: StartRunRequest, authorization: str | None = Header(default=None)):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    if req.mode not in ("both", "original", "adk", "async", "all"):
        raise HTTPException(status_code=400, detail="mode must be 'both', 'original', 'adk', 'async', or 'all'")
    # "both" and "all" run every orchestrator in sequence: roughly 36 minutes
    # and three times the token spend for one click. Off unless deliberately
    # enabled, so a stray click on a deployed instance cannot do that.
    if req.mode in ("both", "all") and os.environ.get("ALLOW_FULL_SWEEP", "") != "1":
        raise HTTPException(
            status_code=403,
            detail=(
                "Running all three orchestrators takes about 36 minutes and 3x "
                "the tokens. Set ALLOW_FULL_SWEEP=1 on the server to enable it."
            ),
        )

    # The only endpoint that costs money. An account is free to create; being
    # allowed to spend API credits is granted separately, so this is where it
    # is checked rather than by hiding the button in the UI.
    user = require_runner(authorization)
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
        include_video=req.include_video,
    )

    with _runs_lock:
        _runs[run_id] = state

    # Record the run against the user immediately so it shows in history while running.
    if user:
        try:
            auth_db.upsert_run(run_id, user["id"], state.topic, "running", state.started_at)
        except Exception:
            pass

    thread = threading.Thread(target=run_manager.run_worker, args=(state,), daemon=True)
    thread.start()

    return {"run_id": run_id, "status": "running"}


@app.get("/run/{run_id}")
async def get_run(run_id: str, authorization: str | None = Header(default=None)):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is not None:
        # A run owned by a user is only served to that user; anonymous in-memory runs stay open.
        require_owner(current_user(authorization), state.user_id)
        return state.to_dict()

    # Not in memory (e.g. after a restart) — fall back to the DB for the owner.
    persisted = auth_db.get_run(run_id)
    if persisted is None:
        raise HTTPException(status_code=404, detail="run not found")
    user = current_user(authorization)
    if not user or user["id"] != persisted["user_id"]:
        raise HTTPException(status_code=404, detail="run not found")
    # The run's own benchmark JSON, if it wrote one. This used to be hardcoded
    # to {}, so every run served from the database reported "no benchmark data"
    # even when the file sat next to its outputs -- the numbers survived a
    # restart on disk but not through this endpoint. The ZIP download already
    # read the same path.
    benchmark: dict = {}
    bench_path = run_manager.benchmark_json_path(run_id)
    if os.path.isfile(bench_path):
        try:
            with open(bench_path, encoding="utf-8") as f:
                benchmark = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            # Same "[api]" prefix the run log uses, which infer_phase filters out.
            print(f"[api] Warning: could not read benchmark JSON for {run_id}: {exc}")

    return {
        "run_id": persisted["run_id"],
        "topic": persisted["topic"],
        "mode": "async",
        "started_at": persisted["started_at"],
        "status": persisted["status"],
        "phase": "done" if persisted["status"] == "complete" else "error",
        "progress_pct": 100 if persisted["status"] == "complete" else 0,
        "log_lines": [],
        "benchmark": benchmark,
        "outputs": persisted["outputs"],
        "run_dir": persisted["run_dir"],
        "error": None,
    }


@app.post("/run/{run_id}/cancel")
async def cancel_run(run_id: str, authorization: str | None = Header(default=None)):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    # Cancelling somebody else's run is a denial of service against them, and
    # this had no check at all: any run id was enough.
    require_owner(current_user(authorization), state.user_id)
    if state.status != "running":
        # Already finished, failed, or cancelled — nothing to stop.
        return {"run_id": run_id, "status": state.status, "cancelled": False}
    signalled = state.cancel()
    return {"run_id": run_id, "status": "cancelled", "cancelled": signalled}


@app.get("/run/{run_id}/stream")
async def stream_run(
    run_id: str,
    authorization: str | None = Header(default=None),
    token: str | None = None,
):
    with _runs_lock:
        state = _runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    # The log carries the topic and every path the run touched, and this had no
    # check at all. EventSource cannot set headers, hence ?token= as well.
    require_owner(user_from_header_or_query(authorization, token), state.user_id)

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
        require_owner(user_from_header_or_query(authorization, token), state.user_id)
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

        # This run's own benchmark JSON, if it produced one. Previously this
        # attached whichever profiling_results_*.json was newest at the repo
        # root, which under concurrent runs was somebody else's.
        bench_path = run_manager.benchmark_json_path(run_id)
        if os.path.isfile(bench_path):
            zf.write(bench_path, arcname="profiling_results.json")

    buf.seek(0)
    topic_str = state.topic if state is not None else persisted["topic"]
    # Same slug rule the orchestrators use for run directories. This was a
    # separate copy of the regex, so changing one silently desynced the
    # download name from the directory it came from.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slugify_topic(topic_str)}_{ts}.zip"

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


@app.get("/benchmarks")
async def curated_benchmarks():
    """The benchmark runs kept deliberately, from benchmarks/.

    These are committed results with their caveats written up in
    benchmarks/README.md, as opposed to output/ and the profiling_results_*.json
    at the repo root, which are working artifacts and git-ignored. Serving them
    means the Benchmark page has something real to show on a machine that has
    never run the pipeline, and there is still only one copy of the numbers.
    """
    root = os.path.join(PROJECT_ROOT, "benchmarks")
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(root, name), encoding="utf-8") as f:
                out.append({"name": name[:-5], "report": json.load(f)})
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[api] Warning: skipping benchmark {name}: {exc}")
    return out


class AccessRequest(BaseModel):
    name: str = ""
    org: str = ""
    message: str = ""


@app.post("/access-request")
async def request_access(
    req: AccessRequest, authorization: str | None = Header(default=None)
):
    """Ask to be allowed to start runs.

    Requires an account. That turns what would be an anonymous write into an
    authenticated one, so the rate limit is "one pending request per account"
    enforced by a unique index rather than per-IP guesswork.

    The text is stored as plain text and rendered as plain text. It is read by
    whoever holds the grant, which makes them the highest-value XSS target in
    the system.
    """
    user = require_signed_in(authorization)

    if user.get("can_run"):
        return {"status": "already_granted"}

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Tell me a little about why.")

    created = auth_db.create_access_request(
        user["id"], req.name, req.org, req.message
    )
    if not created:
        # Not an error: they already asked, and saying so is friendlier than a
        # 409 the front-end has to translate.
        return {"status": "already_pending"}

    # Best effort, and after the row is written. A dead webhook loses a
    # notification, never a request.
    notify.access_requested(user["email"], auth_db.count_pending_access_requests())
    return {"status": "pending"}


@app.get("/access-request")
async def my_access_request(authorization: str | None = Header(default=None)):
    """Whether this account may run, and whether it has already asked."""
    user = require_signed_in(authorization)
    pending = auth_db.pending_access_request(user["id"])
    return {
        "can_run": bool(user.get("can_run")),
        "pending": pending is not None,
        "requested_at": pending["created_at"] if pending else None,
        "is_admin": is_admin(user),
    }


@app.get("/access-requests")
async def access_request_queue(
    status: str = "pending", authorization: str | None = Header(default=None)
):
    """The queue, for whoever is in ADMIN_EMAILS.

    Read-only on purpose. Granting has no HTTP route at all -- it is
    scripts/grant_access.py, run locally -- so there is no privilege-escalation
    endpoint to attack and no admin session worth stealing.
    """
    require_admin(authorization)
    if status not in ("pending", "granted", "declined"):
        raise HTTPException(status_code=400, detail="unknown status")
    return auth_db.list_access_requests(status)


@app.get("/stats")
async def stats(authorization: str | None = Header(default=None)):
    """Counts for the sidebar meters.

    Deliberately small and deliberately real: the design this UI is ported from
    had plan tiers and "agent credits", which do not exist here. These are the
    numbers the app can actually answer for.

    Run counts are per-user; the prompt cache is process-wide, so its figures
    are the same for everybody.
    """
    user = current_user(authorization)
    runs = auth_db.runs_for_user(user["id"]) if user else []

    with _runs_lock:
        active = sum(1 for s in _runs.values() if s.status == "running")

    return {
        "runs_total": len(runs),
        "runs_complete": sum(1 for r in runs if r["status"] == "complete"),
        "runs_active": active,
        "cache": auth_db.cache_stats(),
    }


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
        require_owner(user_from_header_or_query(authorization, token), state.user_id)
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
    uvicorn.run("api_server:app", host="0.0.0.0", port=8010, reload=True)
