import csv
import io
import re
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import ImportJob, Role, SchoolClass, StudentProfile, User
from app.security import hash_password

MAX_CSV_BYTES = 2_000_000
MAX_IMPORT_ROWS = 500
REQUIRED_HEADERS = {"username", "nombre", "apellido", "curso", "password_temporal"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_header(value: str) -> str:
    return "_".join(value.strip().lower().lstrip("\ufeff").split())


def preview_csv(db: DbSession, actor_id: int, filename: str, content: str) -> tuple[ImportJob, list[dict[str, object]]]:
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds the 2 MB limit")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    headers = [normalize_header(field) for field in reader.fieldnames]
    if len(headers) != len(set(headers)):
        raise ValueError("CSV contains duplicate column names")
    if not REQUIRED_HEADERS.issubset(headers):
        missing = ", ".join(sorted(REQUIRED_HEADERS - set(headers)))
        raise ValueError(f"CSV is missing required columns: {missing}")
    reader.fieldnames = headers

    parsed: list[dict[str, object]] = []
    seen_usernames: set[str] = set()
    seen_emails: set[str] = set()
    for row_number, raw in enumerate(reader, start=2):
        if row_number > MAX_IMPORT_ROWS + 1:
            raise ValueError(f"CSV exceeds the {MAX_IMPORT_ROWS} row limit")
        values = {key: (value or "").strip() for key, value in raw.items() if key is not None}
        username = values.get("username", "")
        first_name = values.get("nombre", "")
        last_name = values.get("apellido", "")
        course = values.get("curso", "")
        email = values.get("email", "") or None
        temporary_password = values.get("password_temporal", "")
        errors: list[str] = []
        if None in raw:
            errors.append("row: contains more values than the header")
        normalized_username = username.casefold()
        normalized_email = email.casefold() if email else None
        if not USERNAME_RE.fullmatch(username):
            errors.append("username: use 3–80 letters, digits, dots, underscores or hyphens")
        if normalized_username in seen_usernames:
            errors.append("username: duplicated in this file")
        seen_usernames.add(normalized_username)
        if db.scalar(select(User.id).where(User.username == username)) is not None:
            errors.append("username: already exists")
        if not first_name or len(first_name) > 80:
            errors.append("nombre: required, maximum 80 characters")
        if not last_name or len(last_name) > 80:
            errors.append("apellido: required, maximum 80 characters")
        if not course or len(course) > 120:
            errors.append("curso: required, maximum 120 characters")
        if email and (len(email) > 254 or not EMAIL_RE.fullmatch(email)):
            errors.append("email: invalid address")
        if normalized_email and normalized_email in seen_emails:
            errors.append("email: duplicated in this file")
        if normalized_email:
            seen_emails.add(normalized_email)
            if db.scalar(select(User.id).where(User.email == email)) is not None:
                errors.append("email: already exists")
        if len(temporary_password) < 12 or len(temporary_password) > 256:
            errors.append("password_temporal: use 12–256 characters")

        row_data: dict[str, object] = {
            "row_number": row_number,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "display_name": f"{first_name} {last_name}".strip(),
            "course": course,
            "email": email,
            "valid": not errors,
            "errors": errors,
        }
        if not errors:
            row_data["password_hash"] = hash_password(temporary_password)
        parsed.append(row_data)

    if not parsed:
        raise ValueError("CSV has no student rows")
    valid_count = sum(1 for row in parsed if row["valid"])
    job = ImportJob(
        public_id=str(uuid4()),
        actor_user_id=actor_id,
        status="PREVIEWED",
        row_count=len(parsed),
        valid_count=valid_count,
        error_count=len(parsed) - valid_count,
        preview_rows=parsed,
    )
    db.add(job)
    db.flush()
    public_rows = [
        {key: value for key, value in row.items() if key != "password_hash"}
        for row in parsed
    ]
    return job, public_rows


def confirm_import(db: DbSession, job: ImportJob) -> dict[str, object]:
    if job.status == "IMPORTED":
        return {"job_id": job.public_id, "status": job.status, "imported_count": job.valid_count, "class_count": 0, "already_imported": True}
    if job.status != "PREVIEWED":
        raise HTTPException(status_code=409, detail="import is not ready to confirm")
    rows = [row for row in job.preview_rows if row.get("valid") is True]
    for row in rows:
        username = str(row["username"])
        email = row.get("email")
        if db.scalar(select(User.id).where(User.username == username)) is not None:
            raise HTTPException(status_code=409, detail=f"username {username} was added after the preview")
        if email and db.scalar(select(User.id).where(User.email == str(email))) is not None:
            raise HTTPException(status_code=409, detail="an email was used after the preview")
    if not rows:
        raise HTTPException(status_code=422, detail="there are no valid rows to import")

    student_role = db.scalar(select(Role).where(Role.name == "STUDENT"))
    if student_role is None:
        raise HTTPException(status_code=500, detail="student role is missing")
    classes: dict[str, SchoolClass] = {}
    created_class_count = 0
    for row in rows:
        course = str(row["course"])
        school_class = classes.get(course)
        if school_class is None:
            school_class = db.scalar(select(SchoolClass).where(SchoolClass.name == course, SchoolClass.academic_period == ""))
            if school_class is None:
                school_class = SchoolClass(name=course, academic_period="", description="", teacher_user_id=job.actor_user_id)
                db.add(school_class)
                db.flush()
                created_class_count += 1
            classes[course] = school_class
        student = User(
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            display_name=str(row["display_name"]),
            email=str(row["email"]) if row.get("email") else None,
            is_active=True,
            must_change_password=True,
            roles=[student_role],
            student_profile=StudentProfile(first_name=str(row["first_name"]), last_name=str(row["last_name"])),
            enrolled_classes=[school_class],
        )
        db.add(student)
    job.status = "IMPORTED"
    job.preview_rows = [{key: value for key, value in row.items() if key != "password_hash"} for row in job.preview_rows]
    db.flush()
    return {"job_id": job.public_id, "status": job.status, "imported_count": len(rows), "class_count": created_class_count, "already_imported": False}
