"""Shared fixtures for API-level tests that act as a chosen user."""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.dependencies import current_session, get_db
from app.main import app
from app.models import Permission, Role, User
from app.models import Session as AuthSession
from app.security import digest_token

CSRF = "csrf-token"
INSTRUCTOR_PERMISSIONS = ("event.manage", "class.view", "class.manage_students", "import.preview", "import.execute", "challenge.create", "challenge.update", "user.create", "user.update")
ADMIN_ONLY_PERMISSIONS = ("role.update", "settings.view")


def make_role(db: DbSession, name: str, codes: tuple[str, ...]) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name, is_system=True)
        db.add(role)
    for code in codes:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=code)
            db.add(permission)
        if permission not in role.permissions:
            role.permissions.append(permission)
    db.flush()
    return role


def make_user(db: DbSession, username: str, role_name: str) -> User:
    codes = INSTRUCTOR_PERMISSIONS + (ADMIN_ONLY_PERMISSIONS if role_name == "ADMIN" else ()) if role_name in {"INSTRUCTOR", "ADMIN"} else ("challenge.view",)
    user = User(username=username, password_hash="unused", display_name=username, roles=[make_role(db, role_name, codes)], is_active=True)
    db.add(user)
    db.flush()
    return user


class Caller:
    """Issues API requests as a chosen user against the shared test session."""

    def __init__(self, db: DbSession) -> None:
        self.db = db
        self.client = TestClient(app)
        self.sessions: dict[int, AuthSession] = {}

    def session_for(self, user: User) -> AuthSession:
        if user.id not in self.sessions:
            session = AuthSession(user_id=user.id, token_hash=digest_token(f"s-{user.id}"), csrf_hash=digest_token(CSRF), csrf_token=CSRF, expires_at=datetime(2099, 1, 1, tzinfo=UTC))
            self.db.add(session)
            self.db.flush()
            self.sessions[user.id] = session
        return self.sessions[user.id]

    def __call__(self, user: User, method: str, path: str, **kwargs: Any) -> Any:
        session = self.session_for(user)
        app.dependency_overrides[current_session] = lambda: (user, session)
        app.dependency_overrides[get_db] = lambda: self.db
        headers = {"x-csrf-token": CSRF, **kwargs.pop("headers", {})}
        return self.client.request(method, path, headers=headers, **kwargs)
