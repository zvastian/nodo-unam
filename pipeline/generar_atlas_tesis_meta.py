"""Nivel, programa y plantel de CADA tesis del atlas, alineados con el orden del mapa.

Hasta v4.3 el prototipo solo tenia estos datos para las ~200k tesis de algun tema fino
(tesis_por_micro/). La ficha de una tesis cualquiera (v4.4) los necesita para todas.

Salida (prototypes/atlas_vecindario_mvp/data/):
  tesis_meta.v1.json   diccionarios: niveles, programas, planteles (texto normalizado,
                       sin acentos; la interfaz les pone la escritura real con escritura.v1.json)
  tesis_meta.v1.bin    tres arreglos contiguos de N entradas, en el orden de atlas_chaos_mode:
                         Uint8  nivel     (0 = sin dato; 1..4 = Licenciatura..Doctorado)
                         Uint16 programa  (0 = sin dato; k = programas[k-1])
                         Uint16 plantel   (0 = sin dato; k = planteles[k-1])
El area no va aqui: ya viene por tesis en atlas_chaos_mode (areaCode).
Sin autores: solo se leen columnas institucionales.

Uso (desde la raiz del repo):  python pipeline/generar_atlas_tesis_meta.py
"""
import json
import os
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

D = Path("prototypes/atlas_vecindario_mvp/data")
DATA_PATH = Path(os.getenv("DATA_PATH", "data/public/data_unam.parquet"))
# orden escalonado: la interfaz lo dibuja como escala de intensidad (30/45/70/100 %)
NIVELES = ["Licenciatura", "Especialidad", "Maestría", "Doctorado"]


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn").strip()


def main():
    meta = json.load(open(D / "atlas_chaos_mode.v1.json", encoding="utf8"))
    raw = open(D / "atlas_chaos_mode.v1.bin", "rb").read()
    f = meta["fields"]["thesisIdsBlob"]
    ids = raw[f["byteOffset"]:f["byteOffset"] + f["byteLength"]].decode("utf8").split("\n")
    N = len(ids)
    print("tesis en el atlas", N)

    df = pd.read_parquet(DATA_PATH, columns=["thesis_id", "nivel", "programa", "plantel"])
    df = df.drop_duplicates("thesis_id").set_index("thesis_id").reindex(ids)
    faltan = int(df["nivel"].isna().sum())
    print("sin fila en el catalogo", faltan)

    canon = {sin_acentos(n): k + 1 for k, n in enumerate(NIVELES)}
    nivel = df["nivel"].fillna("").map(lambda v: canon.get(sin_acentos(v), 0)).to_numpy(np.uint8)

    def codificar(col):
        vals = df[col].fillna("").str.strip()
        cats = sorted(v for v in vals.unique() if v)
        assert len(cats) < 65535, col
        idx = {v: k + 1 for k, v in enumerate(cats)}
        return cats, vals.map(lambda v: idx.get(v, 0)).to_numpy(np.uint16)

    programas, programa = codificar("programa")
    planteles, plantel = codificar("plantel")
    for nombre, arr in [("nivel", nivel), ("programa", programa), ("plantel", plantel)]:
        print(f"{nombre}: {int((arr > 0).sum()):,} con dato ({(arr > 0).mean():.1%})")

    # Uint8 primero y relleno a par, para que los Uint16 queden alineados
    pad = N % 2
    blob = nivel.tobytes() + b"\0" * pad + programa.tobytes() + plantel.tobytes()
    off_pr = N + pad
    (D / "tesis_meta.v1.bin").write_bytes(blob)
    out = {
        "version": 1, "count": N, "niveles": NIVELES, "programas": programas, "planteles": planteles,
        "fields": {
            "nivel": {"type": "Uint8", "byteOffset": 0, "count": N},
            "programa": {"type": "Uint16", "byteOffset": off_pr, "count": N},
            "plantel": {"type": "Uint16", "byteOffset": off_pr + 2 * N, "count": N},
        },
    }
    json.dump(out, open(D / "tesis_meta.v1.json", "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
    print("bin", len(blob), "bytes; json", (D / "tesis_meta.v1.json").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
