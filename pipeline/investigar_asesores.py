"""Busca fallos de la unificación de asesores: pares de asesores DISTINTOS tras
unificar_asesores.py que probablemente son la misma persona (o fusiones dudosas).

Lee data/asesores/asesores_variantes.v1.parquet y reporta, por tipo de fallo, cuántos
pares hay, cuántos comparten programa (evidencia de misma persona) y ejemplos.

Uso: python pipeline/investigar_asesores.py [--ejemplos N]
"""
import collections
import itertools
import re
import sys
from pathlib import Path

import pandas as pd

V = Path("data/asesores/asesores_variantes.v1.parquet")
PART = {"de", "del", "la", "las", "los", "y", "e", "da", "di", "van", "von"}


def lev(a, b, tope=2):
    if abs(len(a) - len(b)) > tope: return tope + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > tope: return tope + 1
        prev = cur
    return prev[-1]


def main(nej):
    v = pd.read_parquet(V)
    g = v.groupby("asesor_id").agg(n=("n", "sum"), aps=("ap", lambda s: set(x for x in s if x)), nos=("no", lambda s: set(x for x in s if x)),
                                    bolsas=("bolsa", set), progs=("programas", lambda s: set(p for x in s for p in x.split("|") if p)),
                                    nombre=("display", lambda s: s.iloc[0]), tecs=("tecnico", list)).reset_index()
    G = g.set_index("asesor_id")
    pares = collections.defaultdict(set)

    def add(tipo, a, b):
        if a != b: pares[tipo].add((min(a, b), max(a, b)))

    # índices por grupo
    por_ap = collections.defaultdict(set); por_no = collections.defaultdict(set); por_bolsa = collections.defaultdict(set)
    por_ap_sinpart = collections.defaultdict(set)
    for aid, aps, nos, bolsas in zip(g["asesor_id"], g["aps"], g["nos"], g["bolsas"]):
        for ap in aps:
            por_ap[ap].add(aid)
            por_ap_sinpart[" ".join(t for t in ap.replace("'", "").split() if t not in PART)].add(aid)
        for no in nos: por_no[no].add(aid)
        for b in bolsas: por_bolsa[b].add(aid)

    # A/B: mismos apellidos; nombres con el mismo conjunto en otro orden, o subconjunto en otro orden
    for ap, ids in por_ap.items():
        ids = list(ids)
        if len(ids) < 2 or len(ids) > 60: continue
        for a, b in itertools.combinations(ids, 2):
            for na in G.at[a, "nos"]:
                for nb in G.at[b, "nos"]:
                    if not na or not nb: continue
                    sa, sb = na.split(), nb.split()
                    if sorted(sa) == sorted(sb) and sa != sb: add("A orden de nombres", a, b)
                    elif set(sa) < set(sb) or set(sb) < set(sa):
                        corto, largo = (sa, sb) if len(sa) < len(sb) else (sb, sa)
                        # en orden ya lo cubre R3; aquí solo lo desordenado
                        it = iter(largo)
                        if not all(t in it for t in corto): add("B subconjunto en otro orden", a, b)
                    elif lev(na, nb) <= 2 and len(na) >= 6: add("F dedo en nombre (ambos frecuentes)", a, b)
    # C/D: misma bolsa de palabras, distinto reparto apellido/nombre, o apellidos invertidos
    for b, ids in por_bolsa.items():
        ids = list(ids)
        if len(ids) < 2: continue
        for a, c in itertools.combinations(ids, 2):
            inv = any(ap1.split() == ap2.split()[::-1] and len(ap1.split()) == 2 for ap1 in G.at[a, "aps"] for ap2 in G.at[c, "aps"])
            add("D apellidos invertidos" if inv else "C frontera apellido/nombre", a, c)
    # E: mismos nombres, apellidos a distancia <= 2
    for no, ids in por_no.items():
        ids = list(ids)
        if len(ids) < 2 or len(ids) > 400: continue
        for a, c in itertools.combinations(ids, 2):
            if any(lev(x, y) <= 2 and min(len(x), len(y)) >= 8 for x in G.at[a, "aps"] for y in G.at[c, "aps"]):
                add("E dedo en apellido (ambos frecuentes)", a, c)
    # G: iguales si se quitan partículas (de, del, la, y) y apóstrofos
    for ap, ids in por_ap_sinpart.items():
        ids = list(ids)
        if len(ids) < 2 or len(ids) > 60: continue
        for a, c in itertools.combinations(ids, 2):
            if G.at[a, "nos"] & G.at[c, "nos"] and not (G.at[a, "aps"] & G.at[c, "aps"]): add("G partículas o apóstrofos", a, c)

    # H: residuos en nombres (títulos, grados) y I: caracteres raros
    tok_no = collections.Counter(t for no in v["no"] for t in no.split())
    raros = [t for t, c in tok_no.most_common() if len(t) <= 3 and t not in PART and c >= 5 and t not in {"ma", "jose", "ana", "eva", "luz", "pia", "ali", "rey", "ian", "leo", "noe", "ada", "ivo", "ely", "ciro"}][:40]
    moji = v[v["tecnico"].str.contains(r"[ÃÂ�\?\d@#\*_]", regex=True)]

    print("asesores", len(g))
    for tipo in sorted(pares):
        ps = sorted(pares[tipo], key=lambda p: -(G.at[p[0], "n"] + G.at[p[1], "n"]))
        comp = [p for p in ps if G.at[p[0], "progs"] & G.at[p[1], "progs"]]
        print(f"\n=== {tipo}: {len(ps)} pares, {len(comp)} comparten programa")
        for a, b in ps[:nej]:
            print(f"   {'✓' if G.at[a, 'progs'] & G.at[b, 'progs'] else '·'} {G.at[a, 'tecs'][0]} ({G.at[a, 'n']})  <>  {G.at[b, 'tecs'][0]} ({G.at[b, 'n']})")
    print("\n=== H tokens cortos frecuentes en nombres (¿residuos?):", raros)
    print("\n=== I caracteres raros:", len(moji), moji["tecnico"].head(12).tolist())


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--ejemplos") + 1]) if "--ejemplos" in sys.argv else 10)
