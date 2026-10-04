# Extender Cyberlab

## API/backend

- Modelos SQLAlchemy: `backend/app/models.py`; cambios de esquema siempre requieren una migración Alembic en `backend/migrations/versions/`.
- Reglas de dominio en módulos `*_service.py`; rutas FastAPI en `*_api.py`. Las rutas sensibles exigen dependencias de sesión, CSRF y permiso.
- Registra routers en `backend/app/main.py`. No devuelvas hashes, tokens ni banderas privadas en esquemas públicos.
- Actualiza el contrato OpenAPI versionado en `docs/openapi.json` y regenera tipos con `npm run api:generate` en `frontend/`.

## Interfaz

- La aplicación usa React, TypeScript, React Router y cliente tipado en `frontend/src/api/`.
- Reutiliza componentes en `frontend/src/components/ui.tsx`, protege rutas por permiso y conserva estados de carga, vacío y error.
- Usa tokens del sistema visual; recursos de fuentes e iconos se empaquetan localmente.

## Datos y paquetes de retos

El seed debe poder ejecutarse repetidamente sin duplicar datos. Para un nuevo formato de reto, actualiza validador, límites, exportación, importación y documentación. Los paquetes son datos: nunca ejecutes contenido recibido. Mantén importaciones acotadas por tamaño, ruta, tipo y cantidad.

## Despliegue y compatibilidad

Actualiza instrucciones, riesgos y fase en `PROGRESS.md`. Migra instalaciones existentes de forma compatible, prueba migración desde la revisión anterior y verifica backup/restauración antes de desplegar cambios en tablas o volúmenes. Revisa dependencias frontend y Python en un entorno con acceso a sus índices.
