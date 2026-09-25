"""Titulos (sin autor) + anio de las 609,154 tesis, partidos en teselas espaciales.

Para el tooltip del atlas: al pasar el cursor sobre CUALQUIER punto se muestra su
titulo. Cargar los 609k titulos de golpe (~60 MB) no es viable en el navegador;
como el hover es local (el cursor recorre zonas contiguas), se parte el mapa en una
grilla de GxG teselas sobre las coordenadas PaCMAP crudas y el frontend pide solo
la tesela bajo el cursor (cache despues). Medido con G=64: 855 teselas no vacias,
mediana ~357 titulos, la mas densa ~4,555 (~0.5 MB).

El indice de punto (`i`) es la posicion en atlas_chaos_mode.v1.bin (mismo orden que
x/y/thesisIds). El titulo se limpia con la MISMA funcion que tesis_por_micro
(`titulo_sin_autor` + red de seguridad `AUTOR_RE`): nunca se escribe el autor.

Uso: python pipeline/generar_atlas_titulos_teselas.py
Salida: atlas_data/titulos_teselas/{tx}_{ty}.json + manifest.json (+ copia con COPY_TO)
"""
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_atlas_tesis_por_micro import AUTOR_RE, titulo_sin_autor  # noqa: E402

CHAOS_META = Path("atlas_data/atlas_chaos_mode.v1.json")
CHAOS_BIN = Path("atlas_data/atlas_chaos_mode.v1.bin")
DATA_PATH = Path(os.getenv("DATA_PATH", "data/public/data_unam.parquet"))
OUT_DIR = Path(os.getenv("OUT_DIR", "atlas_data/titulos_teselas"))
COPY_TO = os.getenv("COPY_TO", "prototypes/atlas_vecindario_mvp/data/titulos_teselas")
G = int(os.getenv("GRID", "64"))


def main():
    meta = json.loads(CHAOS_META.read_text(encoding="utf-8"))
    f, n = meta["fields"], meta["n"]
    buf = CHAOS_BIN.read_bytes()
    x = np.frombuffer(buf, np.float32, n, f["x"]["byteOffset"])
    y = np.frombuffer(buf, np.float32, n, f["y"]["byteOffset"])
    ids_blob = buf[f["thesisIdsBlob"]["byteOffset"]: f["thesisIdsBlob"]["byteOffset"] + f["thesisIdsBlob"]["byteLength"]]
    ids = ids_blob.decode("utf-8").split("\n")
    assert len(ids) == n

    d = pd.read_parquet(DATA_PATH, columns=["thesis_id", "anio", "titulo_legible"]).set_index("thesis_id")
    d = d.reindex(ids)
    titulos = d["titulo_legible"].fillna("").map(titulo_sin_autor)
    fugas = titulos.map(lambda t: bool(AUTOR_RE.search(t)))
    print(f"titulos con posible autor tras el corte: {int(fugas.sum())} (se omiten)")
    titulos[fugas] = "(título no disponible)"
    anios = pd.to_numeric(d["anio"], errors="coerce")

    # grilla cuadrada sobre coordenadas crudas (float64 sobre valores float32: el
    # frontend lee los mismos float32 y aplica la misma formula)
    x0, y0 = float(x.min()), float(y.min())
    cell = max(float(x.max()) - x0, float(y.max()) - y0) / G * 1.0001
    tx = np.minimum(((x.astype(np.float64) - x0) / cell).astype(int), G - 1)
    ty = np.minimum(((y.astype(np.float64) - y0) / cell).astype(int), G - 1)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tile = tx * G + ty
    order = np.argsort(tile, kind="stable")
    bounds = np.flatnonzero(np.diff(tile[order])) + 1
    total, biggest = 0, 0
    tit_arr, anio_arr = titulos.to_numpy(), anios.to_numpy()
    for grp in np.split(order, bounds):
        t0 = int(tile[grp[0]])
        payload = {"i": grp.tolist(), "t": [tit_arr[k] for k in grp],
                   "y": [None if np.isnan(anio_arr[k]) else int(anio_arr[k]) for k in grp]}
        p = OUT_DIR / f"{t0 // G}_{t0 % G}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        sz = p.stat().st_size
        total += sz
        biggest = max(biggest, sz)
    manifest = {"version": "atlas-titulos-teselas-v1", "grid": G, "x0": x0, "y0": y0, "cell": cell, "n": n,
                "nota": "tesela = floor((x-x0)/cell), floor((y-y0)/cell) sobre x/y crudos de atlas_chaos_mode.v1.bin; titulos sin autor"}
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    print(f"{len(bounds) + 1} teselas, {total / 1e6:.1f} MB, la mayor {biggest / 1e6:.2f} MB")
    if COPY_TO:
        dst = Path(COPY_TO)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(OUT_DIR, dst)
        print(f"copiado a {dst}")


if __name__ == "__main__":
    main()
