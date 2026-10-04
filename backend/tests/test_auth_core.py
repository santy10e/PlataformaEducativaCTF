from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession

from app.dependencies import current_session, require_csrf, require_permission
from app.models import Permission, Role, Session, User
from app.security import digest_token


def make_session(db: DbSession, user: User, expires_at: datetime) -> Session:
    session = Session(user_id=user.id, token_hash=digest_token("opaque-cookie"), csrf_hash=digest_token("csrf-value"), csrf_token="csrf-value", expires_at=expires_at)
    db.add(session)
    db.flush()
    return session


def test_session_expiry_and_csrf(db: DbSession) -> None:
    user = User(username="learner", password_hash="unused", display_name="Learner", is_active=True)
    db.add(user)
    db.flush()
    session = make_session(db, user, datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5))
    principal = current_session(db=db, cyberlab_session="opaque-cookie")
    assert principal[0].id == user.id
    require_csrf(principal=principal, x_csrf_token="csrf-value")
    with pytest.raises(HTTPException) as csrf_error:
        require_csrf(principal=principal, x_csrf_token="wrong")
    assert csrf_error.value.status_code == 403
    session.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    with pytest.raises(HTTPException) as expired:
        current_session(db=db, cyberlab_session="opaque-cookie")
    assert expired.value.status_code == 401


def test_permission_dependency_grants_only_assigned_permission(db: DbSession) -> None:
    user = User(username="teacher", password_hash="unused", display_name="Teacher", is_active=True)
    role = Role(name="INSTRUCTOR", is_system=True)
    permission = Permission(code="challenge.create", description="Create challenges")
    role.permissions.append(permission)
    user.roles.append(role)
    db.add(user)
    db.flush()
    session = make_session(db, user, datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5))
    principal = (user, session)
    assert require_permission("challenge.create")(principal=principal, db=db).id == user.id
    with pytest.raises(HTTPException) as denied:
        require_permission("audit.view")(principal=principal, db=db)
    assert denied.value.status_code == 403
