from collections.abc import Callable, Generator

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.database import engine
from app.models import Permission, Role, Session, User
from app.security import digest_token


def get_db() -> Generator[DbSession, None, None]:
    with DbSession(engine) as db:
        yield db


def current_session(
    db: DbSession = Depends(get_db),
    cyberlab_session: str | None = Cookie(default=None),
) -> tuple[User, Session]:
    if not cyberlab_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    session = db.scalar(select(Session).where(Session.token_hash == digest_token(cyberlab_session)))
    from datetime import UTC, datetime

    now = datetime.now(UTC).replace(tzinfo=None)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="account unavailable")
    return user, session


def require_permission(code: str) -> Callable[..., User]:
    def dependency(
        principal: tuple[User, Session] = Depends(current_session),
        db: DbSession = Depends(get_db),
    ) -> User:
        user, _ = principal
        permission = db.scalar(
            select(Role.id).join(Role.permissions).where(Role.users.any(User.id == user.id), Permission.code == code)
        )
        if permission is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
        return user

    return dependency


def require_csrf(
    principal: tuple[User, Session] = Depends(current_session),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    session = principal[1]
    if not x_csrf_token or digest_token(x_csrf_token) != session.csrf_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf validation failed")
