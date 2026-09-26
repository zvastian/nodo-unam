"""Contexto de datos del Laboratorio (sin IA), portado de pipeline/lab_contexto.py.

Misma salida que el script offline (la plantilla del Lab la lee tal cual), pero sobre los
artefactos de construir.py: índice FAISS SQ8 en vez de la matriz float32 completa, y
metadatos y estadísticas precalculadas en vez de leer los parquets en cada consulta.
Las similitudes que devuelve el índice son aproximadas (SQ8): difieren en milésimas de las
del producto interno exacto.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

K = 100          # vecinas que se leen
K_VOTO = 50      # vecinas que votan la ubicación
# Umbrales de similitud coseno e5 (título contra título, prefijo "query: "): se
# calibran con el conjunto de evaluación; por ahora, orientativos.
SIM_CERCANA = 0.86
SIM_LEJANA = 0.80
CAMPOS_VECINAS = ["thesis_id", "titulo", "anio", "area", "nivel", "programa", "plantel", "campo", "tema", "subtema", "sim"]


def normalizar(t):
    """Igual que `titulo` de data_unam: minúsculas, sin acentos ni puntuación."""
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def texto_consulta(entrada):
    partes = [entrada.get("title", ""), entrada.get("problematiza", "")]
    partes += entrada.get("keywords", [])
    return "query: " + normalizar(" ".join(p for p in partes if p))


def _o_none(v):
    return None if v < 0 else int(v)


class Datos:
    """Todo lo que no depende de la consulta; se carga una vez al arrancar."""

    def __init__(self, carpeta: Path, nprobe: int = 768):
        self.indice = faiss.read_index(str(carpeta / "indice_ivf_sq8.faiss"))
        self.indice.nprobe = nprobe
        m = pd.read_parquet(carpeta / "meta.parquet")
        self.ids = m["thesis_id"].to_numpy()
        self.titulo = m["titulo"].to_numpy()
        self.anio = m["anio"].to_numpy()
        self.area = m["area"].to_numpy()
        self.nivel = m["nivel"].to_numpy()
        self.programa = m["programa"].to_numpy()
        self.plantel = m["plantel"].to_numpy()
        self.asesores = m["asesores"].to_numpy()
        self.x, self.y = m["x"].to_numpy(), m["y"].to_numpy()
        self.micro, self.meso, self.macro = m["micro"].to_numpy(), m["meso"].to_numpy(), m["macro"].to_numpy()
        pre = json.loads((carpeta / "precalculo.json").read_text(encoding="utf8"))
        self.nombres = {k: {int(i): n for i, n in v.items()} for k, v in pre["nombres"].items()}
        self.corpus_dec = {int(k): v for k, v in pre["corpus_decadas"].items()}
        self.subtemas = {int(k): v for k, v in pre["subtemas"].items()}
        self.stats_asesor = pre["asesores"]

    def vecinas(self, q, k=K):
        sims, idx = self.indice.search(q[None, :], k)
        return idx[0], sims[0]


def analizar(datos: Datos, entrada: dict, q: np.ndarray) -> dict:
    D = datos
    idx, sim = D.vecinas(q)

    # --- ubicación: voto ponderado por sim^2 de las vecinas agrupadas ---
    votos = {"macro": Counter(), "meso": Counter(), "micro": Counter()}
    agrupadas = 0
    for i, s in zip(idx[:K_VOTO], sim[:K_VOTO]):
        if D.micro[i] < 0:
            continue
        agrupadas += 1
        w = float(s) ** 2
        votos["micro"][int(D.micro[i])] += w
        votos["meso"][int(D.meso[i])] += w
        votos["macro"][int(D.macro[i])] += w

    def reparto(c, nombresd, top=4):
        tot = sum(c.values()) or 1
        return [{"id": k, "nombre": nombresd.get(k, str(k)), "peso": round(v / tot, 3)} for k, v in c.most_common(top)]

    ubic = {
        "campo": reparto(votos["macro"], D.nombres["campo"]),
        "tema": reparto(votos["meso"], D.nombres["tema"]),
        "subtema": reparto(votos["micro"], D.nombres["subtema"]),
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
    w = sim[:10].astype(np.float64) ** 2
    ubic["posicion"] = {"x": round(float((D.x[idx[:10]] * w).sum() / w.sum()), 4), "y": round(float((D.y[idx[:10]] * w).sum() / w.sum()), 4)}

    # --- saturación ---
    sub = ubic["subtema"][0]["id"] if ubic["subtema"] else None
    st = D.subtemas.get(sub, {"n": 0, "decadas": {}}) if sub is not None else None
    sat = {"subtema_id": sub, "subtema_n": st["n"] if st else 0, "por_decada": []}
    if st:
        for dd in sorted(k for k in D.corpus_dec if k >= 1950):
            n = st["decadas"].get(str(dd), 0)
            sat["por_decada"].append({"decada": dd, "n": n, "por_mil": round(1000 * n / D.corpus_dec[dd], 3)})
    anios_top20 = [int(D.anio[i]) for i in idx[:20] if D.anio[i]]
    sat["mediana_anio_top20"] = int(np.median(anios_top20)) if anios_top20 else None
    sat["ultima_top20"] = max(anios_top20) if anios_top20 else None
    sat["sim_mas_parecida"] = ubic["sim_max"]
    sat["cercanas_sobre_umbral"] = int((sim >= SIM_CERCANA).sum())  # entre las K leídas, como el script offline

    # --- tesis cercanas ---
    tesis = [{
        "thesis_id": D.ids[i], "titulo": D.titulo[i], "anio": int(D.anio[i]) or None,
        "programa": D.programa[i], "nivel": D.nivel[i], "sim": round(float(s), 4),
        "subtema": _o_none(D.micro[i]), "campo": _o_none(D.macro[i]),
        "x": round(float(D.x[i]), 4), "y": round(float(D.y[i]), 4),
    } for i, s in zip(idx[:15], sim[:15])]

    # --- las 100 vecinas, compactas (perfil y línea de tiempo se calculan en la interfaz) ---
    vec = [[D.ids[i], D.titulo[i], int(D.anio[i]) or None, int(D.area[i]), D.nivel[i], D.programa[i], D.plantel[i],
            _o_none(D.macro[i]), _o_none(D.meso[i]), _o_none(D.micro[i]), round(float(s), 4)] for i, s in zip(idx, sim)]
    temas_nombre = {"campo": {k: D.nombres["campo"].get(k) for k in {v[7] for v in vec if v[7] is not None}},
                    "tema": {k: D.nombres["tema"].get(k) for k in {v[8] for v in vec if v[8] is not None}},
                    "subtema": {k: D.nombres["subtema"].get(k) for k in {v[9] for v in vec if v[9] is not None}}}

    # --- asesores (sin IA) ---
    ev = defaultdict(lambda: {"score": 0.0, "tesis": []})
    for i, s in zip(idx, sim):
        for a in D.asesores[i].split("|"):
            a = a.strip()
            if a:
                ev[a]["score"] += float(s) ** 2
                ev[a]["tesis"].append({"thesis_id": D.ids[i], "titulo": D.titulo[i], "anio": int(D.anio[i]), "sim": round(float(s), 4)})
    asesores = []
    for nombre, e in sorted(ev.items(), key=lambda kv: -kv[1]["score"])[:15]:
        a = D.stats_asesor.get(nombre, {})
        asesores.append({
            "nombre": nombre, "en_cercanas": len(e["tesis"]), "total_corpus": a.get("total", 0),
            "ultimo_anio": a.get("ultimo", 0), "puntaje": round(e["score"], 3), "tesis": e["tesis"][:3],
            "por_anio": a.get("por_anio", {}), "plantel": a.get("plantel"), "programa": a.get("programa"), "area": a.get("area", 0),
        })

    # cobertura de cada palabra clave en las vecinas: qué parte del tema tiene antecedentes
    tit_norm = [normalizar(D.titulo[i]) for i in idx]
    sat["cobertura_palabras"] = [
        {"palabra": k, "vecinas_que_la_mencionan": sum(1 for t in tit_norm if re.search(r"\b" + re.escape(normalizar(k)) + r"\b", t)), "de": len(idx)}
        for k in entrada.get("keywords", [])
    ]
    sat["anios_top20"] = anios_top20
    return {"entrada": entrada, "consulta": texto_consulta(entrada), "ubicacion": ubic,
            "saturacion": sat, "tesis_cercanas": tesis, "asesores": asesores,
            "vecinas_campos": CAMPOS_VECINAS, "vecinas": vec, "nombres": temas_nombre}
