"""Responde dos preguntas sobre el layout PaCMAP 2D (`layout_pacmap2d.parquet`)
y las 4 areas administrativas de la UNAM:

1. Tal como esta el atlas, se puede decir que YA separa algo por area?
   Se contesta con un clasificador de vecino-mas-cercano (voto mayoritario
   de las K=25 tesis mas cercanas EN 2D) contra dos baselines: clase
   mayoritaria y azar uniforme. Complementa (no reemplaza) el hallazgo por
   grilla de `graficar_atlas_por_area.py` -- ahi se midio que ninguna area
   forma una region propia a escala macro; aqui se mide separacion LOCAL
   (vecindario), que es una pregunta distinta.

2. Se puede inferir el area de un laureado Nobel a partir de su posicion
   2D interpolada (`nobel_posicion_interpolada.parquet`)? Mismo voto
   vecino-mas-cercano (K=25, esta vez ponderado por inverso de distancia),
   comparado contra la categoria real del premio (parseada de `node_id`,
   formato `NOBEL::id::cat::anio::n`) como validacion externa independiente
   -- la categoria Nobel nunca se uso para calcular la posicion.
"""
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
THESIS_META_PATH = Path(os.getenv("THESIS_META_PATH", "data/embeddings/embeddings_meta.parquet"))
NOBEL_POS_PATH = Path(os.getenv("NOBEL_POS_PATH", "data/clustering/nobel_posicion_interpolada.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/nobel/nobel_area_inferida.parquet"))

K = int(os.getenv("K", "25"))
N_SAMPLE = int(os.getenv("N_SAMPLE", "30000"))
SEED = 42

CAT_LABELS = {
    "phy": "Fisica", "che": "Quimica", "med": "Medicina/Fisiologia",
    "lit": "Literatura", "eco": "Economia", "pea": "Paz", "peace": "Paz",
}


def parse_cat(node_id: str) -> str:
    parts = node_id.split("::")
    code = parts[2] if len(parts) > 2 else "?"
    return CAT_LABELS.get(code, code)


def main():
    rng = np.random.default_rng(SEED)

    print("Cargando layout + areas...")
    layout = pd.read_parquet(LAYOUT_PATH)
    meta = pd.read_parquet(THESIS_META_PATH, columns=["thesis_id", "area"])
    df = layout.merge(meta, on="thesis_id", how="left")
    assert df["area"].notna().all()
    print("Puntos:", len(df))

    xy = df[["x", "y"]].to_numpy()
    areas = df["area"].to_numpy()
    tree = cKDTree(xy)

    # --- Pregunta 1: separacion local por area en el layout 2D ---
    print("\n=== Separacion local por area (K-NN en 2D) ===")
    sample_idx = rng.choice(len(df), size=N_SAMPLE, replace=False)
    _, idx = tree.query(xy[sample_idx], k=K + 1)
    idx = idx[:, 1:]  # descarta self

    pred = np.array([Counter(areas[row]).most_common(1)[0][0] for row in idx])
    real = areas[sample_idx]

    acc = (pred == real).mean()
    baseline_majority = df["area"].value_counts(normalize=True).max()
    print(f"Accuracy voto-mayoritario de {K} vecinos (2D): {acc:.3f}")
    print(f"Baseline clase mayoritaria: {baseline_majority:.3f}  |  Baseline azar (4 areas): 0.250")

    conf = pd.crosstab(pd.Series(real, name="real"), pd.Series(pred, name="predicho"), normalize="index")
    print("\nMatriz de confusion (filas=real, columnas=predicho):")
    print(conf.round(3))

    # --- Pregunta 2: area inferida de laureados Nobel ---
    print("\n=== Area inferida de laureados Nobel por posicion ===")
    nobel = pd.read_parquet(NOBEL_POS_PATH)
    xy_nobel = nobel[["x", "y"]].to_numpy()
    d_n, idx_n = tree.query(xy_nobel, k=K)

    nobel["category"] = nobel["node_id"].map(parse_cat)

    inferred_area, confianza = [], []
    for row, dist in zip(idx_n, d_n):
        w = 1.0 / np.maximum(dist, 1e-6)
        votes = {}
        for a, wi in zip(areas[row], w):
            votes[a] = votes.get(a, 0.0) + wi
        top_a, top_w = max(votes.items(), key=lambda kv: kv[1])
        inferred_area.append(top_a)
        confianza.append(top_w / sum(votes.values()))

    nobel["area_inferida"] = inferred_area
    nobel["confianza_voto"] = confianza

    ct = pd.crosstab(nobel["category"], nobel["area_inferida"], normalize="index")
    print("\nCrosstab categoria Nobel real x area inferida (proporcion por fila):")
    print(ct.round(3))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    nobel[["node_id", "category", "x", "y", "area_inferida", "confianza_voto"]].to_parquet(OUTPUT_PATH, index=False)
    print("\nGuardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
