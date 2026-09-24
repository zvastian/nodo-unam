"""Visualiza el hueco GRANDE a la izquierda del centro del mapa (distinto del
'hueco central' ya documentado) -- ver `pipeline/analizar_hueco_izquierdo.py`
y `gap.md` para la metodologia y el veredicto completos.

A diferencia de `graficar_hueco_central.py` (que dibujaba un circulo porque
esa asuncion resulto razonable ahi), aqui el contorno rojo es el borde REAL
de la componente conexa de baja densidad (`scipy.ndimage.label` sobre la
grilla 2D), dibujado con `ax.contour` -- no se asume una forma geometrica,
se dibuja la forma que salio de los datos, que es notablemente irregular/
alargada, no circular.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ZONA_PATH = Path(os.getenv("ZONA_PATH", "data/clustering/hueco_izquierdo_puntos.parquet"))
MASK_PATH = Path(os.getenv("MASK_PATH", "data/clustering/hueco_izquierdo_mask.npz"))
LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/12_hueco_izquierdo_composicion.png"))

TOP_CLUSTERS = {
    7: ("#2a78d6", "Cluster 7 — exploración sanitaria (30.4%)"),
    474: ("#eb6834", "Cluster 474 — rata/hipocampo/neuronas (3.6%)"),
    16: ("#1baf7a", "Cluster 16 — reforzamiento/conducta (3.4%)"),
}
COLOR_OTROS = "#b8a888"
COLOR_RUIDO = "#e0dfd8"


def main():
    zona = pd.read_parquet(ZONA_PATH)
    layout = pd.read_parquet(LAYOUT_PATH)
    mask = np.load(MASK_PATH)
    strict, xedges, yedges = mask["strict"], mask["xedges"], mask["yedges"]
    xc, yc = float(mask["cx"]), float(mask["cy"])

    xcenters = (xedges[:-1] + xedges[1:]) / 2
    ycenters = (yedges[:-1] + yedges[1:]) / 2
    Xg, Yg = np.meshgrid(xcenters, ycenters, indexing="ij")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), dpi=150, gridspec_kw={"width_ratios": [1, 1.1]})
    fig.patch.set_facecolor("white")

    # --- Panel 1: localizador ---
    ax1.set_facecolor("white")
    ax1.scatter(layout["x"], layout["y"], s=0.8, c="#d8d8d8", alpha=0.4, linewidths=0, rasterized=True)
    ax1.contour(Xg, Yg, strict.astype(float), levels=[0.5], colors="#e34948", linewidths=1.8, zorder=5)
    ax1.annotate("hueco grande\n(1.25% del corpus en su\nzona ampliada)", xy=(xc, yc + 2.0),
                 xytext=(xc - 10, yc + 9), fontsize=9, color="#e34948", ha="center",
                 arrowprops=dict(arrowstyle="->", color="#e34948", lw=1.2))
    ax1.set_xticks([]); ax1.set_yticks([])
    for s in ax1.spines.values(): s.set_visible(False)
    ax1.set_title("Ubicación en el mapa completo", fontsize=12, color="#1a1a1a")
    ax1.set_aspect("equal")

    # --- Panel 2: composicion, zoom ---
    ax2.set_facecolor("white")
    margen = 3.5
    x0, x1 = zona["x"].min() - margen, zona["x"].max() + margen
    y0, y1 = zona["y"].min() - margen, zona["y"].max() + margen
    zoom = layout[(layout["x"] >= x0) & (layout["x"] <= x1) & (layout["y"] >= y0) & (layout["y"] <= y1)]
    ax2.scatter(zoom["x"], zoom["y"], s=3, c="#f0efe9", alpha=0.5, linewidths=0, rasterized=True)

    resto = zona[~zona["cluster_id"].isin(TOP_CLUSTERS.keys())]
    ruido = resto[resto["cluster_id"] == -1]
    otros = resto[resto["cluster_id"] != -1]
    ax2.scatter(ruido["x"], ruido["y"], s=8, c=COLOR_RUIDO, alpha=0.9, linewidths=0.3,
                edgecolors="#c3c2b7", label=f"Ruido HDBSCAN ({len(ruido)/len(zona)*100:.1f}%)")
    ax2.scatter(otros["x"], otros["y"], s=8, c=COLOR_OTROS, alpha=0.85, linewidths=0,
                label=f"Otros clusters reales ({len(otros)/len(zona)*100:.1f}%)")
    for cid, (color, label) in TOP_CLUSTERS.items():
        sub = zona[zona["cluster_id"] == cid]
        ax2.scatter(sub["x"], sub["y"], s=10, c=color, alpha=0.9, linewidths=0, label=label, zorder=4)

    ax2.contour(Xg, Yg, strict.astype(float), levels=[0.5], colors="#e34948", linewidths=1.5,
                linestyles="dashed", zorder=5)

    ax2.set_xlim(x0, x1)
    ax2.set_ylim(y0, y1)
    ax2.set_xticks([]); ax2.set_yticks([])
    for s in ax2.spines.values(): s.set_visible(False)
    ax2.set_title("Composición de la zona (zoom)", fontsize=12, color="#1a1a1a")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), fontsize=8.5, frameon=False, markerscale=1.8)

    fig.suptitle(
        "Proyección PaCMAP 2D — composición del hueco grande (izquierda del centro)",
        fontsize=15, fontweight="bold", color="#1a1a1a", y=1.02,
    )
    fig.text(
        0.5, -0.24,
        "n=7,640 en zona ampliada (1.25% del corpus) · núcleo estricto=66 tesis, 135 celdas de grilla 200×200 · "
        "ruido=46.2% (global 67.2%) · 84.4% área 2 (enriquecimiento 2.09x) · ver gap.md para el veredicto · 2026-09-22",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
