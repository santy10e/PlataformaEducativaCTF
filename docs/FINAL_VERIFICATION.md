# CYBERLAB — Verificación final

Fecha: 2026-10-04. Código: rama `audit/full-project`, línea base `audit-baseline` (`e3c9c63`) más los cambios de esta auditoría (sin commit, para revisión). Todo lo indicado se ejecutó en esta sesión; donde algo no pudo ejecutarse tal cual, se dice.

## Environment

| Componente | Versión real |
|---|---|
| Host | Windows 11 Pro 10.0.26200, Git Bash |
| Docker Engine / Compose | 29.8.0 / 5.5.1 |
| MySQL (contenedor) | 8.4.11 |
| Nginx (contenedor) | 1.30.5 |
| Python backend (contenedor) / uv | 3.12.15 / 0.12.23 |
| FastAPI / SQLAlchemy / Alembic / Pydantic / Uvicorn | 0.142.2 / 2.1.1 / 1.20.0 / 2.13.5 / 0.54.0 |
| Python host (`backend/.venv`) | 3.12.5 |
| Node / npm (host) | 24.18.0 / 11.16.0 (la imagen de build usa `node:22-alpine`, como pide el CONTRACT) |
| React / Vite / TypeScript / TanStack Query / Vitest / Playwright | 19.3.0 / 8.3.2 / 5.9.3 / 5.104.0 / 5.0.3 / 1.63.0 |

**Limitación:** esta máquina no tiene GNU Make ni `uv` en el PATH. `make test` y `make lint` se ejecutaron como sus comandos exactos del `Makefile`, con `backend/.venv` en lugar de `uv run`. Las recetas `make up`, `seed` y `reset-db` se ejecutaron línea a línea con `docker compose`.

## Tests

`make test` (pytest + Vitest):

```text
$ cd backend && pytest
======================== 60 passed, 1 warning in 8.76s ========================
$ cd frontend && npm test
 Test Files  2 passed (2)
      Tests  24 passed (24)
```

`make lint` (Ruff + mypy strict + ESLint + build):

```text
$ cd backend && ruff check . && mypy app
All checks passed!
Success: no issues found in 27 source files
$ cd frontend && npm run lint && npm run build
> eslint .
✓ 2291 modules transformed.
✓ built in 6.72s
```

`make e2e` (Chromium contra la instalación limpia, sin mocks):

```text
✓ login.spec.ts › la sesión real permite entrar al espacio y cerrarla
✓ student-journey.spec.ts › un estudiante resuelve en el navegador un reto preparado por la administración
✓ instructor-journey.spec.ts › un docente crea y publica un reto desde el panel y su estudiante lo resuelve
3 passed
```

La única advertencia de pytest es una deprecación de Starlette sobre `httpx` en `TestClient`.

**Los tests nuevos detectan los fallos:** los 8 de aislamiento fallan contra `audit-baseline` y pasan ahora; para los de endurecimiento se desactivó cada corrección una a una (10 mutaciones) y su test se puso rojo en todos los casos; el de XLSX y el de marcador oculto también fallan con el código anterior.

## Database

- Instalación limpia (`cyberlab-final`, volúmenes nuevos, `build --no-cache`): el backend aplicó las 8 migraciones al arrancar, `alembic current` = `c7e1f0a9b3d2 (head)`, sin pasos manuales.
- Migración nueva verificada en SQLite: `upgrade head` → `downgrade -1` → `upgrade head`.
- Seed ejecutado dos veces: idempotente.
- Ciclo `reset-db`: sin `CONFIRM=yes` no hace nada; con él → volúmenes eliminados, stack reconstruido, migración en head, seed; resultado 1 usuario (admin), 3 retos `[DEMO]`, login 200.
- Esquema conforme al CONTRACT en tipos de ID, `DATETIME(6)`, `utf8mb4_0900_ai_ci`, InnoDB y FK; desviaciones aceptadas de `created_at/updated_at` registradas en `DECISIONS.md`.

## Docker

| Servicio | Estado |
|---|---|
| mysql | Up (healthy) |
| backend | Up (healthy; migra antes de servir) |
| frontend | Up |
| nginx | Up, único puerto publicado |

Todos con `restart: unless-stopped`. MySQL sigue en la red `internal`.

## Functional verification

Instalación limpia desde `.env.example` (solo se sustituyeron los valores de ejemplo), puerto 8081 porque el 80 lo ocupa otro proyecto del usuario.

**ADMIN: PASS**: login; crear 2 instructores, 2 clases y 3 estudiantes; leer, validar y rechazar ajustes inválidos; Configuración, Roles (ADMIN protegido), Bitácora, Marcador global con congelación, Personas, Clases y Analítica en el navegador; desactivarse a sí mismo → 409; backup y restore.

**INSTRUCTOR: PASS**: primer login con contraseña temporal → bloqueado (403 `PASSWORD_CHANGE_REQUIRED`) → cambio → ve solo su clase; crea evento (rechaza clase ajena), reto, bandera y pista; publica; en el navegador crea evento y reto con los diálogos reales y lo publica; ve analítica, aula en vivo, exportaciones CSV/XLSX/PDF y marcador por clase/evento.

**STUDENT: PASS**: primer login → cambio obligatorio → no ve borradores → ve evento publicado → payload sin bandera, hash ni texto de pistas → inicia reto (idempotente) → pista (−10) → bandera incorrecta → correcta (+100) → reenviar no suma → XP 90 → marcador global y de evento; en el navegador el mismo flujo completo, incluida la redirección tras cambiar la contraseña.

Recorrido API con negativos: **80/80** comprobaciones.

## Security

| Categoría | Resultado | Evidencia |
|---|---|---|
| Autenticación (Argon2id, sesiones, expiración, revocación) | PASS | flujo + tests; logout y cambio de contraseña revocan |
| Cookies | PASS | `HttpOnly`, `SameSite=Lax`; `Secure` con `X-Forwarded-Proto: https` |
| CSRF | PASS | sin token / token erróneo → 403 |
| Fuerza bruta / enumeración | PASS | 429 por equipo+usuario; otras cuentas no afectadas; misma respuesta para usuario inexistente |
| Autorización vertical (STUDENT → admin) | PASS | 10 rutas → 403 |
| Autorización horizontal entre docentes (IDOR) | PASS | PUT de evento ajeno → 404 sin cambios; matrícula ajena → 422; CSV no entra en clases ajenas |
| Acceso entre clases (estudiantes) | PASS | evento, reto, envío, progreso, marcador y adjunto → 404 |
| Contraseña temporal | PASS | 403 `PASSWORD_CHANGE_REQUIRED` hasta cambiarla |
| Subidas | PASS | 413 >10 MB; 415 binario/ejecutable; nombre con traversal saneado; HTML servido como `text/plain` + `attachment` |
| ZIP | PASS | zip-slip, no-ZIP rechazados en vivo; symlink/bomba/YAML en tests |
| XSS en Markdown | PASS | `react-markdown` sin HTML crudo; `javascript:` neutralizado |
| Cabeceras / CSP / CORS | PASS | CSP, XFO, nosniff, Referrer-Policy, Permissions-Policy; sin CORS |
| Secretos en el repositorio | PASS | búsqueda de patrones de claves/tokens: solo valores de ejemplo |
| Concurrencia de puntuación | PASS | 20 envíos simultáneos → un único premio, ledger = 100 |
| Formato de error | PASS | 404/405/500 con envelope, sin detalles internos |

## Offline

**PASS.** Con Chromium abortando toda petición a un host que no fuera el local, 3 roles × claro/oscuro × 1440/390 px recorrieron todas las pantallas: **0** peticiones externas, sin placeholders, sin desbordes horizontales y sin errores de API. No hay URLs externas en el bundle ni en las configuraciones de Nginx. Matiz documentado: el *build* sí necesita Internet.

## Documentation

**PASS** con matices. README, INSTALLATION, NETWORK, SECURITY, TROUBLESHOOTING y las guías de administración y docencia se actualizaron al comportamiento real (migración automática, targets, limitador, reglas de alcance, publicación, credenciales reales: solo la cuenta ADMIN de `.env`). La instalación desde cero siguiendo README funcionó.

## Remaining issues

1. **SPEC v4 (recibido después de esta verificación):** se cumplen 5 de los 16 criterios de aceptación; faltan currículo y actividades, el modelo de notas, plataformas externas y evidencias, y una forma de entregar la flag dinámica. Ver `FULL_AUDIT.md` §12. Desde entonces el ranking para estudiantes viene desactivado por defecto (61 tests backend).
2. `make test`/`make lint` no se ejecutaron con GNU Make y `uv` reales (no están instalados aquí); sí sus comandos exactos.
3. Con Docker Desktop (Windows/macOS) todas las conexiones pueden llegar al proxy desde la misma IP NAT, así que el límite por equipo se convierte en un límite por servidor. En Linux no ocurre.
4. P3 aceptados y documentados en `DECISIONS.md`: backend como root, cinco `fetch` manuales fuera del cliente OpenAPI, roles personalizados no asignables, colores heredados sin token (46 hex en hojas de estudiante/docencia) y tablas sin `created_at/updated_at`.
5. Rendimiento: solo hay prueba de 20 envíos concurrentes y el test sintético de 500 estudiantes y 50 000 envíos; no hay prueba de carga sostenida.
