"""
auth_db.py
----------
A small, dependency-free SQLite layer for Study Bench accounts and per-user run history.

Uses only the standard library:
  - password hashing via hashlib.scrypt with a per-user random salt
  - opaque session tokens via secrets.token_urlsafe (stored server-side, revocable)

Three tables:
  users     (id, email UNIQUE, pw_hash, salt, created_at)
  sessions  (token PRIMARY KEY, user_id, created_at)
  runs      (run_id PRIMARY KEY, user_id, topic, status, started_at, run_dir, outputs_json)

Thread-safe: a single connection guarded by a lock (mirrors the api_server _runs_lock pattern).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone

from paths import DB_PATH as _DB_PATH

# The connection is created on first use, not at import.
#
# It used to be opened at module scope, which meant that merely importing this
# module -- or importing anything that imports it -- created a database file.
# `pytest --collect-only` was enough to do it, and in a container it happened
# before the volume was necessarily ready.
_conn: sqlite3.Connection | None = None
_conn_lock = threading.Lock()
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """Return the process-wide SQLite connection, opening it on first call."""
    global _conn
    if _conn is None:
        with _conn_lock:
            if _conn is None:  # re-check: another thread may have won the race
                os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
                conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                _conn = conn
    return _conn

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with _lock:
        _get_conn().executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT UNIQUE NOT NULL,
                pw_hash    TEXT NOT NULL,
                salt       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id       TEXT PRIMARY KEY,
                user_id      INTEGER NOT NULL,
                topic        TEXT NOT NULL,
                status       TEXT NOT NULL,
                started_at   TEXT NOT NULL,
                run_dir      TEXT,
                outputs_json TEXT
            );
            -- Shared, cross-user cache of completed generations, keyed by prompt embedding.
            -- A similar future prompt can reuse a row's already-generated files.
            CREATE TABLE IF NOT EXISTS prompt_cache (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                topic          TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                run_dir        TEXT NOT NULL,
                outputs_json   TEXT NOT NULL,
                created_at     TEXT NOT NULL,
                hits           INTEGER NOT NULL DEFAULT 0
            );
            -- Requests to be allowed to start runs. Having an account and
            -- being able to spend API credits are deliberately separate: an
            -- account is free to create, running the pipeline is not.
            CREATE TABLE IF NOT EXISTS access_requests (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                name       TEXT NOT NULL,
                org        TEXT NOT NULL,
                message    TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            -- One pending request per account, enforced by the database rather
            -- than by a check that races under concurrent submits.
            CREATE UNIQUE INDEX IF NOT EXISTS access_requests_one_pending
                ON access_requests(user_id) WHERE status = 'pending';
            """
        )
        # users.can_run predates nothing -- it is added here rather than in the
        # CREATE TABLE so existing databases pick it up without a migration
        # step. Default 0: signing up grants no ability to spend.
        cols = {r["name"] for r in _get_conn().execute("PRAGMA table_info(users)")}
        if "can_run" not in cols:
            _get_conn().execute(
                "ALTER TABLE users ADD COLUMN can_run INTEGER NOT NULL DEFAULT 0"
            )
        _get_conn().commit()


# ── password hashing (scrypt) ────────────────────────────────────────────────

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return dk.hex()


class AuthError(Exception):
    """Raised for user-facing auth problems; the message is safe to show."""


def validate_credentials(email: str, password: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise AuthError("That doesn't look like an email address. Check it and try again.")
    if len(password or "") < 8:
        raise AuthError("Use a password of at least 8 characters.")
    return email


# ── users & sessions ─────────────────────────────────────────────────────────

def create_user(email: str, password: str) -> dict:
    email = validate_credentials(email, password)
    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(password, salt)
    with _lock:
        existing = _get_conn().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise AuthError("That email's already registered — sign in instead.")
        cur = _get_conn().execute(
            "INSERT INTO users (email, pw_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (email, pw_hash, salt.hex(), _now()),
        )
        _get_conn().commit()
        return {"id": cur.lastrowid, "email": email}


def verify_login(email: str, password: str) -> dict:
    email = (email or "").strip().lower()
    with _lock:
        row = _get_conn().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        raise AuthError("No account uses that email. Create one to get started.")
    salt = bytes.fromhex(row["salt"])
    if not secrets.compare_digest(_hash_password(password, salt), row["pw_hash"]):
        raise AuthError("That password doesn't match. Try again.")
    return {"id": row["id"], "email": row["email"]}


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _get_conn().execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, _now()),
        )
        _get_conn().commit()
    return token


def delete_session(token: str) -> None:
    with _lock:
        _get_conn().execute("DELETE FROM sessions WHERE token = ?", (token,))
        _get_conn().commit()


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    with _lock:
        row = _get_conn().execute(
            """
            SELECT u.id AS id, u.email AS email, u.can_run AS can_run
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "email": row["email"], "can_run": bool(row["can_run"])}


# ── access requests ──────────────────────────────────────────────────────────

# Length caps. These are enforced here as well as at the route, because this is
# the layer that actually writes to the database and a second caller must not
# be able to bypass them.
NAME_MAX = 100
ORG_MAX = 100
MESSAGE_MAX = 1000


def _clean(text: str, limit: int, *, allow_newlines: bool = False) -> str:
    """Strip control characters, normalise whitespace, truncate.

    Control characters matter because this text is shown to whoever holds the
    grant. A NUL or an ANSI escape has no business in any of these fields, and
    dropping them here means nothing downstream has to think about it.

    Newlines survive only in the message, where paragraph breaks are part of
    what somebody wrote; name and organisation are single-line and collapse.
    Other whitespace becomes a space rather than being deleted, so a pasted
    "line1\r\nline2" does not come back as "line1line2".
    """
    text = text or ""
    keep = " \n" if allow_newlines else " "
    cleaned = []
    for ch in text:
        if ch in keep:
            cleaned.append(ch)
        elif ch.isspace():
            cleaned.append(" ")
        elif ch.isprintable():
            cleaned.append(ch)
    text = "".join(cleaned)

    if not allow_newlines:
        return " ".join(text.split())[:limit]

    # Collapse runs of spaces within each line, and cap a run of blank lines at
    # one, so nobody can pad the admin view with a screenful of nothing.
    out: list[str] = []
    blanks = 0
    for line in text.split("\n"):
        line = " ".join(line.split())
        blanks = blanks + 1 if not line else 0
        if blanks <= 1:
            out.append(line)
    return "\n".join(out).strip()[:limit]

def create_access_request(user_id: int, name: str, org: str, message: str) -> bool:
    """Record a request to be allowed to run the pipeline.

    Returns False when the user already has one pending, so the caller can say
    so without the database raising. One pending row per user is enforced by a
    partial unique index rather than a read-then-write, which would race.
    """
    name, org, message = (
        _clean(name, NAME_MAX),
        _clean(org, ORG_MAX),
        _clean(message, MESSAGE_MAX, allow_newlines=True),
    )
    with _lock:
        try:
            _get_conn().execute(
                """
                INSERT INTO access_requests (user_id, name, org, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, name, org, message, _now()),
            )
            _get_conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


def pending_access_request(user_id: int) -> dict | None:
    with _lock:
        row = _get_conn().execute(
            "SELECT id, created_at FROM access_requests "
            "WHERE user_id = ? AND status = 'pending'",
            (user_id,),
        ).fetchone()
    return {"id": row["id"], "created_at": row["created_at"]} if row else None


def list_access_requests(status: str = "pending") -> list[dict]:
    with _lock:
        rows = _get_conn().execute(
            """
            SELECT r.id, r.user_id, r.name, r.org, r.message, r.status,
                   r.created_at, u.email AS email, u.can_run AS can_run
            FROM access_requests r JOIN users u ON u.id = r.user_id
            WHERE r.status = ?
            ORDER BY r.created_at DESC
            """,
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def count_pending_access_requests() -> int:
    with _lock:
        row = _get_conn().execute(
            "SELECT COUNT(*) AS n FROM access_requests WHERE status = 'pending'"
        ).fetchone()
    return row["n"]


def set_can_run(email: str, allowed: bool) -> bool:
    """Grant or revoke the ability to start runs. Returns False if no such user.

    Deliberately has no HTTP route. The grant is the most valuable action in the
    system, so it is reachable only from a local script -- there is no endpoint
    to attack and no admin session worth stealing.
    """
    email = (email or "").strip().lower()
    with _lock:
        cur = _get_conn().execute(
            "UPDATE users SET can_run = ? WHERE email = ?", (1 if allowed else 0, email)
        )
        if allowed:
            _get_conn().execute(
                "UPDATE access_requests SET status = 'granted' "
                "WHERE status = 'pending' AND user_id = "
                "(SELECT id FROM users WHERE email = ?)",
                (email,),
            )
        _get_conn().commit()
        return cur.rowcount > 0


# ── per-user run history ──────────────────────────────────────────────────────

def upsert_run(run_id: str, user_id: int, topic: str, status: str, started_at: str) -> None:
    with _lock:
        _get_conn().execute(
            """
            INSERT INTO runs (run_id, user_id, topic, status, started_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET status = excluded.status
            """,
            (run_id, user_id, topic, status, started_at),
        )
        _get_conn().commit()


def set_run_result(run_id: str, status: str, run_dir: str, outputs: dict) -> None:
    with _lock:
        _get_conn().execute(
            "UPDATE runs SET status = ?, run_dir = ?, outputs_json = ? WHERE run_id = ?",
            (status, run_dir, json.dumps(outputs), run_id),
        )
        _get_conn().commit()


def owner_of_run(run_id: str) -> int | None:
    with _lock:
        row = _get_conn().execute("SELECT user_id FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return row["user_id"] if row else None


def get_run(run_id: str) -> dict | None:
    with _lock:
        row = _get_conn().execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "user_id": row["user_id"],
        "topic": row["topic"],
        "status": row["status"],
        "started_at": row["started_at"],
        "run_dir": row["run_dir"] or "",
        "outputs": json.loads(row["outputs_json"]) if row["outputs_json"] else {},
    }


def runs_for_user(user_id: int) -> list[dict]:
    with _lock:
        rows = _get_conn().execute(
            "SELECT * FROM runs WHERE user_id = ? ORDER BY started_at DESC",
            (user_id,),
        ).fetchall()
    return [
        {
            "run_id": r["run_id"],
            "topic": r["topic"],
            "status": r["status"],
            "started_at": r["started_at"],
            "run_dir": r["run_dir"] or "",
            "outputs": json.loads(r["outputs_json"]) if r["outputs_json"] else {},
        }
        for r in rows
    ]


# ── prompt cache (shared across users) ────────────────────────────────────────

def add_cache_entry(topic: str, embedding: list[float], run_dir: str, outputs: dict) -> None:
    with _lock:
        _get_conn().execute(
            """
            INSERT INTO prompt_cache (topic, embedding_json, run_dir, outputs_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (topic, json.dumps(embedding), run_dir, json.dumps(outputs), _now()),
        )
        _get_conn().commit()


def all_cache_entries() -> list[dict]:
    with _lock:
        rows = _get_conn().execute(
            "SELECT id, topic, embedding_json, run_dir, outputs_json FROM prompt_cache"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "topic": r["topic"],
            "embedding": json.loads(r["embedding_json"]),
            "run_dir": r["run_dir"],
            "outputs": json.loads(r["outputs_json"]),
        }
        for r in rows
    ]


def cache_stats() -> dict:
    """How many topics are cached, and how often they have been reused.

    A SQL aggregate rather than len(all_cache_entries()), which would deserialise
    every stored embedding just to count rows.
    """
    with _lock:
        row = _get_conn().execute(
            "SELECT COUNT(*) AS entries, COALESCE(SUM(hits), 0) AS hits FROM prompt_cache"
        ).fetchone()
    return {"entries": row["entries"], "hits": row["hits"]}


def bump_cache_hit(entry_id: int) -> None:
    with _lock:
        _get_conn().execute("UPDATE prompt_cache SET hits = hits + 1 WHERE id = ?", (entry_id,))
        _get_conn().commit()
