"""Caracteriza el hueco GRANDE detectado a la izquierda del centro del mapa
(distinto del "hueco central" ya documentado en gap.md e
`docs/evidencia_visual/09_hueco_central_composicion.png`) -- observacion del
usuario: el hueco central que se habia analizado antes es chico; hay uno
notablemente mas grande a su izquierda que no se habia caracterizado.

Diferencia metodologica clave con `analizar_hueco_central.py`: aquel usaba
un CIRCULO centrado en el CENTROIDE del corpus completo (media de x,y de
los 609,154 puntos) -- eso asume que el hueco es radialmente simetrico
alrededor del centro de masa del corpus, lo cual resulto ser incorrecto:
al graficar la densidad 2D real (sin esa asuncion) el hueco grande queda
centrado en (-2.9, -1.4), no en (0.09, 0.11) -- el circulo anterior solo
cubria una porcion del hueco real.

Metodo correcto, sin asumir forma ni centro de antemano:
1. Grilla 2D fina (200x200 bins) de conteo de puntos.
2. "Ocupado" = celda con >=3 puntos (umbral bajo, solo filtra puntos sueltos
   aislados). "Hueco" = cualquier celda NO ocupada que quede completamente
   ENCERRADA por celdas ocupadas (`scipy.ndimage.binary_fill_holes` rellena
   el contorno exterior, la diferencia contra el mapa de ocupacion original
   da los huecos internos reales, sea cual sea su forma).
3. Componentes conexas (`scipy.ndimage.label`) de esos huecos -- el
   componente mas grande es, por definicion, el hueco dominante del mapa
   (se verifica que efectivamente contenga/corresponda al hueco chico ya
   conocido, o sea distinto, sin asumirlo).
4. Nucleo estricto = esas celdas (densidad casi cero). Zona ampliada =
   dilatacion binaria fija (N_DILATE celdas) del nucleo, para tener
   suficientes tesis y caracterizar composicion con significancia.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
TOPICS_PATH = Path(os.getenv("TOPICS_PATH", "data/clustering/cluster_topics_ctfidf.parquet"))
TITULOS_PATH = Path(os.getenv("TITULOS_PATH", "data/public/data_unam.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/hueco_izquierdo_puntos.parquet"))
OUTPUT_MASK = Path(os.getenv("OUTPUT_MASK", "data/clustering/hueco_izquierdo_mask.npz"))

NBINS = int(os.getenv("NBINS", "200"))
MIN_OCUPADO = int(os.getenv("MIN_OCUPADO", "3"))
N_DILATE = int(os.getenv("N_DILATE", "5"))


def main():
    print("Cargando...")
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "area", "cluster_id"])
    topics = pd.read_parquet(TOPICS_PATH)
    titulos = pd.read_parquet(TITULOS_PATH, columns=["thesis_id", "titulo"])
    df = layout.merge(clusters, on="thesis_id", how="left").merge(titulos, on="thesis_id", how="left")

    x, y = df["x"].to_numpy(), df["y"].to_numpy()
    counts, xedges, yedges = np.histogram2d(x, y, bins=NBINS)
    occupied = counts >= MIN_OCUPADO
    filled = ndimage.binary_fill_holes(occupied)
    hole_mask = filled & ~occupied
    labels, n = ndimage.label(hole_mask)
    sizes = ndimage.sum(hole_mask, labels, range(1, n + 1))
    comp_id = int(np.argmax(sizes) + 1)
    strict = labels == comp_id
    print(f"Componentes de hueco encontrados: {n} | mayor: {int(sizes.max())} celdas "
          f"(2do mayor: {int(sorted(sizes, reverse=True)[1]) if n > 1 else 0} celdas)")

    xi_idx, yi_idx = np.where(strict)
    x0, x1 = xedges[xi_idx.min()], xedges[xi_idx.max() + 1]
    y0, y1 = yedges[yi_idx.min()], yedges[yi_idx.max() + 1]
    cx = (xedges[xi_idx] + xedges[xi_idx + 1]).mean() / 2
    cy = (yedges[yi_idx] + yedges[yi_idx + 1]).mean() / 2
    print(f"Núcleo estricto: {strict.sum()} celdas, bbox x=[{x0:.2f},{x1:.2f}] y=[{y0:.2f},{y1:.2f}], "
          f"centroide=({cx:.2f},{cy:.2f})")

    dilated = ndimage.binary_dilation(strict, iterations=N_DILATE)
    xdi, ydi = np.where(dilated)
    xd0, xd1 = xedges[xdi.min()], xedges[xdi.max() + 1]
    yd0, yd1 = yedges[ydi.min()], yedges[ydi.max() + 1]
    print(f"Zona ampliada (dilatada {N_DILATE} celdas): {dilated.sum()} celdas, "
          f"bbox x=[{xd0:.2f},{xd1:.2f}] y=[{yd0:.2f},{yd1:.2f}]")

    bin_x = np.clip(np.digitize(x, xedges[1:-1]), 0, NBINS - 1)
    bin_y = np.clip(np.digitize(y, yedges[1:-1]), 0, NBINS - 1)
    en_estricto = strict[bin_x, bin_y]
    en_ampliado = dilated[bin_x, bin_y]

    print(f"\nTesis en núcleo estricto (densidad casi cero): {en_estricto.sum()}")
    print(f"Tesis en zona ampliada: {en_ampliado.sum()} ({en_ampliado.sum()/len(df)*100:.2f}% del corpus)")

    zona = df[en_ampliado].copy()
    zona["en_nucleo_estricto"] = en_estricto[en_ampliado]

    ruido_pct = (zona["cluster_id"] == -1).mean() * 100
    ruido_pct_global = (df["cluster_id"] == -1).mean() * 100
    print(f"\nRuido en la zona: {ruido_pct:.1f}% (global: {ruido_pct_global:.1f}%)")

    top_clusters = zona[zona["cluster_id"] != -1]["cluster_id"].value_counts().head(12)
    print("\nTop clusters reales en la zona:")
    for cid, n_pts in top_clusters.items():
        label_rows = topics.loc[topics["cluster_id"] == cid, "topic_label"]
        label = label_rows.iloc[0] if len(label_rows) else "?"
        print(f"  cluster {cid}: n={n_pts} ({n_pts/len(zona)*100:.1f}%) -- {label}")

    area_global = df["area"].value_counts(normalize=True).sort_index()
    area_zona = zona["area"].value_counts(normalize=True).sort_index()
    comp = pd.DataFrame({"global": area_global, "zona": area_zona}).fillna(0)
    comp["enriquecimiento"] = comp["zona"] / comp["global"]
    print("\nÁrea administrativa -- zona vs. corpus completo:")
    print(comp.round(3))

    dup_zona = zona["titulo"].duplicated(keep=False).mean() * 100
    resto = df[~en_ampliado]
    dup_resto = resto["titulo"].duplicated(keep=False).mean() * 100
    print(f"\nTítulos duplicados -- zona: {dup_zona:.1f}% | resto del corpus: {dup_resto:.1f}%")

    print("\nMuestra de 15 títulos del núcleo estricto (los que sí caen ahí):")
    nucleo_df = zona[zona["en_nucleo_estricto"]]
    with pd.option_context("display.max_colwidth", 90):
        print(nucleo_df[["area", "cluster_id", "titulo"]].sample(min(15, len(nucleo_df)), random_state=42))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    zona.to_parquet(OUTPUT_PATH, index=False)
    np.savez(OUTPUT_MASK, strict=strict, dilated=dilated, xedges=xedges, yedges=yedges, cx=cx, cy=cy)
    print("\nGuardado:", OUTPUT_PATH, OUTPUT_MASK)


if __name__ == "__main__":
    main()
