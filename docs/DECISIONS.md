# Decisions

- Phase 0 uses uv for Python dependency management.
- Phase 2 uses a professional university fieldbook identity with the user's later navy/cyan palette (`#142550`, `#1BAEC3`) and Apple-like system sans stack, plus IBM Plex Mono for technical labels. Tokens and responsive workspaces are documented in `docs/DESIGN_SYSTEM.md`.
- Frontend route visibility reads the permission codes returned by `/api/v1/auth/me`; the endpoint returns the union of the authenticated user's role permissions.
- Playwright's Chromium smoke test uses explicit `CYBERLAB_E2E_USERNAME` and `CYBERLAB_E2E_PASSWORD` environment variables. It skips cleanly when those are not configured.
- MySQL is isolated on an internal Compose network; only the backend joins that network.
- The auth foundation uses opaque, server-side sessions; database rows store SHA-256 token digests, login passwords use Argon2id, and unsafe methods require a session-bound CSRF header.
- Python test dependencies and runtime dependencies are pinned in `uv.lock`; frontend packages are locked in `package-lock.json`.
- Phase 4 challenge files are stored under a separate Compose named volume (`/app/storage/challenge-files`), addressed by generated storage IDs, with type detection from file signatures and authenticated downloads. Only static delivery is accepted in this phase.
- Student challenge responses omit `flag_hash`, `delivery_config`, hint content and internal challenge IDs. They include safe ordered hint metadata plus explicit prerequisite lock reasons for the Phase 7 student catalog; hint text is returned only after that learner unlocks it. Events with a missing start or end date are treated as unbounded on that side of the active window.
- Phase 5 stores flag strategies per challenge: SHA-256 hashes for static flags, validated regex patterns for regex flags, and per-student HMAC values derived from a dedicated `FLAG_HMAC_SECRET` (falls back to `BACKEND_SECRET_KEY` for existing local deployments). The XP ledger is append-only during play and unique source keys make solve awards idempotent; instructor resets explicitly remove that learner/challenge ledger slice.
- Phase 5 timers and solve times use UTC server timestamps. MySQL row locks serialize submissions after start; a unique solve ledger key is a second guard against double scoring. Scoreboard freezes are persisted snapshots by global, class, or event scope.
- Phase 5 scoring configuration is restricted to strategy-specific keys/ranges; regex flags use a bounded safe subset instead of unrestricted Python regular expressions. XP is a signed append ledger with unique solve/hint source keys; instructor progress reset removes only that student/challenge slice. Phase 7 exposes a student's own XP, timing, attempt history and notifications, with read state scoped to the current learner.
- Phase 8 analytics enforce instructor ownership while resolving shared events: event reports include only classes owned by that instructor. Inactivity is surfaced as a seven-day signal for teaching review, not as a judgement about learner ability. Grade selection is explicit in reports and included in exports; display typography uses local system-font stacks to preserve offline operation.
- Phase 9 reads bounded ZIP members in memory instead of extracting untrusted paths, and only writes referenced attachments under server-generated storage IDs. Exported static flags contain their SHA-256 matcher, never their original plaintext; package imports always result in draft challenges.
- Phase 10 uses same-origin requests without permissive CORS, a restrictive self-hosted CSP and standard browser security headers. The API trusts `X-Forwarded-Proto` only as supplied by the configured institutional gateway; the base Compose deployment remains HTTP-only.
- Phase 10 maintenance runs every six hours, prunes sessions expired/revoked for seven days and only removes stale `.tmp` files from the app-owned `/tmp/cyberlab` directory. No uploaded challenge file is eligible for this cleanup.
- Phase 10 backups pair a transactional MySQL dump with a tarball of `/app/storage`, SHA-256 checksums and 14-day rotation. Restore requires explicit `--confirm`, validates archive entries, and was rehearsed against disposable Compose volumes with a non-empty attachment.
- Submission rate limiting retains the Phase 5 user-and-IP contract. The concurrency smoke uses 20 distinct authenticated students and IPs so it measures parallel scoring without treating unrelated requests as a single rate-limit burst.
- In-process rate-limit maps are protected by locks and capped at 10,000 keys; when full they expire old windows and fail closed for new keys. User buckets keep their configured threshold, while shared proxy IP bursts have a 60/minute minimum for submissions and 120/5-minute login cap.
- Teacher CSV exports prefix spreadsheet formula-leading untrusted text with an apostrophe; XLSX cells remain inline strings. This prevents student display names from executing as formulas when opened in spreadsheet software.
- The plan references `CYBERLAB_PROMPT_V2_PANEL_CTF.md` or `/docs/SPEC.md`, but neither is in the available workspace; exact specification acceptance points 1–13 remain unverified rather than inferred.

## Auditoría integral (2026-10-03/04) — ver `docs/FULL_AUDIT.md` y `docs/REPAIR_PLAN.md`

- Propiedad de eventos: un no-administrador solo puede crear o modificar un evento si incluye al menos una clase que imparte; al editar un evento compartido se conservan las clases de los demás docentes. No se añadió una columna `created_by` (habría exigido migrar datos sin dueño conocido); la propiedad sigue derivándose de las clases asignadas, como ya hacían las lecturas.
- Matrícula: los docentes solo reorganizan estudiantes que ya están en alguna de sus clases; incorporar estudiantes de otros grupos o sin clase es tarea de administración (o de alta/importación CSV del propio docente).
- Importación CSV: el curso se resuelve por nombre **dentro del alcance del actor**, sin depender de `academic_period`; un nombre ambiguo invalida la fila en la vista previa. Las clases creadas por una importación de ADMIN quedan sin docente asignado.
- Solo ADMIN crea cuentas INSTRUCTOR (el código ya lo pretendía con el mensaje «instructors may only create students»; la descripción del permiso `user.create` decía lo contrario). Si el colegio necesita lo contrario, debe resolverse con un permiso específico, no reabriendo este camino.
- `must_change_password` se aplica en el servidor: con contraseña temporal solo responden `/auth/*`; el resto devuelve `403 PASSWORD_CHANGE_REQUIRED`. Cambiar la contraseña revoca las demás sesiones.
- Limitador de login: solo cuentan los fallos, la clave es equipo+usuario (más un tope por equipo) y un acceso correcto la reinicia. Nginx sobrescribe `X-Forwarded-For` con `$remote_addr` y uvicorn confía en él (`--forwarded-allow-ips='*'`) porque el backend no publica puerto y solo Nginx lo alcanza.
- El backend ejecuta `alembic upgrade head` al arrancar. `make migrate`/`make seed` se ejecutan dentro del contenedor; `make reset-db` exige `CONFIRM=yes`. `make test` ya no incluye e2e: `make e2e` los ejecuta contra un stack real y falla (no se salta) sin credenciales.
- `make seed` deja intactos los permisos ya configurados de INSTRUCTOR/STUDENT (antes los sobrescribía en cada ejecución y anulaba lo editado en «Roles»); el rol ADMIN siempre recibe todos. Consecuencia: un permiso nuevo en una actualización futura debe asignarse a esos roles desde «Roles».
- Publicar un reto exige al menos una bandera habilitada y no se puede borrar la última de un reto publicado.
- UI: se eliminaron las pantallas placeholder. Se implementaron Configuración, Roles, Bitácora, Marcador para docentes/administración y Ayuda. «Recursos» se retiró de la navegación porque no había contenido real que servir. «Retos» y «Eventos» solo aparecen a estudiantes; el personal trabaja desde «Diseñar CTF». El pie solo dice «SESIÓN CIFRADA» bajo HTTPS (la instalación base es HTTP).
- Las hojas de estilo de estudiante/docencia usaban hex fijos; se sustituyeron por los tokens `--campus-*` equivalentes para respetar el CONTRACT y el tema oscuro. Quedan colores heredados sin token equivalente (tonos cálidos antiguos), documentados como deuda.

### Conflictos con CONTRACT que se mantienen (no se cambian en silencio)

- `created_at`/`updated_at`: los ledgers (`xp_transactions`, `audit_logs`, `notifications`, `hint_uses`), `challenge_progress` (usa `started_at`/`completed_at`), `scoreboard_freezes` (`frozen_at`) y los perfiles carecen de alguna de las dos columnas. Añadirlas no aporta información y exigiría backfill; se deja como desviación aceptada.
- «OpenAPI-generated API client»: cinco pantallas usan `fetch` directo (subidas binarias, ZIP y descargas). Es deuda, no una vulnerabilidad: todas envían cookies del mismo origen y el CSRF lo añade el código.
- Roles personalizados: existe su CRUD pero no hay forma de asignarlos a un usuario; la UI solo edita los permisos de los roles existentes. No se añade asignación sin una especificación que diga cómo debe convivir con el alcance docente.
- El contenedor backend sigue ejecutándose como root: pasar a un usuario sin privilegios cambiaría la propiedad requerida del volumen de adjuntos en instalaciones existentes y rompería las subidas tras actualizar. Debe hacerse junto con un paso de migración del volumen.
- `/docs/SPEC.md` sigue sin existir; ninguna afirmación de cumplimiento se refiere a él.

## SPEC v4 recibido (2026-10-04)

- `docs/SPEC.md` v4 sustituye al prompt original y manda sobre cualquier contradicción. La auditoría contra él está en `docs/FULL_AUDIT.md` §12 y la hoja de ruta en `docs/REPAIR_PLAN.md`.
- Aplicado ya porque el SPEC es explícito y no choca con nada: el ranking para estudiantes viene **desactivado por defecto** (`scoreboard_enabled=False`, §4 y §7.5). En instalaciones existentes el valor guardado se conserva (el seed no sobrescribe ajustes).
- **Conflicto abierto D1 (no se cambia en silencio):** el SPEC §12 pide identidad «consola de operaciones», modo oscuro por defecto; la entrada de fase 2 de este archivo y `CLAUDE.md` registran como aprobada la identidad «cuaderno universitario» en modo claro.
- **Conflicto abierto D2:** el SPEC §9 nombra tablas (`flags`, `submissions`, `hint_usage`, `activity_hints`…) y trata `ctf_challenge` como tipo de actividad; el esquema actual usa `challenge_flags`, `challenge_submissions`, `hint_uses`, `hints` y una tabla `challenges` independiente.
- **Conflicto abierto D3:** el puntaje §7.1 (base/tiempo/reflexión/pistas/piso) y el XP de §7.5 (no afecta la nota) difieren del motor actual, en el que el XP es la puntuación y la nota se deriva de él.
- El SPEC §2 retira el requisito de funcionar solo en LAN. Se mantiene la ausencia de CDN porque el CONTRACT sigue exigiéndola.

## Decisiones del usuario sobre SPEC v4 (2026-10-04)

- **D1:** se mantiene la identidad «cuaderno universitario», **personalizada y elevada** («con esteroides»), en lugar de la «consola de operaciones» del SPEC §12. Las pantallas nuevas la aplican desde ya; la revisión global de lo existente se hará como fase visual propia con la página `/design` para aprobación (SPEC §12).
- **D2:** `ctf_challenge` es un tipo de actividad que **referencia** un reto existente (`config.challenge_id`); las tablas y la API del motor CTF se conservan.
- **D3:** la fórmula del §7.1 será la estrategia por defecto de los eventos nuevos (fase 6 del SPEC); FIXED/TIME_DECAY/DYNAMIC_BY_SOLVES siguen registradas.
- **D4:** los módulos nuevos se crean como `backend/app/modules/<nombre>/` (`models, schemas, service, router, permissions`); los existentes se migran cuando se toquen.

## Fase 4 del SPEC — currículo y actividades (2026-10-05)

- Propiedad de cursos: `courses.owner_user_id`. El docente gestiona los suyos; un curso sin dueño es una **plantilla compartida** que solo edita ADMIN y que cualquier docente puede duplicar. Un curso se asigna a clases y solo con clases propias (no-ADMIN); al reasignar se conservan las clases de otros docentes.
- Visibilidad para estudiantes: curso, módulo, lección y actividad deben estar `PUBLISHED` y el curso asignado a una de sus clases. Con prerrequisitos pendientes la actividad aparece bloqueada sin enunciado, configuración ni pistas.
- Estados: una actividad completada (lectura, cuestionario, ejercicio correcto, revisión aprobada) queda `APPROVED`. Un cuestionario puede repetirse dentro de su límite de intentos y conserva el mejor resultado; un ejercicio automático incorrecto vuelve a `IN_PROGRESS`; `NEEDS_CHANGES` y `REJECTED` admiten un nuevo envío.
- La puntuación guardada en `activity_progress.score` es el resultado bruto de la actividad. El costo de las pistas se registra en `hint_usage` y lo aplicará la estrategia §7.1 en la fase 6; hasta entonces no descuenta nada (`TODO(fase-6)`).
- `ctf_challenge` no admite envíos propios: su estado se deriva de `challenge_progress` y las pistas son las del reto. Solo puede referenciar retos de eventos que el docente gestiona.
- Proyectos: entrega de texto y/o enlace http(s). Los archivos esperan al canal de subida validado de las evidencias (`TODO(fase-11)`).
- `external_challenge` no se registra hasta la fase 11 para no ofrecer un tipo sin flujo de evidencias.
- Dificultades: se mantienen los nombres en español (Inicial/Intermedio/Avanzado/Experto) como equivalentes de BEGINNER…EXPERT del SPEC §5, porque la interfaz es en español y son datos editables.
- Tests de los módulos nuevos en `backend/tests/` (la configuración de pytest solo recorre esa carpeta), uno por módulo (`test_curriculum.py`).
- Frontend: primera feature en `src/features/curriculum/` (SPEC §8.2); las pantallas existentes se moverán a features cuando se toquen (D4).
- Identidad D1 aplicada a las pantallas nuevas: índice numerado, reglas finas, etiquetas monoespaciadas, estados con color y texto, solo tokens `--campus-*` (claro y oscuro).
