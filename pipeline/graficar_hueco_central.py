"""Item 9 del checklist "Evidencia visual del proceso": visualiza la
composicion del 'hueco central' del mapa PaCMAP -- ver `gap.md` para el
analisis completo y el veredicto metodologico (spoiler: no es evidencia
valida de un vacio real de conocimiento, es un artefacto de layout mas
titulos genericos de varias disciplinas distintas conviviendo ahi).

Dos paneles:
- Localizador (izquierda): el mapa completo con un circulo marcando donde
  cae el hueco -- para orientar, el hueco es <1% del area total del mapa y
  no se aprecia su composicion interna a esa escala.
- Composicion (derecha): zoom al hueco, coloreado por los 3 clusters reales
  mas grandes presentes ahi + "otros clusters reales" (bucket neutro) +
  ruido (bucket neutro). Solo 3 tonos con identidad categorica (limite de
  la guia de dataviz para scatter con separacion CVD-segura en todos los
  pares) -- el resto es contexto gris/tostado, no series a distinguir entre si.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

GAP_POINTS_PATH = Path(os.getenv("GAP_POINTS_PATH", "data/clustering/hueco_central_puntos.parquet"))
LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/09_hueco_central_composicion.png"))

R_HUECO = float(os.getenv("R_HUECO", "1.80"))
ZOOM_FACTOR = float(os.getenv("ZOOM_FACTOR", "1.6"))  # margen de contexto alrededor del hueco

TOP_CLUSTERS = {
    16: ("#2a78d6", "Cluster 16 — reforzamiento/conducta (9.2%)"),
    416: ("#eb6834", "Cluster 416 — química didáctica (8.1%)"),
    503: ("#1baf7a", "Cluster 503 — matemáticas puras (7.7%)"),
}
COLOR_OTROS = "#b8a888"
COLOR_RUIDO = "#e0dfd8"


def main():
    gap = pd.read_parquet(GAP_POINTS_PATH)
    layout = pd.read_parquet(LAYOUT_PATH)
    cx, cy = layout["x"].mean(), layout["y"].mean()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), dpi=150, gridspec_kw={"width_ratios": [1, 1.1]})
    fig.patch.set_facecolor("white")

    # --- Panel 1: localizador ---
    ax1.set_facecolor("white")
    ax1.scatter(layout["x"], layout["y"], s=0.8, c="#d8d8d8", alpha=0.4, linewidths=0, rasterized=True)
    circ = plt.Circle((cx, cy), R_HUECO, fill=False, edgecolor="#e34948", linewidth=1.8, zorder=5)
    ax1.add_patch(circ)
    ax1.annotate("hueco central\n(0.41% del corpus)", xy=(cx, cy + R_HUECO), xytext=(cx - 6, cy + 10),
                 fontsize=9, color="#e34948", ha="center",
                 arrowprops=dict(arrowstyle="->", color="#e34948", lw=1.2))
    ax1.set_xticks([])
    ax1.set_yticks([])
    for spine in ax1.spines.values():
        spine.set_visible(False)
    ax1.set_title("Ubicación en el mapa completo", fontsize=12, color="#1a1a1a")
    ax1.set_aspect("equal")

    # --- Panel 2: composicion, zoom ---
    ax2.set_facecolor("white")
    zoom_r = R_HUECO * ZOOM_FACTOR
    zona = layout[(layout["x"] - cx) ** 2 + (layout["y"] - cy) ** 2 < zoom_r ** 2]
    ax2.scatter(zona["x"], zona["y"], s=3, c="#f0efe9", alpha=0.5, linewidths=0, rasterized=True)

    resto = gap[~gap["cluster_id"].isin(TOP_CLUSTERS.keys())]
    ruido = resto[resto["cluster_id"] == -1]
    otros = resto[resto["cluster_id"] != -1]
    ax2.scatter(ruido["x"], ruido["y"], s=10, c=COLOR_RUIDO, alpha=0.9, linewidths=0.3,
                edgecolors="#c3c2b7", label=f"Ruido HDBSCAN ({len(ruido)/len(gap)*100:.1f}%)")
    ax2.scatter(otros["x"], otros["y"], s=10, c=COLOR_OTROS, alpha=0.9, linewidths=0,
                label=f"Otros clusters reales ({len(otros)/len(gap)*100:.1f}%)")
    for cid, (color, label) in TOP_CLUSTERS.items():
        sub = gap[gap["cluster_id"] == cid]
        ax2.scatter(sub["x"], sub["y"], s=16, c=color, alpha=0.95, linewidths=0, label=label, zorder=4)

    circ2 = plt.Circle((cx, cy), R_HUECO, fill=False, edgecolor="#e34948", linewidth=1.5,
                        linestyle="--", zorder=5)
    ax2.add_patch(circ2)

    ax2.set_xticks([])
    ax2.set_yticks([])
    for spine in ax2.spines.values():
        spine.set_visible(False)
    ax2.set_aspect("equal")
    ax2.set_title("Composición del hueco (zoom)", fontsize=12, color="#1a1a1a")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), fontsize=8.5,
               frameon=False, ncol=1, markerscale=1.8)

    fig.suptitle(
        "Proyección PaCMAP 2D — composición del hueco central",
        fontsize=15, fontweight="bold", color="#1a1a1a", y=1.02,
    )
    fig.text(
        0.5, -0.24,
        "n=2,509 (0.41% del corpus) · radio=1.80 · ruido=68.0% (global 67.2%) · "
        "3 clusters reales concentran 25.0% · ver gap.md para el veredicto metodológico · 2026-09-22",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
