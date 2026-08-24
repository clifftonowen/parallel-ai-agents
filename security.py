"""
security.py

Token extraction and user lookup, shared by the run routes and the auth routes.

Auth stays optional on the read routes: a run started on a laptop with no
accounts remains readable by anyone holding its id. Everything else is
enforced here -- who may spend API credits (`require_runner`), how much they
may spend (`require_quota`), who owns a run (`require_owner`), who may read
the access-request queue (`require_admin`), and which origins may call the API
at all (`cors_origins`).
"""

import os

from fastapi import Header, HTTPException

import auth_db

__all__ = [
    "cors_origins",
    "require_quota",
    "run_daily_limit",
    "run_concurrent_limit",
    "require_owner",
    "token_from_header",
    "current_user",
    "user_from_header_or_query",
    "require_signed_in",
    "require_runner",
    "require_admin",
    "is_admin",
]


def token_from_header(authorization: str | None) -> str | None:
    """Pull the bearer token out of an Authorization header, if there is one."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(authorization: str | None = Header(default=None)) -> dict | None:
    """The signed-in user for a bearer token, or None for anonymous requests."""
    return auth_db.user_for_token(token_from_header(authorization))


def user_from_header_or_query(
    authorization: str | None, token_q: str | None
) -> dict | None:
    """Same lookup, but also accepting a ?token= query parameter.

    Media and download URLs are consumed by <video src>, window.open and
    EventSource, none of which can set an Authorization header.
    """
    return auth_db.user_for_token(token_from_header(authorization) or token_q)


# ── authorisation ────────────────────────────────────────────────────────────

def require_signed_in(authorization: str | None) -> dict:
    """The signed-in user, or 401."""
    user = current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def require_runner(authorization: str | None) -> dict:
    """The signed-in user, if they are allowed to start runs.

    Having an account and being able to spend API credits are separate on
    purpose: signing up is free, running the pipeline costs money. Enforced
    here rather than by hiding the button, which is not access control.
    """
    user = require_signed_in(authorization)
    if not user.get("can_run"):
        raise HTTPException(
            status_code=403,
            detail=(
                "This account can't start runs yet. Request access from the "
                "dashboard and you'll be let in once it's approved."
            ),
        )
    return user


def admin_emails() -> set[str]:
    """Accounts allowed to read the access-request queue.

    Empty by default, which means nobody -- an unset variable must not turn
    into "everyone". Note this grants *reading* the queue only; granting access
    itself has no HTTP route at all and is done with scripts/grant_access.py.
    """
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin(user: dict | None) -> bool:
    return bool(user) and (user.get("email", "").lower() in admin_emails())


def require_admin(authorization: str | None) -> dict:
    """The signed-in user, if they are an admin.

    404 rather than 403: a 403 confirms the route exists and that somebody is
    an admin, which is free reconnaissance. To anyone else this endpoint simply
    is not there.
    """
    user = current_user(authorization)
    if not is_admin(user):
        raise HTTPException(status_code=404, detail="Not found")
    return user


def cors_origins() -> list[str]:
    """Origins allowed to call this API from a browser.

    Was `["*"]`, which combined with a bearer token in localStorage means any
    site the visitor happens to open can call this API with their credentials
    if it can get at the token. Localhost defaults keep dev unchanged; set
    CORS_ORIGINS to the deployed front-end origin, comma separated.

    Note "*" is still permitted if somebody sets it explicitly -- that is a
    decision, not an accident.
    """
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5273",
        "http://127.0.0.1:5273",
    ]


def require_owner(user: dict | None, owner_id: int | None) -> None:
    """Reject unless `user` owns the resource.

    404 rather than 403 throughout: a 403 tells an attacker the run id is real,
    which turns this endpoint into an existence oracle they can enumerate.
    Anonymous runs (owner_id None) are readable by anyone who has the id, which
    is the current behaviour for a laptop with no accounts; that carve-out
    disappears the moment signup is required.
    """
    if owner_id is None:
        return
    if not user or user.get("id") != owner_id:
        raise HTTPException(status_code=404, detail="run not found")


# ── quotas ───────────────────────────────────────────────────────────────────

def _limit(name: str, default: int) -> int:
    """An integer limit from the environment, read at call time.

    Read here rather than at import so the value in `.env` is the value in
    force without a restart to pick it up, and so a test can set one.
    Unparseable values fall back to the default rather than crashing the route.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def run_daily_limit() -> int:
    """Runs one account may start per rolling 24 hours. 0 or less: no limit."""
    return _limit("RUN_DAILY_LIMIT", 10)


def run_concurrent_limit() -> int:
    """Runs one account may have in flight at once. 0 or less: no limit."""
    return _limit("RUN_CONCURRENT_LIMIT", 1)


def require_quota(daily_used: int, active: int) -> None:
    """Reject a run that would exceed either limit.

    `require_runner` decides whether an account may spend at all; this decides
    how much. Without it a granted demo account can sit in a loop starting
    runs, and every one of them spends Anthropic and OpenAI credits on the
    owner's card.

    The two limits do different jobs. The daily one bounds the bill. The
    concurrent one bounds how much damage a loop does before anyone notices,
    and it is the one that actually bites: a caller who waits for each run is
    already limited by the ten minutes a run takes, a caller who does not is
    limited by nothing.

    Unlike the other checks here this takes counts rather than a token, so it
    can be tested without a database or a running server. The route does the
    counting: the daily figure comes from the `runs` table so it survives a
    restart, the active figure from the in-memory table because a restart takes
    the worker threads with it anyway.

    429 rather than 403: this is "not now", not "not you". The message says
    which limit was hit so the caller can tell those two apart.
    """
    concurrent = run_concurrent_limit()
    if concurrent > 0 and active >= concurrent:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You already have {active} run going. Wait for it to finish, "
                "or cancel it, before starting another."
                if active == 1 else
                f"You already have {active} runs going. Wait for those to "
                "finish, or cancel them, before starting another."
            ),
        )

    daily = run_daily_limit()
    if daily > 0 and daily_used >= daily:
        raise HTTPException(
            status_code=429,
            detail=(
                f"That is {daily_used} runs in the last 24 hours, which is the "
                "limit for a demo account. The window rolls, so a slot frees "
                "up 24 hours after each run. Runs you have already made, and "
                "the Benchmark page, still work."
            ),
        )
