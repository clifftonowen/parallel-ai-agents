"""
run_manager.py

Owns the in-memory run registry and the background worker that shells out to
benchmark_profile.py.

The important change from when this lived in api_server.py is that the server
now *dictates* where a run writes instead of inferring it afterwards. It used
to take the newest subdirectory of output/ by mtime as the run directory, and
the newest profiling_results_*.json by mtime as the benchmark. Two concurrent
runs would therefore attribute each other's artifacts, and a run that produced
no JSON would silently adopt a committed one from an earlier session. Both
guesses are gone: the run id is the directory name, and the results path is
passed in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

import auth_db
import prompt_cache
from paths import OUTPUT_ROOT, PROJECT_ROOT, PYTHON
from run_state import RunState, infer_phase

__all__ = [
    "runs",
    "runs_lock",
    "build_cmd",
    "collect_outputs",
    "run_worker",
]

# Process-local. The server must run single-worker: state here is not shared
# across processes, so a second uvicorn worker would 404 on its peer's runs.
runs: dict[str, RunState] = {}
runs_lock = threading.Lock()

_MODE_FLAGS = {
    "adk": "--adk-only",
    "original": "--original-only",
    "async": "--async-only",
    # "both" and "all" run every path, which needs no flag.
}

# Artifacts the front-ends know how to render, mapped to their filenames in a
# run directory.
_OUTPUT_FILES = {
    "notes_md": "notes.md",
    "flashcards_md": "flashcards.md",
    "notes_pdf": "notes.pdf",
    "flashcards_pdf": "flashcards.pdf",
    "video": "study_video.mp4",
}

# Which variant's run directory to show when a run produced several. Async is
# the mode the learner app uses, so it wins when present.
_RUN_DIR_PRIORITY = ("async", "original", "adk")


def build_cmd(
    topic: str,
    mode: str,
    run_root: str,
    out_json: str,
    include_video: bool = True,
) -> list[str]:
    """Command line for one pipeline run.

    -u matters: without it the child block-buffers stdout when it is a pipe, so
    progress arrives in bursts at the end instead of streaming to the SSE
    clients.
    """
    cmd = [
        PYTHON, "-u", "benchmark_profile.py",
        "--topic", topic,
        "--no-cprofile",
        "--run-root", run_root,
        "--out-json", out_json,
    ]
    flag = _MODE_FLAGS.get(mode)
    if flag:
        cmd.append(flag)
    if not include_video:
        cmd.append("--skip-video")
    return cmd


def benchmark_json_path(run_id: str) -> str:
    """Where this run's benchmark JSON lives.

    Deterministic from the run id, so callers never have to search for it.
    """
    return os.path.join(OUTPUT_ROOT, run_id, "profiling_results.json")


def collect_outputs(run_dir: str) -> dict[str, str]:
    """Absolute paths of whichever known artifacts this run actually produced."""
    result: dict[str, str] = {}
    if not run_dir or not os.path.isdir(run_dir):
        return result
    for key, filename in _OUTPUT_FILES.items():
        path = os.path.join(run_dir, filename)
        if os.path.isfile(path):
            result[key] = path
    return result


def _persist_run_result(state: RunState) -> None:
    """Save a signed-in user's run so it survives a restart. No-op if anonymous."""
    if state.user_id is None:
        return
    try:
        auth_db.set_run_result(state.run_id, state.status, state.run_dir, state.outputs)
    except Exception as exc:  # a DB hiccup must never fail the run
        state.append_log(f"[api] Warning: could not save run to history: {exc}")


def _pick_run_dir(bench: dict, fallback: str) -> str:
    """The directory to surface, from the run_dirs the subprocess reported."""
    reported = bench.get("run_dirs") or {}
    for key in _RUN_DIR_PRIORITY:
        if reported.get(key):
            return reported[key]
    return fallback


def run_worker(state: RunState) -> None:
    # The run id is the directory name, so concurrent runs cannot collide and
    # nothing has to be inferred from mtimes afterwards.
    run_root = os.path.join(OUTPUT_ROOT, state.run_id)
    out_json = os.path.join(run_root, "profiling_results.json")
    os.makedirs(run_root, exist_ok=True)

    cmd = build_cmd(
        state.topic, state.mode, run_root, out_json,
        include_video=state.include_video,
    )
    state.append_log(f"[api] Launching: {' '.join(cmd)}")
    state.set_phase("starting", 2)

    try:
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        # Put the child in its own process group so cancelling can signal the
        # whole tree -- it spawns Chromium, pandoc and ffmpeg.
        if sys.platform == "win32":
            group_kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            group_kw = {"start_new_session": True}

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT,
            env=env,
            **group_kw,
        )
        with state._lock:
            state._proc = proc

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            state.append_log(line)
            infer_phase(state, line)

        proc.wait()
        return_code = proc.returncode

        if state._cancelled:
            with state._lock:
                state.status = "cancelled"
                state.phase = "error"
            _persist_run_result(state)
            state._push_sse({
                "log": "[api] Run cancelled.",
                "phase": "error",
                "progress_pct": state.progress_pct,
            })
            return

        if return_code != 0:
            with state._lock:
                state.status = "error"
                state.error = f"Process exited with code {return_code}"
            state.set_phase("error", state.progress_pct)
            _persist_run_result(state)
            state._push_sse({
                "log": state.error,
                "phase": "error",
                "progress_pct": state.progress_pct,
            })
            return

        # Read the results the subprocess was told to write. A missing file is
        # now a real error rather than a cue to adopt someone else's.
        bench: dict = {}
        if os.path.isfile(out_json):
            try:
                with open(out_json, encoding="utf-8") as f:
                    bench = json.load(f)
                with state._lock:
                    state.benchmark = bench
                state.append_log(f"[api] Benchmark JSON loaded: {out_json}")
            except Exception as exc:
                state.append_log(f"[api] Warning: could not load benchmark JSON: {exc}")
        else:
            state.append_log(
                f"[api] Warning: expected benchmark JSON at {out_json} but none was written."
            )

        run_dir = _pick_run_dir(bench, run_root)

        with state._lock:
            state.run_dir = run_dir
            state.outputs = collect_outputs(run_dir)
            state.status = "complete"
            state.progress_pct = 100
            state.phase = "done"

        _persist_run_result(state)
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
        state._push_sse({
            "log": f"[api] ERROR: {exc}",
            "phase": "error",
            "progress_pct": state.progress_pct,
        })

    finally:
        # Tell every SSE subscriber the stream is over.
        sentinel = json.dumps({"done": True})
        for q in list(state._queues):
            try:
                if state._loop:
                    state._loop.call_soon_threadsafe(q.put_nowait, sentinel)
            except Exception:
                pass
