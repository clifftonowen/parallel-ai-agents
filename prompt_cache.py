"""
prompt_cache.py
---------------
A semantic cache of completed study-material generations, keyed on the *meaning* of the
prompt rather than its exact text. When a new prompt is close enough to a past one, the
already-generated notes / flashcards / video / PDFs are reused instead of regenerating.

Design:
  - Prompts are embedded with OpenAI text-embedding-3-small (the app's existing OPENAI_API_KEY
    covers it — no new secret).
  - Vectors + result metadata live in the existing SQLite DB (auth_db `prompt_cache` table);
    no MongoDB, no separate server.
  - Similarity is cosine (numpy). At prototype scale a linear scan is fine; the marked spot
    below is where an ANN index (sqlite-vss / Chroma / Mongo Atlas Vector Search) would slot in.

The cache is best-effort: if embeddings are unavailable or anything fails, callers fall back
to normal generation. It never blocks a run.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
from dotenv import load_dotenv

import auth_db

# Load .env here too — the API server process (unlike the generation subprocess) doesn't,
# and without OPENAI_API_KEY every cache lookup would silently degrade to a miss.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

log = logging.getLogger("prompt_cache")

_MODEL = os.environ.get("CACHE_EMBED_MODEL", "text-embedding-3-small")
# 0.78 cleanly separates same-topic rephrasings (measured 0.78–0.96) from different
# topics (gradient descent vs logistic regression measured 0.33) — so reuse is confident,
# never serving a different topic's materials. Tune via CACHE_SIM_THRESHOLD.
_THRESHOLD = float(os.environ.get("CACHE_SIM_THRESHOLD", "0.78"))
_ENABLED = os.environ.get("CACHE_ENABLED", "1") not in ("0", "false", "False", "")

_client = None  # lazily created OpenAI client


def _openai_client():
    global _client
    if _client is not None:
        return _client
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI

        _client = OpenAI(api_key=key)
        return _client
    except Exception as exc:  # library/version issue — degrade gracefully
        log.warning("prompt_cache: OpenAI client unavailable (%s); cache disabled", exc)
        return None


@lru_cache(maxsize=256)
def _embed_cached(text: str) -> tuple[float, ...] | None:
    client = _openai_client()
    if client is None:
        return None
    try:
        resp = client.embeddings.create(model=_MODEL, input=text)
        return tuple(resp.data[0].embedding)
    except Exception as exc:
        log.warning("prompt_cache: embedding failed (%s); skipping cache", exc)
        return None


def embed(text: str) -> list[float] | None:
    vec = _embed_cached(text.strip())
    return list(vec) if vec is not None else None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _outputs_exist(outputs: dict) -> bool:
    """A cache entry is only usable if at least one referenced file is still on disk."""
    paths = [p for p in outputs.values() if p]
    return any(os.path.isfile(p) for p in paths)


def find_similar(topic: str) -> dict | None:
    """Return {run_dir, outputs, score, cached_topic} for the best cached prompt whose
    cosine similarity to `topic` meets the threshold, or None (miss / disabled / error)."""
    if not _ENABLED:
        return None
    query = embed(topic)
    if query is None:
        return None

    q = np.asarray(query, dtype=np.float32)
    best = None
    best_score = -1.0
    # NOTE: linear scan. Fine for a prototype's handful of rows. If the cache grows large,
    # replace this with an approximate-nearest-neighbour index (sqlite-vss / Chroma / Atlas).
    for entry in auth_db.all_cache_entries():
        try:
            vec = np.asarray(entry["embedding"], dtype=np.float32)
        except Exception:
            continue
        if vec.shape != q.shape:
            continue
        score = _cosine(q, vec)
        if score > best_score:
            best_score, best = score, entry

    if best is None or best_score < _THRESHOLD:
        return None
    if not _outputs_exist(best["outputs"]):
        return None  # files were cleaned up — treat as a miss so a fresh run is made

    auth_db.bump_cache_hit(best["id"])
    return {
        "run_dir": best["run_dir"],
        "outputs": best["outputs"],
        "score": round(best_score, 4),
        "cached_topic": best["topic"],
    }


def remember(topic: str, run_dir: str, outputs: dict) -> None:
    """Record a freshly completed generation so future similar prompts can reuse it.
    No-op if the cache is disabled, embeddings are unavailable, or the files don't exist."""
    if not _ENABLED:
        return
    if not _outputs_exist(outputs):
        return
    vec = embed(topic)
    if vec is None:
        return
    try:
        auth_db.add_cache_entry(topic, vec, run_dir, outputs)
    except Exception as exc:
        log.warning("prompt_cache: could not store entry (%s)", exc)
