"""
paths.py

Every filesystem location the backend writes to, in one place and overridable
by environment variable.

Before this, `study_bench.db` and `output/` were hardcoded relative to the repo
root. That works on a dev machine and breaks in a container, where the code
lives on an ephemeral layer and durable state has to sit on a mounted volume.

Deliberately stdlib-only so anything can import it without pulling in FastAPI.
"""

import os
import sys

__all__ = ["PROJECT_ROOT", "OUTPUT_ROOT", "DB_PATH", "PYTHON", "resolve_python"]

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Generated run artifacts (notes, slides, audio, video, PDFs). In a container
# this should point at a mounted volume, otherwise every run is lost on deploy.
OUTPUT_ROOT = os.path.abspath(
    os.environ.get("OUTPUT_ROOT") or os.path.join(PROJECT_ROOT, "output")
)

# Accounts, sessions, run history and the prompt cache.
DB_PATH = os.path.abspath(
    os.environ.get("STUDY_BENCH_DB") or os.path.join(PROJECT_ROOT, "study_bench.db")
)


def resolve_python() -> str:
    """Interpreter used to spawn benchmark_profile.py as a subprocess.

    Prefers an explicit override, then a sibling venv in either the Windows or
    POSIX layout, then the running interpreter. In a container the app python
    *is* the pipeline python, so the sys.executable case is the normal path
    rather than a degraded one.
    """
    explicit = os.environ.get("PIPELINE_PYTHON", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        cand = os.path.abspath(os.path.join(PROJECT_ROOT, "..", ".venv", *rel))
        if os.path.isfile(cand):
            return cand
    return sys.executable


PYTHON = resolve_python()
