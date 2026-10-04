from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models import SystemSetting

DEFAULTS: dict[str, tuple[Any, str]] = {
    "school_timezone": ("America/Guayaquil", "Zona horaria local del colegio"),
    "session_ttl_hours": (12, "Duración máxima de las sesiones"),
    "scoreboard_enabled": (True, "Visibilidad general del scoreboard"),
    "max_attempts_global": (20, "Intentos máximos por reto y estudiante"),
    "submission_rate_limit": (8, "Límite por estudiante y ráfaga compartida por IP cada 60 segundos"),
}
_cache: dict[str, Any] = {}


def get(db: Session, key: str) -> Any:
    if key in _cache:
        return _cache[key]
    setting = db.get(SystemSetting, key)
    value = setting.value if setting else DEFAULTS.get(key, (None, ""))[0]
    _cache[key] = value
    return value


def set_value(db: Session, key: str, value: Any, actor: int) -> SystemSetting:
    if key not in DEFAULTS:
        raise ValueError("unknown setting")
    if key == "school_timezone":
        if not isinstance(value, str) or len(value) > 80:
            raise ValueError("school_timezone must be a timezone name")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("unknown timezone") from exc
    if key == "max_attempts_global" and (type(value) is not int or not 1 <= value <= 1000):
        raise ValueError("max_attempts_global must be between 1 and 1000")
    if key == "submission_rate_limit" and (type(value) is not int or not 1 <= value <= 120):
        raise ValueError("submission_rate_limit must be between 1 and 120")
    if key == "scoreboard_enabled" and type(value) is not bool:
        raise ValueError("scoreboard_enabled must be a boolean")
    if key == "session_ttl_hours" and (type(value) is not int or not 1 <= value <= 720):
        raise ValueError("session_ttl_hours must be between 1 and 720")
    setting = db.get(SystemSetting, key)
    if setting is None:
        setting = SystemSetting(key=key, value=value, description=DEFAULTS.get(key, (None, ""))[1])
        db.add(setting)
    else:
        setting.value = value
    _cache.pop(key, None)
    audit.log(db, "SETTING_CHANGED", actor, "system_setting", key)
    return setting


def list_values(db: Session) -> list[dict[str, Any]]:
    rows = {row.key: row for row in db.scalars(select(SystemSetting)).all()}
    return [{"key": key, "value": rows[key].value if key in rows else default, "description": rows[key].description if key in rows else description} for key, (default, description) in DEFAULTS.items()]
