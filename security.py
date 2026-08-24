"""
security.py

Token extraction and user lookup, shared by the run routes and the auth routes.

Auth is still optional on most routes. Two things are now enforced: who may
spend API credits (`require_runner`) and who may read the access-request queue
(`require_admin`). The rest of the hardening -- ownership checks that do not
depend on the run being owned, session expiry, CORS -- is still ahead.
"""

import os

from fastapi import Header, HTTPException

import auth_db

__all__ = [
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
