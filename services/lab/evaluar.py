"""Prueba de aceptación del servicio de datos del Lab (ADR-0015): ¿el servicio encuentra las
mismas 100 vecinas que el modelo original en float32 con búsqueda exacta?

Referencia: SentenceTransformer e5-large (float32, como se embebió el corpus) + producto
interno exacto contra la matriz completa. Se mide por separado cada fuente de error:
  onnx32    exportación ONNX en float32 + búsqueda exacta (verifica la exportación)
  int8      modelo int8 dinámico + búsqueda exacta     (rechazado: ver construir.py)
  indice    referencia + índice IVF-SQ8 con LAB_NPROBE (error del índice)
  servicio  onnx32 + IVF-SQ8                            (lo que corre en producción)
Criterio: al menos 95 % del top-100 en común con la referencia, en promedio y en cada caso.

Corre con el Python del pipeline, con los datos locales. Uso: python services/lab/evaluar.py
"""
import json
import os
import sys
import time
from pathlib import Path

import faiss
import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from app.contexto import texto_consulta  # noqa: E402
from app.embeber import Embebedor  # noqa: E402

EMB = AQUI.parents[1] / "data" / "embeddings" / "embeddings_full_e5large.npy"
K = 100
CRITERIO = 95


def exacta(X, q, k=K):
    s = X @ q
    i = np.argpartition(-s, k)[:k]
    return i[np.argsort(-s[i])]


def main():
    from sentence_transformers import SentenceTransformer

    casos = json.loads((AQUI / "casos_evaluacion.json").read_text(encoding="utf8"))
    X = np.load(EMB)  # 2.5 GB en RAM: solo aquí, el servicio no la carga
    ref_m = SentenceTransformer("intfloat/multilingual-e5-large")
    carpeta = AQUI / "artefactos" / "modelo"
    m32 = Embebedor(carpeta, "model_fp32.onnx")
    m8 = Embebedor(carpeta, "model_int8.onnx") if (carpeta / "model_int8.onnx").exists() else None
    idx = faiss.read_index(str(AQUI / "artefactos" / "indice_ivf_sq8.faiss"))
    idx.nprobe = int(os.getenv("LAB_NPROBE", "768"))

    filas, t = [], {"embedding": [], "indice": []}
    for c in casos:
        texto = texto_consulta(c)
        q = ref_m.encode(texto, normalize_embeddings=True).astype(np.float32)
        t0 = time.perf_counter(); q32 = m32(texto); t["embedding"].append(time.perf_counter() - t0)
        ref = exacta(X, q)
        t0 = time.perf_counter(); ind = idx.search(q[None], K)[1][0]; t["indice"].append(time.perf_counter() - t0)
        serv = idx.search(q32[None], K)[1][0]
        comun = lambda a: len(set(ref) & set(a))
        f = {"caso": c["caso"], "onnx32": comun(exacta(X, q32)), "indice": comun(ind), "servicio": comun(serv),
             "top10_servicio": len(set(ref[:10]) & set(serv[:10]))}
        if m8:
            f["int8"] = comun(exacta(X, m8(texto)))
        filas.append(f)
        print(f, flush=True)

    claves = [k for k in ("onnx32", "int8", "indice", "servicio") if k in filas[0]]
    print("\npromedio:", {k: round(float(np.mean([f[k] for f in filas])), 1) for k in claves + ["top10_servicio"]})
    print("mínimo:", {k: min(f[k] for f in filas) for k in claves})
    print("ms por consulta (mediana):", {k: round(1000 * float(np.median(v))) for k, v in t.items()})
    serv = [f["servicio"] for f in filas]
    ok = np.mean(serv) >= CRITERIO and min(serv) >= CRITERIO
    print("ACEPTADO" if ok else "RECHAZADO", f"(criterio: {CRITERIO} % en promedio y en cada caso)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
