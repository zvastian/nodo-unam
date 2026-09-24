"""Genera embeddings semanticos del corpus COMPLETO (609,156 tesis) con
multilingual-e5-large, para correr en un Kaggle Notebook con GPU.

Como usarlo en Kaggle:
1. Crear un Kaggle Dataset nuevo subiendo data/public/data_unam.parquet
   (o data/clean/base7_kaggle_clean.parquet si prefieres el maestro interno
   con mas columnas -- este script solo necesita thesis_id/titulo/programa/
   nivel/area/plantel, que existen en ambos, con esos nombres exactos en
   data_unam.parquet).
2. Crear un Kaggle Notebook nuevo, activar GPU (Settings > Accelerator > GPU T4 x2 o P100).
3. Agregar el dataset como input del notebook.
4. Pegar este script en una celda (ajustar SOURCE_PATH a la ruta de Kaggle,
   normalmente /kaggle/input/<nombre-dataset>/data_unam.parquet).
5. Correr. Al terminar, descargar embeddings.npy + metadata.parquet desde
   /kaggle/working/.

Texto que se embebe: SOLO titulo (confirmado contra notebooks/proc_abril28.ipynb,
el notebook real que genero los embeddings de produccion -- nunca concateno
programa/nivel/area/plantel, a diferencia de rebuild_01_sample_embeddings.py
que era un experimento distinto para la muestra de 50k).

Se mantiene asi a proposito, no solo por precedente: concatenar categoria
dentro del texto embebido empuja el clustering a agruparse por categoria
(que ya existe como filtro explicito) en vez de por contenido semantico real
-- eso suprime justo el tipo de hallazgo cruzado entre areas/programas que
hace valioso un atlas semantico en primer lugar. programa/nivel/area/plantel
se guardan como metadata adjunta (para filtrar/colorear en la UI), no se
mezclan con el texto que se embebe.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# --- Ajustar esto en Kaggle ---
SOURCE_PATH = Path(os.getenv(
    "SOURCE_PATH",
    "/kaggle/input/datasets/sebastiandiazprado/tesis-unam/data_unam.parquet",
))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/kaggle/working"))

MODEL_NAME = "intfloat/multilingual-e5-large"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "128"))

# E5 requiere el prefijo "query: " en cada texto para similitud simetrica
# (comparar tesis contra tesis, tesis contra Nobel) -- es la convencion
# documentada del modelo, no una eleccion arbitraria de este script.
E5_PREFIX = "query: "


def build_embedding_text(row: pd.Series) -> str:
    return E5_PREFIX + str(row.get("titulo", "") or "").strip()


def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"No encontre {SOURCE_PATH} -- revisa la ruta del dataset en Kaggle "
            "(normalmente /kaggle/input/<nombre-del-dataset>/data_unam.parquet)"
        )

    print(f"Leyendo {SOURCE_PATH}")
    df = pd.read_parquet(
        SOURCE_PATH,
        columns=["thesis_id", "titulo", "programa", "nivel", "area", "plantel"],
    )
    print("Filas:", len(df))

    df = df[df["titulo"].str.strip() != ""].reset_index(drop=True)
    print("Filas con titulo no vacio:", len(df))

    texts = [build_embedding_text(row) for _, row in df.iterrows()]

    print(f"Cargando modelo: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    print("Dispositivo:", model.device)

    print(f"Generando embeddings para {len(texts):,} tesis (batch_size={BATCH_SIZE})...")
    X = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")

    print("Embeddings:", X.shape)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # programa/nivel/area/plantel viajan como metadata adjunta (filtrar/colorear
    # en la UI), no se mezclaron con el texto embebido -- ver nota arriba.
    meta = df[["thesis_id", "programa", "nivel", "area", "plantel"]].copy()
    meta.to_parquet(OUTPUT_DIR / "embeddings_meta.parquet", index=False)
    np.save(OUTPUT_DIR / "embeddings_full_e5large.npy", X)

    print("\nOK")
    print("Guardado:", OUTPUT_DIR / "embeddings_full_e5large.npy", X.shape)
    print("Guardado:", OUTPUT_DIR / "embeddings_meta.parquet", meta.shape)
    print("\nOrden de embeddings_meta.parquet == orden de filas en el .npy (mismo indice).")


if __name__ == "__main__":
    main()
