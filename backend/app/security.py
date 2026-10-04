import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import Session, User
from app.settings_service import get as get_setting

password_hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = password_hasher.hash("constant timing placeholder")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(db: DbSession, username: str, password: str, ip: str | None, user_agent: str | None) -> tuple[User, Session, str, str] | None:
    user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    valid_password = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, password)
    if user is None or not valid_password:
        return None
    now = datetime.now(UTC).replace(tzinfo=None)
    cookie = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    session = Session(
        user_id=user.id,
        token_hash=digest_token(cookie),
        csrf_hash=digest_token(csrf),
        csrf_token=csrf,
        expires_at=now + timedelta(hours=get_setting(db, "session_ttl_hours")),
        ip_address=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    user.last_login_at = now
    db.add(session)
    db.flush()
    return user, session, cookie, csrf


class LoginRateLimiter:
    """Replaceable in-memory sliding-window limiter; use shared storage when horizontally scaled."""

    def __init__(self, limit: int = 8, window_seconds: int = 300, ip_limit: int | None = None, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.ip_limit = limit if ip_limit is None else ip_limit
        self.max_keys = max_keys
        self.attempts: dict[str, list[float]] = {}
        self._last_trim = float("-inf")
        self._lock = Lock()

    def allow(self, *keys: str, now: float | None = None) -> bool:
        import time

        current = time.monotonic() if now is None else now
        with self._lock:
            self._trim(current)
            accepted = True
            for key in keys:
                if key not in self.attempts and len(self.attempts) >= self.max_keys:
                    accepted = False
                    continue
                recent = [stamp for stamp in self.attempts.get(key, []) if current - stamp < self.window_seconds]
                key_limit = self.ip_limit if key.startswith("ip:") else self.limit
                if len(recent) >= key_limit:
                    accepted = False
                recent.append(current)
                self.attempts[key] = recent
            self._trim(current)
            return accepted

    def _trim(self, current: float) -> None:
        if len(self.attempts) < self.max_keys or current - self._last_trim < 60:
            return
        self._last_trim = current
        expired = [key for key, stamps in self.attempts.items() if not stamps or current - stamps[-1] >= self.window_seconds]
        for key in expired:
            self.attempts.pop(key, None)


login_limiter = LoginRateLimiter(limit=8, ip_limit=120)
