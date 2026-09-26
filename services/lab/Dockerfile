# Servicio de datos del Laboratorio (ADR-0015). La imagen lleva solo el código: los artefactos
# (modelo ONNX de 2.2 GB, índice y metadatos, unos 3 GB) se montan o se descargan al arrancar
# en LAB_ARTEFACTOS. PENDIENTE (paso 4, despliegue): descarga desde Cloud Storage al arrancar.
# Probado en local con Docker 29.8 (2026-09-26): misma salida que el servicio en Windows.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LAB_ARTEFACTOS=/artefactos
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --system --uid 10001 lab
USER lab
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
