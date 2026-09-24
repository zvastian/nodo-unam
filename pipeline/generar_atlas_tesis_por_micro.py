"""Payload del "modo taller" por tema fino (micro-cluster HDBSCAN) para el atlas.

Un JSON por micro-cluster con TODAS sus tesis (no solo las representativas de
`theses_by_micro/`): id, titulo, anio, plantel, programa, nivel y asesores. Lo
consume la v3.1 del prototipo para (a) resaltar en el mapa las tesis del tema al
hacer clic, (b) el listado A->Z del panel y (c) el modo taller (stats, vista
analitica, red de asesores). Ver development.md, "v3.1.0".

PRIVACIDAD (hallazgo 2026-09-23): `titulo_original` de data_unam.parquet incluye
la mencion de responsabilidad del catalogo (" / tesis que para obtener el titulo
de ..., presenta NOMBRE DEL AUTOR ; asesor ...") en el 92% de las filas. Aqui el
titulo se corta en la mencion de responsabilidad (RESP_RE) y lo que aun parezca
autor se omite (AUTOR_RE) -- nunca se escribe el nombre del autor. El
asesor si se incluye (dato academico publico, decision ya tomada en el Paso 6).

Uso: python pipeline/generar_atlas_tesis_por_micro.py
Salida: atlas_data/tesis_por_micro/{cluster_id}.json (+ copia opcional con COPY_TO)
"""
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

import pandas as pd

DATA_PATH = Path(os.getenv("DATA_PATH", "data/public/data_unam.parquet"))
JERARQUIA_TESIS = Path(os.getenv("JERARQUIA_TESIS", "data/clustering/tesis_macro_meso.parquet"))
OUT_DIR = Path(os.getenv("OUT_DIR", "atlas_data/tesis_por_micro"))
COPY_TO = os.getenv("COPY_TO", "prototypes/atlas_vecindario_mvp/data/tesis_por_micro")


# Mencion de responsabilidad: " / ...", "/ tesis ...", o sin barra "... tesis que para
# obtener/optar ... presenta NOMBRE". Variantes reales del corpus (1,055 filas no traen
# " / " con espacios). Se corta en la PRIMERA de estas marcas.
RESP_RE = re.compile(
    r"\s/\s|\s*/\s*(?=(tesis|tesina|informe|reporte|trabajo|memoria|ensayo)\b)"
    r"|\s+(tesis|tesina|informe|reporte|trabajo|memoria|ensayo)[\w\s,()]{0,60}?\s+que\s+para\s+(obtener|optar)",
    re.IGNORECASE,
)
AUTOR_RE = re.compile(r"\bpresentan?\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ]|que\s+para\s+(obtener|optar)")


def titulo_sin_autor(t: str) -> str:
    """Corta la mencion de responsabilidad (MARC 245 $c) -- nunca debe quedar el autor."""
    t = t or ""
    m = RESP_RE.search(t)
    if m:
        t = t[: m.start()]
    return t.strip().rstrip(" :;,./").strip()


def clave_orden(t: str) -> str:
    s = unicodedata.normalize("NFD", t.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c for c in s if c.isalnum() or c == " ").strip()


VECINDARIO_PATH = Path(os.getenv("VECINDARIO_PATH", "data/vecindario/tesis_vecindario_top100.parquet"))
EDGES_K = int(os.getenv("EDGES_K", "3"))


def aristas_intra_tema(tm: pd.DataFrame) -> dict:
    """Enlaces REALES entre tesis del mismo tema fino, para el estado "ecosistema" del
    modo aislado: de los 100 vecinos e5 de cada tesis (tesis_vecindario_top100, FAISS
    exacto, ADR-0014) se conservan los que caen en su mismo micro-cluster, hasta
    EDGES_K por tesis (ya vienen ordenados por similitud), sin duplicar a-b / b-a.
    Devuelve {cluster_id: [(thesis_a, thesis_b, sim), ...]}. Ids como enteros para no
    materializar 20M strings en Python."""
    import numpy as np
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    to_int = lambda arr: pc.cast(pc.utf8_slice_codeunits(arr, 3), "int32")  # 'TH_0000123' -> 123
    t = pq.read_table(VECINDARIO_PATH)
    src = to_int(t["thesis_id"]).to_numpy()
    lens = pc.list_value_length(t["neighbor_ids"]).to_numpy()
    nb = to_int(pc.list_flatten(t["neighbor_ids"])).to_numpy()
    sim = pc.list_flatten(t["neighbor_similarities"]).to_numpy()
    src_rep = np.repeat(src, lens)
    rank = np.concatenate([np.arange(k) for k in lens])

    cl = np.full(int(max(src.max(), nb.max())) + 1, -1, dtype=np.int32)
    tm_int = tm["thesis_id"].str.slice(3).astype(int).to_numpy()
    cl[tm_int] = tm["cluster_id"].to_numpy()
    keep = (cl[src_rep] >= 0) & (cl[src_rep] == cl[nb]) & (src_rep != nb)
    src_rep, nb, sim, rank = src_rep[keep], nb[keep], sim[keep], rank[keep]
    # top-EDGES_K por tesis de origen (los vecinos ya vienen en orden de similitud)
    order = np.lexsort((rank, src_rep))
    src_rep, nb, sim = src_rep[order], nb[order], sim[order]
    first = np.r_[True, src_rep[1:] != src_rep[:-1]]
    pos = np.arange(len(src_rep)) - np.maximum.accumulate(np.where(first, np.arange(len(src_rep)), 0))
    top = pos < EDGES_K
    a, b, s = src_rep[top], nb[top], sim[top]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    df = pd.DataFrame({"a": lo, "b": hi, "s": s, "c": cl[lo]}).groupby(["a", "b", "c"], as_index=False)["s"].max()
    out = {}
    for c, g in df.groupby("c"):
        out[int(c)] = list(zip(g["a"].tolist(), g["b"].tolist(), g["s"].round(3).tolist()))
    print(f"aristas intra-tema: {len(df):,} en {len(out)} temas (k={EDGES_K})")
    return out


def main():
    tm = pd.read_parquet(JERARQUIA_TESIS, columns=["thesis_id", "cluster_id", "macro_id", "meso_id"])
    d = pd.read_parquet(DATA_PATH, columns=["thesis_id", "anio", "titulo_original", "plantel", "programa", "nivel", "asesores"])
    df = tm.merge(d, on="thesis_id", how="left", validate="one_to_one")
    assert len(df) == len(tm), "merge perdio filas"

    df["titulo"] = df["titulo_original"].fillna("").map(titulo_sin_autor)
    # Red de seguridad: si tras el corte aun parece haber autor, se omite ESE titulo
    # (mejor "no disponible" que filtrar un nombre) y se reporta cuantos.
    fugas = df["titulo"].map(lambda t: bool(AUTOR_RE.search(t)))
    print(f"titulos con posible autor tras el corte: {int(fugas.sum())}")
    for t in df.loc[fugas, "titulo"].head(5):
        print("   ", t[-140:])
    df.loc[fugas, "titulo"] = "(título no disponible)"
    # el catalogo trae variantes de mayusculas y acento ("licenciatura", "Maestria")
    NIVEL_CANON = {"licenciatura": "Licenciatura", "especialidad": "Especialidad", "maestria": "Maestría",
                   "maestría": "Maestría", "doctorado": "Doctorado"}
    df["nivel"] = df["nivel"].fillna("").str.strip().map(lambda v: NIVEL_CANON.get(v.lower(), v.capitalize()))
    df["asesores_l"] = df["asesores"].fillna("").map(lambda s: [a.strip() for a in s.split("|") if a.strip()])
    df["orden"] = df["titulo"].map(clave_orden)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")

    aristas = aristas_intra_tema(tm) if VECINDARIO_PATH.exists() else {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for cid, g in df.groupby("cluster_id"):
        g = g.sort_values(["orden", "anio"])
        pos = {int(t[3:]): k for k, t in enumerate(g["thesis_id"])}
        edges = [[pos[x], pos[y], round(float(s), 3)] for x, y, s in aristas.get(int(cid), []) if x in pos and y in pos]
        rows = [
            [r.thesis_id, r.titulo, None if pd.isna(r.anio) else int(r.anio), r.plantel or "", r.programa or "",
             r.nivel, r.asesores_l]
            for r in g.itertuples()
        ]
        payload = {
            "version": "atlas-tesis-por-micro-v1",
            "clusterId": int(cid),
            "macroId": int(g["macro_id"].iloc[0]),
            "mesoId": int(g["meso_id"].iloc[0]),
            "n": len(rows),
            "fields": ["thesisId", "titulo", "anio", "plantel", "programa", "nivel", "asesores"],
            "note": "titulo sin mencion de responsabilidad (sin autor); orden alfabetico sin acentos",
            "rows": rows,
            # [fila_a, fila_b, similitud coseno e5] -- vecinas reales dentro del tema
            "edges": edges,
        }
        p = OUT_DIR / f"{int(cid)}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        total_bytes += p.stat().st_size

    n_files = df["cluster_id"].nunique()
    print(f"{n_files} archivos, {len(df):,} tesis, {total_bytes / 1e6:.1f} MB en {OUT_DIR}")
    if COPY_TO:
        dst = Path(COPY_TO)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(OUT_DIR, dst)
        print(f"copiado a {dst}")


if __name__ == "__main__":
    main()
