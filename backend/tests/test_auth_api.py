from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import Permission, Role, Session, User
from app.security import digest_token


def test_me_returns_permissions_for_route_guards() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = DbSession(engine)
    user = User(username="learner", password_hash="unused", display_name="Learner", is_active=True)
    role = Role(name="STUDENT", is_system=True)
    role.permissions.append(Permission(code="challenge.view", description="View challenges"))
    user.roles.append(role)
    db.add(user)
    db.flush()
    db.add(
        Session(
            user_id=user.id,
            token_hash=digest_token("test-session"),
            csrf_hash=digest_token("test-csrf"),
            csrf_token="test-csrf",
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
        )
    )
    db.commit()

    def override_db() -> Generator[DbSession, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            client.cookies.set("cyberlab_session", "test-session")
            response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["roles"] == ["STUDENT"]
        assert response.json()["permissions"] == ["challenge.view"]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
