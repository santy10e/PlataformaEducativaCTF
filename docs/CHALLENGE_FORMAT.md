# Formato portable de retos — versión 1

Los paquetes son archivos ZIP de datos. Cyberlab lee los manifiestos YAML con un cargador seguro; no ejecuta scripts, binarios ni comandos incluidos en el ZIP. La importación siempre deja los retos como `DRAFT`.

## Paquete de un reto

Incluye exactamente un `challenge.yml` en cualquier carpeta. Las rutas de archivos adjuntos son relativas a la carpeta que contiene ese manifiesto.

```yaml
format_version: 1
slug: request-trace
title: Sigue la pista de la solicitud
category: Web
difficulty: Inicial
description_markdown: |
  Examina la evidencia y explica qué valor falta en la solicitud.
points: 100
sort_order: 0
delivery_config: {}
scoring_strategy: FIXED
prerequisites: []
hints:
  - content_markdown: Empieza por inspeccionar los encabezados.
    cost: 5
flags:
  - strategy: STATIC
    value: CYBERLAB{example_answer}
files:
  - path: files/evidence.txt
    name: evidence.txt
    content_type: text/plain
```

Valores permitidos de estrategia: `FIXED`, `TIME_DECAY`, `DYNAMIC_BY_SOLVES`. Las banderas estáticas importadas desde un manifiesto escrito a mano usan `value`; un ZIP exportado por Cyberlab usa `matcher_sha256` para conservar la bandera sin revelar su valor original. Los patrones `REGEX` deben pasar la validación segura del backend. Las banderas `DYNAMIC_HMAC` se describen con `format` y deben contener `{digest}`.

## Paquete de evento

Para agrupar varios retos, agrega `ctf.yml` en la raíz. Cada referencia debe señalar un `challenge.yml` dentro del ZIP. Las categorías y dificultades deben existir en el Cyberlab de destino; las relaciones de prerrequisito se indican por `slug`.

```yaml
format_version: 1
name: Práctica de investigación web
challenges:
  - 01-request-trace/challenge.yml
  - 02-cookie-notes/challenge.yml
```

Cyberlab importa en el evento seleccionado por el profesor, no crea ni reasigna eventos desde el ZIP. Un slug existente en ese evento se actualiza; uno nuevo se crea. Adjuntos anteriores del reto se sustituyen por los del paquete. Los slugs deben ser únicos y los prerrequisitos no pueden contener referencias ausentes ni ciclos.

## Límites y seguridad

- ZIP de hasta 20 MB; 1000 entradas como máximo; contenido expandido total de hasta 50 MB.
- Cada archivo adjunto admite hasta 10 MB y cada manifiesto hasta 128 KB.
- No se admiten rutas absolutas, `..`, rutas Windows, entradas cifradas, enlaces simbólicos, rutas duplicadas, claves YAML duplicadas ni alias YAML.
- Los adjuntos se escriben con nombres aleatorios generados por el servidor. Las rutas del ZIP nunca se usan como rutas de escritura.
- Preview valida nuevamente al confirmar. El navegador reenvía el mismo archivo para que el backend no necesite guardar paquetes pendientes.
- Archivos del ZIP no referenciados se reportan como advertencias y se ignoran.

El seed de desarrollo incluye el evento borrador `[DEMO] Paquete de práctica Cyberlab` y tres retos `[DEMO]`, identificables por título y slug. No se publican automáticamente.
