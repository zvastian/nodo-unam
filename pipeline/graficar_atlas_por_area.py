"""Small multiples: como se dispersan las 4 areas administrativas de la UNAM
sobre el mapa semantico (PaCMAP + HDBSCAN). Responde la pregunta de si las
areas quedan contenidas en regiones propias del mapa o se mezclan -- la
misma logica que la idea de onboarding "Encuentra tu area" ya registrada en
development.md.

Un solo color superpuesto por las 5 categorias (area 1-4 + sin area) no
aguanta separacion confiable en un scatter de 609k puntos (ver dataviz:
mas de 3 series en un scatter satura el canal de color) -- por eso un panel
por area, cada uno una sola serie (un solo hue, sin necesidad de leyenda),
con el resto del corpus como contexto gris de fondo.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/02_mapa_por_area.png"))

AREA_LABELS = {
    "area 1": "Area 1 -- Fisico-Matematicas",
    "area 2": "Area 2 -- Biologicas y de la Salud",
    "area 3": "Area 3 -- Sociales",
    "area 4": "Area 4 -- Humanidades y las Artes",
}
HIGHLIGHT = "#2a78d6"  # slot 1 (blue) de la paleta categorica -- una sola serie por panel


def main():
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "area", "cluster_id"])
    df = layout.merge(clusters, on="thesis_id", how="left")

    fig, axes = plt.subplots(2, 2, figsize=(14, 13), dpi=150)
    fig.patch.set_facecolor("white")

    for ax, area_code in zip(axes.ravel(), ["area 1", "area 2", "area 3", "area 4"]):
        ax.set_facecolor("white")
        resto = df[df["area"] != area_code]
        propia = df[df["area"] == area_code]
        ruido_pct = (propia["cluster_id"] == -1).mean() * 100

        ax.scatter(resto["x"], resto["y"], s=0.5, c="#e6e5e0", alpha=0.3,
                   linewidths=0, rasterized=True)
        ax.scatter(propia["x"], propia["y"], s=1.0, c=HIGHLIGHT, alpha=0.5,
                   linewidths=0, rasterized=True)

        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(
            f"{AREA_LABELS[area_code]}\nn={len(propia):,} · ruido={ruido_pct:.1f}%",
            fontsize=11, color="#1a1a1a",
        )

    fig.suptitle(
        "Proyeccion PaCMAP 2D -- distribucion por area administrativa",
        fontsize=15, fontweight="bold", color="#1a1a1a", y=0.98,
    )
    fig.text(
        0.5, 0.005,
        "Mismo layout PaCMAP en los 4 paneles -- gris = resto del corpus, azul = tesis de esa area",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
