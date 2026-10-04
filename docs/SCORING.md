# Motor de flags y puntuación

Este documento describe el motor de flags y puntuación. El espacio docente y la experiencia estudiantil ya incluyen sus pantallas; las peticiones de cambio usan la cookie de sesión y `X-CSRF-Token`.

## Flags

Un administrador o instructor con `challenge.update` administra varias flags por reto desde:

- `GET/POST /api/v1/ctf/events/{event_id}/challenges/{challenge_id}/flags`
- `DELETE /api/v1/ctf/events/{event_id}/challenges/{challenge_id}/flags/{flag_id}`

Estrategias disponibles:

- `STATIC`: se persiste SHA-256, se compara en tiempo constante. Para flags estáticas conviene usar valores aleatorios.
- `REGEX`: se valida con `fullmatch`; se admiten expresiones de hasta 256 caracteres. Se rechazan referencias, lookarounds y cuantificadores de grupos para evitar expresiones de coste descontrolado.
- `DYNAMIC_HMAC`: formato con el marcador `{digest}`. El digest es HMAC-SHA256 de `student_id|challenge_id|flag_id`; la misma flag se mantiene para ese estudiante y cambia para otro. La respuesta administrativa solo lista estrategia y formato, nunca la flag ni el patrón.

Configura `FLAG_HMAC_SECRET` en `.env` antes de desplegar, con un secreto aleatorio dedicado y estable. Si se omite, Compose usa `BACKEND_SECRET_KEY` para conservar compatibilidad con las instalaciones actuales; cambiar ese secreto invalida flags dinámicas existentes.

## Flujo estudiantil

Usa el `public_id` del reto en las rutas estudiantiles:

1. `POST /api/v1/ctf/student/challenges/{public_id}/start`
2. `POST /api/v1/ctf/student/challenges/{public_id}/submit` con `{"flag":"..."}`
3. `POST /api/v1/ctf/student/challenges/{public_id}/hints/{hint_id}`
4. `GET /api/v1/ctf/student/challenges/{public_id}/progress`

El servidor fija `started_at`, mide el tiempo y aplica pausas; no acepta tiempo del navegador. El inicio es idempotente. El primer solve completa el reto y registra puntos una sola vez. Los intentos guardan un hash del texto enviado, nunca la flag en claro. Las pistas se revelan una por una y su coste se registra como transacción negativa de XP.

El límite efectivo de intentos es el menor entre `max_attempts_global`, el máximo del evento y el máximo del reto que estén configurados. `submission_rate_limit` limita los envíos de cada estudiante; el límite de la IP compartida tiene un mínimo de 60 por minuto para que una clase detrás del mismo proxy no se bloquee al iniciar una práctica. Los contadores residen en memoria y son por proceso; las restricciones de intentos sí quedan persistidas en MySQL.

## Puntuación y notas

Cada premio usa `challenge.points × category.multiplier × difficulty.multiplier`, redondeado a entero. El evento define la estrategia y el reto puede sobrescribirla:

- `FIXED`: conserva la base.
- `TIME_DECAY`: reduce la base según `window_seconds` hasta `minimum_ratio`, usando el tiempo activo del servidor.
- `DYNAMIC_BY_SOLVES`: reduce la base en `decay_per_solve` por cada solve anterior del evento, hasta `minimum_ratio`.

La suma del ledger `xp_transactions` incluye los premios y las penalizaciones de pistas. Los umbrales de `grade_scales` asignan el grado más alto cuyo `min_score` no supere el puntaje. Se editan con `POST/PUT /api/v1/ctf/grade-scales`.

`GET /api/v1/ctf/scoreboard?scope=GLOBAL|CLASS|EVENT&scope_id=...` devuelve puestos con empates. En el caso `EVENT`, `scope_id` es el `public_id` del evento; para `CLASS` es el ID de la clase asignada. `scoreboard_enabled` controla su disponibilidad. Un administrador puede congelar cualquier alcance, y un instructor puede congelar los eventos o clases que tiene asignados; se guarda o retira un snapshot con `POST /api/v1/ctf/scoreboard/freeze`.

## Control docente y próximos pasos

Con permiso `event.manage`, el profesor puede pausar/reanudar o reiniciar el progreso de un estudiante en un reto mediante `POST /api/v1/ctf/instructor/events/{event_id}/challenges/{challenge_id}/progress/{student_id}/pause` (`{"paused":true|false}`) y la ruta hermana `/reset`. El reset elimina el progreso, intentos, pistas usadas y transacciones de ese estudiante para ese reto.

Las notificaciones de `CHALLENGE_SOLVED`, `SUBMISSION_FAILED` y `HINT_USED` quedan persistidas y están disponibles en el centro de notificaciones del estudiante.
