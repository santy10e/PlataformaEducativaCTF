# Sistema visual

Cyberlab usa una dirección visual de cuaderno universitario: superficies claras, navegación editorial, jerarquía tipográfica sobria y acentos cyan para acciones educativas.

## Tokens de marca

- Navy principal: `#142550`; cyan: `#1BAEC3`.
- Fondo: `#FFFFFF`; fondo secundario: `#F5F7FA`.
- Texto: `#172033`; secundario: `#667085`; bordes: `#D9E1EA`.
- Realces: cyan claro `#E8F8FA`; navy claro `#E9EDF6`.
- Tipografías se incluyen localmente desde `@fontsource`; no agregues un CDN.

## Implementación

Los estilos globales y componentes compartidos están en `frontend/src/style.css`, `fieldbook.css`, `workspace.css` y `education.css`. Usa variables CSS existentes antes de añadir colores nuevos. Componentes base viven en `frontend/src/components/ui.tsx`; los espacios de estudiante/docencia están en `frontend/src/app/`.

Mantén navegación por teclado, foco visible, etiquetas de formulario, contraste legible, estados vacíos y errores claros. Verifica escritorio y móvil y conserva la identidad editorial en lugar de introducir paneles genéricos de métricas o adornos sin función.
