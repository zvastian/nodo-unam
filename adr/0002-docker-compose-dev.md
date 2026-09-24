# ADR-0002: Entorno de desarrollo local con Docker Compose + reverse proxy

- **Estado**: Aceptado (2026-09-20).
- **Contexto**: Hoy, probar la app localmente requiere levantar a mano el servidor estático y (cuando aplica) la API de FastAPI en puertos distintos, sin garantía de que el entorno sea igual entre sesiones o máquinas. `requirements.txt` no tiene versiones fijadas, lo que agrava el problema de reproducibilidad.
- **Decisión**: Entorno de dev definido como 3 servicios en `docker-compose.yml`:
  1. `api` — FastAPI/uvicorn con `--reload`, corriendo contra una **muestra de datos** (`sample_50k_*.parquet`), no el corpus completo, para iteración rápida.
  2. `static` — servidor de archivos estáticos sirviendo `deploy/static/`.
  3. `proxy` — reverse proxy (Caddy) que expone un solo origen: `/api/*` → `api`, todo lo demás → `static`. Mismo esquema de rutas que usará producción, para paridad dev/prod real.
  - Un solo comando (`docker compose up`) levanta el entorno completo en cualquier máquina, sin depender de instalaciones globales de Python/Node en el host.
- **Consecuencias**:
  - (+) Reproducibilidad entre máquinas/sesiones.
  - (+) Elimina bugs de "asume que la API vive en localhost:8000" en el frontend (mismo bug que causó el error de vecindario en producción).
  - (-) Requiere Docker Desktop instalado en Windows.
  - (-) Pendiente: fijar versiones en `requirements.txt` (o migrar a `pip-tools`/`poetry`) para que la imagen de `api` sea reproducible bit a bit.
