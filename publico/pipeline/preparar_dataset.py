"""Paso 0 del pipeline: prepara el dataset público para los scripts que siguen.

Entrada: el parquet del dataset abierto de Kaggle (sebastiandiazprado/nodos-map), con una fila
por tesis y la columna `titulo_legible` (título sin mención de autor).
Salida: data/public/data_unam.parquet, el mismo dataset con una columna más, `titulo`: el título
normalizado (minúsculas, sin acentos ni signos) que usan el embedding y las palabras clave c-TF-IDF.

Uso:
    python pipeline/preparar_dataset.py ruta/al/dataset.parquet

Nota de reproducibilidad: la corrida original normalizó el título a partir de la cadena
bibliográfica completa del catálogo. Aquí se normaliza `titulo_legible`, que ya no trae la mención
de responsabilidad. En unas decenas de miles de títulos el texto difiere (signos y mención de
autor), así que los embeddings y los grupos resultantes son equivalentes, no idénticos.
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "data" / "public" / "data_unam.parquet"


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos ni signos, con espacios simples (ñ pasa a n, como en la corrida original)."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    df = pd.read_parquet(sys.argv[1])
    for col in ("thesis_id", "titulo_legible"):
        if col not in df.columns:
            sys.exit(f"Falta la columna {col!r}: ¿es el dataset de Kaggle?")
    df["titulo"] = df["titulo_legible"].fillna("").map(normalizar)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SALIDA, index=False)
    vacios = int((df["titulo"] == "").sum())
    print(f"{SALIDA}: {len(df):,} filas; {vacios} sin título (se excluyen al embeber).")


if __name__ == "__main__":
    main()
