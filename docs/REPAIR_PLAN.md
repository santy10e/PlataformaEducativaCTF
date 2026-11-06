# CYBERLAB — Plan de reparación

Orden de ejecución: P0 seguridad → P1 funcionalidad rota/ausente → tests → P2 → P3. Cada grupo se verifica con `pytest`, `ruff`, `mypy`, `vitest`, `eslint`, build y el recorrido real contra el stack Compose aislado antes de pasar al siguiente. Referencia: `docs/FULL_AUDIT.md`, tag `audit-baseline`.

| ID | Problema | Severidad | Archivo | Causa | Solución | Test |
|---|---|---|---|---|---|---|
| R-01 | Instructor modifica eventos de otro docente (y, con sus propias clases, se apropia de él) | **P0** | `backend/app/ctf_service.py` (`save_event`) | `db.get(CtfEvent, id)` sin comprobar propiedad; `get_event` solo se usaba en lecturas | Comprobar propiedad con `get_event` antes de mutar; un docente no puede quitar clases de otros docentes de un evento compartido; no-admin debe asignar ≥1 clase propia (evita eventos huérfanos) | `test_ctf.py`: PUT ajeno → 404 y evento intacto; evento sin clase propia → 422; compartido conserva clases ajenas |
| R-02 | Instructor inscribe a cualquier estudiante en su clase | **P0** | `backend/app/classes_service.py` (`replace_students`), `classes_api.py` | Valida rol y estado, no pertenencia al alcance del docente | No-admin solo puede dejar en su clase estudiantes que ya estén en alguna de sus clases; si no → 422 | `test_education.py`: instructor intenta añadir estudiante ajeno → 422 y la clase no cambia |
| R-03 | Importación CSV resuelve clases fuera de alcance y duplica clases | P1 | `backend/app/imports_service.py` | Busca `name == curso AND academic_period == ""` sin filtrar por docente; crea clase con el admin como docente | Resolver por nombre dentro del alcance del actor (admin: cualquiera, nombre único; instructor: solo propias); ambigüedad → fila inválida en vista previa; crear solo si no existe (instructor: propia; admin: sin docente) | `test_education.py`: instructor no importa a clase ajena; importar a clase existente con período no duplica; admin no queda como docente |
| R-04 | `must_change_password` no se aplica en servidor | P1 | `backend/app/dependencies.py`, `ctf_api.py` (descarga) | Solo la UI lo lee | `require_permission` y la descarga responden 403 `PASSWORD_CHANGE_REQUIRED` hasta cambiar; `/auth/*` queda exento | `test_auth_api.py`: con flag activo → 403; tras cambio → 200 |
| R-05 | Pantallas placeholder (Configuración, Roles, Bitácora, Recursos, Ayuda, Marcador de staff) y textos «FASE N» | P1 | `frontend/src/app/*` | Nunca se implementaron | Implementar Configuración (editar ajustes), Roles (ver/editar permisos de roles no sistema; sistema solo lectura salvo permisos de rol con aviso), Bitácora (filtros + paginación), Marcador de staff (global/clase/evento + congelar), Ayuda con contenido real; eliminar Recursos de la navegación (sin contenido real que servir) y todo texto de fase | Vitest de las nuevas pantallas + e2e real |
| R-06 | `make up` no deja sistema usable; `make migrate/seed/reset-db` no funcionan | P1 | `Makefile`, `backend/Dockerfile`, `README.md`, `docs/INSTALLATION.md` | Migración solo manual; targets ejecutan `uv` en host sin BD | El backend aplica `alembic upgrade head` al arrancar; `make migrate`/`seed` usan `docker compose exec`; `reset-db` pide `CONFIRM=yes` y repite up+migrate+seed; documentación alineada | Instalación limpia verificada de punta a punta |
| R-07 | Un admin puede desactivarse / dejar el sistema sin admin | P2 | `backend/app/users_api.py` | Sin guardas | Prohibir autodesactivación y desactivar al último admin activo (409) | `test_education.py` |
| R-08 | Login: bloqueo de cuenta por terceros, cuenta logins correctos, IP del cliente = nginx | P2 | `backend/app/security.py`, `auth.py`, `docker/nginx.conf`, `backend/Dockerfile` | Una clave `user:` global; `allow()` registra todo intento | Contar solo fallos; clave por IP+usuario; reinicio al éxito; nginx envía `$remote_addr` y uvicorn confía en `X-Forwarded-For` solo de la red interna | `test_security.py` |
| R-09 | 404/405/500 fuera del envelope del CONTRACT | P2 | `backend/app/main.py` | Handler registrado para `fastapi.HTTPException`, no el de Starlette; sin handler de excepciones | Handlers para Starlette HTTPException y `Exception` (500 `INTERNAL_ERROR` sin detalles) | `test_health.py`/`test_security.py` |
| R-10 | Sesiones activas sobreviven al cambio de contraseña | P2 | `backend/app/auth.py` | No se revocan | Revocar las demás sesiones del usuario | `test_auth_api.py` |
| R-11 | Retos PUBLISHED sin flag; instructor crea cuentas INSTRUCTOR | P2 | `ctf_api.py`, `users_service.py` | Sin validación de publicación; condición de rol incompleta | Publicar exige ≥1 flag habilitada (422); eliminar la última flag de un reto publicado → 409; solo ADMIN crea INSTRUCTOR (alineado con el mensaje del propio código) | `test_ctf.py`, `test_education.py` |
| R-12 | Falta de tests de aislamiento y de e2e reales | P1 | `backend/tests`, `frontend/e2e` | Los P0 pasaron la suite | Tests de R-01…R-11 + e2e que hace login real y recorre el flujo estudiante; `make test` falla si el e2e no puede ejecutarse con credenciales | — |
| R-13 | Defectos visuales | P3 | `frontend/src/*.css`, `routes.ts`, `App.tsx` | — | Corregir desbordes (filtros de fecha, marcador móvil), icono único para Marcador, ocultar permisos crudos y saludo «Hola, System» | Capturas 1440/390 sin desborde |
| R-14 | XLSX deja en blanco los valores 0 | P3 | `backend/app/teaching_api.py` | `str(v or "")` | `"" if v is None else str(v)` | `test_teaching.py` |
| R-15 | N+1 en resumen del estudiante; prerrequisitos cargan todo; índice | P3 | `scoring_api.py`, `ctf_service.py`, nueva migración | — | Calcular una vez por reto; cargar solo retos del evento; índice `(user_id, challenge_id)` | tests existentes + migración desde cero |
| R-16 | Desviaciones del CONTRACT por decisión | P3 | `docs/DECISIONS.md` | — | Documentar: tablas sin `created_at/updated_at` (ledgers/progreso/perfiles), roles personalizados no asignables, `lab-manager` vacío | — |
| R-17 | `fetch` manual en 5 sitios; healthcheck no valida esquema; `tsbuildinfo` versionado; backend como root; sin `restart:`; dependencias `latest` | P3 | varios | Deuda | `tsbuildinfo` fuera de Git; usuario no root y `restart: unless-stopped`; resto documentado como deuda en `DECISIONS.md` (no bloquea) | — |

## No se repara (deliberado)

- Roles personalizados asignables a usuarios y reemplazo de `fetch` manual por el cliente generado: refactor mayor sin impacto de seguridad; se documenta como deuda.
- Ausencia de `SPEC.md`: no puede repararse sin el documento original; queda como limitación declarada.

## Estado de ejecución (2026-10-04)

| ID | Estado | Verificación |
|---|---|---|
| R-01, R-02, R-03 | Corregido | `test_isolation.py` falla contra `audit-baseline`, pasa ahora; recorrido real 80/80 |
| R-04, R-07, R-08, R-09, R-10, R-11 | Corregido | `test_hardening.py` + 10 mutaciones detectadas; recorrido real |
| R-05 | Corregido | `admin.test.tsx` (19 tests) y pasada visual sin placeholders |
| R-06 | Corregido | instalación limpia sin pasos manuales; ciclo `reset-db` ejecutado |
| R-12 | Corregido | 3 e2e reales; `make e2e` exige credenciales |
| R-13 | Corregido | sin desbordes a 1440/390 px en claro y oscuro |
| R-14 | Corregido | `test_spreadsheet_and_pdf_exports_keep_zero_values` |
| R-15 | Corregido | índice + N+1 eliminado + grafo de prerrequisitos por evento |
| R-16 | Documentado | `DECISIONS.md` |
| R-17 | Parcial | `tsbuildinfo` fuera de Git, `restart:` añadido; root, `fetch` manual y dependencias `latest` documentados como deuda |
| Extra | Corregido | OpenAPI regenerado (faltaban 12 rutas de fases 8–9); redirección tras cambiar contraseña; marcador visible para el personal aunque esté oculto a estudiantes; «SESIÓN CIFRADA» solo con HTTPS; tokens en lugar de hex |

## Hoja de ruta para cumplir `docs/SPEC.md` v4

Una fase por sesión y por rama (SPEC §15, §19). El orden respeta las dependencias: las notas por módulo (§7.2) necesitan módulos; la importación de progreso externo necesita evidencias.

| Orden | Fase SPEC | Entrega | Cierra criterios §17 | Depende de |
|---|---|---|---|---|
| 1 ✅ | 4 — Currículo y actividades (hecho 2026-10-05) | `courses/modules/lessons/activities`, registro `ActivityType` (`lesson_read`, `quiz`, `exercise`, `project`, `ctf_challenge` enlazado a los retos existentes), prerrequisitos y progreso por actividad (`activity_progress`), UI de autor y de estudiante, plan de 9 meses en el seed | 3, parte de 16 | decisión D2 |
| 2 | 6 — Puntaje y notas | estrategia por defecto §7.1 (base/tiempo/reflexión/pistas/piso), XP separado de puntos, escala por tramos y lineal, pesos, `grade_periods`, `module_grades`, `final_grades` con instantánea, `score_adjustments`, niveles, aviso de pendientes; tests obligatorios de calificación | 11, 12, 13 | 1, decisión D3 |
| 3 | 6/8 — Flag dinámica entregable y rankings | entrega por estudiante de la flag dinámica (adjunto o texto generado por estudiante en la entrega estática), rankings por clase/módulo/periodo desactivados por defecto y activables por el profesor, evolución en el tiempo | 6, 8 | — |
| 4 | 11 — Plataformas externas y evidencias | `external_platforms` (con seed de sugerencias), actividad `external_challenge`, evidencias (imagen validada, texto, URL, borrado), cola de revisión con filtros, aprobación masiva y atajos, `CsvImportProvider` | 10, 14 (borrado) | 1, 2 |
| 5 | 12 — Endurecimiento | `worker`, variables de `.env` del SPEC, política de retención y borrado de datos de menores, seed demo (instructor, estudiantes, curso, plataformas) | 1, 16 | 1–4 |
| — | 2 — Dirección visual | según decisión D1 | 15 | decisión D1 |

### Decisiones pendientes del usuario

- **D1 — Identidad visual.** El SPEC pide «consola de operaciones» con modo oscuro por defecto; `DECISIONS.md` y `CLAUDE.md` dan por aprobada la identidad «cuaderno universitario» con modo claro por defecto. El SPEC dice que la página `/design` «debe ser aprobada», así que no se cambia sin confirmación.
- **D2 — Retos CTF dentro del modelo de actividades.** Recomendado: `ctf_challenge` como tipo de actividad que **referencia** el reto existente (`config.challenge_id`), conservando tablas, datos y API del motor CTF. La alternativa (migrar los retos a `activities` y renombrar tablas según §9) toca todo el motor y sus datos.
- **D3 — Modelo de puntaje.** Recomendado: la fórmula §7.1 pasa a ser la estrategia por defecto de los eventos nuevos; FIXED/TIME_DECAY/DYNAMIC_BY_SOLVES se conservan como estrategias registrables (§7.1 las nombra). Los eventos existentes mantienen su estrategia salvo que el profesor la cambie.
- **D4 — Estructura modular (§8.1).** Recomendado: los módulos nuevos se crean ya con la estructura `modules/<nombre>/`; los existentes se migran de forma incremental cuando se toquen, en lugar de una reorganización masiva sin cambio funcional.
