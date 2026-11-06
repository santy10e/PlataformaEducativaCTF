"""The 9-month course plan of SPEC §14 as editable seed data.

It is created once as a shared template (no owner): administrators edit it, instructors duplicate it
into their own course. Re-running the seed never overwrites what someone changed.
Suggested external resources are named, never copied, and flagged for verification (SPEC §6.1).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.curriculum.models import Activity, Course, CourseModule, Lesson

COURSE_ID = "00000000-0000-4000-9000-000000000001"
VERIFY = "Verifica disponibilidad, precios, términos de uso y política de privacidad antes de usarlo con estudiantes."

PLAN: list[tuple[str, str, list[str], str]] = [
    ("Linux y fundamentos", "Moverse con soltura en la terminal y entender usuarios, permisos y procesos.",
     ["Navegar el sistema de archivos y leer documentación con `man`", "Gestionar permisos con `chmod` y `chown`", "Encadenar comandos con tuberías y redirecciones"],
     "OverTheWire (Bandit) y guías propias"),
    ("Redes", "Explicar cómo viaja la información entre equipos y observarlo con herramientas.",
     ["Modelo OSI y TCP/IP", "Direcciones IP, puertos y servicios", "Capturar y leer tráfico con un analizador de paquetes"],
     "Cisco Networking Academy y guías propias"),
    ("HTTP y fundamentos web", "Leer peticiones y respuestas HTTP y usar las herramientas del navegador.",
     ["Métodos, cabeceras y códigos de estado", "Cookies y sesiones", "Herramientas de desarrollador del navegador"],
     "Guías propias y herramientas del navegador"),
    ("Seguridad web", "Reconocer vulnerabilidades web comunes y cómo se previenen.",
     ["Inyección y validación de entradas", "XSS y política de seguridad de contenido", "Control de acceso roto"],
     "PortSwigger Web Security Academy y OWASP Juice Shop"),
    ("Linux security y escalada de privilegios", "Detectar configuraciones inseguras en Linux y proponer correcciones.",
     ["Archivos con SUID y permisos amplios", "Servicios y tareas programadas", "Principio de mínimo privilegio"],
     "CyLab Security Academy y guías propias"),
    ("Windows y Active Directory", "Comprender la administración de identidades en redes Windows.",
     ["Usuarios, grupos y políticas", "Dominios y controladores de dominio", "Registros de eventos útiles para defensa"],
     "Contenido propio; recursos por definir"),
    ("Forense y análisis", "Reconstruir lo ocurrido a partir de evidencias digitales sin alterarlas.",
     ["Cadena de custodia y hashes", "Metadatos de archivos", "Línea de tiempo de un incidente"],
     "CyLab Security Academy"),
    ("Red Team / Blue Team", "Practicar ataque y defensa de forma ética dentro de un entorno autorizado.",
     ["Reconocimiento y superficie de ataque", "Detección y respuesta", "Informe técnico y ético"],
     "Mezcla de recursos"),
    ("Capstone / CTF final", "Integrar lo aprendido en un CTF propio del curso.",
     ["Planificar y documentar la resolución", "Trabajo en equipo y comunicación", "Reflexión sobre el aprendizaje del año"],
     "CTF propio o evento en una plataforma externa"),
]


def _lesson_body(month: int, title: str, goal: str, topics: list[str], resources: str) -> str:
    items = "\n".join(f"- {topic}" for topic in topics)
    return (
        f"## Mes {month}: {title}\n\n**Objetivo:** {goal}\n\n### Qué vas a trabajar\n{items}\n\n"
        "### Cómo trabajaremos\nCada semana combina una explicación breve, retos CTF propios del curso y una reflexión escrita "
        "sobre lo aprendido. Practica solo en los entornos y objetivos que autorice tu docente.\n\n"
        f"### Recursos complementarios sugeridos\n{resources}. {VERIFY}\n"
    )


def seed_curriculum_plan(db: Session) -> None:
    if db.scalar(select(Course.id).where(Course.public_id == COURSE_ID)) is not None:
        return
    course = Course(public_id=COURSE_ID, owner_user_id=None, status="DRAFT", title="Ciberseguridad — plan de 9 meses",
                    description_markdown="Propuesta inicial para bachillerato. Es una plantilla: duplícala para tu clase y ajústala libremente.")
    db.add(course)
    db.flush()
    for month, (title, goal, topics, resources) in enumerate(PLAN, start=1):
        module = CourseModule(public_id=f"00000000-0000-4000-9001-{month:012d}", course_id=course.id, title=f"Mes {month} · {title}",
                              description_markdown=goal, sort_order=month, status="PUBLISHED")
        db.add(module)
        db.flush()
        lesson = Lesson(public_id=f"00000000-0000-4000-9002-{month:012d}", module_id=module.id, title=f"Orientación: {title}",
                        content_markdown=_lesson_body(month, title, goal, topics, resources), estimated_minutes=15, sort_order=0, status="PUBLISHED")
        db.add(lesson)
        db.flush()
        db.add(Activity(public_id=f"00000000-0000-4000-9003-{month:012d}", lesson_id=lesson.id, type="lesson_read",
                        title="He leído la orientación del mes", description_markdown="Marca la lectura cuando hayas revisado los objetivos del mes.",
                        sort_order=0, points=10, xp=10, status="PUBLISHED", config={}))
    db.flush()
