"""Servicio de datos del Laboratorio en Modal (prueba del 2026-09-26; alternativa a Cloud Run).

Sirve la misma app FastAPI de app/main.py, sin cambios. Los artefactos (~2.9 GB) viven en el
volumen «nodos-lab-artefactos» y se montan en /artefactos; la imagen lleva solo el código.

  modal deploy modal_app.py        # publica en https://<workspace>--nodos-lab-servicio.modal.run

La clave compartida con el Worker puerta sale del secreto «nodos-lab» (variable LAB_CLAVE).
Topes de gasto: un solo contenedor y 1 minuto despierto tras la última petición (la espera del
arranque en frío, 12 a 16 s, se acepta: decisión del usuario, 26-sep-2026).
"""
from pathlib import Path

import modal

AQUI = Path(__file__).parent

imagen = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(AQUI / "requirements.txt"))
    .env({"LAB_ARTEFACTOS": "/artefactos", "LAB_HILOS": "2"})
    .add_local_python_source("app")
)
volumen = modal.Volume.from_name("nodos-lab-artefactos", create_if_missing=True)
app = modal.App("nodos-lab")


@app.function(
    image=imagen,
    volumes={"/artefactos": volumen},
    secrets=[modal.Secret.from_name("nodos-lab")],
    cpu=2.0,
    memory=4096,
    max_containers=1,
    scaledown_window=60,
    timeout=120,
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def servicio():
    from app.main import app as fastapi_app
    return fastapi_app
