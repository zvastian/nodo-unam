"""Servicio de datos del Laboratorio (ADR-0015, paso 1).

Recibe lo que escribe el usuario y devuelve el contexto de datos (ubicación, saturación,
tesis cercanas, asesores y las 100 vecinas), sin IA. En producción solo lo llama el Worker
puerta, que ya verificó sesión, Turnstile y cuota; este servicio no ve cuentas.

Configuración por variables de entorno:
  LAB_ARTEFACTOS   carpeta con modelo/, indice_ivf_sq8.faiss, meta.parquet y precalculo.json
  LAB_ORIGENES     orígenes permitidos por CORS, separados por coma (solo desarrollo local)
  LAB_HILOS        hilos de ONNX Runtime (0 = los que decida)
  LAB_MODELO       archivo del modelo dentro de modelo/ (por defecto model_fp32.onnx; ver evaluar.py)
  LAB_NPROBE       listas del índice IVF que se recorren por búsqueda (por defecto 768)
  LAB_CLAVE        clave compartida con el Worker puerta; si está puesta, /v1/* exige la cabecera
                   X-Lab-Clave (en local puede ir vacía para que el boceto llame directo)
  LAB_EXIGIR_CLAVE «1» en cualquier despliegue (Modal lo pone): sin una LAB_CLAVE de 32+ caracteres,
                   el servicio no arranca, en lugar de quedar abierto a cualquiera

Privacidad: ningún texto de la tesis va a los logs; solo tiempos y tamaños.
"""
import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .contexto import Datos, analizar, texto_consulta
from .embeber import Embebedor

CARPETA = Path(os.getenv("LAB_ARTEFACTOS", Path(__file__).resolve().parents[1] / "artefactos"))
log = logging.getLogger("lab")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
estado = {}


@asynccontextmanager
async def ciclo(app):
    t0 = time.perf_counter()
    estado["datos"] = Datos(CARPETA, int(os.getenv("LAB_NPROBE", "768")))
    estado["embeber"] = Embebedor(CARPETA / "modelo", os.getenv("LAB_MODELO", "model_fp32.onnx"), hilos=int(os.getenv("LAB_HILOS", "0")))
    estado["arranque_s"] = round(time.perf_counter() - t0, 2)
    log.info("listo en %s s: %s vectores", estado["arranque_s"], estado["datos"].indice.ntotal)
    yield
    estado.clear()


app = FastAPI(title="NodOS: servicio de datos del Laboratorio", lifespan=ciclo, docs_url=None, redoc_url=None)
origenes = [o.strip() for o in os.getenv("LAB_ORIGENES", "").split(",") if o.strip()]
CLAVE = os.getenv("LAB_CLAVE", "")
# Falla cerrado: un despliegue sin la clave (p. ej., el secreto de Modal sin LAB_CLAVE) no arranca.
if os.getenv("LAB_EXIGIR_CLAVE") == "1" and len(CLAVE) < 32:
    raise RuntimeError("LAB_EXIGIR_CLAVE=1 y falta LAB_CLAVE (32+ caracteres)")


@app.middleware("http")
async def exigir_clave(request: Request, siguiente):
    # Antes de validar el cuerpo: sin la clave no se responde ni siquiera un 422.
    if CLAVE and request.url.path.startswith("/v1/") and request.method != "OPTIONS":
        if not hmac.compare_digest(request.headers.get("x-lab-clave", "").encode(), CLAVE.encode()):
            return JSONResponse({"detail": "sin clave"}, status_code=401)
    return await siguiente(request)


if origenes:
    app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=["POST"], allow_headers=["Content-Type"])


class Periodo(BaseModel):
    applies: bool = False
    start_year: int | None = None
    end_year: int | None = None
    label: str = Field("", max_length=40)


class Entrada(BaseModel):
    """Lo que escribe el usuario. Topes de tamaño: el embedding trunca a 512 tokens de todos modos."""
    title: str = Field(min_length=3, max_length=400)
    problematiza: str = Field("", max_length=2000)
    keywords: list[str] = Field(default_factory=list, max_length=12)
    objectives: list[str] = Field(default_factory=list, max_length=8)
    program: str = Field("", max_length=160)
    degree: str = Field("", max_length=40)
    study_period: Periodo = Field(default_factory=Periodo)


@app.get("/salud")
def salud():
    return {"ok": "datos" in estado, "arranque_s": estado.get("arranque_s")}


@app.post("/v1/contexto")
def contexto(entrada: Entrada):
    e = entrada.model_dump()
    e["keywords"] = [k[:80] for k in e["keywords"]]
    t0 = time.perf_counter()
    q = estado["embeber"](texto_consulta(e))
    t1 = time.perf_counter()
    out = analizar(estado["datos"], e, q)
    t2 = time.perf_counter()
    out["tiempos_ms"] = {"embedding": round(1000 * (t1 - t0)), "contexto": round(1000 * (t2 - t1))}
    log.info("contexto: embedding %s ms, contexto %s ms", out["tiempos_ms"]["embedding"], out["tiempos_ms"]["contexto"])
    return out
