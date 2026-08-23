"""
routes_auth.py

Email + password accounts for the Study Bench learner app.

Split out of api_server.py because it is the one route group with no dependency
on run state -- it touches auth_db and nothing else.
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

import auth_db
from security import current_user, token_from_header

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


@router.post("/signup")
async def signup(req: AuthRequest):
    try:
        user = auth_db.create_user(req.email, req.password)
    except auth_db.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = auth_db.create_session(user["id"])
    return {"token": token, "email": user["email"]}


@router.post("/login")
async def login(req: AuthRequest):
    try:
        user = auth_db.verify_login(req.email, req.password)
    except auth_db.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    token = auth_db.create_session(user["id"])
    return {"token": token, "email": user["email"]}


@router.post("/logout", status_code=204)
async def logout(authorization: str | None = Header(default=None)):
    token = token_from_header(authorization)
    if token:
        auth_db.delete_session(token)
    return None


@router.get("/me")
async def me(authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="not signed in")
    return {"email": user["email"]}
