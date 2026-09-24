"""Genera el layout 2D con PaCMAP sobre los embeddings completos -- paso 3/7
de "Proximos pasos concretos" en development.md. Da las coordenadas x,y de
cada tesis para el mapa visual.

Por que PaCMAP y no UMAP aqui (ADR-0013): UMAP se uso en el paso de
clustering porque preserva densidad LOCAL, que es lo que HDBSCAN necesita.
PaCMAP preserva mejor estructura GLOBAL entre macroclusters (via sus pares
"mid-near"), justo lo que un layout necesita para verse bien -- son dos
reducciones con proposito distinto, no redundantes ni intercambiables.

Por que un script aparte y no reduce_dimensions_pacmap() de
clustering_hdbscan.py: esa funcion existe ahi solo como opcion de
comparacion para el paso de clustering (PCA_COMPONENTS default 15d en ese
contexto); este paso necesita 2D fijo para el mapa, con su propio smoke
test independiente -- a diferencia de UMAP, el costo de PaCMAP nunca se
midio a la escala del corpus completo (609,154 puntos).

Uso (smoke test antes de comprometerse al corpus completo):
    SAMPLE_N=100000 python pipeline/generar_layout_pacmap.py
Corpus completo (SAMPLE_N=0, default):
    python pipeline/generar_layout_pacmap.py
"""
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

EMBEDDINGS_PATH = Path(os.getenv("EMBEDDINGS_PATH", "data/embeddings/embeddings_full_e5large.npy"))
META_PATH = Path(os.getenv("META_PATH", "data/embeddings/embeddings_meta.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/layout_pacmap2d.parquet"))

N_COMPONENTS = int(os.getenv("N_COMPONENTS", "2"))
SAMPLE_N = int(os.getenv("SAMPLE_N", "0"))  # 0 = corpus completo
SAMPLE_SEED = int(os.getenv("SAMPLE_SEED", "42"))


def ram_libre_gb() -> float:
    return psutil.virtual_memory().available / 1e9


def main():
    import pacmap

    print(f"RAM disponible al iniciar: {ram_libre_gb():.1f} GB")

    print(f"Leyendo {EMBEDDINGS_PATH} (mmap)")
    X = np.load(EMBEDDINGS_PATH, mmap_mode="r")
    meta = pd.read_parquet(META_PATH, columns=["thesis_id"])
    print("Embeddings:", X.shape, X.dtype, "| meta:", len(meta))
    assert X.shape[0] == len(meta), "embeddings y meta desalineados -- no deberia pasar"

    if SAMPLE_N and SAMPLE_N < X.shape[0]:
        rng = np.random.default_rng(SAMPLE_SEED)
        idx = np.sort(rng.choice(X.shape[0], size=SAMPLE_N, replace=False))
        print(f"Smoke test: muestra de {SAMPLE_N:,} de {X.shape[0]:,} puntos")
    else:
        idx = np.arange(X.shape[0])
        print(f"Corpus completo: {X.shape[0]:,} puntos")

    # PaCMAP necesita denso en memoria, no mmap (no soporta partial_fit como
    # IncrementalPCA) -- este es el momento en que el costo de RAM real pega.
    X_sub = np.asarray(X[idx], dtype="float32")
    print(f"RAM disponible tras materializar embeddings: {ram_libre_gb():.1f} GB")

    print(f"PaCMAP: {X_sub.shape[1]}d -> {N_COMPONENTS}d sobre {X_sub.shape[0]:,} puntos")
    reducer = pacmap.PaCMAP(n_components=N_COMPONENTS, random_state=SAMPLE_SEED)

    t0 = time.time()
    out = reducer.fit_transform(X_sub).astype("float32")
    elapsed = time.time() - t0
    print(f"fit_transform total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"RAM disponible al terminar: {ram_libre_gb():.1f} GB")

    result = pd.DataFrame({
        "thesis_id": meta.iloc[idx]["thesis_id"].to_numpy(),
        "x": out[:, 0],
        "y": out[:, 1],
    })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT_PATH, index=False)

    print("\nOK")
    print("Guardado:", OUTPUT_PATH, result.shape)


if __name__ == "__main__":
    main()
