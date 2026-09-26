"""Numero de registro de TESIUNAM (Koha) de CADA tesis del atlas, alineado con el orden del mapa.

Las ligas guardadas en base6 son de Aleph, con sesion caducada, y ya no abren. Pero Koha
conservo el numero de registro de Aleph como biblionumber: en los registros MARC,
system_number = "TES01" + "00" + biblionumber en el 100 %. Asi, la liga permanente es
  https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-detail.pl?biblionumber=<n>
  base6           n = doc_number de texto_completo_url (doc_library=TES01)
  marc_recovered  n = biblionumber
Sin numero (unas 15.8k de base6), la interfaz manda al buscador del catalogo.

Salida (prototypes/atlas_vecindario_mvp/data/):
  tesis_catalogo.v1.bin   Uint32 por tesis, en el orden de atlas_chaos_mode (0 = sin numero)

Uso (desde la raiz del repo):  python pipeline/generar_atlas_catalogo.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

D = Path("prototypes/atlas_vecindario_mvp/data")
BASE7 = Path(os.getenv("BASE7_PATH", "data/clean/base7_kaggle_clean.parquet"))


def main():
    meta = json.load(open(D / "atlas_chaos_mode.v1.json", encoding="utf8"))
    raw = open(D / "atlas_chaos_mode.v1.bin", "rb").read()
    f = meta["fields"]["thesisIdsBlob"]
    ids = raw[f["byteOffset"]:f["byteOffset"] + f["byteLength"]].decode("utf8").split("\n")
    N = len(ids)
    print("tesis en el atlas", N)

    # sin autores: solo identificadores
    df = pd.read_parquet(BASE7, columns=["thesis_id", "source_record", "biblionumber", "texto_completo_url"])
    doc = df["texto_completo_url"].fillna("").str.extract(r"doc_library=TES01&doc_number=(\d+)", expand=False)
    bn = pd.to_numeric(df["biblionumber"].replace("", None), errors="coerce")
    num = pd.to_numeric(doc, errors="coerce").where(df["source_record"] == "base6", bn)
    s = pd.Series(num.to_numpy(), index=df["thesis_id"])
    s = s[~s.index.duplicated()]
    print("sin fila en base7", int((~pd.Index(ids).isin(s.index)).sum()))
    s = s.reindex(ids)

    arr = s.fillna(0).astype(np.int64).to_numpy()
    assert arr.max() < 2**32
    arr = arr.astype(np.uint32)
    con = int((arr > 0).sum())
    print(f"con numero de registro: {con:,} ({con / N:.1%}); sin numero: {N - con:,}")
    dup = pd.Series(arr[arr > 0]).duplicated().sum()
    print("numeros repetidos entre tesis", int(dup))

    (D / "tesis_catalogo.v1.bin").write_bytes(arr.tobytes())
    print("bin", arr.nbytes, "bytes")


if __name__ == "__main__":
    main()
