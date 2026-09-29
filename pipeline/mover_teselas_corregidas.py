"""Reubica en las teselas de titulos las tesis que `corregir_layout_manual.py` movio.

Regenerar las teselas completas con `generar_atlas_titulos_teselas.py` cambiaria tambien
los titulos ya publicados (la limpieza de autores posterior a la generacion). Como la
grilla depende solo de los limites del mapa, que la correccion no altera, basta sacar
cada tesis movida de su tesela vieja y ponerla en la nueva, con su titulo y anio tal cual.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

D = Path(os.getenv("DATA_DIR", "prototypes/atlas_vecindario_mvp/data"))
MOVIDOS = Path(os.getenv("OUT_MOVIDOS", "data/clustering/layout_movidos.json"))


def main():
    meta = json.loads((D / "atlas_chaos_mode.v1.json").read_text(encoding="utf-8"))
    f, n = meta["fields"], meta["n"]
    buf = (D / "atlas_chaos_mode.v1.bin").read_bytes()
    x = np.frombuffer(buf, np.float32, n, f["x"]["byteOffset"]).astype(np.float64)
    y = np.frombuffer(buf, np.float32, n, f["y"]["byteOffset"]).astype(np.float64)
    ids = buf[f["thesisIdsBlob"]["byteOffset"]: f["thesisIdsBlob"]["byteOffset"] + f["thesisIdsBlob"]["byteLength"]].decode("utf-8").split("\n")
    pos = {t: i for i, t in enumerate(ids)}
    man = json.loads((D / "titulos_teselas" / "manifest.json").read_text(encoding="utf-8"))
    G, x0, y0, cell = man["grid"], man["x0"], man["y0"], man["cell"]
    assert x.min() == x0 and y.min() == y0 or (x.min() >= x0 and y.min() >= y0), "los limites del mapa cambiaron: regenerar las teselas completas"

    movidos = sorted(pos[t] for t in json.loads(MOVIDOS.read_text(encoding="utf-8"))["thesis_ids"])
    nueva = {i: (min(int((x[i] - x0) / cell), G - 1), min(int((y[i] - y0) / cell), G - 1)) for i in movidos}
    mset = set(movidos)

    cache = {}
    def cargar(k):
        if k not in cache:
            p = D / "titulos_teselas" / f"{k[0]}_{k[1]}.json"
            cache[k] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"i": [], "t": [], "y": []}
        return cache[k]

    # 1) sacar cada tesis movida de la tesela que la tenga (la vieja)
    saco = {}
    for p in (D / "titulos_teselas").glob("*_*.json"):
        k = tuple(int(v) for v in p.stem.split("_"))
        d = cargar(k)
        keep = [j for j, i in enumerate(d["i"]) if i not in mset]
        if len(keep) != len(d["i"]):
            for j, i in enumerate(d["i"]):
                if i in mset:
                    saco[i] = (d["t"][j], d["y"][j])
            d["i"], d["t"], d["y"] = ([d[c][j] for j in keep] for c in ("i", "t", "y"))
    assert set(saco) == mset, f"faltan {len(mset - set(saco))} tesis en las teselas"

    # 2) ponerlas en la nueva, manteniendo el orden por indice
    por_tesela = defaultdict(list)
    for i in movidos:
        por_tesela[nueva[i]].append(i)
    for k, lst in por_tesela.items():
        d = cargar(k)
        filas = sorted(list(zip(d["i"], d["t"], d["y"])) + [(i, *saco[i]) for i in lst])
        d["i"], d["t"], d["y"] = ([r[c] for r in filas] for c in range(3))

    for k, d in cache.items():
        p = D / "titulos_teselas" / f"{k[0]}_{k[1]}.json"
        if d["i"]:
            p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        elif p.exists():
            p.unlink()
    print(f"{len(movidos)} tesis reubicadas en {len(por_tesela)} teselas nuevas")


if __name__ == "__main__":
    main()
