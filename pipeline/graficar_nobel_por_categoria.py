"""Item 8 del checklist "Evidencia visual del proceso": valida visualmente el
hallazgo cuantitativo de `pipeline/analizar_area_por_posicion.py` (categoria
Nobel real -> area inferida por posicion, ver development.md) mostrando donde
cae cada categoria por separado sobre el mismo mapa.

Small multiples (mismo criterio que `graficar_atlas_por_area.py`) en vez de
un solo scatter con 6 colores: un solo acento por panel evita apilar una
paleta categorica de 6 tonos sobre un scatter de 609k puntos (la guia de
dataviz limita un scatter a 3 series categoricas simultaneas antes de perder
separacion CVD-segura; con 6 categorias la salida correcta es facetar, no
forzar la paleta). Cada panel usa el mismo acento dorado que ya identifica
"laureado Nobel" en `docs/evidencia_visual/04_mapa_con_nobel.png` -- el color
no distingue categoria aqui, el titulo del panel lo hace; lo que cambia entre
paneles es solo el subconjunto resaltado, igual que en el mapa por area.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TESIS_LAYOUT_PATH = Path(os.getenv("TESIS_LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
NOBEL_AREA_PATH = Path(os.getenv("NOBEL_AREA_PATH", "data/nobel/nobel_area_inferida.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/08_nobel_por_categoria.png"))

# Orden clasico de introduccion de los premios Nobel (Fisica/Quimica/Medicina/
# Literatura/Paz en 1901, Economia agregado en 1969) -- orden formal, no por
# tamano de categoria.
CATEGORY_ORDER = ["Fisica", "Quimica", "Medicina/Fisiologia", "Literatura", "Paz", "Economia"]
GOLD = "#eda100"
GOLD_EDGE = "#7a5c00"


def main():
    tesis = pd.read_parquet(TESIS_LAYOUT_PATH)
    nobel = pd.read_parquet(NOBEL_AREA_PATH)

    fig, axes = plt.subplots(2, 3, figsize=(16, 11), dpi=150)
    fig.patch.set_facecolor("white")

    for ax, cat in zip(axes.ravel(), CATEGORY_ORDER):
        ax.set_facecolor("white")
        subset = nobel[nobel["category"] == cat]
        area_top = subset["area_inferida"].value_counts(normalize=True)
        area_label = f"{area_top.index[0]} ({area_top.iloc[0]*100:.0f}%)" if len(area_top) else "--"

        ax.scatter(tesis["x"], tesis["y"], s=0.4, c="#e6e5e0", alpha=0.3,
                   linewidths=0, rasterized=True)
        ax.scatter(subset["x"], subset["y"], s=26, c=GOLD, alpha=0.9,
                   marker="*", linewidths=0.4, edgecolors=GOLD_EDGE, zorder=5)

        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(
            f"{cat}\nn={len(subset)} · área dominante: {area_label}",
            fontsize=11, color="#1a1a1a",
        )

    fig.suptitle(
        "Proyección PaCMAP 2D — laureados Nobel por categoría real",
        fontsize=15, fontweight="bold", color="#1a1a1a", y=0.99,
    )
    fig.text(
        0.5, 0.005,
        "Mismo layout PaCMAP en los 6 paneles · gris = corpus UNAM · estrella dorada = laureado de esa categoría · "
        "área dominante = voto de sus 25 tesis vecinas más cercanas en 2D (pipeline/analizar_area_por_posicion.py)",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
