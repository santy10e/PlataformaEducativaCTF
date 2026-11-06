# CYBERLAB v2 — PANEL CTF (alcance reducido)

## 0. Cómo leer este documento

Este prompt REEMPLAZA el alcance del prompt original. Se conserva la visión (plataforma educativa, LAN, 9 meses, seguridad primero), pero ahora solo se construye el **panel y el motor de CTF**. Los CTF y retos concretos NO se crean ahora: se cargarán después desde el panel o por importación. Lo que se entrega es la plataforma lista, vacía y extensible.

Regla de oro: **todo lo que cambie con el tiempo es DATO configurable, no código.** Categorías, dificultades, escalas de nota, puntuación, textos, tipos de reto, roles y permisos viven en la base de datos y se editan desde el panel.

---

## 1. Alcance

### DENTRO (construir ahora)
1. Autenticación, sesiones y RBAC (ADMIN, INSTRUCTOR, STUDENT) con permisos granulares editables.
2. Gestión de usuarios, clases/grupos e importación CSV de estudiantes.
3. **Eventos CTF** (equivalente a "un CTF"): nombre, descripción, reglas, ventana de fechas, modo, visibilidad, clase asignada, estado.
4. **Retos (challenges)**: CRUD completo, categorías, dificultad, puntos, archivos adjuntos, hints, flags, prerequisitos, orden, visibilidad.
5. **Flags**: estática, regex, múltiples flags por reto, y **flag dinámica por estudiante** (HMAC derivada de student_id + challenge_id + secreto del servidor). Validación solo en servidor.
6. **Envíos (submissions)** con registro de intentos, límite de intentos y rate limiting.
7. **Hints** con costo y orden; descuento de puntos registrado.
8. **Cronómetro server-side** (started_at / completed_at, nunca confiar en el navegador).
9. **Puntuación configurable** por evento y por reto (base, bonus de tiempo, penalización por hints, intentos).
10. **Scoreboard** configurable (activable/desactivable, por clase, por evento, congelable).
11. **Dashboard del estudiante** y **dashboard del profesor** (analítica básica: completados, tiempo promedio, intentos, hints, retos con más fallos).
12. Conversión score → nota con **escala configurable**.
13. Exportación CSV/XLSX.
14. Auditoría de acciones clave.
15. Configuración del sistema desde el panel (`system_settings`).
16. Notificaciones y anuncios del profesor (simples).
17. **Importador de retos** vía ZIP + `challenge.yml` (la estructura se define ahora; los retos reales se suben después).
18. Docker Compose del sistema (nginx, frontend, backend, mysql), `.env.example`, migraciones, seed, docs y tests.

### FUERA (NO construir ahora, pero dejar puntos de extensión)
- LMS completo (cursos/módulos/lecciones/quizzes) → solo dejar el modelo preparado (`module_id` nullable en retos).
- Gamificación avanzada (badges, streaks, logros) → solo tabla `xp_transactions`.
- Lab manager con Docker, instancias por estudiante, VLANs → **definir la interfaz** (sección 5) pero implementar solo el proveedor `static`.
- LDAP / AD / Google / Entra.
- Multi-servidor, balanceo.

Todo lo no implementado se marca `TODO(fase-x)` de forma explícita. **Prohibido** código ficticio que aparente funcionar.

---

## 2. Principios de arquitectura (modular y escalable)

### Backend: monolito modular
Python + FastAPI + SQLAlchemy 2.x + Alembic + MySQL 8 (NO PostgreSQL). Un solo despliegue, pero dividido por **módulos de dominio** con fronteras claras:

```
backend/app/
  core/            # config, db, seguridad, errores, eventos, logging
  modules/
    auth/          # login, sesiones, passwords
    users/         # usuarios, roles, permisos, clases, import CSV
    ctf/           # eventos, retos, categorías, hints, adjuntos
    flags/         # estrategias de flag y validación
    submissions/   # intentos, rate limit, cronómetro
    scoring/       # motor de puntuación y escalas de nota
    scoreboard/
    analytics/
    audit/
    settings/      # system_settings + feature flags
    notifications/
    importer/      # ZIP + challenge.yml
  providers/
    delivery/      # interfaz ChallengeDelivery (static ahora, docker después)
  main.py          # registra módulos
```

Reglas:
- Cada módulo tiene `models.py`, `schemas.py`, `service.py`, `router.py`, `permissions.py`, `tests/`.
- Los routers NO contienen lógica; la lógica vive en `service.py`.
- Un módulo no importa modelos internos de otro: se comunica por servicios públicos o por **eventos de dominio** (`challenge_solved`, `hint_used`, `submission_failed`). Así scoring, notificaciones y auditoría se enganchan sin acoplarse.
- Registro de módulos en un solo lugar (`main.py`), activables por feature flag.
- API versionada `/api/v1`, OpenAPI completo (el frontend genera su cliente desde ahí).

### Extensibilidad por registro (plugins internos)
- **FlagStrategy**: `static`, `regex`, `dynamic_hmac`. Añadir otra = una clase + registro.
- **ChallengeType**: `jeopardy` ahora; `scenario`, `multi_stage` después.
- **ScoringStrategy**: `fixed`, `time_decay`, `dynamic_by_solves`.
- **ChallengeDelivery**: ver sección 5.

### Todo configurable desde el panel
Categorías, dificultades (nombre, color, orden, multiplicador), escala de notas, pesos de puntuación, límites de intentos, tiempos, textos de reglas, ranking on/off, congelado de scoreboard, política de contraseñas, duración de sesión.

### Roles y permisos
Permisos granulares (`challenge.create`, `submission.view_all`, `user.import`, …) asignados a roles. Los 3 roles base vienen en el seed, pero el ADMIN puede crear roles nuevos o ajustar permisos sin tocar código. Verificación en servidor siempre; el frontend solo oculta UI.

---

## 3. Base de datos (MySQL 8, normalizada, migraciones Alembic)

Tablas mínimas: `users, roles, permissions, role_permissions, user_roles, sessions, classes, class_students, ctf_events, ctf_event_classes, categories, difficulties, challenges, challenge_files, challenge_prerequisites, flags, hints, hint_usage, submissions, solves, scores, grade_scales, grade_scale_items, xp_transactions, announcements, notifications, audit_logs, system_settings, import_jobs`.

Requisitos:
- Charset `utf8mb4`, InnoDB, claves foráneas, índices en consultas de scoreboard y submissions.
- `submissions` y `audit_logs` pensadas para crecer (índices por fecha, usuario, reto).
- Flags guardadas **hasheadas** cuando son estáticas (comparación en tiempo constante); la dinámica no se almacena, se recalcula con HMAC.
- Soft-delete en retos y eventos (`deleted_at`).
- Seed idempotente.

---

## 4. Seguridad (mínimos obligatorios)

- Passwords con Argon2id. Cookies HTTP-only, Secure/SameSite, expiración y logout real. CSRF donde aplique.
- Rate limiting en login y en envío de flags (por usuario y por IP).
- Validación estricta con Pydantic. ORM/queries parametrizadas.
- Uploads: validar tipo real, tamaño máximo, nombres saneados, almacenamiento fuera del webroot, **nunca ejecutar nada subido**.
- El importador ZIP debe protegerse contra zip-slip, zip bombs y rutas absolutas; solo extrae a un directorio temporal controlado y valida el manifest.
- Un estudiante jamás ve: flags, soluciones, hints no desbloqueados, datos de otros estudiantes (salvo scoreboard público configurado).
- Auditoría de: login/logout, creación/edición/publicación de retos, flag success/failure, hints, cambios de configuración, import CSV.
- Secretos solo en `.env`; ninguno en el repositorio.
- Funciona 100% offline: **cero dependencias de CDN** (fuentes, iconos y scripts van empaquetados).

---

## 5. Punto de extensión para laboratorios Docker (definir, no implementar)

```python
class ChallengeDelivery(Protocol):
    def prepare(self, student, challenge) -> DeliveryInfo: ...
    def reset(self, student, challenge) -> DeliveryInfo: ...
    def teardown(self, student, challenge) -> None: ...
```

- Ahora: `StaticDelivery` (adjuntos, texto, enlaces o URL fija).
- Después: `DockerDelivery` en un servicio `lab-manager` separado, con aislamiento de red, límites de CPU/RAM/PIDs, sin `--privileged`, sin `docker.sock` expuesto.
- La tabla de retos ya incluye `delivery_type` y `delivery_config` (JSON) para que el cambio futuro no requiera migrar el modelo.

---

## 6. Formato de importación de retos (para subirlos después)

ZIP con `challenge.yml` (o un `ctf.yml` con varios retos):

```yaml
name: Nombre del reto
slug: nombre-del-reto
category: web
difficulty: beginner
points: 100
type: jeopardy
description_md: descripcion.md
flags:
  - id: f1
    strategy: static | regex | dynamic_hmac
    value: "..."          # no aplica a dynamic_hmac
hints:
  - { id: h1, text: "...", cost: 5, order: 1 }
files: [ files/capture.pcap ]
prerequisites: [ otro-reto ]
delivery: { type: static }
```

El importador: valida → muestra vista previa y errores → permite corregir → crea en estado `DRAFT` → el profesor publica. Debe ser idempotente por `slug`.

---

## 7. Frontend: diseño propio, NO plantilla de IA

### Stack
React + Vite + TypeScript, **Tailwind CSS** (build local), React Router, TanStack Query, TanStack Table, React Hook Form + Zod, Zustand solo para estado de UI, primitivas accesibles con Radix UI **copiadas y adaptadas al proyecto** (no una librería de componentes con estilo por defecto). Cliente API generado desde OpenAPI. i18n con español por defecto.

### Estructura por features
```
frontend/src/
  app/            # router, providers, layouts
  design/         # tokens, tailwind preset, componentes base (propios)
  features/       # auth, ctf, challenges, scoreboard, users, classes, settings, analytics...
  shared/         # hooks, utilidades, api
```
Cada feature es autocontenida (páginas, componentes, hooks, queries). Agregar una sección = agregar una carpeta y una entrada en el registro de navegación.

### Identidad visual (importante)
Evitar de forma explícita lo típico de "UI hecha por IA": degradados morados/azules, glassmorphism, tarjetas redondeadas idénticas con sombras suaves, emojis como iconos, estética hacker de lluvia verde.

Dirección: **"consola de operaciones"**, sobria y profesional, apropiada para un colegio.
- Rejilla visible y estricta, bordes finos (hairlines), densidad de información cuidada, mucho uso de tablas bien diseñadas.
- Un solo color de acento con significado; el resto neutros con carácter (no gris genérico). Estados con color **y** forma/icono/texto.
- Tipografía con personalidad: una sans de lectura (p. ej. IBM Plex Sans o similar) + una monoespaciada (p. ej. JetBrains Mono) para datos, comandos, flags, IDs y cronómetros. **Fuentes autoalojadas.**
- Iconos de un set único y consistente (Lucide), tamaños y grosor uniformes.
- Modo oscuro por defecto y modo claro completo, ambos con tokens en variables CSS (`design/tokens`), no valores sueltos.
- Microinteracciones útiles (envío de flag, desbloqueo de hint, cambio de estado), no decorativas. Respetar `prefers-reduced-motion`.
- Estados vacíos, de carga (skeletons), de error y de éxito diseñados a propósito, con mensajes claros en español.

### UX superior
- **Paleta de comandos** (Ctrl/Cmd+K): saltar a retos, usuarios, ajustes, crear reto.
- Atajos de teclado en el panel (documentados en un modal).
- Tablas con búsqueda, filtros guardados, orden, selección múltiple, acciones masivas y exportación.
- Formularios con autoguardado de borradores, validación en línea y confirmaciones solo en acciones destructivas (con opción de deshacer cuando sea posible).
- Editor Markdown con vista previa en vivo para descripciones y soluciones.
- Pantalla del reto para el estudiante: enunciado, adjuntos, hints con costo visible, campo de flag con feedback inmediato, intentos restantes, cronómetro server-side, estado.
- Scoreboard con actualización periódica y vista de evolución en el tiempo.
- Panel del profesor: vista de "clase en vivo" (estudiante · estado · tiempo · intentos · hints · score).
- Accesibilidad: contraste AA, navegación completa por teclado, foco visible, labels/ARIA, nunca depender solo del color.
- Desktop primero, utilizable en tablet y móvil.

Antes de codificar pantallas, entregar un **mini sistema de diseño** (tokens, tipografía, componentes base: Button, Input, Table, Badge, Dialog, Toast, Tabs, Command palette) y revisarlo conmigo.

---

## 8. Infraestructura

- `docker-compose.yml`: `nginx`, `frontend`, `backend`, `mysql` (+ `worker` opcional para tareas diferidas y limpieza).
- Volúmenes separados para base de datos, uploads y definiciones de retos.
- Backups automáticos de MySQL y uploads (script + documentación); no respaldar contenedores efímeros.
- `.env.example` con: `DATABASE_URL, MYSQL_*, SECRET_KEY, FLAG_HMAC_SECRET, ADMIN_EMAIL, SESSION_TTL, MAX_UPLOAD_MB`.
- Acceso por `http://cyberlab.local` o IP del servidor, sin Internet.

---

## 9. Fases (construir una a la vez)

**FASE 1 — Fundación:** repo, Compose, MySQL + migraciones, auth, RBAC con permisos, settings, auditoría base, layout del frontend + sistema de diseño.
**FASE 2 — Usuarios y clases:** CRUD, import CSV, clases.
**FASE 3 — Núcleo CTF:** categorías/dificultades editables, eventos, retos, hints, adjuntos, flags (3 estrategias), submissions, cronómetro, scoring, notas.
**FASE 4 — Experiencia estudiante:** dashboard, pantalla de reto, scoreboard, historial.
**FASE 5 — Experiencia profesor:** dashboard analítico, clase en vivo, exportaciones, anuncios, notificaciones.
**FASE 6 — Importador de retos:** ZIP + `challenge.yml`, vista previa, DRAFT → PUBLISHED.
**FASE 7 — Endurecimiento y documentación.**

Al terminar CADA fase: correr tests, revisar seguridad, revisar UX, revisar la BD, documentar y dejar el sistema ejecutable. Detenerse y reportar antes de empezar la siguiente.

---

## 10. Tests obligatorios

Auth y sesiones · autorización por rol y permiso · validación de flags (estática, regex, dinámica) · **flag de otro estudiante rechazada** · rate limit · cronómetro server-side · scoring y escala de notas · hints (costo y orden) · **estudiante no ve soluciones ni hints bloqueados** · **estudiante no accede a endpoints admin** · importador (zip-slip, manifest inválido, idempotencia) · migraciones desde cero.

---

## 11. Seed de demostración

Admin, instructor, 3 estudiantes, 1 clase, 1 evento CTF "Demo", 6 categorías, 4 dificultades, escala de notas 1–10, y **3 retos de ejemplo claramente marcados como DEMO** (uno con flag estática, uno regex, uno dinámica) para probar el flujo completo. No es contenido del curso.

---

## 12. Documentación

`README.md`, `INSTALLATION.md`, `ADMIN_GUIDE.md`, `TEACHER_GUIDE.md`, `STUDENT_GUIDE.md`, `CHALLENGE_FORMAT.md`, `SECURITY.md`, `BACKUP.md`, `NETWORK.md`, `TROUBLESHOOTING.md`, `DESIGN_SYSTEM.md`, `EXTENDING.md` (cómo añadir un módulo, una estrategia de flag, una pantalla).

---

## 13. Criterios de aceptación

1. Se levanta con un solo `docker compose up` desde cero siguiendo la documentación.
2. El profesor crea estudiantes (manual y CSV) y una clase.
3. El profesor crea un evento CTF y un reto completo (flags, hints, puntos, adjuntos) **solo desde la interfaz**.
4. El profesor cambia categorías, dificultades, pesos de puntuación y escala de notas **sin tocar código ni BD**.
5. El estudiante resuelve un reto: intenta, usa hint, envía flag, ve score.
6. La flag dinámica de un estudiante NO funciona para otro.
7. El tiempo lo mide el servidor.
8. Scoreboard y dashboards muestran datos correctos.
9. El profesor exporta resultados a CSV/XLSX.
10. El importador ZIP carga un reto de prueba en DRAFT y se puede publicar.
11. Funciona sin Internet.
12. La UI cumple la dirección visual de la sección 7 y supera los chequeos de accesibilidad básicos.
13. Todos los tests pasan; lo no implementado está marcado `TODO`.

---

## 14. Instrucción final

Construye un producto **mantenible y extensible**, no un prototipo visual. Prioriza: seguridad, modularidad, configurabilidad, claridad de código y experiencia de usuario. Si una decisión de diseño bloquea la escalabilidad futura, detente y pregunta antes de continuar.