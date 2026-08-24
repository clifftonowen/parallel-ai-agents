"""
signing.py

Short-lived, run-scoped URLs for the routes a browser cannot send a header to.

The problem this replaces: `<video src>`, `window.open` and `EventSource`
cannot set an Authorization header, so the session token was appended to the
URL instead. A URL is not a private place. It reaches browser history, the
Referer header on anything the page links out to, and every proxy and server
log in between. What leaked there was the session token itself -- full account
access, for as long as the session lasted.

A grant is not the session token. It says one thing: "the holder may read the
files of run X, until time T". It cannot start a run, cannot read the account,
cannot be exchanged for a session, and cannot be replayed against a different
run, because the run id is inside what gets signed.

Format: `{exp}.{signature}`, where the signature is HMAC-SHA256 over
`{run_id}|{exp}`. Nothing secret is in the string, so there is nothing to
decrypt and no state to store: a grant is verified by recomputing it. That also
means grants cannot be revoked individually -- the TTL is the only expiry,
which is why it is short rather than session-length.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from paths import DB_PATH

__all__ = ["issue", "verify", "grant_ttl_seconds", "KEY_PATH"]

# Next to the database, because it is the same kind of thing: local state that
# must survive a restart and must never be committed.
KEY_PATH = os.path.join(os.path.dirname(DB_PATH) or ".", ".signing_key")

_key_cache: bytes | None = None


def grant_ttl_seconds() -> int:
    """How long a grant stays valid. 45 minutes by default.

    Longer than it looks like it should be, for a concrete reason. Two
    consumers reuse the same URL long after it is issued: a `<video>` element
    re-requests it for every seek, and EventSource reconnects to it by itself
    after a dropped connection. A run takes about ten minutes, and the full
    sweep about thirty-six, so a five-minute grant would break playback
    mid-file and streaming mid-run.

    Even at 45 minutes this is categorically better than what it replaces: a
    leaked grant reads one run's files for under an hour, where a leaked
    session token read the whole account for two weeks.
    """
    raw = os.environ.get("GRANT_TTL_SECONDS", "").strip()
    try:
        ttl = int(raw) if raw else 2700
    except ValueError:
        ttl = 2700
    return max(60, ttl)


def _key() -> bytes:
    """The signing key: from the environment, or a generated file beside the DB.

    SIGNING_SECRET is the deployed path -- with more than one process serving
    the app they all have to agree, and a file on one container's disk does
    not do that.

    The generated file is for development, and it has to be a file rather than
    a per-process value: `uvicorn --reload` restarts the child on every save,
    and a key that changed with it would invalidate every outstanding grant
    each time anyone touched the code. Video would break mid-playback for no
    visible reason.
    """
    global _key_cache
    if _key_cache is not None:
        return _key_cache

    env = os.environ.get("SIGNING_SECRET", "").strip()
    if env:
        _key_cache = env.encode("utf-8")
        return _key_cache

    try:
        with open(KEY_PATH, encoding="ascii") as fh:
            stored = fh.read().strip()
        if stored:
            _key_cache = base64.urlsafe_b64decode(stored + "=" * (-len(stored) % 4))
            return _key_cache
    except (FileNotFoundError, ValueError):
        # Unreadable or not what we wrote: fall through and generate a new one
        # rather than signing with something malformed.
        pass

    # Base64 rather than raw bytes, and this is not cosmetic. Reading raw bytes
    # back with .strip() silently ate a leading or trailing whitespace byte,
    # which 32 random bytes carry about 5% of the time -- so roughly one
    # restart in twenty came back with a key one byte short of the one it
    # signed with, and every outstanding grant stopped verifying for no visible
    # reason. Text has no such edge.
    key = secrets.token_bytes(32)
    os.makedirs(os.path.dirname(KEY_PATH) or ".", exist_ok=True)
    # Written before use, so a crash between generating and writing cannot
    # leave two processes signing with different keys.
    with open(KEY_PATH, "w", encoding="ascii") as fh:
        fh.write(base64.urlsafe_b64encode(key).decode("ascii"))
    try:
        os.chmod(KEY_PATH, 0o600)
    except OSError:
        # No-op on Windows. Not worth failing over -- the file sits beside the
        # database, which has the same exposure.
        pass
    _key_cache = key
    return key


def _sign(run_id: str, exp: int) -> str:
    mac = hmac.new(_key(), f"{run_id}|{exp}".encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def issue(run_id: str, ttl: int | None = None) -> tuple[str, int]:
    """A grant for one run, and how many seconds it lasts."""
    ttl = grant_ttl_seconds() if ttl is None else ttl
    exp = int(time.time()) + ttl
    return f"{exp}.{_sign(run_id, exp)}", ttl


def verify(grant: str | None, run_id: str) -> bool:
    """Is this grant valid, right now, for this run?

    Returns False for anything malformed rather than raising: this runs on
    every media request and the input is entirely attacker-controlled.
    """
    if not grant or "." not in grant:
        return False
    exp_s, _, sig = grant.partition(".")
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < time.time():
        return False
    # compare_digest, not ==. A plain comparison returns early on the first
    # differing byte, which leaks how much of a guess was right.
    return hmac.compare_digest(sig, _sign(run_id, exp))
