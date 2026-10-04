"""Small, bounded maintenance jobs for records and app-owned temporary files."""

import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session as DbSession

from app.database import engine
from app.models import Session

logger = logging.getLogger("cyberlab.maintenance")
TEMP_ROOT = Path("/tmp/cyberlab")


def cleanup_once(now: datetime | None = None) -> tuple[int, int]:
    """Delete old sessions and stale `*.tmp` files in CYBERLAB's private temp dir."""
    current = now or datetime.now(UTC).replace(tzinfo=None)
    session_cutoff = current - timedelta(days=7)
    with DbSession(engine) as db:
        stale_sessions = or_(
            Session.expires_at < session_cutoff,
            Session.revoked_at < session_cutoff,
        )
        deleted_sessions = len(db.scalars(select(Session.id).where(stale_sessions)).all())
        db.execute(delete(Session).where(stale_sessions))
        db.commit()

    deleted_files = 0
    if TEMP_ROOT.is_dir() and not TEMP_ROOT.is_symlink():
        file_cutoff = time.time() - 24 * 60 * 60
        for path in TEMP_ROOT.glob("*.tmp"):
            try:
                if path.is_file() and not path.is_symlink() and path.stat().st_mtime < file_cutoff:
                    path.unlink()
                    deleted_files += 1
            except FileNotFoundError:
                continue
            except OSError:
                logger.warning("Could not remove stale temporary file")
    return deleted_sessions, deleted_files
