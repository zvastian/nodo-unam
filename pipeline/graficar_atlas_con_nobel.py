"""Item 4 del checklist "Evidencia visual del proceso": Nobel embebido como
easter egg sobre el mapa de tesis -- confirma visualmente que ADR-0012
(fusion de Nobel dentro de Explorar via vecindario) funciona con datos
reales, usando el layout conjunto de `generar_layout_pacmap_con_nobel.py`.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TESIS_LAYOUT_PATH = Path(os.getenv("TESIS_LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
NOBEL_POS_PATH = Path(os.getenv("NOBEL_POS_PATH", "data/clustering/nobel_posicion_interpolada.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/04_mapa_con_nobel.png"))


def main():
    tesis = pd.read_parquet(TESIS_LAYOUT_PATH)
    nobel = pd.read_parquet(NOBEL_POS_PATH)

    fig, ax = plt.subplots(figsize=(14, 12), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.scatter(tesis["x"], tesis["y"], s=1.0, c="#d5d4cd", alpha=0.35,
               linewidths=0, rasterized=True)
    ax.scatter(nobel["x"], nobel["y"], s=22, c="#eda100", alpha=0.9,
               marker="*", linewidths=0.4, edgecolors="#7a5c00", zorder=5)

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Proyeccion PaCMAP 2D -- corpus UNAM + laureados Nobel (n=610,180)",
        fontsize=14, fontweight="bold", color="#1a1a1a", pad=14,
    )
    ax.text(
        0.5, -0.02,
        "gris = tesis UNAM  ·  estrella dorada = laureado Nobel  ·  mismo fit de PaCMAP  ·  2026-09-22",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
