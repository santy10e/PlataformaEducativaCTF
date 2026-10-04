from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from app.models import (
    Role,
    SchoolClass,
    Session,
    StudentProfile,
    TeacherProfile,
    User,
    class_students,
)
from app.security import hash_password


def user_roles(user: User) -> set[str]:
    return {role.name for role in user.roles}


def can_manage_class(actor: User, school_class: SchoolClass) -> bool:
    return "ADMIN" in user_roles(actor) or school_class.teacher_user_id == actor.id


def list_users(db: DbSession, actor: User, page: int, page_size: int, search: str | None, role_name: str | None) -> dict[str, object]:
    query = select(User).options(selectinload(User.roles), selectinload(User.enrolled_classes), selectinload(User.student_profile), selectinload(User.teacher_profile))
    if "ADMIN" not in user_roles(actor):
        in_scope = select(class_students.c.student_user_id).join(SchoolClass, class_students.c.class_id == SchoolClass.id).where(SchoolClass.teacher_user_id == actor.id)
        query = query.where(User.id.in_(in_scope))
    if role_name:
        query = query.join(User.roles).where(Role.name == role_name.upper())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(User.display_name.ilike(term) | User.username.ilike(term) | User.email.ilike(term))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    users = db.scalars(query.order_by(User.display_name, User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [serialize_user(user) for user in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def serialize_user(user: User) -> dict[str, object]:
    profile = user.student_profile or user.teacher_profile
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "first_name": profile.first_name if profile else "",
        "last_name": profile.last_name if profile else "",
        "email": user.email,
        "roles": sorted(user_roles(user)),
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "class_ids": [school_class.id for school_class in user.enrolled_classes],
    }


def create_user(
    db: DbSession,
    actor: User,
    *,
    username: str,
    password: str,
    first_name: str,
    last_name: str,
    role_name: str,
    email: str | None,
    class_ids: list[int],
) -> User:
    actor_roles = user_roles(actor)
    role_name = role_name.upper()
    if role_name not in {"STUDENT", "INSTRUCTOR"} and "ADMIN" not in actor_roles:
        raise PermissionError("instructors may only create students")
    if role_name == "ADMIN" and "ADMIN" not in actor_roles:
        raise PermissionError("only administrators may create administrators")
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise ValueError("username already exists")
    if email and db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ValueError("email already exists")
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise ValueError("unknown role")
    school_classes = list(db.scalars(select(SchoolClass).where(SchoolClass.id.in_(class_ids))).all()) if class_ids else []
    if len(school_classes) != len(set(class_ids)):
        raise ValueError("one or more classes were not found")
    if role_name == "STUDENT" and "ADMIN" not in actor_roles and (
        not school_classes or any(not can_manage_class(actor, item) for item in school_classes)
    ):
        raise PermissionError("students may only be added to classes you teach")
    if role_name == "INSTRUCTOR" and class_ids:
        raise ValueError("instructors cannot be enrolled as students")
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=f"{first_name} {last_name}".strip(),
        email=email,
        is_active=True,
        must_change_password=True,
        roles=[role],
        enrolled_classes=school_classes if role_name == "STUDENT" else [],
    )
    if role_name == "STUDENT":
        user.student_profile = StudentProfile(first_name=first_name, last_name=last_name)
    elif role_name == "INSTRUCTOR":
        user.teacher_profile = TeacherProfile(first_name=first_name, last_name=last_name)
    db.add(user)
    db.flush()
    return user


def get_visible_user(db: DbSession, actor: User, user_id: int) -> User | None:
    user = db.scalar(select(User).options(selectinload(User.roles), selectinload(User.enrolled_classes), selectinload(User.student_profile), selectinload(User.teacher_profile)).where(User.id == user_id))
    if user is None or "ADMIN" in user_roles(actor):
        return user
    in_scope = db.scalar(select(class_students.c.student_user_id).join(SchoolClass, class_students.c.class_id == SchoolClass.id).where(SchoolClass.teacher_user_id == actor.id, class_students.c.student_user_id == user_id).limit(1))
    return user if in_scope is not None else None


def update_user(db: DbSession, user: User, *, first_name: str, last_name: str, email: str | None) -> User:
    if email and db.scalar(select(User.id).where(User.email == email, User.id != user.id)) is not None:
        raise ValueError("email already exists")
    user.display_name = f"{first_name} {last_name}".strip()
    user.email = email
    profile = user.student_profile or user.teacher_profile
    if profile:
        profile.first_name = first_name
        profile.last_name = last_name
    return user


def deactivate_user(db: DbSession, user: User) -> None:
    user.is_active = False
    for session in db.scalars(select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))).all():
        session.revoked_at = datetime.now(UTC).replace(tzinfo=None)
