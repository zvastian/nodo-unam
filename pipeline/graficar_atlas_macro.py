"""Compara, lado a lado sobre el mismo layout PaCMAP, los 513 micro-clusters
de HDBSCAN (como en `01_mapa_pacmap_clusters_hdbscan.png`) contra los 53
macro-grupos construidos en `pipeline/construir_jerarquia_macro_meso.py`
(Ward sobre centroides) -- pedido explicito del usuario para ver como se
agregan los ~500 micro-clusters en los 53 macro-temas.

Mismo criterio de paleta que el mapa 01: con 53-513 categorias no hay forma
de que una leyenda sea legible (la guia de dataviz limita legibilidad a
~8-9 entradas) -- el color codifica identidad para que la estructura salte
a la vista, no para leerse contra una leyenda. En el panel macro se agrega
el numero de macro_id en el centroide de cada grupo (mediana de posicion
2D de sus miembros) porque, a diferencia del micro (513, demasiados para
poner numero a cada uno), 53 es un numero donde etiquetar cada blob es
factible y es literalmente "senalar" cada macro-grupo, como pidio el usuario.
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
JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/11_atlas_micro_vs_macro.png"))

SEED = 42


def paleta_hsv(ids: np.ndarray, seed: int) -> dict:
    n = len(ids)
    rng = np.random.default_rng(seed)
    orden = rng.permutation(n)
    hues = orden / n
    sats = 0.55 + 0.35 * ((orden * 7) % n) / n
    vals = 0.55 + 0.35 * ((orden * 13) % n) / n
    rgb = matplotlib.colors.hsv_to_rgb(np.stack([hues, sats, vals], axis=1))
    return dict(zip(ids, rgb))


def main():
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id"])
    jerarquia = pd.read_parquet(JERARQUIA_PATH, columns=["cluster_id", "macro_id"])

    df = layout.merge(clusters, on="thesis_id", how="left").merge(jerarquia, on="cluster_id", how="left")
    ruido = df[df["cluster_id"] == -1]
    asignados = df[df["cluster_id"] != -1].copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10), dpi=150)
    fig.patch.set_facecolor("white")

    # --- Panel 1: 513 micro-clusters ---
    ax1.set_facecolor("white")
    micro_ids = np.sort(asignados["cluster_id"].unique())
    color_micro = paleta_hsv(micro_ids, SEED)
    pts_micro = np.array([color_micro[c] for c in asignados["cluster_id"]])
    ax1.scatter(ruido["x"], ruido["y"], s=1.0, c="#d8d8d8", alpha=0.35, linewidths=0, rasterized=True)
    ax1.scatter(asignados["x"], asignados["y"], s=1.3, c=pts_micro, alpha=0.75, linewidths=0, rasterized=True)
    ax1.set_xticks([]); ax1.set_yticks([])
    for s in ax1.spines.values(): s.set_visible(False)
    ax1.set_aspect("equal")
    ax1.set_title(f"{len(micro_ids)} micro-clusters (HDBSCAN)", fontsize=13, color="#1a1a1a")

    # --- Panel 2: 53 macro-grupos, con numero en el centroide ---
    ax2.set_facecolor("white")
    macro_ids = np.sort(asignados["macro_id"].unique())
    color_macro = paleta_hsv(macro_ids, SEED + 1)
    pts_macro = np.array([color_macro[m] for m in asignados["macro_id"]])
    ax2.scatter(ruido["x"], ruido["y"], s=1.0, c="#d8d8d8", alpha=0.35, linewidths=0, rasterized=True)
    ax2.scatter(asignados["x"], asignados["y"], s=1.3, c=pts_macro, alpha=0.75, linewidths=0, rasterized=True)

    centroides = asignados.groupby("macro_id")[["x", "y"]].median()
    for macro_id, (cx, cy) in centroides.iterrows():
        ax2.annotate(str(int(macro_id)), (cx, cy), fontsize=7.5, fontweight="bold",
                     color="#1a1a1a", ha="center", va="center",
                     bbox=dict(boxstyle="circle,pad=0.15", facecolor="white", edgecolor="#1a1a1a",
                               linewidth=0.6, alpha=0.85), zorder=6)

    ax2.set_xticks([]); ax2.set_yticks([])
    for s in ax2.spines.values(): s.set_visible(False)
    ax2.set_aspect("equal")
    ax2.set_title(f"{len(macro_ids)} macro-grupos (Ward sobre centroides)", fontsize=13, color="#1a1a1a")

    fig.suptitle(
        f"Proyección PaCMAP 2D — de {len(micro_ids)} micro-clusters a {len(macro_ids)} macro-grupos",
        fontsize=16, fontweight="bold", color="#1a1a1a", y=1.0,
    )
    fig.text(
        0.5, -0.02,
        "n=609,154 · mismo layout PaCMAP en ambos paneles · gris = ruido HDBSCAN (67.2%) · color = identidad de "
        "cluster/macro (no hay leyenda legible a esta cantidad de categorías) · números en el panel derecho = macro_id, "
        "en el centroide (mediana x,y) de cada macro-grupo · ver macro_topics_ctfidf.parquet para sus etiquetas · 2026-09-22",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
