# SPEC — CYBERLAB (Portal educativo de ciberseguridad en español)

> Versión 4 · Documento maestro (CTF propios desde el MVP). Reemplaza al prompt original y a `CYBERLAB_PROMPT_V2_PANEL_CTF.md`.
> Los prompts por fase (`CYBERLAB_FASES.md`) deben leerse junto con este documento. Si hay contradicción, **manda este SPEC**.

---

## 1. Visión

CyberLab es un **portal educativo en español** para un curso de ciberseguridad de bachillerato (~9 meses). Organiza el currículo, explica en español y hace seguimiento del progreso y las notas. Los ejercicios prácticos son principalmente **retos CTF propios** (con flags validadas en servidor, cronómetro, pistas y puntuación), diseñados y subidos por el profesor desde el panel. Las **plataformas externas** (p. ej. CyLab Security Academy) son un complemento enlazado desde el currículo.

**Principio fundamental:** CyberLab es a la vez **plataforma pedagógica y plataforma CTF propia**; las plataformas externas complementan, no sustituyen. Separa con claridad:

- CONTENIDO EDUCATIVO (lecciones en español)
- ACTIVIDADES PRÁCTICAS (propias o externas)
- EVALUACIÓN (notas, XP, escala académica)
- ADMINISTRACIÓN (usuarios, clases, configuración)
- ANALÍTICA (progreso, estadísticas)

**Principio de ingeniería:** todo lo que cambie con el tiempo es **dato configurable** (categorías, dificultades, plataformas, escalas, textos), no código.

---

## 2. Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| Usuarios | Estudiantes de bachillerato (menores de edad), un profesor/administrador |
| Red | Ya **no** se exige funcionar solo en LAN; puede depender de Internet |
| Idioma | Interfaz y contenido propio en **español**; i18n preparado |
| Contenido práctico | **CTF propios desde el MVP** (flags validadas en servidor); enlaces a plataformas externas como complemento |
| Contenido de terceros | **No** se copia ni raspa; se escribe material propio en español que enlaza al recurso. Traducir/replicar solo con permiso o licencia abierta |
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic |
| Base de datos | **MySQL 8+** (NO PostgreSQL) |
| Frontend | React + Vite + TypeScript + **Tailwind**, diseño propio (no plantilla de IA) |
| Sesiones | Server-side con cookie HTTP-only (revocables), no JWT |
| Infraestructura | Docker Compose; Nginx; despliegue en un servidor o VPS |
| Verificación de resultados externos | Manual con aprobación del profesor (ver §6), con integración futura posible |

---

## 3. Alcance

### 3.1 Dentro (MVP)
1. Autenticación, sesiones, RBAC con permisos granulares editables.
2. Usuarios, clases/grupos, importación CSV de estudiantes.
3. **Currículo:** cursos → módulos → lecciones → actividades, con Markdown.
4. **Actividades de varios tipos** (ver §5), con el **reto CTF propio** como tipo principal y la actividad externa como complemento.
5. **Seguimiento de progreso** por estudiante, módulo y clase.
6. **Flujo de evidencia y aprobación** para actividades externas.
7. **Pistas/hints en español** con costo opcional.
8. Evaluación: puntuación, XP, escala de notas configurable.
9. Dashboard del estudiante y del profesor.
10. Anuncios y notificaciones simples.
11. Exportación CSV/XLSX (y PDF simple).
12. Importación de progreso externo por CSV (si aplica).
13. **Motor CTF propio:** eventos, retos, flags estática/regex/**dinámica por estudiante**, envíos con límite de intentos, cronómetro server-side, puntuación configurable y scoreboard configurable.
14. **Creador de retos y CTF desde el panel** e **importador ZIP** (`challenge.yml`) para cargar retos después.
15. Auditoría y configuración desde el panel.
16. Plan de 9 meses como datos de seed, editable.

### 3.2 Opcional / fase posterior (módulos ya previstos en la arquitectura)
- **Integración automática** con plataformas externas vía `ExternalProgressProvider` (solo si ofrecen API o exportación y con permiso).
- Gamificación avanzada (badges, logros, rachas), rankings.
- LDAP/Google/Microsoft SSO.

### 3.3 Fuera de alcance por ahora
- Labs Docker aislados por estudiante y lab-manager. Los retos CTF del MVP son de **entrega estática** (enunciado, archivos adjuntos, enlaces o URL fija); la interfaz `ChallengeDelivery` queda preparada para añadir Docker después.
- Multi-servidor, Kubernetes, VLANs.
- App móvil nativa.

Todo lo no implementado se marca `TODO(fase-N)`. **Prohibido** código ficticio que aparente funcionar.

---

## 4. Roles y permisos

RBAC con permisos `recurso.accion`, asignados a roles; el ADMIN puede crear roles y ajustar permisos. La verificación es **siempre en servidor**.

| Rol | Puede |
|---|---|
| **ADMIN** | Todo: usuarios, roles, configuración, contenido, evaluación, auditoría |
| **INSTRUCTOR** | Crear/editar contenido, actividades y retos CTF (flags, hints, eventos), gestionar clases y asignaciones, aprobar evidencias, ver progreso de sus clases, exportar. No toca configuración crítica |
| **STUDENT** | Ver contenido asignado, completar actividades, enviar evidencias, usar pistas, ver su progreso, XP y notas |

El estudiante **nunca** ve datos de otros estudiantes (salvo ranking público si el profesor lo activa), ni soluciones o pistas no desbloqueadas.

---

## 5. Modelo de contenido

```
CURSO → MÓDULO → LECCIÓN
                 └─ ACTIVIDAD (varios tipos)
```

### Tipos de actividad (registro extensible)
| Tipo | Descripción | Estado |
|---|---|---|
| `lesson_read` | Lección marcada como leída | MVP |
| `quiz` | Preguntas (opción múltiple, texto) con autocorrección | MVP |
| `exercise` | Pregunta/respuesta teórica o práctica | MVP |
| `external_challenge` | Reto en plataforma externa con enlace, guía en español y evidencia | MVP (complemento) |
| `project` | Entrega libre (archivo/enlace/texto) evaluada por el profesor | MVP |
| `ctf_challenge` | Reto CTF propio con flags validadas en servidor, cronómetro, pistas y puntuación | **MVP (núcleo)** |

Cada actividad tiene: título, descripción Markdown, módulo, orden, dificultad, categoría, puntos, XP, prerrequisitos, estado `DRAFT/PUBLISHED/ARCHIVED`, hints, y `config` JSON propio del tipo. Las actividades futuras se añaden **registrando un tipo nuevo**, sin tocar el resto.

### Dificultades y categorías
Editables desde el panel (nombre, color, orden, multiplicador). Seed inicial: BEGINNER / INTERMEDIATE / ADVANCED / EXPERT; categorías: Linux, Redes, Web, Criptografía, Forense, Seguridad general.

---

## 6. Recursos externos y verificación (complemento)

### 6.1 Registro de plataformas (dato, no código)
Tabla `external_platforms`: nombre, URL base, idioma, descripción, logo, notas de licencia/permiso, estado de integración (`manual` / `csv` / `api`). Editable por el admin. El seed incluye **sugerencias** (CyLab Security Academy, OverTheWire, Cisco Networking Academy, PortSwigger Web Security Academy, TryHackMe, OWASP Juice Shop/DVWA) marcadas como *"verificar disponibilidad, precios y términos antes de usar"*.

### 6.2 Actividad externa
`config` JSON: `platform_id`, `url` del reto, `estimated_minutes`, `instructions_md` (guía propia en español), `vocabulary` (glosario), `evidence_policy`.

Contenido propio en español que la acompaña: contexto, teoría previa, glosario, pasos orientativos, pistas, y reflexión posterior ("¿qué aprendiste?"). **No se copian enunciados, archivos ni soluciones de terceros** salvo permiso o licencia que lo permita.

### 6.3 Flujo de evidencia y aprobación
```
Estudiante abre actividad → ve guía en español → clic "Ir al reto" (nueva pestaña)
→ resuelve en la plataforma → vuelve y pulsa "Marcar como hecho"
→ adjunta evidencia (captura, texto, enlace, reflexión) → estado PENDING_REVIEW
→ Profesor revisa → APPROVED / REJECTED (con comentario) / NEEDS_CHANGES
→ se calculan puntos, XP y nota → notificación al estudiante
```
Estados de progreso: `NOT_STARTED, IN_PROGRESS, PENDING_REVIEW, NEEDS_CHANGES, APPROVED, REJECTED`.

Reglas:
- La evidencia admite imagen (validada por tipo real y tamaño), texto y URL.
- Cola de revisión con filtros, aprobación masiva y atajos de teclado.
- Aprobación del profesor siempre auditada.
- Opcional por actividad: política de autoaprobación (p. ej. confianza total en lecciones de lectura).

### 6.4 Integración futura (no MVP)
Interfaz `ExternalProgressProvider` con `sync(student) -> ProgressUpdate[]`. Implementaciones posibles: `CsvImportProvider` (MVP+), `ApiProvider` (solo con API oficial/permiso). Nunca se raspa contenido ni se almacenan credenciales de estudiantes en plataformas de terceros.

---

## 7. Evaluación y calificación

### 7.1 Puntaje de un reto (automático, calculado en el servidor)

Valores **por defecto**, todos editables por evento y por reto desde el panel:

| Componente | Puntos | Regla |
|---|---|---|
| Base | 70 | Se gana al enviar una flag correcta |
| Bonus de tiempo | hasta 20 | Completo si se resuelve dentro del tiempo estimado; baja linealmente hasta 0 al triple del tiempo estimado |
| Reflexión | 10 | Texto corto "¿qué aprendí?" tras resolver (ver 7.4) |
| Pistas | −5 / −10 / −20 | Costo propio de cada pista, visible **antes** de usarla |

Reglas:
- **Piso mínimo** configurable (por defecto 30 % de la base): las pistas nunca dejan el reto en cero si se resolvió.
- **Reto no resuelto:** 0 puntos.
- **Intentos:** límite configurable; penalización por intento fallido existe pero va **apagada** por defecto.
- **Tiempo:** mide el servidor desde `started_at`; el profesor puede pausar o resetear el cronómetro. El bonus de tiempo puede reducirse o desactivarse (recomendado en retos de principiantes para no premiar la prisa).
- **Estrategias de puntaje registrables:** `fixed`, `time_decay`, `dynamic_by_solves`. Esta última solo se recomienda en eventos competitivos en vivo, no en trabajo calificado.
- Un reto resuelto no se vuelve a puntuar. Doble envío concurrente no duplica puntos (transacción/lock).

Ejemplo: reto con 20 min estimados, resuelto en 30 min, 1 pista (−5) y reflexión completa → 70 + 15 + 10 − 5 = **90/100**.

### 7.2 De puntos a nota (automático)

1. Los puntos de los retos de un módulo se comparan con el máximo posible → **porcentaje**.
2. El porcentaje se convierte en nota con una **escala de notas editable** con dos modos: **por tramos** (p. ej. 90–100 = 10) o **lineal** (82 % = 8,2). Modo por defecto: por tramos.
3. La **nota del curso** combina módulos y tipos de actividad con **pesos configurables** (p. ej. 60 % retos CTF, 20 % quizzes, 20 % proyecto).
4. Seed sugerido: escala de aprendizajes del Ministerio de Educación de Ecuador (9–10 domina; 7–8,99 alcanza; 4,01–6,99 próximo a alcanzar). **Debe confirmarse con el colegio** antes de usarla.

### 7.3 Nota provisional y nota final

| Estado | Significado |
|---|---|
| `PROVISIONAL` | Calculada automáticamente y recalculada ante cualquier cambio. El estudiante la ve marcada como "en progreso" |
| `FINAL` | El profesor la **confirma** al cerrar el módulo o periodo. Queda **congelada** |

Reglas:
- Al confirmar se guarda una **instantánea** (escala, pesos, puntajes y fecha vigentes) en `final_grades`.
- Cambiar la escala o los pesos **no recalcula** notas finales; solo afecta periodos abiertos.
- Recalcular una nota final es una **acción explícita del admin**, con motivo obligatorio y registro en auditoría.
- El sistema avisa si hay actividades **sin revisar** antes de permitir cerrar un periodo.

### 7.4 Calificaciones que requieren al profesor
- **Reflexión** (10 pts): revisión del profesor si se quiere valorar el contenido; configurable como "solo completar" o "revisada".
- **Proyectos y actividades externas:** aprobación o rúbrica del profesor.
- **Ajuste manual** de cualquier puntaje, con **motivo obligatorio**, guardado en `score_adjustments` y auditado.

### 7.5 XP, niveles y ranking
- **XP** en `xp_transactions` = puntos × multiplicador de dificultad. **No afecta la nota.**
- Niveles definidos en una tabla editable.
- Rankings opcionales (por clase, módulo, periodo), desactivados por defecto, sin influencia en la nota.
- La analítica describe datos; no emite conclusiones automáticas sobre la capacidad del estudiante.

---

## 8. Arquitectura

### 8.1 Backend: monolito modular
```
backend/app/
  core/            # config, db, seguridad, errores, eventos, logging
  modules/
    auth/ users/ classes/
    curriculum/    # cursos, módulos, lecciones
    activities/    # tipos de actividad (registro), hints
    external/      # plataformas, evidencias, revisión
    progress/      # estados y cálculo de avance
    grading/       # puntuación, XP, escalas, notas
    analytics/ reports/ announcements/ notifications/
    audit/ settings/ imports/
    ctf/           # eventos, retos, categorías, adjuntos
    flags/         # estrategias: static, regex, dynamic_hmac
    submissions/   # envíos, intentos, cronómetro server-side, rate limit
    scoreboard/
    importer/      # ZIP + challenge.yml
  providers/
    external_progress/   # CsvImportProvider, (ApiProvider futuro)
    delivery/            # StaticDelivery (DockerDelivery futuro)
  main.py
```
Reglas: cada módulo con `models, schemas, service, router, permissions, tests`; routers sin lógica; módulos comunicados por servicios públicos y **eventos de dominio** (`activity_approved`, `activity_submitted`, `hint_used`); API versionada `/api/v1` con OpenAPI completo; registros extensibles (`ActivityType`, `ScoringStrategy`, `FlagStrategy`, `ExternalProgressProvider`).

### 8.2 Frontend
React + Vite + TS + Tailwind; React Router; TanStack Query/Table; React Hook Form + Zod; Radix adaptado; Lucide; cliente API generado desde OpenAPI; estructura por features (`features/<nombre>`); navegación desde un registro de rutas por permisos.

### 8.3 Convenciones técnicas (contrato)
- PK `BIGINT UNSIGNED`; `public_id` UUID donde corresponda.
- Fechas `DATETIME(6)` en UTC; zona del colegio configurable (`America/Guayaquil` por defecto).
- Soft-delete en contenido (`deleted_at`). `utf8mb4`, InnoDB.
- API: prefijo `/api/v1`; paginación `{items,total,page,page_size}`; errores `{error:{code,message,details}}` con códigos estables.
- Permisos con dependencia única `require_permission("recurso.accion")`.
- Migraciones Alembic desde BD vacía siempre funcionales; seed idempotente.

---

## 9. Modelo de datos (MySQL 8)

Tablas mínimas:
`users, roles, permissions, role_permissions, user_roles, sessions, classes, class_students, courses, modules, lessons, activities, activity_prerequisites, activity_hints, hint_usage, external_platforms, activity_progress, evidence_items, reviews, ctf_events, ctf_event_classes, challenge_files, flags, flag_attempts, submissions, solves, grade_scales, grade_scale_items, module_grades, grade_periods, final_grades, score_adjustments, xp_transactions, levels, announcements, notifications, audit_logs, system_settings, import_jobs`.

Modelo CTF: las flags estáticas se guardan **hasheadas** (comparación en tiempo constante); las dinámicas no se almacenan, se recalculan con HMAC(`FLAG_HMAC_SECRET`, student_id|challenge_id|flag_id). Las actividades `ctf_challenge` reutilizan hints, prerrequisitos y progreso.

Requisitos: índices para consultas de progreso por clase y cola de revisión; `audit_logs` y `activity_progress` pensadas para crecer; FKs; sin datos sensibles innecesarios.

---

## 10. API (resumen)

```
POST /auth/login · POST /auth/logout · GET /me
GET  /courses · /courses/{id} · /modules/{id} · /lessons/{id}
GET  /activities/{id}
POST /activities/{id}/start
POST /activities/{id}/hint
POST /activities/{id}/submit-evidence       # multipart (actividades externas)
CTF: POST /challenges/{id}/start · /submit · /hint  ·  GET /scoreboard
ADMIN CTF: CRUD /admin/ctf-events, /admin/challenges, /admin/flags · POST /admin/import/challenges-zip (preview + confirm)
GET  /dashboard · /progress · /grades
ADMIN/INSTRUCTOR (prefijo /admin):
CRUD courses, modules, lessons, activities, platforms, classes, users
POST /admin/import/students-csv  (preview + confirm)
GET  /admin/reviews?status=PENDING_REVIEW
POST /admin/reviews/{id}/decision           # approve/reject/needs_changes
GET  /admin/analytics/* · /admin/export/*
```
Esquemas de respuesta **separados** para estudiante y para admin (el estudiante nunca recibe campos sensibles).

---

## 11. Seguridad y privacidad

**Seguridad:** Argon2id; cookies HTTP-only/Secure/SameSite; CSRF en métodos mutantes; rate limiting en login y envíos; validación Pydantic; queries parametrizadas; uploads con validación de tipo real, tamaño máximo y almacenamiento fuera del webroot (nada subido se ejecuta jamás); cabeceras de seguridad en Nginx; secretos solo en `.env`; auditoría de acciones clave; flags estáticas hasheadas y dinámicas por estudiante (HMAC), validadas **solo en servidor**; el estudiante nunca recibe flags, soluciones ni hints bloqueados.

**Menores y datos personales (importante):**
- Recolectar el **mínimo de datos** necesario (idealmente username, nombre, curso; email opcional).
- No pedir ni almacenar credenciales de plataformas externas.
- Antes de que los estudiantes creen cuentas en plataformas externas, revisar sus políticas de privacidad y obtener autorización del colegio y, si corresponde, de los representantes.
- Política de retención y eliminación de datos documentada en `SECURITY.md`.
- Evidencias (capturas) pueden contener datos personales: advertir al estudiante y permitir borrado.

**Permisos de terceros:** registrar en `external_platforms` el estado del permiso/licencia. No integrar ni reutilizar contenido sin verificarlo.

---

## 12. Diseño y UX

### Identidad (no plantilla de IA)
Dirección: **"consola de operaciones"** sobria y profesional, apropiada para un colegio: rejilla visible, bordes finos, densidad cuidada, datos en monoespaciada, un solo color de acento con significado, estados con color **y** forma/texto, modo oscuro por defecto + claro completo, tokens CSS.

**Evitar explícitamente:** degradados morados/azules, glassmorphism, tarjetas idénticas redondeadas con sombra suave, emojis como iconos, estética hacker cliché.

Tipografía: sans de lectura + monoespaciada, **autoalojadas**; iconos Lucide.

### UX
- Paleta de comandos (Ctrl/Cmd+K) y atajos de teclado.
- Tablas con búsqueda, filtros guardados, orden, selección múltiple, acciones masivas, exportación.
- Editor Markdown con vista previa en vivo y autoguardado de borradores.
- **Vista de actividad externa:** guía en español, glosario, botón "Ir al reto", pistas con costo visible, carga de evidencia, estado de revisión claro.
- **Pantalla del reto CTF:** enunciado, adjuntos, pistas con costo visible, campo de flag con feedback inmediato, intentos restantes, cronómetro (valor del servidor), estado y explicación al resolver; scoreboard con evolución en el tiempo.
- **Cola de revisión del profesor** rápida y con atajos.
- Estados vacío/carga/error diseñados a propósito, mensajes claros en español.
- Accesibilidad: contraste AA, teclado completo, foco visible, ARIA, nunca solo color.
- Desktop primero; usable en tablet y móvil.

Antes de construir pantallas se entrega un mini sistema de diseño (página `/design`) que **debe ser aprobado**.

---

## 13. Infraestructura

`docker-compose.yml`: `nginx`, `frontend`, `backend`, `mysql` (+ `worker` para tareas diferidas). Redes `app` y `db` (interna); volúmenes para BD y uploads. `.env.example` con `DATABASE_URL, MYSQL_*, SECRET_KEY, ADMIN_EMAIL, SESSION_TTL, MAX_UPLOAD_MB, TIMEZONE` (y `FLAG_HMAC_SECRET`). `Makefile`: `up, down, test, lint, migrate, seed, reset-db`. Backups automáticos de MySQL y uploads con restauración probada. HTTPS si se expone a Internet.

---

## 14. Plan de 9 meses (datos de seed, editable)

Cada mes se compone principalmente de **retos CTF propios** del profesor; los recursos externos son apoyo.

| Mes | Tema | Recursos sugeridos (verificar) |
|---|---|---|
| 1 | Linux y fundamentos | OverTheWire (Bandit), guías propias |
| 2 | Redes | Cisco Networking Academy, guías propias |
| 3 | HTTP y fundamentos web | Guías propias, herramientas del navegador |
| 4 | Seguridad web | PortSwigger Web Security Academy, OWASP Juice Shop |
| 5 | Linux security y escalada de privilegios | CyLab Security Academy, guías propias |
| 6 | Windows y Active Directory | Contenido propio / recursos a definir |
| 7 | Forense y análisis | CyLab Security Academy |
| 8 | Red Team / Blue Team | Mezcla de recursos |
| 9 | Capstone / CTF final | CTF propio o evento en plataforma externa |

Es una **propuesta inicial**; el profesor la cambia desde el panel.

---

## 15. Fases (resumen)

| Fase | Contenido |
|---|---|
| 0 | Bootstrap: repo, Compose, health check, contrato técnico |
| 1 | Backend base: auth, RBAC, settings, auditoría |
| 2 | Frontend base y sistema de diseño (**aprobación visual**) |
| 3 | Usuarios, clases, importación CSV |
| 4 | Currículo y actividades base: cursos, módulos, lecciones, quiz/ejercicio/lectura/proyecto, registro de tipos |
| 5 | **Núcleo CTF (backend):** categorías, dificultades, eventos, retos, adjuntos, hints, visibilidad |
| 6 | **Motor CTF:** flags (estática/regex/dinámica), envíos, cronómetro, puntuación, notas |
| 7 | **Panel CTF del profesor (frontend):** creador de retos y eventos |
| 8 | Experiencia del estudiante + scoreboard |
| 9 | Panel del profesor: analítica, clase en vivo, anuncios, exportación |
| 10 | **Importador ZIP** de retos (`challenge.yml`) + exportar |
| 11 | Plataformas externas y evidencias (complemento) |
| 12 | Endurecimiento, backups, documentación |
| 13 (opcional) | Integraciones externas, gamificación avanzada, labs Docker |

Una fase = una sesión = una rama git. No se avanza sin cumplir el criterio de salida. Los prompts detallados por fase se regeneran a partir de este SPEC.

---

## 16. Tests obligatorios

Auth y sesiones · autorización por rol/permiso · el estudiante no accede a endpoints admin · el estudiante no ve datos de otros · schemas de estudiante sin campos sensibles · flujo de evidencia (enviar → revisar → aprobar/rechazar) · cálculo de puntos/XP/nota · escala de notas editable · prerrequisitos (sin ciclos) · importación CSV (filas inválidas, UTF-8, duplicados) · uploads maliciosos rechazados · migraciones desde cero · E2E del flujo estudiante y profesor. **Calificación (obligatorios):** puntaje de reto con base/tiempo/pistas/piso mínimo · escala por tramos y lineal · pesos del curso · nota provisional recalculada y nota final congelada · cambiar la escala no altera notas finales · recalcular una final exige admin y motivo · ajuste manual auditado · aviso de actividades sin revisar al cerrar periodo.

**Motor CTF (obligatorios):** flag de otro estudiante rechazada · regex · HMAC determinista y distinto por estudiante · cronómetro calculado en servidor · límite de intentos · hints con costo y orden · doble envío concurrente sin duplicar puntos · estudiante sin acceso a flags/soluciones/hints bloqueados · importador ZIP (zip-slip, manifest inválido, round-trip exportar→importar).

---

## 17. Criterios de aceptación del MVP

1. Se levanta desde cero con `make up` siguiendo la documentación.
2. El profesor crea estudiantes (manual y CSV) y una clase.
3. El profesor crea un curso con módulos, lecciones y actividades solo desde la interfaz.
4. El profesor crea un **evento CTF y un reto completo** (flags, hints, puntos, adjuntos) solo desde la interfaz.
5. El estudiante resuelve un reto: intenta, usa una pista, envía la flag y ve su puntaje.
6. La **flag dinámica de un estudiante no funciona para otro**.
7. El tiempo lo mide el servidor (cambiar la hora del PC no lo altera).
8. El scoreboard y los dashboards muestran datos correctos y el profesor puede activarlos/desactivarlos.
9. El profesor sube un ZIP con `challenge.yml`, lo previsualiza, lo corrige y lo publica.
10. El profesor registra una plataforma externa y crea una actividad externa; el estudiante envía evidencia y el profesor la aprueba o rechaza.
11. Categorías, dificultades, escala de notas y pesos de puntuación se editan sin tocar código ni BD.
12. Las notas se calculan automáticamente como **provisionales**; el profesor las confirma como **finales** y quedan congeladas con la escala y pesos vigentes.
13. Se exporta progreso y notas a CSV/XLSX.
14. Un estudiante no puede ver datos de otros ni acceder a funciones administrativas.
15. La UI cumple la dirección visual y las comprobaciones de accesibilidad básicas.
16. Todos los tests pasan; lo no implementado está marcado `TODO`.

---

## 18. Riesgos y preguntas abiertas

| Tema | Acción |
|---|---|
| **Permiso de CyLab para reutilizar o traducir su contenido** | Escribir a educator@cylabacademy.org. Hasta tener respuesta, solo material propio + enlaces |
| **API o exportación de progreso de CyLab** | Preguntar si existe; si no, se mantiene la aprobación manual |
| **Cuentas de menores en plataformas de terceros** | Revisar políticas de privacidad y autorización del colegio/representantes |
| **Dependencia de enlaces externos** | Revisión periódica de enlaces rotos (tarea del worker) |
| **Carga del profesor** | La cola de revisión debe ser muy ágil; considerar autoaprobación en actividades de bajo riesgo |
| **Alcance mayor al tener CTF propios desde el inicio** | Construir estrictamente por fases; el MVP mínimo utilizable son las fases 0–9; el resto puede esperar |
| **Retos CTF que requieren un servicio vulnerable en ejecución** | Fuera del MVP: usar retos de entrega estática (criptografía, forense con archivos, OSINT, enunciados con archivos). Los labs Docker llegan en una fase posterior con aislamiento |
| **Creación de contenido CTF** | Tiempo del profesor: priorizar el importador ZIP y plantillas de reto para producir retos rápido |

---

## 19. Reglas para el agente de desarrollo

1. Leer este SPEC, `CLAUDE.md` y `PROGRESS.md` antes de cada sesión.
2. Trabajar **solo** en la fase indicada; no adelantar funcionalidades.
3. Todo lo configurable va en BD; la lógica en `service.py`.
4. Nada de código ficticio: lo pendiente se marca `TODO(fase-N)`.
5. Ejecutar linters y tests antes de dar algo por terminado.
6. Registrar decisiones en `/docs/DECISIONS.md`; no cambiar el contrato técnico sin preguntar.
7. No copiar ni raspar contenido de terceros; no almacenar credenciales de plataformas externas.
8. Cerrar cada fase con el informe de cierre: qué se hizo, qué queda como TODO, salida real de lint/tests, cómo verificarlo, riesgos.
9. Si algo bloquea y es ambiguo, preguntar; si no bloquea, decidir, documentar y continuar.

---

## 20. Entregables finales

`/frontend`, `/backend`, `/docs`, `/scripts`, `/tests`, `/docker`, `docker-compose.yml`, `.env.example`, `Makefile`, `README.md`, esquema MySQL con migraciones, seed (admin, instructor, estudiantes demo, curso demo, plataformas sugeridas, escala de notas), y documentación: `INSTALLATION, ADMIN_GUIDE, TEACHER_GUIDE, STUDENT_GUIDE, CHALLENGE_FORMAT, SECURITY, BACKUP, TROUBLESHOOTING, DESIGN_SYSTEM, EXTENDING`. El sistema debe poder instalarse desde cero siguiendo solo la documentación.
