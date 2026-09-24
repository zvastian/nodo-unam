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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for cid, g in df.groupby("cluster_id"):
        g = g.sort_values(["orden", "anio"])
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
