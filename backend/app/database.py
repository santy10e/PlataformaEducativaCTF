from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


def check_database() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
