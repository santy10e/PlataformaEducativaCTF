from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.dependencies import current_session, get_db, require_csrf
from app.models import Session, User
from app.security import authenticate, hash_password, login_limiter, verify_password

router = APIRouter(prefix="/api/v1", tags=["auth"])


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class LoginOutput(BaseModel):
    id: int
    username: str
    display_name: str
    csrf_token: str
    must_change_password: bool


class CurrentUserOutput(LoginOutput):
    roles: list[str]
    permissions: list[str]


class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


@router.post("/auth/login", response_model=LoginOutput)
def login(payload: LoginInput, request: Request, response: Response, db: DbSession = Depends(get_db)) -> dict[str, object]:
    ip = request.client.host if request.client else "unknown"
    if not login_limiter.allow("user:" + payload.username.casefold(), "ip:" + ip):
        raise HTTPException(status_code=429, detail="too many login attempts")
    result = authenticate(db, payload.username, payload.password, ip, request.headers.get("user-agent"))
    if result is None:
        audit.log(db, "LOGIN_FAILED", meta={"username": payload.username[:80], "ip": ip})
        db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")
    user, session, cookie, csrf = result
    action = "ADMIN_LOGIN" if any(role.name == "ADMIN" for role in user.roles) else "LOGIN"
    audit.log(db, action, user.id, "session", str(session.id))
    db.commit()
    max_age = max(0, int((session.expires_at - datetime.now(UTC).replace(tzinfo=None)).total_seconds()))
    # Nginx is the only service exposing the API and overwrites this header from
    # the incoming request scheme before proxying to the internal HTTP backend.
    secure_cookie = request.headers.get("x-forwarded-proto", request.url.scheme).split(",", 1)[0].strip().lower() == "https"
    response.set_cookie("cyberlab_session", cookie, httponly=True, secure=secure_cookie, samesite="lax", path="/", max_age=max_age)
    response.set_cookie("cyberlab_csrf", csrf, httponly=False, secure=secure_cookie, samesite="lax", path="/", max_age=max_age)
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "csrf_token": csrf, "must_change_password": user.must_change_password}


@router.post("/auth/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, principal: tuple[User, Session] = Depends(current_session), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    user, session = principal
    session.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    audit.log(db, "LOGOUT", user.id, "session", str(session.id))
    db.commit()
    response.delete_cookie("cyberlab_session", path="/")
    response.delete_cookie("cyberlab_csrf", path="/")
    return {"ok": True}


@router.get("/auth/me", response_model=CurrentUserOutput)
def me(principal: tuple[User, Session] = Depends(current_session)) -> dict[str, object]:
    user, session = principal
    permissions = sorted({permission.code for role in user.roles for permission in role.permissions})
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "csrf_token": session.csrf_token, "must_change_password": user.must_change_password, "roles": [role.name for role in user.roles], "permissions": permissions}


@router.post("/auth/change-password", dependencies=[Depends(require_csrf)])
def change_password(payload: ChangePasswordInput, principal: tuple[User, Session] = Depends(current_session), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    user, _session = principal
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=403, detail="current password does not match")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    audit.log(db, "PASSWORD_CHANGED", user.id, "user", str(user.id))
    db.commit()
    return {"ok": True}


@router.get("/auth/sessions")
def list_sessions(principal: tuple[User, Session] = Depends(current_session), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    user, current = principal
    rows = db.scalars(select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))).all()
    return [{"id": row.id, "current": row.id == current.id, "created_at": row.created_at, "expires_at": row.expires_at, "ip_address": row.ip_address, "user_agent": row.user_agent} for row in rows]


@router.delete("/auth/sessions/{session_id}", dependencies=[Depends(require_csrf)])
def revoke_session(session_id: int, principal: tuple[User, Session] = Depends(current_session), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    user, current = principal
    row = db.scalar(select(Session).where(Session.id == session_id, Session.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    row.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    if row.id == current.id:
        audit.log(db, "LOGOUT", user.id, "session", str(row.id))
    db.commit()
    return {"ok": True}
