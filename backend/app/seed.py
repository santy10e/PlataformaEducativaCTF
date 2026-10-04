from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.config import settings
from app.database import engine
from app.models import (
    Category,
    Challenge,
    CtfEvent,
    Difficulty,
    Permission,
    Role,
    SystemSetting,
    User,
)
from app.scoring_service import add_flag
from app.security import hash_password
from app.settings_service import DEFAULTS

PERMISSIONS = {
    "role.view": "View roles",
    "role.create": "Create roles",
    "role.update": "Edit roles",
    "role.delete": "Delete roles",
    "settings.view": "View system settings",
    "settings.update": "Edit system settings",
    "audit.view": "View audit logs",
    "challenge.view": "View challenges",
    "challenge.create": "Create challenges",
    "challenge.update": "Edit challenges",
    "challenge.delete": "Delete challenges",
    "challenge.submit": "Submit challenge flags",
    "scoreboard.view": "View CTF scoreboards",
    "scoreboard.manage": "Freeze CTF scoreboards and edit grade scales",
    "category.create": "Create challenge categories",
    "category.update": "Edit challenge categories",
    "category.delete": "Delete unused challenge categories",
    "difficulty.create": "Create challenge difficulties",
    "difficulty.update": "Edit challenge difficulties",
    "difficulty.delete": "Delete unused challenge difficulties",
    "event.view": "View CTF events",
    "event.manage": "Manage CTF events",
    "user.view": "View users within assigned scope",
    "user.create": "Create students and instructors within assigned scope",
    "user.update": "Edit users within assigned scope",
    "user.password_reset": "Reset user passwords",
    "class.view": "View assigned classes",
    "class.create": "Create classes",
    "class.update": "Edit assigned classes",
    "class.delete": "Delete classes",
    "class.manage_students": "Manage class membership",
    "import.preview": "Preview student CSV imports",
    "import.execute": "Confirm student CSV imports",
}
ROLE_PERMISSIONS = {
    "ADMIN": list(PERMISSIONS),
    "INSTRUCTOR": ["scoreboard.view", "scoreboard.manage", "challenge.view", "challenge.create", "challenge.update", "category.create", "category.update", "difficulty.create", "difficulty.update", "event.view", "event.manage", "settings.view", "user.view", "user.create", "user.update", "class.view", "class.create", "class.update", "class.manage_students", "import.preview", "import.execute"],
    "STUDENT": ["challenge.view", "challenge.submit", "scoreboard.view", "event.view"],
}


def seed() -> None:
    if not settings.admin_password:
        raise RuntimeError("ADMIN_PASSWORD must be set before seeding")
    with OrmSession(engine) as db:
        permissions: dict[str, Permission] = {}
        for code, description in PERMISSIONS.items():
            item = db.scalar(select(Permission).where(Permission.code == code))
            if item is None:
                item = Permission(code=code, description=description)
                db.add(item)
                db.flush()
            permissions[code] = item
        roles: dict[str, Role] = {}
        for name, permission_codes in ROLE_PERMISSIONS.items():
            role = db.scalar(select(Role).where(Role.name == name))
            if role is None:
                role = Role(name=name, is_system=True)
                db.add(role)
            role.is_system = True
            role.permissions = [permissions[code] for code in permission_codes]
            roles[name] = role
        user = db.scalar(select(User).where(User.username == settings.admin_username))
        if user is None:
            user = User(username=settings.admin_username, password_hash=hash_password(settings.admin_password), display_name="System Administrator", is_active=True, roles=[roles["ADMIN"]])
            db.add(user)
        else:
            user.is_active = True
            if roles["ADMIN"] not in user.roles:
                user.roles.append(roles["ADMIN"])
        for key, (value, description) in DEFAULTS.items():
            if db.get(SystemSetting, key) is None:
                db.add(SystemSetting(key=key, value=value, description=description))
        from app.models import GradeScale
        for index, (min_score, grade_value, label) in enumerate(((0, 1.0, "Insuficiente"), (50, 2.0, "Básico"), (100, 3.0, "Intermedio"), (150, 4.0, "Avanzado"), (200, 5.0, "Excelente"))):
            if db.scalar(select(GradeScale.id).where(GradeScale.name == "Escala base", GradeScale.min_score == min_score)) is None:
                db.add(GradeScale(name="Escala base", min_score=min_score, grade_value=grade_value, label=label, sort_order=index))
        for index, name in enumerate(("Web", "Criptografía", "Forense", "Ingeniería inversa", "Explotación", "Miscelánea")):
            if db.scalar(select(Category.id).where(Category.name == name)) is None:
                db.add(Category(name=name, color="#587666", sort_order=index, multiplier=1.0))
        for index, (name, multiplier) in enumerate((("Inicial", 0.75), ("Intermedio", 1.0), ("Avanzado", 1.5), ("Experto", 2.0))):
            if db.scalar(select(Difficulty.id).where(Difficulty.name == name)) is None:
                db.add(Difficulty(name=name, color="#587666", sort_order=index, multiplier=multiplier))
        db.flush()
        demo_public_id = "00000000-0000-4000-8000-000000000009"
        demo_event = db.scalar(select(CtfEvent).where(CtfEvent.public_id == demo_public_id))
        if demo_event is None:
            demo_event = CtfEvent(public_id=demo_public_id, name="[DEMO] Paquete de práctica Cyberlab", status="DRAFT",
                visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="Contenido de demostración. Importa o duplica este evento para crear tus propias actividades.")
            db.add(demo_event)
            db.flush()
        demo_specs = (
            ("demo-request-trace", "[DEMO] Sigue la pista de la solicitud", "Web", "Inicial", 100,
             "Identifica el valor del encabezado de demostración y envía la bandera indicada.", "CYBERLAB{demo_header_trace}"),
            ("demo-cipher-notebook", "[DEMO] Cuaderno de cifrado", "Criptografía", "Inicial", 100,
             "Una cadena de práctica fue transformada con una regla sencilla. Documenta cada paso antes de responder.", "CYBERLAB{demo_cipher_notes}"),
            ("demo-evidence-room", "[DEMO] Sala de evidencias", "Forense", "Inicial", 100,
             "Revisa la evidencia de demostración que acompaña el reto y relaciona los hallazgos con la bandera.", "CYBERLAB{demo_evidence_room}"),
        )
        for order, (slug, title, category_name, difficulty_name, points, description, flag_value) in enumerate(demo_specs):
            challenge = db.scalar(select(Challenge).where(Challenge.event_id == demo_event.id, Challenge.slug == slug))
            if challenge is None:
                category = db.scalar(select(Category).where(Category.name == category_name))
                difficulty = db.scalar(select(Difficulty).where(Difficulty.name == difficulty_name))
                assert category is not None and difficulty is not None
                challenge = Challenge(public_id=f"00000000-0000-4000-8000-{order + 10:012d}", event_id=demo_event.id,
                    category_id=category.id, difficulty_id=difficulty.id, slug=slug, title=title,
                    description_markdown=description, status="DRAFT", points=points, sort_order=order,
                    delivery_type="STATIC", delivery_config={})
                db.add(challenge)
                db.flush()
                add_flag(db, challenge, "STATIC", flag_value, None)
        db.commit()


if __name__ == "__main__":
    seed()
