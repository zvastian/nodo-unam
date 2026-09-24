"""Dendrograma del corte macro (Ward sobre los 513 centroides de micro-cluster)
-- pedido explicito del usuario tras `pipeline/construir_jerarquia_macro_meso.py`.

Trunca a los ultimos `TRUNCATE_P` merges (`truncate_mode='lastp'`) porque 513
hojas no caben legibles en un dendrograma -- lo relevante para esta pieza es
la parte ALTA del arbol (donde se decide el corte macro), no el detalle fino
de como se fusionaron micro-clusters individuales (eso ya vive en
`macro_topics_ctfidf.parquet`). Linea horizontal marca la altura de corte
elegida para N=53 (banda 50-60 pedida por el usuario, ver development.md).
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram

Z_PATH = Path(os.getenv("Z_PATH", "data/clustering/macro_linkage_Z.npy"))
JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/10_dendrograma_macro.png"))
TRUNCATE_P = int(os.getenv("TRUNCATE_P", "80"))


def main():
    Z = np.load(Z_PATH)
    jerarquia = pd.read_parquet(JERARQUIA_PATH)
    n_clusters = len(jerarquia)
    n_macro = jerarquia["macro_id"].nunique()

    # D_MACRO fijo (no se re-deriva del conteo de macros): tras la correccion
    # manual (pipeline/aplicar_correccion_manual_macro.py) el conteo de macros
    # ya no corresponde a un corte plano unico del arbol -- se separaron 6
    # ramas mas alla del corte automatico de D=0.40, asi que back-calcular la
    # altura desde n_macro daria una linea sin sentido. La linea roja marca el
    # corte automatico ORIGINAL; las 6 separaciones manuales no se ven como
    # una segunda linea (serian 6 alturas locales distintas, una por rama).
    D_MACRO_ORIGINAL = float(os.getenv("D_MACRO_ORIGINAL", "0.40"))
    altura_corte = D_MACRO_ORIGINAL

    fig, ax = plt.subplots(figsize=(16, 7), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    dendrogram(
        Z, truncate_mode="lastp", p=TRUNCATE_P, no_labels=True,
        color_threshold=altura_corte, above_threshold_color="#c3c2b7",
        ax=ax,
    )
    ax.axhline(altura_corte, color="#e34948", linestyle="--", linewidth=1.5, zorder=5)
    ax.text(ax.get_xlim()[1] * 0.995, altura_corte, f"  corte automático (D={D_MACRO_ORIGINAL:.2f})",
            color="#e34948", fontsize=10, va="center", ha="left")

    ax.set_xticks([])
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.set_ylabel("Distancia de fusión (Ward)", fontsize=10, color="#52514e")
    ax.tick_params(axis="y", colors="#52514e")

    ax.set_title(
        f"Dendrograma Ward — {n_clusters} micro-clusters → {n_macro} macro-grupos finales",
        fontsize=15, fontweight="bold", color="#1a1a1a", pad=14,
    )
    fig.text(
        0.5, -0.03,
        f"Ward sobre centroides de embeddings (1024d, e5-large, normalizados a coseno) · truncado a los últimos "
        f"{TRUNCATE_P} merges para legibilidad (las hojas individuales de los {n_clusters} micro-clusters no se muestran) · "
        f"línea roja = corte automático por distancia (89 macro-grupos) · 6 de esos 89 se separaron después a mano en sus "
        f"meso constituyentes (ver development.md), dando el total final de {n_macro} · 2026-09-22",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
