import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://cyberlab:cyberlab@127.0.0.1/cyberlab")
os.environ.setdefault("BACKEND_SECRET_KEY", "test-only-key-not-used-for-security")


@pytest.fixture
def db() -> Generator[DbSession, None, None]:
    import app.models  # noqa: F401
    from app.database import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session
    engine.dispose()
