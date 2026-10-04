from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app import audit, settings_service
from app.dependencies import get_db, require_csrf, require_permission
from app.models import AuditLog, Permission, Role, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class RoleInput(BaseModel):
    name: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    permissions: list[str] = Field(default_factory=list, max_length=100)


class SettingInput(BaseModel):
    value: str | int | bool | dict[str, object] | list[object]


@router.get("/roles", dependencies=[Depends(require_permission("role.view"))])
def roles(db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return [{"id": role.id, "name": role.name, "is_system": role.is_system, "permissions": [permission.code for permission in role.permissions]} for role in db.scalars(select(Role)).all()]


@router.post("/roles", dependencies=[Depends(require_csrf)])
def create_role(payload: RoleInput, actor: User = Depends(require_permission("role.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    if db.scalar(select(Role.id).where(Role.name == payload.name)) is not None:
        raise HTTPException(status_code=409, detail="role already exists")
    permissions = list(db.scalars(select(Permission).where(Permission.code.in_(payload.permissions))).all()) if payload.permissions else []
    if len(permissions) != len(set(payload.permissions)):
        raise HTTPException(status_code=422, detail="unknown permission")
    role = Role(name=payload.name, is_system=False, permissions=permissions)
    db.add(role)
    db.flush()
    audit.log(db, "ROLE_CREATED", actor.id, "role", str(role.id))
    db.commit()
    return {"id": role.id, "name": role.name, "permissions": [permission.code for permission in permissions]}


@router.put("/roles/{role_id}", dependencies=[Depends(require_csrf)])
def update_role(role_id: int, payload: RoleInput, actor: User = Depends(require_permission("role.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="role not found")
    if role.is_system and role.name != payload.name:
        raise HTTPException(status_code=403, detail="system role name is protected")
    permissions = list(db.scalars(select(Permission).where(Permission.code.in_(payload.permissions))).all()) if payload.permissions else []
    if len(permissions) != len(set(payload.permissions)):
        raise HTTPException(status_code=422, detail="unknown permission")
    role.name = payload.name
    role.permissions = permissions
    audit.log(db, "ROLE_MODIFIED", actor.id, "role", str(role.id))
    db.commit()
    return {"id": role.id, "name": role.name, "permissions": [permission.code for permission in role.permissions]}


@router.delete("/roles/{role_id}", dependencies=[Depends(require_csrf)])
def delete_role(role_id: int, actor: User = Depends(require_permission("role.delete")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="role not found")
    if role.is_system:
        raise HTTPException(status_code=403, detail="system role cannot be deleted")
    db.delete(role)
    audit.log(db, "ROLE_DELETED", actor.id, "role", str(role_id))
    db.commit()
    return {"ok": True}


@router.get("/settings", dependencies=[Depends(require_permission("settings.view"))])
def get_settings(db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return settings_service.list_values(db)


@router.put("/settings/{key}", dependencies=[Depends(require_csrf), Depends(require_permission("settings.update"))])
def put_setting(key: str, payload: SettingInput, actor: User = Depends(require_permission("settings.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    try:
        setting = settings_service.set_value(db, key, payload.value, actor.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"key": setting.key, "value": setting.value}


@router.get("/audit", dependencies=[Depends(require_permission("audit.view"))])
def list_audit(action: str | None = None, actor_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: DbSession = Depends(get_db)) -> dict[str, object]:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_id:
        query = query.where(AuditLog.actor_user_id == actor_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": item.id, "action": item.action, "actor_user_id": item.actor_user_id, "target_type": item.target_type, "target_id": item.target_id, "meta": item.meta, "created_at": item.created_at} for item in items], "total": total, "page": page, "page_size": page_size}
