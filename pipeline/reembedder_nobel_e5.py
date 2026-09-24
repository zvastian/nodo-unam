"""Re-embebe el corpus de Nobel con multilingual-e5-large, para que siga
viviendo en el mismo espacio semantico que las tesis (ver
generar_embeddings_full_e5.py) -- necesario para que "Nobel mas cercano a
tu tesis" siga siendo una comparacion valida tras el cambio de modelo.

Reutiliza build_nodes() de build_nobel_atlas.py (ya probado) en vez de
reimplementar el parseo de laureates/premios -- solo cambia el paso de
embedding.

Correr en el mismo Kaggle Notebook que generar_embeddings_full_e5.py
(agregar RAW_LAUREATES/RAW_PRIZES como input adicional del dataset, o
subirlos junto con data_unam.parquet).
"""
import importlib.util
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

BUILD_SCRIPT_PATH = Path(os.getenv(
    "BUILD_SCRIPT_PATH",
    "/kaggle/input/datasets/sebastiandiazprado/nobel-raw/build_nobel_atlas.py",
))
RAW_LAUREATES = Path(os.getenv(
    "RAW_LAUREATES",
    "/kaggle/input/datasets/sebastiandiazprado/nobel-raw/laureates_complete.json",
))
RAW_PRIZES = Path(os.getenv(
    "RAW_PRIZES",
    "/kaggle/input/datasets/sebastiandiazprado/nobel-raw/nobelPrizes_complete.json",
))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/kaggle/working"))

MODEL_NAME = "intfloat/multilingual-e5-large"
E5_PREFIX = "query: "


def load_build_module():
    """Importa build_nobel_atlas.py como modulo para reusar build_nodes()."""
    spec = importlib.util.spec_from_file_location("build_nobel_atlas", BUILD_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    # el script original espera RAW_LAUREATES/RAW_PRIZES como Path relativos;
    # se los sobreescribimos despues de cargarlo para apuntar a las rutas de Kaggle
    spec.loader.exec_module(module)
    module.RAW_LAUREATES = RAW_LAUREATES
    module.RAW_PRIZES = RAW_PRIZES
    return module


def main():
    if not BUILD_SCRIPT_PATH.exists():
        raise FileNotFoundError(
            f"No encontre {BUILD_SCRIPT_PATH} -- sube build_nobel_atlas.py, "
            "laureates_complete.json y nobelPrizes_complete.json como input del notebook."
        )

    mod = load_build_module()

    import json
    laureate_payload = json.loads(RAW_LAUREATES.read_text(encoding="utf-8"))
    laureates = laureate_payload["laureates"]
    nodes, _entities, _organization_ids = mod.build_nodes(laureates)
    print("Nodos de Nobel:", len(nodes))

    texts = [
        E5_PREFIX + (node["motivation"] or f'{node["name"]} {node["category_en"]}')
        for node in nodes
    ]

    print(f"Cargando modelo: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print("Generando embeddings de Nobel...")
    X = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")

    print("Embeddings Nobel:", X.shape)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    node_ids = pd.DataFrame({"node_id": [n["id"] for n in nodes]})
    node_ids.to_parquet(OUTPUT_DIR / "nobel_embeddings_meta.parquet", index=False)
    np.save(OUTPUT_DIR / "nobel_embeddings_e5large.npy", X)

    print("\nOK")
    print("Guardado:", OUTPUT_DIR / "nobel_embeddings_e5large.npy", X.shape)
    print("Guardado:", OUTPUT_DIR / "nobel_embeddings_meta.parquet", node_ids.shape)


if __name__ == "__main__":
    main()
