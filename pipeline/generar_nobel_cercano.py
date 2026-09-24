"""Paso 4/7 (parte 1) de "Proximos pasos concretos" en development.md: para
cada tesis, encuentra el laureado Nobel mas cercano por similitud coseno de
embeddings (ADR-0012 -- Nobel se fusiona en Explorar via vecindario, no
pestana propia).

Embeddings normalizados (norma=1) -> similitud coseno = producto punto.
Se procesa en lotes para no materializar la matriz completa 609,154 x 1,026
de una sola vez (aunque cabria en RAM, ~2.5GB, se prefiere no arriesgar tras
el incidente de OOM ya documentado).

Metadata legible (nombre/categoria/anio/motivacion) sale de
nobel_award_nodes.json -- el atlas viejo (Leiden/MiniLM), pero esos campos
son datos biograficos reales, no dependen del modelo de embeddings usado
para posicionar nodos, asi que se reusan tal cual. El campo `category`
(espanol) de ese JSON tiene mojibake ("F�sica") de un bug de encoding viejo
no relacionado con este pipeline -- se reconstruye limpio aqui desde
`category_code` en vez de heredar el bug.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

THESIS_EMB_PATH = Path(os.getenv("THESIS_EMB_PATH", "data/embeddings/embeddings_full_e5large.npy"))
THESIS_META_PATH = Path(os.getenv("THESIS_META_PATH", "data/embeddings/embeddings_meta.parquet"))
NOBEL_EMB_PATH = Path(os.getenv("NOBEL_EMB_PATH", "data/embeddings/nobel_embeddings_e5large.npy"))
NOBEL_META_PATH = Path(os.getenv("NOBEL_META_PATH", "data/embeddings/nobel_embeddings_meta.parquet"))
NOBEL_NODES_JSON = Path(os.getenv(
    "NOBEL_NODES_JSON",
    "app/MI-TESIS-UNAM_github/nobel/outputs/processed/nobel_award_nodes.json",
))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/nobel/thesis_nobel_nearest.parquet"))

TOP_K = int(os.getenv("TOP_K", "3"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20000"))

# Correccion de "hubness": en busqueda de vecinos de alta dimension, cross-
# lingue (609,154 consultas cortas en espanol vs 1,026 candidatos largos en
# ingles), algunos candidatos se vuelven "el mas cercano" de una fraccion
# desproporcionada de las consultas por geometria del espacio, no por
# similitud semantica real (problema bien documentado en la literatura de
# alineacion de embeddings cross-lingues). Medido en esta corrida: 15/1026
# laureados (1.5%) acaparaban 36.1% de las asignaciones sin corregir.
# Fix: z-score por candidato (restar su similitud media y dividir por su
# desviacion estandar, calculadas contra el corpus completo) antes de
# rankear -- un candidato "generalmente similar a todo" (hub) pasa a tener
# z-score bajo aunque su similitud cruda sea alta, porque esa alta similitud
# ya es su "normal". Equivalente simplificado de CSLS (Cross-domain
# Similarity Local Scaling).

CATEGORY_ES = {
    "phy": "Fisica", "che": "Quimica", "med": "Medicina",
    "pea": "Paz", "lit": "Literatura", "eco": "Ciencias Economicas",
}


def load_nobel_nodes() -> pd.DataFrame:
    with open(NOBEL_NODES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    nodes = pd.DataFrame(data["nodes"])[["id", "name", "category_code", "award_year", "motivation"]]
    nodes["category_es"] = nodes["category_code"].map(CATEGORY_ES)
    return nodes.rename(columns={"id": "node_id"})


def main():
    print(f"Leyendo {THESIS_EMB_PATH} (mmap)")
    X_tesis = np.load(THESIS_EMB_PATH, mmap_mode="r")
    thesis_meta = pd.read_parquet(THESIS_META_PATH, columns=["thesis_id"])
    print("Tesis:", X_tesis.shape)

    print(f"Leyendo {NOBEL_EMB_PATH}")
    X_nobel = np.load(NOBEL_EMB_PATH).astype("float32")
    nobel_meta = pd.read_parquet(NOBEL_META_PATH)
    nobel_nodes = load_nobel_nodes()
    nobel_info = nobel_meta.merge(nobel_nodes, on="node_id", how="left")
    print("Nobel:", X_nobel.shape, "| con metadata:", nobel_info["name"].notna().sum())

    n = X_tesis.shape[0]
    n_nobel = X_nobel.shape[0]

    print("Pasada 1/2: calculando media/desviacion de similitud por candidato Nobel (correccion de hubness)")
    sum_ = np.zeros(n_nobel, dtype="float64")
    sumsq = np.zeros(n_nobel, dtype="float64")
    for start in range(0, n, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n)
        batch = np.asarray(X_tesis[start:end], dtype="float32")
        sims = batch @ X_nobel.T
        sum_ += sims.sum(axis=0, dtype="float64")
        sumsq += (sims.astype("float64") ** 2).sum(axis=0)
    mean_ = sum_ / n
    std_ = np.sqrt(np.maximum(sumsq / n - mean_ ** 2, 1e-12))
    print(f"  candidato con std mas baja (mas 'hub'): {nobel_info['name'].iloc[std_.argmin()]!r} (std={std_.min():.4f})")

    print("Pasada 2/2: rankeando por z-score en vez de similitud cruda")
    top_idx = np.empty((n, TOP_K), dtype="int32")
    top_sim = np.empty((n, TOP_K), dtype="float32")   # similitud coseno cruda (para mostrar/auditar)
    top_z = np.empty((n, TOP_K), dtype="float32")     # z-score (usado para rankear)

    for start in range(0, n, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n)
        batch = np.asarray(X_tesis[start:end], dtype="float32")
        sims = batch @ X_nobel.T
        z = (sims - mean_) / std_
        idx = np.argpartition(-z, TOP_K - 1, axis=1)[:, :TOP_K]
        row_z = np.take_along_axis(z, idx, axis=1)
        row_sims = np.take_along_axis(sims, idx, axis=1)
        order = np.argsort(-row_z, axis=1)
        top_idx[start:end] = np.take_along_axis(idx, order, axis=1)
        top_z[start:end] = np.take_along_axis(row_z, order, axis=1)
        top_sim[start:end] = np.take_along_axis(row_sims, order, axis=1)
        print(f"  {end:,}/{n:,}", flush=True)

    result = pd.DataFrame({"thesis_id": thesis_meta["thesis_id"]})
    node_ids = nobel_info["node_id"].to_numpy()
    for k in range(TOP_K):
        result[f"nobel_top{k+1}_id"] = node_ids[top_idx[:, k]]
        result[f"nobel_top{k+1}_similarity"] = top_sim[:, k]
        result[f"nobel_top{k+1}_zscore"] = top_z[:, k]

    nearest = nobel_info.rename(columns={
        "node_id": "nobel_top1_id", "name": "nobel_nearest_name",
        "category_es": "nobel_nearest_category", "award_year": "nobel_nearest_year",
        "motivation": "nobel_nearest_motivation",
    })[["nobel_top1_id", "nobel_nearest_name", "nobel_nearest_category",
        "nobel_nearest_year", "nobel_nearest_motivation"]]
    result = result.merge(nearest, on="nobel_top1_id", how="left")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT_PATH, index=False)

    print("\nOK")
    print("Guardado:", OUTPUT_PATH, result.shape)
    print("\nDistribucion de similitud (coseno cruda) del top1:")
    print(result["nobel_top1_similarity"].describe())
    vc = result["nobel_nearest_name"].value_counts()
    print(f"\nLaureados distintos usados como 'mas cercano': {(vc>0).sum()} de {len(nobel_info)}")
    print(f"Top 15 acaparan: {vc.head(15).sum():,} de {len(result):,} ({vc.head(15).sum()/len(result)*100:.1f}%)")
    print(vc.head(15))


if __name__ == "__main__":
    main()
