# Fase 2 — sistema visual y base del frontend

**Estado: completada.** Dirección editorial aprobada por el usuario. La pantalla de referencia queda en `/`, la biblioteca de componentes en `/design` y el acceso funcional en `/login`.

## Identidad

CYBERLAB se presenta como un cuaderno de investigación universitario: papel cálido, tinta verde oscura, rojo de señalización, serif editorial y tipografía técnica mono para etiquetas. La ilustración principal es una lámina de análisis hecha en CSS. La composición usa jerarquía editorial y anotaciones de laboratorio en lugar de tarjetas repetidas de dashboard.

Inter, Lora e IBM Plex Mono se sirven desde los paquetes locales. No hay fuentes ni iconos desde CDN. Los tokens semánticos viven en `frontend/src/workspace.css`; claro es el tema inicial y oscuro está disponible en la interfaz.

## Páginas

- `/`: portada pública y punto de entrada al campus.
- `/design`: catálogo interactivo de estados, campos, tabla, diálogo, panel, tabs, toast, tooltip, carga, vacío, error, Markdown, paleta de comandos y temas.
- `/login`: formulario validado conectado a `/api/v1/auth/login`.
- `/workspace`: espacio privado con shell, navegación, búsqueda global, breadcrumbs y selector de tema.
- `/403` y `/404`: estados de acceso denegado y página inexistente.

La navegación se define en `frontend/src/app/routes.ts` y filtra por los permisos devueltos desde `/api/v1/auth/me`. Los permisos ausentes en rutas aún no construidas ocultan esas secciones hasta las fases correspondientes.

## Componentes y accesibilidad

`frontend/src/components/ui.tsx` contiene Button, Input, Textarea, Select, Checkbox, Switch, Badge/StatusDot, tabla TanStack con búsqueda, orden, paginación y selección, Dialog, Drawer, Tabs, Toast, Tooltip, Skeleton, EmptyState, ErrorState, Markdown seguro y CommandPalette (Ctrl/Cmd+K). Las primitivas Radix manejan foco y teclado; los controles tienen nombres, foco visible, estados textuales y diseño adaptable.

El cliente de sesión usa OpenAPI TypeScript generado desde `docs/openapi.json`, TanStack Query, cookies HTTP-only, cabecera CSRF, cierre de sesión y guardas para sesión expirada y permisos.

## Verificación

`npm test`, `npm run lint`, `npm run build`, `pytest`, Ruff y mypy se ejecutan para esta fase. El smoke E2E de Playwright usa un Chromium local, credenciales definidas en `CYBERLAB_E2E_USERNAME` y `CYBERLAB_E2E_PASSWORD`, y confirma login y logout reales.

Para regenerar los tipos tras cambiar la API: `cd frontend && npm run api:generate`.
