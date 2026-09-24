"""Índices de búsqueda y de asesores para el prototipo del atlas (v4.2).

Salidas en prototypes/atlas_vecindario_mvp/data/:

  busqueda/titulos/t{xx}.json  índice invertido de los 609k títulos, repartido por las dos
                              primeras letras de la palabra (tres, en los repartos grandes
                              listados en _indice.json). {"palabra": "<base64>"}: índices
                              del atlas (orden de atlas_chaos_mode) ordenados, en deltas
                              varint. Palabras vacías fuera. Se carga solo el reparto de
                              lo que se escribe (máx. ~300 KB).
  busqueda/temas.v1.json      subtemas y temas finos: [nivel, macroId, id, label, size]
                              (sustituye cargar 238 archivos para buscar nombres).
  asesores.v1.json            asesores unificados (pipeline/unificar_asesores.py):
                              {"nombres": [...], "n": [...]}, el id es la posición.
  asesores_por_tesis.v1.bin   por tesis del atlas, sus asesores: Uint32 offsets[N+1] y
                              Uint32 ids (CSR). Base de la búsqueda por asesor y de las
                              futuras vistas de asesores (recomendar, analizar, mapa propio).
  tesis_anio.v1.bin           Uint16 año por tesis del atlas (0 = sin año).

Los títulos salen de titulos_teselas/ (ya sin autor: limpiar_autores_atlas.py).
Uso: python pipeline/generar_atlas_busqueda.py   (después de unificar_asesores.py)
"""
import base64
import collections
import json
import os
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

D = Path("prototypes/atlas_vecindario_mvp/data")
ASES = Path("data/asesores")
TOK = re.compile(r"[a-z0-9ñ]+")
VACIAS = set("""a al ante bajo con contra de del desde durante e el ella ellos en entre es esta este
esto estos estas hacia hasta la las le les lo los mas me mi mis muy ni no o os para pero por que
se ser si sin sobre son su sus tal te tu un una unas uno unos y ya como cual cuales donde cuando
the of and in on for to an at by with from is its""".split())


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn" or c == "̃")
    return unicodedata.normalize("NFC", s).replace("ñ", "n")


def varint_deltas(ids):
    out, prev = bytearray(), 0
    for v in ids:
        d = v - prev; prev = v
        while d >= 0x80:
            out.append((d & 0x7F) | 0x80); d >>= 7
        out.append(d)
    return base64.b64encode(bytes(out)).decode("ascii")


def main():
    meta = json.load(open(D / "atlas_chaos_mode.v1.json", encoding="utf8"))
    raw = open(D / "atlas_chaos_mode.v1.bin", "rb").read()
    f = meta["fields"]["thesisIdsBlob"]
    ids = raw[f["byteOffset"]:f["byteOffset"] + f["byteLength"]].decode("utf8").split("\n")
    N = len(ids); pos = {t: i for i, t in enumerate(ids)}
    print("tesis en el atlas", N)

    # --- títulos y años ---
    post = collections.defaultdict(list)
    anio = np.zeros(N, dtype=np.uint16)
    tdir = D / "titulos_teselas"
    for fn in os.listdir(tdir):
        if fn == "manifest.json": continue
        d = json.load(open(tdir / fn, encoding="utf8"))
        for i, t, y in zip(d["i"], d["t"], d["y"]):
            if y: anio[i] = int(y)
            for w in set(TOK.findall(norm(t))):
                if len(w) >= 2 and w not in VACIAS: post[w].append(i)
    # repartos por 2 letras; los que pasan de ~200 KB se parten por 3 letras
    # (_indice.json lista los partidos). Las palabras de 2 letras de un reparto partido van
    # a «xx_».
    enc = {w: varint_deltas(sorted(l)) for w, l in post.items()}
    por2 = collections.defaultdict(dict)
    for w, b in enc.items(): por2[w[:2]][w] = b
    shards, partidos = {}, []
    for k, v in por2.items():
        if sum(len(w) + len(b) + 6 for w, b in v.items()) > 200_000:
            partidos.append(k)
            for w, b in v.items(): shards.setdefault(w[:3] if len(w) >= 3 else k + "_", {})[w] = b
        else:
            shards[k] = v
    out = D / "busqueda" / "titulos"; out.mkdir(parents=True, exist_ok=True)
    for f_ in out.glob("*.json"): f_.unlink()
    tam = 0
    # prefijo «t»: en Windows «con», «prn», «aux» y «nul» son nombres reservados y
    # «con.json» se escribía a la consola sin error (se perdían las palabras «con...»)
    for k, v in shards.items():
        p = out / ("t" + k + ".json")
        p.write_text(json.dumps(v, separators=(",", ":")), encoding="utf8"); tam += p.stat().st_size
    (out / "_indice.json").write_text(json.dumps({"partidos": sorted(partidos)}), encoding="utf8")
    print("palabras", len(post), "repartos", len(shards), "partidos", len(partidos), "MB", round(tam / 1e6, 1),
          "reparto mayor KB", round(max((out / ("t" + k + ".json")).stat().st_size for k in shards) / 1e3))
    assert len(list(out.glob("t*.json"))) == len(shards), "faltan repartos en disco"
    anio.tofile(D / "tesis_anio.v1.bin")

    # --- temas (subtemas y temas finos) ---
    temas = []
    for sub, lvl in (("meso_by_macro", "meso"), ("micro_by_macro", "micro")):
        for fn in sorted(os.listdir(D / sub)):
            dd = json.load(open(D / sub / fn, encoding="utf8"))
            for n in dd["nodes"]:
                temas.append([lvl, dd.get("macroId", n.get("macroId")), n["id"], n["label"], n["size"]])
    (D / "busqueda" / "temas.v1.json").write_text(json.dumps(temas, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print("temas", len(temas))

    # --- asesores unificados ---
    cat = pd.read_parquet(ASES / "asesores_catalogo.v1.parquet").sort_values("asesor_id")
    assert (cat["asesor_id"].values == np.arange(len(cat))).all()
    json.dump({"version": "asesores-v1", "nota": "unificados con pipeline/unificar_asesores.py; id = posición",
               "nombres": cat["nombre"].tolist(), "n": cat["n_tesis"].astype(int).tolist()},
              open(D / "asesores.v1.json", "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))
    can = pd.read_parquet(ASES / "asesores_canon.v1.parquet")
    can["i"] = can["thesis_id"].map(pos)
    fuera = can["i"].isna().sum()
    can = can.dropna(subset=["i"]).astype({"i": "int64"}).sort_values(["i", "orden"])
    cnt = np.bincount(can["i"].values, minlength=N)
    offsets = np.zeros(N + 1, dtype=np.uint32); offsets[1:] = np.cumsum(cnt)
    np.concatenate([offsets, can["asesor_id"].values.astype(np.uint32)]).tofile(D / "asesores_por_tesis.v1.bin")
    print("asesores", len(cat), "| tesis del atlas con asesor", int((cnt > 0).sum()), "| vínculos", len(can), "| fuera del atlas", int(fuera))


if __name__ == "__main__":
    main()
