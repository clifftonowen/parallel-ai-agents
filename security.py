"""
security.py

Token extraction and user lookup, shared by the run routes and the auth routes.

Behaviour here is unchanged from when this lived in api_server.py: auth is
still optional on every route. Tightening that -- an allowlist for who may
start a run, ownership checks that do not depend on the run being owned, and
session expiry -- is a separate change.
"""

from fastapi import Header

import auth_db

__all__ = ["token_from_header", "current_user", "user_from_header_or_query"]


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
