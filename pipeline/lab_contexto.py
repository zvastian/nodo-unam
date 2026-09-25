"""Contexto de datos del Laboratorio (sin IA) sobre el atlas nuevo.

Reemplaza la parte de datos de `thesis.py` del Lab viejo (MiniLM sobre una muestra de
50k y clusters viejos). Dado lo que escribe el usuario, calcula:

- ubicación: vecinas e5-large entre las 609,154 tesis, voto por campo, tema y subtema,
  y una confianza que combina concentración del voto y similitud absoluta;
- saturación: tamaño del subtema, tesis por década (y su peso frente al corpus),
  recencia de las antecedentes y distancia a la tesis más parecida;
- tesis cercanas con título legible (sin autor) y posición en el mapa;
- asesores con evidencia: cuántas de las vecinas asesoraron, total en el corpus
  completo (no en una muestra), último año y tesis representativas.

Uso:
    python pipeline/lab_contexto.py entrada.json salida.json
La entrada tiene: title, problematiza, keywords, objectives, program, degree, study_period.
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EMB = ROOT / "data" / "embeddings" / "embeddings_full_e5large.npy"
EMB_META = ROOT / "data" / "embeddings" / "embeddings_meta.parquet"
DATA = ROOT / "data" / "public" / "data_unam.parquet"
LAYOUT = ROOT / "data" / "clustering" / "layout_pacmap2d.parquet"
APP = ROOT / "prototypes" / "atlas_vecindario_mvp" / "data"
MODEL = "intfloat/multilingual-e5-large"

K = 100          # vecinas que se leen
K_VOTO = 50      # vecinas que votan la ubicación
# Umbrales de similitud coseno e5 (título contra título, prefijo "query: "): se
# calibran con el conjunto de evaluación; por ahora, orientativos.
SIM_CERCANA = 0.86
SIM_LEJANA = 0.80


def normalizar(t):
    """Igual que `titulo` de data_unam: minúsculas, sin acentos ni puntuación."""
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def texto_consulta(entrada):
    partes = [entrada.get("title", ""), entrada.get("problematiza", "")]
    partes += entrada.get("keywords", [])
    return "query: " + normalizar(" ".join(p for p in partes if p))


def vecinas(q, k=K):
    X = np.load(EMB, mmap_mode="r")
    sims = np.empty(X.shape[0], dtype=np.float32)
    paso = 50_000
    for i in range(0, X.shape[0], paso):
        sims[i:i + paso] = X[i:i + paso] @ q
    idx = np.argpartition(-sims, k)[:k]
    idx = idx[np.argsort(-sims[idx])]
    return idx, sims[idx], sims


def cargar_micros():
    """thesis_id -> (micro, meso, macro) y filas de cada subtema, desde tesis_por_micro."""
    asignacion, filas = {}, {}
    for f in (APP / "tesis_por_micro").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf8"))
        cid, meso, macro = d["clusterId"], d["mesoId"], d["macroId"]
        filas[cid] = d["rows"]
        for r in d["rows"]:
            asignacion[r[0]] = (cid, meso, macro)
    return asignacion, filas


def nombres():
    mac = json.loads((APP / "macro_nombres.v1.json").read_text(encoding="utf8"))
    macro = {int(k): v["nombre"] for k, v in mac["macros"].items()}
    meso, micro = {}, {}
    for f in (APP / "meso_by_macro").glob("*.json"):
        for n in json.loads(f.read_text(encoding="utf8"))["nodes"]:
            meso[n["clusterId"]] = n.get("name") or n["label"]
    for f in (APP / "micro_by_macro").glob("*.json"):
        for n in json.loads(f.read_text(encoding="utf8"))["nodes"]:
            micro[n["clusterId"]] = n.get("name") or n["label"]
    return macro, meso, micro


def decada(a):
    return int(a) // 10 * 10 if a and a > 1800 else None


def main(entrada_path, salida_path):
    from sentence_transformers import SentenceTransformer

    entrada = json.loads(Path(entrada_path).read_text(encoding="utf8"))
    modelo = SentenceTransformer(MODEL)
    q = modelo.encode(texto_consulta(entrada), normalize_embeddings=True).astype(np.float32)

    meta = pd.read_parquet(EMB_META, columns=["thesis_id"])
    idx, sim, _ = vecinas(q)
    ids = meta["thesis_id"].to_numpy()[idx]

    d = pd.read_parquet(DATA, columns=["thesis_id", "anio", "titulo_legible", "programa", "nivel", "plantel", "area", "asesores"]).set_index("thesis_id")
    lay = pd.read_parquet(LAYOUT).set_index("thesis_id")
    asignacion, filas = cargar_micros()
    n_macro, n_meso, n_micro = nombres()

    # --- ubicación: voto ponderado por sim^2 de las vecinas agrupadas ---
    votos = {"macro": Counter(), "meso": Counter(), "micro": Counter()}
    agrupadas = 0
    for tid, s in zip(ids[:K_VOTO], sim[:K_VOTO]):
        a = asignacion.get(tid)
        if not a:
            continue
        agrupadas += 1
        w = float(s) ** 2
        votos["micro"][a[0]] += w
        votos["meso"][a[1]] += w
        votos["macro"][a[2]] += w

    def reparto(c, nombresd, top=4):
        tot = sum(c.values()) or 1
        return [{"id": k, "nombre": nombresd.get(k, str(k)), "peso": round(v / tot, 3)} for k, v in c.most_common(top)]

    ubic = {
        "campo": reparto(votos["macro"], n_macro),
        "tema": reparto(votos["meso"], n_meso),
        "subtema": reparto(votos["micro"], n_micro),
        "vecinas_agrupadas": agrupadas,
        "vecinas_leidas": K_VOTO,
        "sim_max": round(float(sim[0]), 4),
        "sim_media_top10": round(float(sim[:10].mean()), 4),
    }
    concentracion = ubic["subtema"][0]["peso"] if ubic["subtema"] else 0
    if ubic["sim_media_top10"] < SIM_LEJANA:
        ubic["lectura"] = "sin_antecedentes_cercanos"
    elif concentracion >= 0.6 and ubic["sim_media_top10"] >= SIM_CERCANA:
        ubic["lectura"] = "clara"
    elif concentracion >= 0.35:
        ubic["lectura"] = "entre_temas"
    else:
        ubic["lectura"] = "dispersa"
    # posición en el mapa: media ponderada de las 10 más parecidas
    w = sim[:10] ** 2
    xy = lay.loc[ids[:10], ["x", "y"]].to_numpy()
    ubic["posicion"] = {"x": round(float((xy[:, 0] * w).sum() / w.sum()), 4), "y": round(float((xy[:, 1] * w).sum() / w.sum()), 4)}

    # --- saturación ---
    sub = ubic["subtema"][0]["id"] if ubic["subtema"] else None
    corpus_dec = d["anio"].map(decada).value_counts()
    sat = {"subtema_id": sub, "subtema_n": len(filas.get(sub, [])), "por_decada": []}
    if sub is not None:
        dec_sub = Counter(decada(r[2]) for r in filas[sub])
        for dd in sorted(k for k in corpus_dec.index if k and k >= 1950):
            n = dec_sub.get(dd, 0)
            sat["por_decada"].append({"decada": dd, "n": n, "por_mil": round(1000 * n / corpus_dec[dd], 3)})
    anios_top20 = [int(d.at[t, "anio"]) for t in ids[:20] if t in d.index and d.at[t, "anio"]]
    sat["mediana_anio_top20"] = int(np.median(anios_top20)) if anios_top20 else None
    sat["ultima_top20"] = max(anios_top20) if anios_top20 else None
    sat["sim_mas_parecida"] = ubic["sim_max"]
    sat["cercanas_sobre_umbral"] = int((sim >= SIM_CERCANA).sum())

    # --- tesis cercanas ---
    tesis = []
    for tid, s in zip(ids[:15], sim[:15]):
        r = d.loc[tid]
        a = asignacion.get(tid)
        tesis.append({
            "thesis_id": tid, "titulo": r["titulo_legible"], "anio": int(r["anio"]) if r["anio"] else None,
            "programa": r["programa"], "nivel": (r["nivel"] or "").capitalize(), "sim": round(float(s), 4),
            "subtema": a[0] if a else None, "campo": a[2] if a else None,
            "x": round(float(lay.at[tid, "x"]), 4), "y": round(float(lay.at[tid, "y"]), 4),
        })

    # --- las 100 vecinas, compactas: perfil (áreas, niveles, programas, planteles, campos,
    # temas) y línea de tiempo con títulos, calculados en la interfaz como en el taller ---
    area_cod = {"area 1": 1, "area 2": 2, "area 3": 3, "area 4": 4}
    vec = []
    for tid, s_ in zip(ids, sim):
        r = d.loc[tid]
        a = asignacion.get(tid)
        vec.append([tid, r["titulo_legible"], int(r["anio"]) if r["anio"] else None, area_cod.get(str(r["area"]).lower(), 0),
                    (r["nivel"] or "").capitalize(), r["programa"], r["plantel"],
                    a[2] if a else None, a[1] if a else None, a[0] if a else None, round(float(s_), 4)])
    temas_nombre = {"campo": {k: n_macro.get(k) for k in {v[7] for v in vec if v[7] is not None}},
                    "tema": {k: n_meso.get(k) for k in {v[8] for v in vec if v[8] is not None}},
                    "subtema": {k: n_micro.get(k) for k in {v[9] for v in vec if v[9] is not None}}}

    # --- asesores (sin IA) ---
    todos = d["asesores"].fillna("")
    total_corpus = Counter(a for s in todos for a in s.split("|") if a.strip())
    ultimo = defaultdict(int)
    por_anio = defaultdict(Counter)
    plantel_de, programa_de, area_de = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for s, an, pl, pr, ar in zip(todos, d["anio"].fillna(0), d["plantel"].fillna(""), d["programa"].fillna(""), d["area"].fillna("")):
        for a in s.split("|"):
            if a.strip():
                ultimo[a] = max(ultimo[a], int(an))
                por_anio[a][int(an)] += 1
                if pl: plantel_de[a][pl] += 1
                if pr: programa_de[a][pr] += 1
                area_de[a][area_cod.get(str(ar).lower(), 0)] += 1
    ev = defaultdict(lambda: {"score": 0.0, "tesis": []})
    for tid, s in zip(ids, sim):
        for a in (d.at[tid, "asesores"] or "").split("|"):
            a = a.strip()
            if a:
                ev[a]["score"] += float(s) ** 2
                ev[a]["tesis"].append({"thesis_id": tid, "titulo": d.at[tid, "titulo_legible"], "anio": int(d.at[tid, "anio"]), "sim": round(float(s), 4)})
    asesores = []
    for nombre, e in sorted(ev.items(), key=lambda kv: -kv[1]["score"])[:15]:
        asesores.append({
            "nombre": nombre, "en_cercanas": len(e["tesis"]), "total_corpus": total_corpus[nombre],
            "ultimo_anio": ultimo[nombre], "puntaje": round(e["score"], 3), "tesis": e["tesis"][:3],
            "por_anio": {str(k): v for k, v in sorted(por_anio[nombre].items()) if k > 1900},
            "plantel": plantel_de[nombre].most_common(1)[0][0] if plantel_de[nombre] else None,
            "programa": programa_de[nombre].most_common(1)[0][0] if programa_de[nombre] else None,
            "area": area_de[nombre].most_common(1)[0][0] if area_de[nombre] else 0,
        })

    # cobertura de cada palabra clave en las vecinas: qué parte del tema tiene
    # antecedentes y cuál es la novedosa
    tit_norm = [normalizar(d.at[t, "titulo_legible"]) if t in d.index else "" for t in ids]
    sat["cobertura_palabras"] = [
        {"palabra": k, "vecinas_que_la_mencionan": sum(1 for t in tit_norm if re.search(r"\b" + re.escape(normalizar(k)) + r"\b", t)), "de": len(ids)}
        for k in entrada.get("keywords", [])
    ]
    # años de las 20 más parecidas (tira de recencia)
    sat["anios_top20"] = anios_top20
    out = {"entrada": entrada, "consulta": texto_consulta(entrada), "ubicacion": ubic,
           "saturacion": sat, "tesis_cercanas": tesis, "asesores": asesores,
           "vecinas_campos": ["thesis_id", "titulo", "anio", "area", "nivel", "programa", "plantel", "campo", "tema", "subtema", "sim"],
           "vecinas": vec, "nombres": temas_nombre}
    Path(salida_path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
    print(json.dumps({k: out[k] for k in ("ubicacion", "saturacion")}, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
