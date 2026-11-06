# CYBERLAB — PLAN POR FASES (prompts listos para pegar)

Este documento complementa `CYBERLAB_PROMPT_V2_PANEL_CTF.md` (la especificación completa). Aquí está todo dividido en **11 fases (0 a 10)**. Cada fase es un prompt independiente, con entregables, verificación y criterio de salida.

---

## A. Cómo usarlo (flujo anti-errores)

1. **Una fase = una sesión del agente = una rama git** (`fase-0`, `fase-1`, …). Al terminar, merge a `main` y tag (`v0.1-fase-1`).
2. **Al iniciar cada sesión** pega primero el bloque **B (Contexto base)** y luego el prompt de la fase.
3. **Adjunta siempre** `CYBERLAB_PROMPT_V2_PANEL_CTF.md` (la spec) o déjalo en `/docs/SPEC.md` dentro del repo y dile al agente que lo lea.
4. **No avances de fase** si no se cumple el **criterio de salida** (tests verdes + checklist). Un error arrastrado se multiplica en la siguiente fase.
5. El agente mantiene `PROGRESS.md` y `CLAUDE.md` (o `AGENTS.md`) en la raíz: son la memoria entre sesiones. Si una sesión se corta, la siguiente empieza leyéndolos.
6. Si el agente propone cambiar una decisión del **bloque C (Contrato técnico)**, que pregunte antes. Cambiar contratos a mitad de proyecto es la causa #1 de código que no encaja.
7. Pide siempre al final de cada fase el **informe de cierre** (formato en el bloque D).

---

## B. Contexto base (pegar al inicio de CADA sesión)

```
Eres el ingeniero principal de CYBERLAB: una plataforma educativa de CTF para
estudiantes de bachillerato, instalada en un servidor dentro de la LAN de un
colegio (sin Internet obligatorio). Stack fijo: Python 3.12 + FastAPI +
SQLAlchemy 2 + Alembic + MySQL 8 (NO PostgreSQL), React + Vite + TypeScript +
Tailwind, Nginx, Docker Compose.

Antes de escribir código:
1. Lee /docs/SPEC.md, /CLAUDE.md y /PROGRESS.md.
2. Resume en 5 líneas en qué fase estamos y qué falta.
3. No toques nada fuera del alcance de la fase actual.

Reglas permanentes:
- Todo lo configurable es dato en BD, no código.
- Backend modular por dominio; la lógica va en service.py, no en routers.
- Nada de código ficticio: lo no implementado se marca TODO(fase-N).
- Cero dependencias de CDN (offline). Fuentes e iconos autoalojados.
- Seguridad: validación estricta, queries parametrizadas, sin secretos en el repo.
- Tras cada bloque de trabajo: ejecuta tests y linters; no digas "listo" sin haberlos corrido.
- Al terminar: actualiza PROGRESS.md y entrega el informe de cierre.
- Si algo es ambiguo y bloquea, pregunta; si no bloquea, decide, anótalo en
  /docs/DECISIONS.md y continúa.
```

---

## C. Contrato técnico (decisiones fijas desde el inicio)

El agente las escribe en `/docs/CONTRACT.md` en la Fase 0 y todas las fases las respetan.

**Versiones:** Python 3.12, Node 22 LTS, MySQL 8.4 (compatible 8.0+), Nginx estable.

**Backend:** FastAPI, SQLAlchemy 2.x (estilo 2.0, tipado), Alembic, Pydantic v2, argon2-cffi, pytest + httpx, ruff + mypy. Gestor: `uv` o `pip-tools` (uno solo, anotado).

**Frontend:** React 18+, Vite, TypeScript estricto, Tailwind (build local), React Router, TanStack Query + Table, React Hook Form + Zod, Radix primitives adaptadas, Lucide, Vitest + Testing Library, Playwright (solo smoke E2E).

**Convenciones de datos**
- PK: `BIGINT UNSIGNED AUTO_INCREMENT`; además `public_id` (UUID) donde el ID se exponga por URL a estudiantes.
- Fechas: `DATETIME(6)` siempre en **UTC**; el frontend las convierte a la zona del navegador para mostrar. Zona del colegio configurable en `system_settings` (por defecto `America/Guayaquil`).
- `created_at`, `updated_at`; `deleted_at` en retos y eventos (soft-delete).
- Charset `utf8mb4`, collation `utf8mb4_0900_ai_ci`, InnoDB.
- Nombres de tablas en plural y snake_case.

**Convenciones de API**
- Prefijo `/api/v1`. JSON. Paginación: `?page=&page_size=` → `{items, total, page, page_size}`.
- Errores: `{ "error": { "code": "CHALLENGE_NOT_FOUND", "message": "...", "details": {...} } }` con códigos estables.
- Sesiones **server-side** (tabla `sessions`) con cookie HTTP-only, Secure en producción, SameSite=Lax; CSRF por token en cabecera para métodos mutantes. (Se elige sesión en vez de JWT para poder revocar y listar sesiones activas.)
- Permisos como strings `recurso.accion` (ej. `challenge.create`). Endpoints declaran el permiso con una dependencia única `require_permission("...")`.
- Eventos de dominio: `challenge_solved`, `submission_failed`, `hint_used`, `lab_reset` (futuro), publicados por un bus interno síncrono simple.

**Frontend**
- Estructura por features (`features/<nombre>`), cliente API generado desde OpenAPI (`openapi-typescript` o similar), sin `fetch` sueltos.
- Tokens de diseño en variables CSS + preset de Tailwind. Prohibidos colores hexadecimales sueltos en componentes.

**Repositorio**
```
/backend  /frontend  /lab-manager (vacío, TODO)  /docker  /docs  /scripts  /tests
docker-compose.yml  .env.example  Makefile  README.md  CLAUDE.md  PROGRESS.md
```
`Makefile` con: `make up`, `make down`, `make test`, `make lint`, `make migrate`, `make seed`, `make reset-db`.

---

## D. Informe de cierre (pedir al final de cada fase)

```
Cierra la fase. Entrega:
1. Qué se implementó (lista corta).
2. Qué quedó como TODO y por qué.
3. Resultado de: make lint, make test (pega el resumen real).
4. Cómo verificarlo manualmente (pasos exactos, URLs, usuarios del seed).
5. Riesgos o decisiones tomadas (también en /docs/DECISIONS.md).
6. PROGRESS.md actualizado.
No avances a otra fase.
```

---

# FASES

---

## FASE 0 — Bootstrap y contrato

**Objetivo:** un esqueleto ejecutable de punta a punta, sin funcionalidad de negocio. Todo lo demás se apoya aquí.

**Prompt:**
```
FASE 0. Crea el esqueleto del repositorio según la estructura del contrato.

Entregables:
- Estructura de carpetas, Makefile, .env.example (todas las variables, sin secretos reales).
- docker-compose.yml con nginx, frontend, backend, mysql (healthchecks, redes
  separadas: red 'app' y red 'db' interna, volúmenes nombrados).
- Backend FastAPI mínimo: GET /api/v1/health (verifica conexión a MySQL),
  config por variables de entorno (pydantic-settings), logging estructurado,
  Alembic configurado con una migración inicial vacía.
- Frontend Vite+TS+Tailwind mínimo que muestra una página y consulta /health.
- Nginx: sirve el frontend y proxea /api al backend.
- Linters y tests configurados (ruff, mypy, pytest, eslint, vitest) con un
  test de ejemplo por lado.
- /docs/CONTRACT.md con las decisiones del bloque C, /docs/DECISIONS.md,
  /CLAUDE.md (comandos, convenciones, reglas), /PROGRESS.md.

No implementes autenticación ni modelos de negocio.
```
**Verificación:** `make up` levanta todo; `http://localhost` muestra la página y el health en verde; `make test` y `make lint` pasan; `make down && make up` conserva la BD.
**Criterio de salida:** instalación desde cero con solo `.env` + `make up`.

---

## FASE 1 — Backend fundación: auth, RBAC, settings, auditoría

**Objetivo:** el núcleo seguro sobre el que se apoya todo.

**Prompt:**
```
FASE 1. Implementa los módulos core, auth, users (solo modelos base), settings y audit.

Entregables:
- Migraciones: users, roles, permissions, role_permissions, user_roles,
  sessions, system_settings, audit_logs.
- Seed idempotente: permisos base, roles ADMIN/INSTRUCTOR/STUDENT con sus
  permisos, un admin inicial (credenciales desde .env), settings por defecto.
- Auth: login (username+password, Argon2id), logout, GET /me, sesiones
  server-side con cookie, expiración configurable, registro de último login,
  IP, user agent; listado y revocación de sesiones propias. CSRF en métodos mutantes.
- Rate limiting en login (por usuario e IP) con interfaz reemplazable.
- RBAC: dependencia require_permission, CRUD de roles y asignación de
  permisos (solo ADMIN). Un rol del sistema no se puede borrar.
- Settings: lectura/escritura tipada con validación y valores por defecto;
  cache simple invalidable.
- Auditoría: servicio audit.log(action, actor, target, meta) y endpoint de
  consulta con filtros (permiso audit.view). Registrar LOGIN/LOGOUT/ADMIN_LOGIN
  y cambios de settings/roles.
- Bus de eventos de dominio mínimo.

Tests: hashing, login ok/fallido, rate limit, expiración de sesión, CSRF,
require_permission (permitido/denegado por rol), rol del sistema protegido,
auditoría escrita, migraciones desde cero.
```
**Verificación:** login con el admin vía curl/Swagger; STUDENT recibe 403 en endpoints admin; migración desde BD vacía OK.
**Criterio de salida:** todos los tests de seguridad verdes; ninguna contraseña ni secreto en logs.

---

## FASE 2 — Frontend fundación y sistema de diseño

**Objetivo:** la identidad visual y los componentes base. **Esta fase decide si el diseño queda distinto o genérico: revísala antes de seguir.**

**Prompt:**
```
FASE 2. Construye el sistema de diseño y el shell de la aplicación.

Primero (y detente a esperar mi revisión):
- Propuesta de identidad: paleta (neutros con carácter + 1 acento), tipografía
  (sans + mono, autoalojadas), escala de espaciado, radios, bordes, sombras
  mínimas, iconografía (Lucide), modo oscuro y claro con tokens CSS.
- Página /design (kitchen sink) con todos los componentes en todos sus estados.

Evita: degradados morados/azules, glassmorphism, tarjetas idénticas redondeadas
con sombra suave, emojis como iconos, estética hacker de cliché. Dirección:
"consola de operaciones": rejilla visible, hairlines, densidad cuidada, datos en mono.

Luego implementa:
- Componentes base propios: Button, Input, Textarea, Select, Checkbox, Switch,
  Badge/StatusDot (color + forma/texto), Table (TanStack: búsqueda, orden,
  paginación, selección), Dialog, Drawer, Tabs, Toast, Tooltip, Skeleton,
  EmptyState, ErrorState, Markdown renderer, CommandPalette (Ctrl/Cmd+K).
- App shell: sidebar + topbar, navegación desde un REGISTRO de rutas por
  permisos (agregar una sección = agregar una entrada), breadcrumbs, selector
  de tema, menú de usuario.
- Auth en el frontend: pantalla de login, guard de rutas, manejo de expiración
  de sesión, página 403/404.
- Cliente API generado desde OpenAPI + TanStack Query configurado, manejo
  centralizado de errores con el formato del contrato.
- Accesibilidad: foco visible, navegación por teclado, contraste AA, ARIA.

Tests: Vitest de componentes clave y de los guards; un smoke E2E de login.
```
**Verificación:** `/design` muestra todo; login real contra el backend; tema claro/oscuro; navegación solo por teclado.
**Criterio de salida:** **aprobación visual tuya** del sistema de diseño antes de la Fase 3.

---

## FASE 3 — Usuarios, clases e importación CSV

**Prompt:**
```
FASE 3. Gestión de usuarios y clases (backend + frontend).

Backend: migraciones students/teachers (perfil), classes, class_students;
CRUD de usuarios (crear, editar, desactivar, reset de password por admin);
CRUD de clases; asignar/quitar estudiantes; importación CSV
(username, nombre, apellido, curso, email opcional, password temporal) con
VISTA PREVIA, validación fila por fila, reporte de errores y tabla import_jobs;
forzar cambio de password en el primer login. Auditoría de USER_CREATED/MODIFIED
e import.
Frontend: secciones Usuarios, Estudiantes, Profesores y Clases con tablas
completas (búsqueda, filtros, acciones masivas, exportar), formularios con
validación en línea, asistente de importación CSV en 3 pasos (subir → revisar → confirmar).
Tests: permisos por rol, CSV con filas inválidas/duplicadas, codificación UTF-8,
límite de tamaño, un INSTRUCTOR no puede crear ADMIN.
```
**Criterio de salida:** importar un CSV de 30 estudiantes y verlos en una clase sin tocar la BD.

---

## FASE 4 — Núcleo CTF (backend): categorías, dificultades, eventos, retos

**Prompt:**
```
FASE 4. Implementa el módulo ctf (solo backend, con su API completa).

- Migraciones: categories, difficulties, ctf_events, ctf_event_classes,
  challenges, challenge_files, challenge_prerequisites, hints.
- Categorías y dificultades EDITABLES (nombre, color, orden, multiplicador).
  Seed con 6 categorías y 4 dificultades, editables y borrables si no están en uso.
- Eventos CTF: CRUD, estados DRAFT/PUBLISHED/ARCHIVED, ventana de fechas,
  modo (jeopardy por ahora), visibilidad, clases asignadas, reglas (markdown).
- Retos: CRUD, soft-delete, estado DRAFT/PUBLISHED/ARCHIVED, puntos,
  descripción markdown, categoría, dificultad, prerequisitos (sin ciclos),
  orden, delivery_type/delivery_config (JSON; solo 'static' implementado),
  module_id nullable (preparado para LMS).
- Adjuntos: subida segura (tipo real, tamaño, nombre saneado, fuera del
  webroot), descarga autenticada con autorización.
- Hints: CRUD con costo y orden.
- Reglas de visibilidad: un estudiante solo ve retos PUBLISHED de eventos
  activos asignados a su clase y con prerequisitos cumplidos. NUNCA devuelve
  flags, soluciones ni hints no desbloqueados (schemas de respuesta separados
  para admin y estudiante).
- Duplicar reto/evento.
Tests: permisos, visibilidad por clase/fecha/estado, prerequisitos con ciclo
rechazado, schemas de estudiante sin campos sensibles, subida maliciosa rechazada.
```
**Criterio de salida:** el test "estudiante nunca recibe campos sensibles" cubre todos los endpoints de lectura de retos.

---

## FASE 5 — Motor de flags, envíos, cronómetro y puntuación (backend)

**Prompt:**
```
FASE 5. Implementa flags, submissions, scoring y grades.

- FlagStrategy por registro: static (hash, comparación en tiempo constante),
  regex, dynamic_hmac (HMAC(FLAG_HMAC_SECRET, student_id|challenge_id|flag_id),
  formato configurable, ej. CYBER{...}). Varias flags por reto.
- POST /challenges/{id}/start (started_at server-side, idempotente),
  POST /challenges/{id}/submit, POST /challenges/{id}/hint.
  Registrar start, intentos, hints, completed_at. Pausa/reset por instructor.
- Límite de intentos configurable (por reto/evento/global), rate limit por
  usuario e IP, mensajes sin filtrar información.
- ScoringStrategy por registro: fixed, time_decay, dynamic_by_solves.
  Fórmula: base + bonus de tiempo − hints, pesos configurables por evento/reto.
  Escala score→nota (grade_scales) editable.
- Eventos de dominio: challenge_solved, submission_failed, hint_used →
  auditoría, xp_transactions, notificaciones.
- Una flag dinámica de otro estudiante NO valida. Un reto resuelto no se re-puntúa.
- Scoreboard (consulta): global/clase/evento, congelable, activable por settings.
Tests (obligatorios): flag ajena rechazada, regex, HMAC determinista y distinto
por estudiante, tiempo calculado en servidor (ignora cabeceras/cliente), límite
de intentos, descuento de hints en orden, idempotencia del start, doble envío
concurrente no duplica puntos (transacción/lock), escala de notas, scoreboard con empates.
```
**Criterio de salida:** test de concurrencia verde (dos submits simultáneos correctos → un solo solve).

---

## FASE 6 — Panel CTF del profesor (frontend)

**Prompt:**
```
FASE 6. Interfaz de administración del CTF, usando el sistema de diseño de la Fase 2.

- Secciones: CTFs (eventos), Retos, Categorías, Dificultades, Flags, Hints,
  Asignaciones, Escalas de nota, Puntuación, Configuración, Auditoría.
- Creador de reto (wizard o formulario por pestañas): datos, descripción con
  editor Markdown + vista previa en vivo, adjuntos (arrastrar y soltar),
  flags (con prueba "validar una flag de ejemplo"), hints (reordenables),
  prerequisitos, puntos, estado. Autoguardado de borrador.
- Vista previa "como estudiante" sin afectar datos.
- Creador de CTF: reto a reto, orden por arrastre, fechas, clase asignada, publicar.
- Tablas con filtros guardados, selección múltiple, acciones masivas
  (publicar/archivar/duplicar), confirmación solo en acciones destructivas, deshacer cuando sea posible.
- Todo gestionable sin tocar BD: categorías, dificultades, pesos, escalas, ajustes.
Tests: componentes del formulario, flujo E2E "crear CTF con un reto y publicarlo".
```
**Criterio de salida:** crear un CTF completo solo desde la interfaz, en menos de 5 minutos.

---

## FASE 7 — Experiencia del estudiante y scoreboard (frontend)

**Prompt:**
```
FASE 7. Interfaz del estudiante.

- Dashboard: nombre, XP, progreso, retos resueltos, tiempo total, promedio,
  eventos activos, anuncios, historial (RETO | TIEMPO | HINTS | INTENTOS | SCORE | ESTADO).
- Lista de retos por evento: filtros por categoría/dificultad/estado
  (resuelto, en progreso, bloqueado con la razón del bloqueo).
- Pantalla del reto: enunciado Markdown, adjuntos, hints con costo visible y
  confirmación al usarlos, campo de flag con feedback inmediato, intentos
  restantes, cronómetro (valor del servidor, el cliente solo lo muestra),
  estados claros de éxito/fallo, explicación al resolver (según configuración).
- Scoreboard con actualización periódica, evolución en el tiempo y respeto de
  las opciones del profesor (oculto/congelado).
- Notificaciones (campana) y centro de anuncios.
- Estados de carga, vacío y error cuidados; accesibilidad completa; responsive
  desktop-first, usable en tablet.
Tests: flujo E2E estudiante (login → reto → hint → flag errónea → flag correcta → score).
```
**Criterio de salida:** un estudiante del seed completa un reto sin ayuda; el cronómetro no cambia al alterar la hora local.

---

## FASE 8 — Analítica del profesor, clase en vivo, exportación

**Prompt:**
```
FASE 8. Panel analítico.

- Dashboard del profesor: estudiantes, retos activos/completados, flags
  capturadas, tiempo y score promedio, hints, intentos, tasa de finalización,
  retos con más fallos y más abandono. Solo datos, sin conclusiones automáticas
  sobre la capacidad del estudiante.
- Vista "clase en vivo": ESTUDIANTE | ESTADO | TIEMPO | INTENTOS | HINTS | SCORE,
  con actualización periódica.
- Vista individual de estudiante para el profesor: evolución temporal,
  historial, competencias por categoría.
- Anuncios del profesor (crear/programar/archivar) y cierre manual de eventos.
- Exportación CSV/XLSX (y PDF simple) de resultados con filtros por
  estudiante/clase/evento/fecha; nota calculada con la escala configurada.
- Consultas con índices adecuados; probar con datos sintéticos (500 estudiantes, 50k envíos).
Tests: exactitud de agregados, permisos (instructor solo ve sus clases), export con tildes y comas.
```
**Criterio de salida:** los números del dashboard coinciden con un cálculo manual sobre el seed.

---

## FASE 9 — Importador de retos (ZIP + challenge.yml)

**Prompt:**
```
FASE 9. Importador para cargar los CTF reales después.

- Especificación en /docs/CHALLENGE_FORMAT.md (challenge.yml y ctf.yml con varios retos).
- Backend: subir ZIP → extraer a directorio temporal controlado → validar
  manifest (esquema versionado) → vista previa con errores y advertencias →
  confirmar → crear en DRAFT. Idempotente por slug (actualiza o crea).
- Seguridad: protección contra zip-slip, zip bombs, rutas absolutas, symlinks,
  límites de tamaño/archivos; NUNCA ejecutar nada del ZIP.
- Frontend: asistente "subir → revisar → confirmar" con reporte de errores
  por archivo/campo y descarga de plantilla de ejemplo.
- Exportar un reto/evento existente a ZIP (mismo formato).
- Incluir 3 retos DEMO en el seed, claramente marcados como demostración.
Tests: zip-slip, manifest inválido, slug repetido, round-trip exportar→importar.
```
**Criterio de salida:** exportar un reto y reimportarlo produce un reto idéntico.

---

## FASE 10 — Endurecimiento, backups y documentación

**Prompt:**
```
FASE 10. Cierre del MVP.

- Revisión de seguridad completa: checklist OWASP básico, cabeceras en Nginx
  (CSP, X-Frame-Options, etc.), cookies, CORS, límites de tamaño, logs sin
  datos sensibles, dependencias auditadas.
- Backups: script de respaldo de MySQL + uploads con rotación, script de
  restauración PROBADO, documentación y cron/timer de ejemplo.
- Worker/tareas: limpieza de sesiones expiradas y archivos temporales.
- Prueba offline: verificar que la app funciona sin Internet (sin CDN).
- Pruebas de carga ligeras (20-60 usuarios simultáneos enviando flags).
- Documentación: README, INSTALLATION, ADMIN_GUIDE, TEACHER_GUIDE,
  STUDENT_GUIDE, CHALLENGE_FORMAT, SECURITY, BACKUP, NETWORK, TROUBLESHOOTING,
  DESIGN_SYSTEM, EXTENDING (cómo añadir un módulo, una estrategia de flag y una pantalla).
- Verificación de los criterios de aceptación 1–13 de la especificación, uno por uno, con evidencia.
- Lista final de TODO(fase-N) pendientes (LMS, gamificación, Docker labs) para el futuro.
```
**Criterio de salida:** instalación desde cero en una máquina limpia siguiendo únicamente `INSTALLATION.md`.

---

## E. Checklist anti-errores (revisar tú entre fases)

- [ ] `make lint` y `make test` verdes (pide ver la salida real).
- [ ] Probaste la fase manualmente con el seed, no solo los tests.
- [ ] Ningún secreto en el repo (`git grep -i "password\|secret"`).
- [ ] Migraciones funcionan desde BD vacía y `make reset-db`.
- [ ] No aparecen pseudofunciones: todo lo pendiente está como `TODO(fase-N)`.
- [ ] `PROGRESS.md` y `DECISIONS.md` actualizados.
- [ ] Commit y tag antes de abrir la siguiente fase.

## F. Si algo sale mal en una fase

- **El agente rompe lo anterior:** `git revert` a la etiqueta previa y repite la fase con el prompt más acotado (una sección a la vez).
- **Sesión sin contexto:** nueva sesión → bloque B → "continúa la fase N desde PROGRESS.md".
- **Se desvía del diseño:** vuelve a pegar la sección "Identidad visual" de la spec y pide corregir solo los componentes afectados.
- **Fase demasiado grande:** pide que la divida en sub-fases (ej. 5a flags, 5b envíos, 5c scoring) y trabaje una por vez.