# CYBERLAB — Auditoría integral (estado ANTES de reparar)

Línea base: tag `audit-baseline` = commit `e3c9c63` (árbol limpio, rama `audit/full-project`).
Fecha de la auditoría: 2026-10-03/04. Toda afirmación de este documento viene de algo ejecutado o leído en esta sesión; lo que no pudo comprobarse figura como `UNVERIFIED`.

## 0. Limitaciones declaradas

- **`/docs/SPEC.md` no existe** en el repositorio (ya lo reconocía `docs/DECISIONS.md`). No existe tampoco `CYBERLAB_PROMPT_V2_PANEL_CTF.md`. La matriz se compara por tanto contra `docs/CONTRACT.md`, las 11 fases del encargo, lo que `PROGRESS.md` declara como entregado y el comportamiento esperable de un LMS-CTF escolar. **No puede certificarse cumplimiento de SPEC**; solo de CONTRACT + PROGRESS.
- El stack Docker que ocupaba el puerto 80 pertenece a otro directorio (`D:\Documents\Projects\PlataformaCTF`) y no se tocó. Esta auditoría levantó el repo como proyecto Compose aislado `cyberlab-audit` en el puerto 8080, con un `.env` generado desde `.env.example` (fuera del repo) y volúmenes nuevos. Eso equivale a una instalación limpia.
- `uv` no está instalado en esta máquina; `make test`/`make lint` se ejecutaron con el entorno `backend/.venv` existente (mismos comandos `pytest`, `ruff`, `mypy`) y `npm`.
- No se midió cobertura con herramienta; las áreas sin tests se determinaron leyendo los tests.

## 1. Resumen ejecutivo

**Estado general: NO COMPLETE.** El recorrido feliz ADMIN → INSTRUCTOR → STUDENT funciona de punta a punta por API, la arquitectura es razonable y la suite existente pasa. Pero hay **dos fallos P0 de autorización entre docentes que los tests no detectaban**, el arranque en limpio con `make` no deja el sistema usable, y la UI de administración (Configuración, Roles, Bitácora) y el marcador docente **son placeholders** aunque `PROGRESS.md` marca esas fases como completas.

### Cómo se calculó el porcentaje

Se cuentan las filas de la matriz (§3), una por requisito verificable, con el mismo peso. «Realmente completo» = estado `COMPLETE` (implementado, integrado, probado por ejecución real o por test que realmente falla si se rompe). Es un indicador de orden de magnitud, no una métrica de esfuerzo.

| Estado | Filas |
|---|---|
| COMPLETE | 24 |
| PARTIAL | 13 |
| BROKEN | 8 |
| MISSING | 5 |
| UNVERIFIED | 2 |
| **Total** | **52** |

**≈ 46 % COMPLETE (24/52)**. Las 13 filas PARTIAL no se cuentan como completas.

### Resultado de lo ejecutado

| Prueba | Resultado |
|---|---|
| `pytest` backend | 41 passed |
| `ruff check` / `mypy --strict app` | limpio / limpio |
| `vitest` | 5 passed (un único fichero de test para ~5 000 líneas de UI) |
| `eslint` | limpio (config mínima) |
| Playwright e2e | 1 test, **se salta** sin credenciales (`make test` pasa sin ejecutar ningún e2e real) |
| `docker compose up --build` | 4 servicios sanos |
| Migración desde BD vacía | OK, 7 migraciones, 31 tablas, `utf8mb4_0900_ai_ci`, InnoDB |
| Script de recorrido real + negativos (`flow.py`, 75 comprobaciones) | **70 pasan, 5 fallan** (ver §5) |
| Peticiones externas con la red externa bloqueada (Chromium, 3 roles, 25 pantallas) | **0** |
| Backup real + `sha256sum -c` | OK |
| Export/Import ZIP, zip-slip, no-ZIP | OK |

### Hallazgos críticos (resumen)

1. **P0 — Un instructor puede modificar cualquier evento CTF de otro docente** (`PUT /ctf/events/{id}`): devuelve 404 en GET pero 200 en PUT. Reproducido: `prof2` borró las clases asignadas al evento de `prof1`, que dejó de verlo; con `class_ids` propios se queda con el evento y accede a retos, pistas, exportación, analíticas.
2. **P0 — Un instructor puede inscribir a cualquier estudiante del colegio en su clase** (`PUT /classes/{id}/students`) por ID numérico, y desde ahí leer su progreso y reiniciarlo. Reproducido (`alumno1` quedó inscrito en la clase de otro docente).
3. **P1 — Importación CSV fuera de alcance**: busca la clase por nombre solo con `academic_period=""`; con períodos reales crea clases duplicadas, y con período vacío puede añadir cuentas a clases de otro docente. Las clases creadas por un ADMIN quedan con el admin como «docente».
4. **P1 — `must_change_password` no se aplica en el servidor**: un estudiante con contraseña temporal usa toda la API sin cambiarla.
5. **P1 — `make up` no deja un sistema usable**: no hay migraciones; el login devuelve 500 en texto plano. `make migrate`/`make seed` ejecutan `uv` en el host sin `DATABASE_URL` y MySQL no está publicado: no pueden funcionar. `make reset-db` solo hace `down -v`.
6. **P1 — Pantallas placeholder**: Configuración, Roles, Bitácora, Recursos, Ayuda («Esta sección se está preparando… Fase N») y Marcador/Eventos/Retos para admin e instructor. El backend de settings/roles/auditoría/marcador existe, pero no hay forma de usarlo desde la UI.

### Por categoría

- **Seguridad:** P0×2, P1×2 (CSV, must_change), P2: autodesactivación/último admin, bloqueo de cuenta ajeno (DoS) y contabilización de logins correctos en el limitador, IP compartida por el proxy, sesiones no revocadas al cambiar contraseña, un instructor puede crear instructores. Bien resueltos: CSRF, cookies, hashing Argon2id, enumeración de usuarios, schemas de estudiante sin flags, subidas (tipo por firma, `attachment`, nombre sanitizado, 413), ZIP seguro, CSP/cabeceras, secretos fuera del repo.
- **Arquitectura:** capas `*_api` → `*_service` correctas en general; ownership dependiente de cada endpoint (de ahí los P0). `scoring_api` y `teaching_api` contienen lógica de autorización y agregados que deberían estar en servicios. Sin repositorios (aceptable a este tamaño). Código frontend con ficheros monolíticos (`education.tsx` 1 215 líneas, `ctf-management.tsx` con líneas de varios cientos de caracteres y `any`).
- **UX:** identidad visual coherente y cuidada. Defectos: texto de hoja de ruta visible al usuario («FASE 06», «cuando se habiliten en las siguientes fases»), permisos crudos (`class.manage_students`…) en el espacio del admin, desbordes horizontales (filtros de fechas en analítica a 1440 px; fila del marcador a 390 px), mismo icono para «Eventos» y «Marcador», saludo «Hola, System.».
- **Testing:** sin tests de aislamiento entre docentes (por eso pasaron los P0), sin e2e real, sin test de `must_change_password`, el lint no aplica `no-explicit-any` de forma efectiva.
- **Deployment:** migraciones manuales no documentadas en el Makefile, contenedor backend como root, sin `restart:`, healthcheck que no detecta esquema ausente, build requiere Internet (npm/pip) aunque la ejecución es offline.

## 2. Revisión de TODO/placeholder/mock

Resultados de la búsqueda (`TODO|FIXME|XXX|HACK|NotImplemented|placeholder|dummy|fake|mock|stub`):

| Resultado | Veredicto |
|---|---|
| `security.py` `DUMMY_PASSWORD_HASH` | Intencional (igualar tiempos de login) |
| Atributos HTML `placeholder=` | Intencional |
| `app.test.tsx` `fetchMock` | Intencional (test) |
| `PROGRESS.md` `TODO(fase-futuro)` (LMS, labs Docker, gamificación, almacenamiento compartido de rate-limit) | Deuda declarada, fuera de MVP |
| `WorkspacePage` «Esta sección se está preparando» | **Incompleto presentado como completo** → R-05 |
| `toast("El catálogo de prácticas llegará en la Fase 4.")` | **Incompleto** (botón sin función real) → R-05 |

No hay `NotImplementedError`, `pass` sospechosos ni mocks permanentes en backend.

## 3. Matriz de implementación (SPEC ausente → CONTRACT + fases del encargo)

| # | Área | Requisito | Estado | Evidencia | Problemas | Prio |
|---|---|---|---|---|---|---|
| 1 | Fase 0 | Compose levanta mysql/backend/frontend/nginx | COMPLETE | `docker compose up --build`, 4 sanos | — | — |
| 2 | Fase 0 | `make up` deja el sistema usable | BROKEN | login → 500 tras `make up` | sin migraciones automáticas (R-06) | P1 |
| 3 | Fase 0 | `make migrate` / `seed` / `reset-db` funcionan | BROKEN | `Makefile`; `config.py` exige `DATABASE_URL`; MySQL en red interna | R-06 | P1 |
| 4 | Fase 0 | Migración desde BD vacía | COMPLETE | `alembic upgrade head`, 31 tablas | — | — |
| 5 | Fase 0 | Healthcheck | PARTIAL | `/api/v1/health` = ok sin esquema | no valida migración (R-17) | P3 |
| 6 | Fase 0 | Nginx proxy + cabeceras | COMPLETE | `curl -i`, CSP/XFO/nosniff | — | — |
| 7 | BD | Tipos/colación/FK/UUID públicos (CONTRACT) | COMPLETE | `information_schema` | — | — |
| 8 | BD | `created_at`/`updated_at` en todas las tablas | PARTIAL | faltan en `challenge_progress`, `hint_uses`, `scoreboard_freezes`, profiles… | desviación CONTRACT (R-16) | P3 |
| 9 | BD | Índices para consultas reales | PARTIAL | falta `(user_id, challenge_id)` en `challenge_submissions` | R-15 | P3 |
| 10 | Fase 1 | Login/logout, sesión servidor, Argon2id, cookies | COMPLETE | `flow.py`, `test_auth_*` | — | — |
| 11 | Fase 1 | CSRF | COMPLETE | 403 sin/mal token | — | — |
| 12 | Fase 1 | Rate limit de login | PARTIAL | 8 fallos bloquean al usuario real; cuenta logins correctos; IP = nginx | R-08 | P2 |
| 13 | Fase 1 | Cambio de contraseña obligatorio (temporal) | BROKEN | API usable con contraseña temporal | R-04 | P1 |
| 14 | Fase 1 | Sesiones revocadas al cambiar contraseña | MISSING | `change_password` | R-10 | P2 |
| 15 | Fase 1 | `require_permission` en todos los endpoints | COMPLETE | inventario de endpoints (§4) | — | — |
| 16 | Fase 1 | Aislamiento de eventos entre instructores | BROKEN | `save_event` sin ownership | R-01 | **P0** |
| 17 | Fase 1/3 | Aislamiento de estudiantes entre docentes | BROKEN | `replace_students` | R-02 | **P0** |
| 18 | Fase 1 | Guardas sobre cuentas ADMIN | MISSING | admin se desactivó a sí mismo (200) | R-07 | P2 |
| 19 | Fase 1 | API de settings validada | COMPLETE | 422 ante valor inválido | — | — |
| 20 | Fase 1 | Roles: CRUD API; roles personalizados asignables | PARTIAL | no hay endpoint para asignarlos a usuarios | decisión pendiente (R-16) | P3 |
| 21 | Fase 1 | Auditoría: API | COMPLETE | `/admin/audit` | — | — |
| 22 | Fase 1 | Envelope de errores del CONTRACT | PARTIAL | 404 de ruta = `{"detail"}`; 500 = texto plano | R-09 | P2 |
| 23 | Fase 2 | Design system, tokens, responsive | PARTIAL | capturas; desbordes a 390/1440 px | R-13 | P3 |
| 24 | Fase 2 | Cliente API OpenAPI único | PARTIAL | 5 `fetch` manuales | R-17 | P3 |
| 25 | Fase 2 | UI Configuración / Roles / Bitácora | MISSING | placeholder «Fase 2/1» | R-05 | P1 |
| 26 | Fase 2 | UI Recursos / Ayuda | MISSING | placeholder | R-05 | P2 |
| 27 | Fase 2/10 | Sin CDN, fuentes e iconos locales | COMPLETE | 0 peticiones externas bloqueadas | — | — |
| 28 | Fase 3 | CRUD de usuarios con alcance | PARTIAL | instructor crea instructores sin alcance | R-11 | P2 |
| 29 | Fase 3 | CRUD de clases y rosters (admin) | COMPLETE | `flow.py` | — | — |
| 30 | Fase 3 | Importación CSV (preview/confirm, idempotencia) | BROKEN | clases duplicadas / fuera de alcance | R-03 | P1 |
| 31 | Fase 3 | Contraseña temporal + primer login (UI) | UNVERIFIED | solo el flag; pantalla no ejercitada | — | — |
| 32 | Fase 4 | Eventos/retos/categorías/dificultades/hints/prerrequisitos | COMPLETE | flujo + tests | — | — |
| 33 | Fase 4 | Adjuntos seguros | COMPLETE | HTML→text/plain+attachment, 413, 415, traversal | — | — |
| 34 | Fase 4 | Schemas estudiante sin datos sensibles | COMPLETE | `flow.py` | — | — |
| 35 | Fase 4 | Publicar reto sin flag | BROKEN | 200 y es irresoluble | R-11 | P2 |
| 36 | Fase 4 | Evento de instructor sin clases | BROKEN | creado → 404 al leerlo | R-11 | P2 |
| 37 | Fase 5 | Flags STATIC/REGEX/DYNAMIC_HMAC | COMPLETE | tests + flujo STATIC | — | — |
| 38 | Fase 5 | start/hint/submit/intentos/timer | COMPLETE | flujo STUDENT real | — | — |
| 39 | Fase 5 | Scoring FIXED/TIME_DECAY/DYNAMIC | COMPLETE | `test_scoring.py` | — | — |
| 40 | Fase 5 | Concurrencia (doble envío, 20 alumnos) | COMPLETE | test + lock de fila + clave única | — | — |
| 41 | Fase 5 | Scoreboard global/clase/evento/freeze (API) | COMPLETE | `flow.py` + tests | — | — |
| 42 | Fase 5 | Rate limit de envíos | PARTIAL | cubo por IP compartido (IP nginx) | R-08 | P2 |
| 43 | Fase 6 | Panel docente: formularios de evento/reto/flag/pista | UNVERIFIED | pantalla renderiza; formularios no ejercitados en navegador | R-12 | P2 |
| 44 | Fase 7 | Experiencia estudiante (resumen, eventos, reto, marcador) | COMPLETE | capturas + flujo API | — | — |
| 45 | Fase 7 | Marcador para admin/instructor (UI) | MISSING | placeholder | R-05 | P1 |
| 46 | Fase 8 | Analítica/aula en vivo/detalle de estudiante | COMPLETE | captura + tests + alcance | — | — |
| 47 | Fase 8 | Exportaciones CSV/XLSX/PDF | PARTIAL | válidas; XLSX deja en blanco los ceros | R-14 | P3 |
| 48 | Fase 8 | Avisos por clase | COMPLETE | publicado y visible solo a su clase | — | — |
| 49 | Fase 9 | Importador/exportador ZIP seguro | COMPLETE | roundtrip, zip-slip, no-ZIP, sin flag en claro | — | — |
| 50 | Fase 10 | Backups con checksums | COMPLETE | `backup.sh` real + `sha256sum -c` (restore no repetido aquí) | — | — |
| 51 | Fase 10 | Pruebas de carga | PARTIAL | solo smoke de 20 envíos concurrentes | — | P3 |
| 52 | Transversal | Tests de seguridad/permisos/e2e | PARTIAL | ver §6 | R-12 | P1 |

Recuento (comprobado con `awk` sobre la columna Estado): COMPLETE 24, PARTIAL 13, BROKEN 8, MISSING 5, UNVERIFIED 2 = 52.

## 4. Auditoría de API

Inventario completo: ~110 rutas bajo `/api/v1` (auth 6, admin 8, users 8, classes 7, ctf catálogo/eventos/retos/ficheros ~34, scoring ~22, teaching 11, health 1). Verificado por lectura de cada router:

- **Todo endpoint no público depende de `require_permission` o `current_session`**; todas las mutaciones llevan `require_csrf`. Sin endpoints olvidados.
- Los endpoints usan `response_model` solo en `users` y `classes`; el resto devuelve `dict` construido a mano (no hay modelos ORM expuestos; sí se pierde documentación OpenAPI precisa).
- **IDOR / BOLA confirmados:** `PUT /ctf/events/{id}` (R-01), `PUT /classes/{id}/students` (R-02), `POST /users/import/*/confirm` (R-03).
- `POST /users/{id}/password-reset` carga el usuario sin alcance, pero solo ADMIN tiene `user.password_reset` (seguro con los roles por defecto; frágil con roles personalizados).
- Paginación: `page/page_size/items/total` correcta con límites (422 a `page_size=100000`).
- Sin `Cache-Control: no-store` en respuestas con datos personales (P3).

## 5. Pruebas negativas ejecutadas (resultado)

Pasan: anónimo→401; STUDENT→403 en 10 rutas de admin; STUDENT no crea ADMIN; CSRF ausente/erróneo→403; sesión revocada→401; alumno de otra clase: sin evento, no inicia, no envía, sin progreso, sin marcador de clase/evento, sin descarga de fichero; instructor B no ve evento/clase/estudiante de A, no analiza ni reinicia progreso ajeno, no reinicia contraseñas; enumeración de usuarios (misma respuesta); fuerza bruta→429; cuerpo inválido→422 con envelope; ID inexistente→404 con envelope; subida de 11 MB→413; binario/ejecutable→415; nombre con traversal sanitizado; HTML subido se sirve como `text/plain` + `attachment`; ZIP con `../` rechazado; no-ZIP rechazado; payload XSS almacenado y renderizado con `react-markdown` sin HTML crudo.

**Fallan (5):** `must_change_password` no bloquea (R-04); **instructor modifica evento ajeno (R-01)**; **instructor inscribe estudiante ajeno (R-02)**; instructor crea cuentas INSTRUCTOR (R-11, decisión de diseño por confirmar); el usuario legítimo queda bloqueado por intentos fallidos de un tercero (R-08).

## 6. Auditoría de tests

- Backend: 41 tests rápidos y pertinentes (flags/HMAC, scoring, concurrencia, ZIP seguro, límites del limitador, CSV con fórmulas). **Ninguno** prueba aislamiento entre docentes en escritura, `must_change_password`, ni cobertura de errores 404/500.
- Frontend: 5 tests (render/permisos); sin tests de formularios ni de flujo de reto.
- E2E: 1 test que se salta sin credenciales; `make test` lo cuenta como verde.
- ESLint: configuración mínima; `useState<any>` y `as any` pasan sin avisos.
- Sin tests flaky detectados en dos ejecuciones.

## 7. Auditoría de rendimiento

- `student_summary` recalcula `progress_for_student` por fila (N+1, dos veces).
- `_check_prerequisites` carga **todos** los retos de la plataforma para construir el grafo.
- `get_event_challenges` por evento carga con `selectinload` (bien).
- Marcador: una consulta agregada con `GROUP BY` (bien); sin caché, aceptable para un aula.
- Falta índice compuesto en `challenge_submissions`.
- Todo P3 para el tamaño de un colegio; ninguno bloquea un piloto.

## 8. Auditoría offline

PASS. No hay URLs externas en `frontend/src`, `index.html`, `nginx`; fuentes vía `@fontsource` locales; con todas las peticiones a hosts no locales abortadas, tres roles recorrieron 25 pantallas y se registraron **0** intentos externos. Matiz: `docker compose build` necesita Internet (npm/pip/imágenes); para una LAN aislada hay que construir o importar las imágenes antes.

## 9. Git

Árbol limpio; tag `audit-baseline` creado. Versionado indebidamente: `frontend/tsconfig.tsbuildinfo` (artefacto). `.env` correctamente ignorado y no versionado. Búsqueda de secretos en ficheros versionados (patrones de claves/tokens/cadenas largas): **sin secretos reales**; solo valores de ejemplo en `.env.example`. `lab-manager/` y `tests/` existen como directorios vacíos no versionados.

## 10. Documentación

`README.md`/`docs/INSTALLATION.md` describen `docker compose exec backend uv run alembic upgrade head` y `app.seed` (correcto) pero omiten que `make migrate`/`make seed` no sirven; describen un seed sin usuarios de demostración (correcto: solo admin + evento `[DEMO]`). `PROGRESS.md` marca como completas fases cuya UI es placeholder, y cita 40 tests (hay 41). `docs/DESIGN_SYSTEM.md`/`DesignPage` muestran una paleta (`#f4f0e7`, `#16e654`…) distinta de la decisión vigente en `DECISIONS.md` (`#142550`/`#1BAEC3`).

## 11. Re-auditoría tras la reparación (2026-10-04)

Misma matriz de §3, reevaluada con la evidencia de `docs/FINAL_VERIFICATION.md` (instalación limpia, 80/80 comprobaciones API, 3 e2e en navegador, pasada visual/offline, backup+restore, concurrencia).

| Filas | Antes | Después | Evidencia del cambio |
|---|---|---|---|
| 2, 3, 5 | BROKEN / BROKEN / PARTIAL | COMPLETE | migración al arrancar; recetas de `make` ejecutadas; health solo responde con esquema aplicado |
| 9 | PARTIAL | COMPLETE | índice `ix_challenge_submissions_user_challenge` (migración `c7e1f0a9b3d2`) |
| 12, 42 | PARTIAL | COMPLETE | solo fallos, clave equipo+usuario, IP real vía Nginx |
| 13, 14 | BROKEN / MISSING | COMPLETE | `PASSWORD_CHANGE_REQUIRED`; revocación de otras sesiones |
| 16, 17, 30 | BROKEN | COMPLETE | `test_isolation.py` (8 tests que fallan contra la línea base) |
| 18, 22 | MISSING / PARTIAL | COMPLETE | `test_hardening.py` |
| 25, 26, 45 | MISSING | COMPLETE | Configuración, Roles, Bitácora, Ayuda, Marcador del personal; `admin.test.tsx` |
| 28, 35, 36 | PARTIAL / BROKEN / BROKEN | COMPLETE | solo ADMIN crea instructores; publicar exige bandera; evento con clase propia |
| 31, 43 | UNVERIFIED | COMPLETE | e2e `student-journey` e `instructor-journey` |
| 47 | PARTIAL | COMPLETE | ceros en XLSX/PDF |
| 8, 20, 23, 24, 51, 52 | PARTIAL | PARTIAL | desviaciones y deuda documentadas (ver `DECISIONS.md`) |

**Recuento después: COMPLETE 46, PARTIAL 6, BROKEN 0, MISSING 0, UNVERIFIED 0 (52).** No quedan P0 ni P1 conocidos. Hallazgos nuevos durante la reparación, ya corregidos: tras el cambio obligatorio de contraseña la UI no salía de esa pantalla (lo detectó el e2e); el ajuste «scoreboard visible» ocultaba el marcador también al personal; el pie decía «SESIÓN CIFRADA» sobre HTTP; las hojas de estudiante/docencia usaban hex fijos que rompían el tema oscuro.

Hallazgo adicional de la re-auditoría: `docs/openapi.json` (y con él `frontend/src/api/schema.d.ts`) estaba desfasado y no incluía 12 rutas de las fases 8 y 9 (`/teaching/*`, importación y exportación ZIP). Se regeneró desde la aplicación (55 → 67 rutas). El cliente tipado ya cubre esos endpoints; migrar los `fetch` manuales restantes a él sigue siendo deuda P3.

## 12. Auditoría contra `docs/SPEC.md` v4 (2026-10-04)

El SPEC llegó después de la reparación. Cambia el alcance: CyberLab es **plataforma pedagógica + CTF**, con currículo, actividades de varios tipos, evidencias de plataformas externas y un modelo de notas propio. Las fases del SPEC (0–13) no coinciden con las del repositorio (0–10): el repo no tiene equivalente a la fase 4 del SPEC (currículo y actividades) ni a la 11 (plataformas externas y evidencias), y solo cubre una parte de la 6 (notas).

### 12.1 Criterios de aceptación del MVP (§17)

| # | Criterio | Estado | Evidencia / problema |
|---|---|---|---|
| 1 | Se levanta desde cero con `make up` según la documentación | COMPLETE | instalación limpia verificada (§FINAL_VERIFICATION) |
| 2 | El profesor crea estudiantes (manual y CSV) y una clase | COMPLETE | flujo API + UI |
| 3 | Curso → módulos → lecciones → actividades desde la interfaz | MISSING | no existen tablas, API ni UI de currículo |
| 4 | Evento CTF y reto completo (flags, hints, puntos, adjuntos) solo desde la UI | PARTIAL | e2e del docente cubre evento, reto, bandera y publicación; adjuntos y pistas del diálogo no ejercitados en navegador |
| 5 | El estudiante intenta, usa pista, envía flag y ve su puntaje | COMPLETE | e2e `student-journey` |
| 6 | La flag dinámica de un estudiante no funciona para otro | PARTIAL | la validación HMAC es correcta y está probada, pero **no existe forma de entregar al estudiante su flag** (ningún endpoint ni adjunto por estudiante): la estrategia no es usable en clase |
| 7 | El tiempo lo mide el servidor | COMPLETE | `started_at` del servidor; test con reloj manipulado |
| 8 | Scoreboard y dashboards correctos; el profesor los activa/desactiva | PARTIAL | dashboards correctos; el interruptor es un ajuste global solo editable con `settings.update` (ADMIN); no hay ranking por clase/módulo/periodo ni «evolución en el tiempo» (§12) |
| 9 | ZIP con `challenge.yml`: previsualizar, corregir, publicar | COMPLETE | importa como borrador, se edita y publica |
| 10 | Plataforma externa + actividad externa + evidencia + aprobación | MISSING | sin `external_platforms`, evidencias, cola de revisión |
| 11 | Categorías, dificultades, escala de notas y **pesos** editables sin código | PARTIAL | categorías/dificultades/escala sí; no hay pesos ni modo lineal de la escala |
| 12 | Notas provisionales → finales congeladas con instantánea | MISSING | sin `grade_periods`, `module_grades`, `final_grades` |
| 13 | Exportar progreso y notas a CSV/XLSX | PARTIAL | exporta XP y una «nota» derivada del XP, no las notas del modelo §7.2 |
| 14 | Un estudiante no ve datos de otros ni funciones administrativas | PARTIAL → corregido en parte | funciones admin: verificado. El ranking global (con nombres) estaba **activado por defecto**; ahora viene desactivado (§4, §7.5). Faltan rankings por ámbito que el profesor active |
| 15 | La UI cumple la dirección visual y accesibilidad básica | PARTIAL / CONFLICTO | el SPEC pide «consola de operaciones», modo oscuro por defecto; `DECISIONS.md` registra como **aprobada** la identidad «cuaderno universitario» con modo claro por defecto. Requiere decisión |
| 16 | Todos los tests pasan; lo no implementado marcado `TODO` | PARTIAL | 61 + 24 + 3 e2e pasan; faltan los tests obligatorios de §16 sobre calificación y evidencias, y lo ausente no está marcado `TODO(fase-N)` en el código |

Recuento: COMPLETE 5, PARTIAL 8, MISSING 3 (16). **≈ 31 % de los criterios de aceptación cumplidos**.

### 12.2 Alcance MVP (§3.1)

| # | Elemento | Estado |
|---|---|---|
| 1 | Auth, sesiones, RBAC con permisos editables | PARTIAL: permisos editables en UI; crear roles solo por API; roles personalizados no asignables |
| 2 | Usuarios, clases, CSV | COMPLETE |
| 3 | Currículo cursos→módulos→lecciones→actividades | MISSING |
| 4 | Tipos de actividad (`lesson_read`, `quiz`, `exercise`, `external_challenge`, `project`, `ctf_challenge`) con registro extensible | MISSING (solo existe el reto CTF, fuera de un modelo de actividades) |
| 5 | Progreso por estudiante, **módulo** y clase | PARTIAL: por estudiante, clase y evento |
| 6 | Evidencia y aprobación | MISSING |
| 7 | Pistas en español con costo | COMPLETE |
| 8 | Puntuación, XP, escala configurable | PARTIAL: el modelo difiere de §7.1 (ver 12.3) |
| 9 | Dashboards estudiante y profesor | COMPLETE (sobre CTF) |
| 10 | Anuncios y notificaciones | COMPLETE |
| 11 | Exportación CSV/XLSX/PDF | COMPLETE (formato), PARTIAL (contenido de notas) |
| 12 | Importación de progreso externo por CSV | MISSING (depende de 6) |
| 13 | Motor CTF | PARTIAL: flag dinámica no entregable; ranking configurable por ámbito ausente |
| 14 | Creador de retos y CTF + importador ZIP | COMPLETE |
| 15 | Auditoría y configuración desde el panel | COMPLETE |
| 16 | Plan de 9 meses como seed editable | MISSING |

### 12.3 Diferencias de comportamiento con el SPEC

- **Puntaje (§7.1):** el SPEC define base 70 + bonus de tiempo hasta 20 (lineal hasta 3× el tiempo estimado) + reflexión 10 − costo de pistas, con piso del 30 %, penalización por intento apagada, valores editables por evento y reto. El sistema calcula `puntos × multiplicador de categoría × multiplicador de dificultad` con estrategias FIXED/TIME_DECAY/DYNAMIC_BY_SOLVES, y las pistas restan del libro de XP sin piso. No hay reflexión ni tiempo estimado por reto.
- **XP (§7.5):** el SPEC separa puntos (nota) de XP (= puntos × multiplicador de dificultad, **no afecta la nota**). El sistema usa el XP como puntuación y deriva la nota del XP total.
- **Notas (§7.2–7.4):** faltan porcentaje por módulo, escala lineal, pesos por tipo de actividad, nota provisional/final con instantánea, recálculo explícito con motivo, ajuste manual auditado (`score_adjustments`), aviso de actividades sin revisar y niveles.
- **Seed (§5, §20):** categorías del SPEC (Linux, Redes, Web, Criptografía, Forense, Seguridad general) y dificultades BEGINNER…EXPERT; el seed actual usa otras. Faltan instructor, estudiantes, curso demo, plataformas sugeridas y el plan de 9 meses.
- **Infraestructura (§13):** falta el servicio `worker` (revisión de enlaces externos y tareas diferidas); `.env.example` no tiene `ADMIN_EMAIL`, `SESSION_TTL`, `MAX_UPLOAD_MB`, `TIMEZONE` y usa `BACKEND_SECRET_KEY` en lugar de `SECRET_KEY`.
- **Privacidad (§11):** no hay política de retención y eliminación en `SECURITY.md` ni forma de **borrar** los datos de un estudiante (solo desactivar).
- **Arquitectura (§8):** el backend es plano (`*_api.py`/`*_service.py`), no `modules/<nombre>/{models,schemas,service,router,permissions,tests}`; el frontend no está organizado en `features/<nombre>`; nombres de tabla distintos de §9 (`challenge_flags`, `challenge_submissions`, `hint_uses`… frente a `flags`, `submissions`, `hint_usage`…).
- **Red (§2):** el SPEC ya no exige operación solo-LAN. Lo verificado sobre offline sigue siendo válido pero deja de ser requisito.

### 12.4 Estado tras la fase 4 del SPEC (2026-10-05)

| Ref. | Antes | Después | Evidencia |
|---|---|---|---|
| §17.3 Curso → módulos → lecciones → actividades desde la UI | MISSING | COMPLETE | e2e `curriculum-journey` (docente solo con la interfaz; la estudiante completa el cuestionario y el docente ve 100 % en Progreso) |
| §17.16 Tests y `TODO` | PARTIAL | PARTIAL | currículo cubierto; faltan los tests obligatorios de calificación (fase 6) y evidencias (fase 11) |
| §3.1.3 Currículo | MISSING | COMPLETE | `test_curriculum.py` |
| §3.1.4 Tipos de actividad | MISSING | PARTIAL | 5 de 6 tipos; `external_challenge` llega con la fase 11 |
| §3.1.5 Progreso por estudiante, módulo y clase | PARTIAL | COMPLETE | matriz de progreso por módulo |
| §3.1.16 Plan de 9 meses como seed editable | MISSING | COMPLETE | plantilla compartida, duplicable |

Criterios de aceptación: **COMPLETE 6, PARTIAL 7, MISSING 3** de 16 (antes 5/8/3). Siguen ausentes §17.10 (evidencias), §17.12 (notas provisionales y finales); el resto de parciales dependen de la fase 6.
