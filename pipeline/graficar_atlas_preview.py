"""Genera el 'money shot': mapa 2D de PaCMAP coloreado por cluster de HDBSCAN
-- item 1 del checklist "Evidencia visual del proceso" en development.md.

Es una imagen estatica (matplotlib, rasterizada) para captura/portafolio, NO
el visor interactivo de produccion (ese sera regl-scatterplot para la vista
"modo caos", ver development.md) -- aqui solo interesa ver la estructura de
un vistazo.

Con 513 clusters no cabe una leyenda legible (ver dataviz: una leyenda deja
de tener sentido bien pasados 8-9 categorias) -- el color aqui codifica
identidad de cluster para que la estructura salte a la vista, no para leerse
cluster por cluster contra una leyenda. El ruido (cluster_id=-1, 67.2% del
corpus) se dibuja primero, gris claro y detras, para que los clusters
resalten encima -- es la misma idea de "nucleo denso + halo disperso" del
Design Manifest v1.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/01_mapa_pacmap_clusters_hdbscan.png"))

SEED = 42


def main():
    print(f"Leyendo {LAYOUT_PATH}")
    layout = pd.read_parquet(LAYOUT_PATH)
    print(f"Leyendo {CLUSTERS_PATH}")
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id"])

    df = layout.merge(clusters, on="thesis_id", how="left")
    assert df["cluster_id"].notna().all()
    print("Puntos:", len(df))

    ruido = df[df["cluster_id"] == -1]
    asignados = df[df["cluster_id"] != -1].copy()
    print(f"Ruido: {len(ruido):,} | Asignados: {len(asignados):,}")

    # Paleta categorica grande: HSV barrido parejo en matiz para 513 clusters,
    # con saturacion/valor alternados para separar visualmente clusters con
    # matiz cercano, y una permutacion fija (mismo SEED) para que clusters
    # vecinos en cluster_id no salgan con matices vecinos.
    cluster_ids = np.sort(asignados["cluster_id"].unique())
    n = len(cluster_ids)
    rng = np.random.default_rng(SEED)
    orden = rng.permutation(n)
    hues = orden / n
    sats = 0.55 + 0.35 * ((orden * 7) % n) / n
    vals = 0.55 + 0.35 * ((orden * 13) % n) / n
    colores_hsv = np.stack([hues, sats, vals], axis=1)
    colores_rgb = matplotlib.colors.hsv_to_rgb(colores_hsv)
    color_by_cluster = dict(zip(cluster_ids, colores_rgb))
    point_colors = np.array([color_by_cluster[c] for c in asignados["cluster_id"]])

    fig, ax = plt.subplots(figsize=(14, 12), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.scatter(
        ruido["x"], ruido["y"],
        s=1.2, c="#d8d8d8", alpha=0.35, linewidths=0, rasterized=True,
    )
    ax.scatter(
        asignados["x"], asignados["y"],
        s=1.6, c=point_colors, alpha=0.75, linewidths=0, rasterized=True,
    )

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Proyeccion PaCMAP 2D -- clustering HDBSCAN (513 clusters)",
        fontsize=15, fontweight="bold", color="#1a1a1a", pad=14,
    )
    ax.text(
        0.5, -0.02,
        f"n={len(df):,} tesis  ·  HDBSCAN (513 clusters, {len(ruido)/len(df)*100:.1f}% ruido) "
        f"+ PaCMAP  ·  embeddings e5-large  ·  2026-09-22",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("\nOK")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
