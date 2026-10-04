# Seguridad y operación

## Controles incluidos

- Contraseñas con Argon2id; cookies de sesión `HttpOnly`, `SameSite=Lax` y `Secure` cuando la petición externa usa HTTPS.
- No hay política CORS permisiva: frontend y API comparten origen; cualquier origen adicional debe ser institucional, específico y habilitarse con credenciales solo cuando sea necesario.
- Token CSRF requerido en operaciones que cambian estado; permisos por rol y alcance docente comprobados en el servidor.
- Sesiones con token aleatorio, persistidas como hash; la tarea de mantenimiento elimina sesiones expiradas hace más de siete días y sesiones revocadas antiguas.
- Los envíos de bandera se validan en backend. Los registros de contraseñas estáticas de bandera se guardan como hash; las respuestas estudiantiles no revelan valores privados.
- Nginx añade CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy`; limita solicitudes a 21 MB.
- No se cargan fuentes, scripts ni hojas de estilo desde CDN. El frontend incluye localmente sus recursos.
- Los paquetes de retos se validan como datos; no ejecutan comandos incluidos. Consulta [CHALLENGE_FORMAT.md](CHALLENGE_FORMAT.md).

## Antes de abrir la plataforma

1. Cambia todas las credenciales de `.env`; usa claves aleatorias largas y separadas. No compartas ese archivo ni lo adjuntes a incidencias.
2. Define `APP_ENV=production`, controla quién puede leer el servidor y limita `docker`/Docker Desktop a administradores. El acceso al daemon Docker equivale prácticamente a administración del host.
3. Mantén Docker, imágenes base y dependencias actualizados. Revisa cambios de seguridad antes de desplegar actualizaciones.
4. Expón la aplicación solo en una VLAN institucional controlada. Configura TLS en un gateway confiable delante de Nginx; el Compose incluido sirve HTTP y no provisiona certificados.
5. Guarda las copias fuera del host, restringe su acceso y cifra el destino de almacenamiento. Las copias contienen datos personales, sesiones, resultados y archivos de retos.
6. Revisa usuarios administradores y docentes, permisos, registros y accesos al servidor al terminar cada periodo académico.

## Límites conocidos

- Los limitadores de login y envíos viven en memoria por proceso; reiniciar el backend los reinicia y varias réplicas no comparten los contadores. Los envíos limitan por estudiante y aplican una ráfaga mínima de 60 por IP compartida; login admite 8 por usuario y 120 por IP cada cinco minutos. Si se escala horizontalmente, añade almacenamiento compartido.
- Nginx usa HTTP en el Compose base. `Secure` en cookies se activa cuando el gateway entrega `X-Forwarded-Proto: https`; Nginx lo pasa a la API, así que solo debe confiarse ese encabezado desde el proxy institucional de confianza.
- El health check confirma disponibilidad de API y base de datos, no sustituye monitoreo, alertas ni verificación periódica de restauraciones.
- `APP_ENV=production` no configura por sí solo TLS, firewall, rotación externa de registros ni gestión de secretos.

## Revisión para cada versión

- Ejecuta Ruff, mypy, las pruebas backend, ESLint, pruebas frontend y build de producción.
- Revisa `npm audit` y una herramienta de auditoría de paquetes Python en un entorno con acceso a los índices; registra excepciones con fecha y responsable.
- Comprueba que el diff no introduce secretos, dependencias CDN, datos de estudiantes o logs de credenciales.
- La auditoría de login conserva usuario e IP para investigar intentos, pero no registra contraseñas, cookies, tokens ni el texto de las banderas enviadas.
- Prueba una restauración en una instancia desechable antes de aprobar cambios del esquema o volúmenes.
