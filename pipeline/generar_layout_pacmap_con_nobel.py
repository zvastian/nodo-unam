"""Paso 4/7 (parte 2) de "Proximos pasos concretos" en development.md: corre
PaCMAP sobre tesis + Nobel JUNTOS (concatenados antes del fit), para que las
posiciones 2D sean realmente comparables en el mismo mapa -- la opcion
"recomendada" documentada en vez de proyectar Nobel aparte.

Reemplaza a `generar_layout_pacmap.py` para el layout final (ese script
sigue vivo como referencia/smoke-test tesis-solo). Mismos parametros y
semilla que esa corrida para que el layout de las tesis no cambie de forma
importante -- solo se le agregan 1,026 puntos mas (0.17% del total) al
fit, así que la geometria deberia ser muy similar, no identica bit a bit
(PaCMAP se re-ajusta desde cero, no hay transform incremental real).
"""
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

THESIS_EMB_PATH = Path(os.getenv("THESIS_EMB_PATH", "data/embeddings/embeddings_full_e5large.npy"))
THESIS_META_PATH = Path(os.getenv("THESIS_META_PATH", "data/embeddings/embeddings_meta.parquet"))
NOBEL_EMB_PATH = Path(os.getenv("NOBEL_EMB_PATH", "data/embeddings/nobel_embeddings_e5large.npy"))
NOBEL_META_PATH = Path(os.getenv("NOBEL_META_PATH", "data/embeddings/nobel_embeddings_meta.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/layout_pacmap2d_con_nobel.parquet"))

N_COMPONENTS = int(os.getenv("N_COMPONENTS", "2"))
SEED = int(os.getenv("SAMPLE_SEED", "42"))


def ram_libre_gb() -> float:
    return psutil.virtual_memory().available / 1e9


def main():
    import pacmap

    print(f"RAM disponible al iniciar: {ram_libre_gb():.1f} GB")

    print(f"Leyendo {THESIS_EMB_PATH}")
    X_tesis = np.asarray(np.load(THESIS_EMB_PATH, mmap_mode="r"), dtype="float32")
    thesis_meta = pd.read_parquet(THESIS_META_PATH, columns=["thesis_id"])

    print(f"Leyendo {NOBEL_EMB_PATH}")
    X_nobel = np.load(NOBEL_EMB_PATH).astype("float32")
    nobel_meta = pd.read_parquet(NOBEL_META_PATH)

    print("Tesis:", X_tesis.shape, "| Nobel:", X_nobel.shape)
    X = np.concatenate([X_tesis, X_nobel], axis=0)
    print(f"RAM disponible tras concatenar: {ram_libre_gb():.1f} GB")

    print(f"PaCMAP: {X.shape[1]}d -> {N_COMPONENTS}d sobre {X.shape[0]:,} puntos (tesis + Nobel)")
    reducer = pacmap.PaCMAP(n_components=N_COMPONENTS, random_state=SEED)

    t0 = time.time()
    out = reducer.fit_transform(X).astype("float32")
    elapsed = time.time() - t0
    print(f"fit_transform total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"RAM disponible al terminar: {ram_libre_gb():.1f} GB")

    n_tesis = len(thesis_meta)
    result = pd.concat([
        pd.DataFrame({
            "id": thesis_meta["thesis_id"].to_numpy(),
            "kind": "tesis",
            "x": out[:n_tesis, 0],
            "y": out[:n_tesis, 1],
        }),
        pd.DataFrame({
            "id": nobel_meta["node_id"].to_numpy(),
            "kind": "nobel",
            "x": out[n_tesis:, 0],
            "y": out[n_tesis:, 1],
        }),
    ], ignore_index=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT_PATH, index=False)

    print("\nOK")
    print("Guardado:", OUTPUT_PATH, result.shape)


if __name__ == "__main__":
    main()
