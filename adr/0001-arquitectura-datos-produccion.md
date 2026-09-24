# ADR-0001: Arquitectura estática + object storage (R2) para payloads precalculados

- **Estado**: Propuesto (2026-09-20) — pendiente de confirmación del usuario.
- **Contexto**: NODO UNAM sirve datos precalculados por tesis (vecindarios semánticos, ~2-5KB por archivo). Cloudflare Pages (donde vive el sitio hoy) tiene un límite práctico de ~20,000 archivos por deployment. Precomputar vecindarios para las 609,156 tesis del corpus completo generaría cientos de miles de archivos, muy por encima de ese límite, y el volumen total puede acercarse a cientos de MB–unidades de GB.
- **Decisión**: Los datasets precalculados de alto volumen (muchos archivos pequeños o pocos archivos grandes) se sirven desde **Cloudflare R2** (object storage, sin límite práctico de objetos, sin costo de egress dentro de la red de Cloudflare), no desde el deployment de Pages. El frontend los consume vía un dominio público de R2 o un Worker delgado con cache, con `Cache-Control: immutable` dado que estos archivos no cambian hasta la siguiente corrida del pipeline.
- **Consecuencias**:
  - (+) Cero límite de archivos, cero costo de banda dentro de Cloudflare, cacheable en el edge.
  - (+) El navegador de un usuario nunca descarga el dataset completo — solo el archivo de la tesis que visita.
  - (-) Requiere un paso de build/deploy adicional (subir a R2) separado del deploy de Pages.
  - (-) Requiere convención de versionado de rutas (ver nota de rollback abajo) para no mezclar snapshots viejos/nuevos del pipeline a mitad de un despliegue.
- **Nota de versionado**: subir cada regeneración bajo una ruta con versión (`r2://neighborhood/v2/...`) y cambiar el `dataBaseUrl` del frontend al final del despliegue — permite rollback instantáneo cambiando un string.
