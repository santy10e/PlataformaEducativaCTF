from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from app.models import SchoolClass, User, class_students
from app.users_service import can_manage_class, user_roles


def serialize_class(db: DbSession, item: SchoolClass) -> dict[str, object]:
    return {
        "id": item.id,
        "name": item.name,
        "academic_period": item.academic_period,
        "description": item.description,
        "teacher_user_id": item.teacher_user_id,
        "teacher_name": item.teacher.display_name if item.teacher else None,
        "student_count": db.scalar(select(func.count()).select_from(class_students).where(class_students.c.class_id == item.id)) or 0,
    }


def list_classes(db: DbSession, actor: User, page: int, page_size: int, search: str | None) -> dict[str, object]:
    query = select(SchoolClass).options(selectinload(SchoolClass.teacher)).order_by(SchoolClass.name, SchoolClass.id)
    if "ADMIN" not in user_roles(actor):
        query = query.where(SchoolClass.teacher_user_id == actor.id)
    if search:
        query = query.where(SchoolClass.name.ilike(f"%{search.strip()}%"))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_class(db, item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_class(db: DbSession, actor: User, class_id: int) -> SchoolClass | None:
    item = db.scalar(select(SchoolClass).options(selectinload(SchoolClass.teacher), selectinload(SchoolClass.students).selectinload(User.student_profile), selectinload(SchoolClass.students).selectinload(User.roles)).where(SchoolClass.id == class_id))
    if item is None or can_manage_class(actor, item):
        return item
    return None


def create_class(db: DbSession, actor: User, *, name: str, academic_period: str, description: str, teacher_user_id: int | None) -> SchoolClass:
    roles = user_roles(actor)
    assigned_teacher_id = actor.id if "ADMIN" not in roles else teacher_user_id
    if assigned_teacher_id is not None:
        teacher = db.scalar(select(User).options(selectinload(User.roles)).where(User.id == assigned_teacher_id, User.is_active.is_(True)))
        if teacher is None or "INSTRUCTOR" not in user_roles(teacher):
            raise ValueError("the assigned account is not an active instructor")
    item = SchoolClass(name=name.strip(), academic_period=academic_period.strip(), description=description.strip(), teacher_user_id=assigned_teacher_id)
    db.add(item)
    db.flush()
    return item


def update_class(db: DbSession, item: SchoolClass, *, name: str, academic_period: str, description: str, teacher_user_id: int | None, actor: User) -> None:
    if "ADMIN" in user_roles(actor):
        if teacher_user_id is not None:
            teacher = db.scalar(select(User).options(selectinload(User.roles)).where(User.id == teacher_user_id, User.is_active.is_(True)))
            if teacher is None or "INSTRUCTOR" not in user_roles(teacher):
                raise ValueError("the assigned account is not an active instructor")
        item.teacher_user_id = teacher_user_id
    item.name = name.strip()
    item.academic_period = academic_period.strip()
    item.description = description.strip()


def replace_students(db: DbSession, item: SchoolClass, student_ids: list[int]) -> list[User]:
    if len(student_ids) != len(set(student_ids)):
        raise ValueError("duplicate student id")
    students = list(db.scalars(select(User).options(selectinload(User.roles)).where(User.id.in_(student_ids), User.is_active.is_(True))).all()) if student_ids else []
    if len(students) != len(student_ids) or any("STUDENT" not in user_roles(student) for student in students):
        raise ValueError("all class members must be active student accounts")
    item.students = students
    return students


def delete_class(db: DbSession, item: SchoolClass) -> None:
    if item.students:
        raise ValueError("remove students before deleting the class")
    db.delete(item)
