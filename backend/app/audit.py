from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, action: str, actor: int | None = None, target_type: str | None = None, target_id: str | None = None, meta: dict[str, object] | None = None) -> None:
    db.add(AuditLog(actor_user_id=actor, action=action, target_type=target_type, target_id=target_id, meta=meta or {}))
