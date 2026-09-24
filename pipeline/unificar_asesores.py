"""Unificación de asesores (entity resolution) sobre el catálogo completo.

Entrada: data/clean/base7_kaggle_clean.parquet, columna `asesores_limpios_v2`
("Apellidos, Nombres | Apellidos, Nombres"; ADR-0010). Solo se leen columnas de asesor.

Idea: fusionar a dos personas distintas es peor que dejar dos variantes sin unir
(atribuiría tesis a quien no las dirigió). Por eso las reglas van de la más segura a la
menos, y la regla difusa exige que el candidato sea ÚNICO y que compartan contexto.

Reglas (en orden):
  R1  misma clave normalizada: sin acentos, minúsculas, sin títulos (Dr., Lic...),
      «Ma.» = María, iniciales expandidas con su paréntesis («David U. (David Uriel)»).
  R2  mismo conjunto de palabras en otro orden (registros sin coma, «Tenorio Guajardo
      Guadalupe» = «Guadalupe Tenorio Guajardo»), si el conjunto es único.
  R3  mismos apellidos y nombre de pila compatible: uno es la versión corta del otro
      («Rafael» ⊂ «Filiberto Rafael», «J. Antonio» ~ «José Antonio»), solo si dentro de
      esos apellidos hay UNA sola forma completa compatible (si «María» podría ser
      «María Elena» o «María Luisa», no se toca).
  R5  error de dedo: variante rara a distancia de edición <= 2 de una forma >= 3 veces más
      frecuente, candidato único y programa en común.
  R6-R10 (fase 2, grupo contra grupo): nombres de pila en otro orden y partículas (R6),
      coma mal puesta (R8), apellidos invertidos raros (R9), errores de dedo incluida la
      primera letra (R10), misma pronunciación en español (R11). Ver
      pipeline/investigar_asesores.py.
  R4  un solo apellido registrado («Witker, Jorge») frente a dos («Witker Velásquez,
      Jorge»): mismo primer apellido y nombre compatible, candidato único y al menos un
      programa en común.

Salidas:
  data/asesores/asesores_canon.v1.parquet   (thesis_id, orden, asesor_id)  -- local, no versionado
  data/asesores/asesores_catalogo.v1.parquet (asesor_id, nombre, n_tesis, variantes, ...)
  pipeline/audits/asesores_unificacion_v1.csv (cada variante fusionada, con su regla)

Uso: python pipeline/unificar_asesores.py
"""
import collections
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd

# Reproducibilidad: el orden de iteración de conjuntos de tuplas de texto depende de la
# semilla de hash de Python, y ese orden cambia algunas uniones (se encontró «Siivia /
# Silvia Tejada Castañeda» unido en una corrida y no en otra). Se fija la semilla.
if os.environ.get("PYTHONHASHSEED") != "0":
    import subprocess
    import sys
    sys.exit(subprocess.call([sys.executable] + sys.argv, env={**os.environ, "PYTHONHASHSEED": "0"}))

SRC = Path(os.getenv("BASE7", "data/clean/base7_kaggle_clean.parquet"))
OUT = Path("data/asesores")
AUDIT = Path("pipeline/audits/asesores_unificacion_v1.csv")

TITULOS = re.compile(r"(?i)\b(dr|dra|mtro|mtra|mto|lic|licda|ing|arq|mc|m\.c|c\.p|q\.f\.b|biol|psic|prof|profa)\.?(?=\s|,|$)")
PAREN = re.compile(r"^(?P<ini>.*?)\s*\((?P<full>[^)]+)\)\s*$")


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


ABREV = {"ma": "maria", "fco": "francisco", "gpe": "guadalupe", "jse": "jose"}
PARTICULAS = {"de", "del", "la", "las", "los", "y", "e"}


def arreglar_mojibake(s):
    """«NuÃ±ez» -> «Nuñez» (UTF-8 leído como Latin-1)."""
    if "Ã" in s or "Â" in s:
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def tokens(s):
    s = sin_acentos(arreglar_mojibake(s).lower())
    s = re.sub("[`'\u2019\u00b4]", "", s)  # D’Hoyos = D'Hoyos = DHoyos
    s = re.sub(r"\bj\.?\s+(?=[a-z])", "j ", s)
    return [ABREV.get(t, t) for t in re.split(r"[^a-z]+", s) if t]


def partir(raw):
    """-> (apellidos_tokens, nombres_tokens) o None si no hay coma."""
    raw = TITULOS.sub(" ", raw).strip(" ,")
    if "," not in raw:
        return None
    ap, no = raw.split(",", 1)
    m = PAREN.match(no.strip())
    if m:  # «David U. (David Uriel)» -> usa la forma expandida
        no = m.group("full")
    return tokens(ap), tokens(no)


def compatible(corto, largo):
    """Nombre de pila corto compatible con el largo: cada token del corto es igual a un token
    del largo o es su inicial, en el mismo orden relativo."""
    i = 0
    for t in corto:
        while i < len(largo) and not (largo[i] == t or (len(t) == 1 and largo[i].startswith(t))):
            i += 1
        if i == len(largo):
            return False
        i += 1
    return True


def main():
    d = pd.read_parquet(SRC, columns=["thesis_id", "asesores_limpios_v2", "asesores_display", "programa"])
    d = d[d["asesores_limpios_v2"].fillna("").str.strip() != ""]
    tec = d["asesores_limpios_v2"].str.split(r"\s*\|\s*")
    dis = d["asesores_display"].fillna("").str.split(r"\s*\|\s*")
    filas = []
    for tid, prog, ts, ds in zip(d["thesis_id"], d["programa"], tec, dis):
        for k, t in enumerate(ts):
            t = t.strip()
            if not t:
                continue
            filas.append((tid, k, t, ds[k].strip() if k < len(ds) and len(ds) == len(ts) else t, prog))
    m = pd.DataFrame(filas, columns=["thesis_id", "orden", "tecnico", "display", "programa"])
    print("menciones", len(m), "variantes", m["tecnico"].nunique())

    # --- R1: clave normalizada ---
    var = m.groupby("tecnico").agg(n=("thesis_id", "size"), display=("display", lambda s: s.mode().iat[0]),
                                   programas=("programa", lambda s: set(s.dropna()))).reset_index()
    ap_no = var["tecnico"].map(partir)
    var["ap"] = ap_no.map(lambda x: tuple(x[0]) if x else None)
    var["no"] = ap_no.map(lambda x: tuple(x[1]) if x else None)
    var["bolsa"] = var["tecnico"].map(lambda s: tuple(sorted(tokens(TITULOS.sub(" ", s)))))
    var["clave"] = [("C", a, n) if a is not None else ("S",) + b for a, n, b in zip(var["ap"], var["no"], var["bolsa"])]
    var = var[var["bolsa"].map(len) >= 2]  # descarta basura de una sola palabra («E»)

    parent = {}
    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra
    regla = {}

    for c in var["clave"]: find(c)

    # --- R2: misma bolsa de palabras en otro orden ---
    # Apellidos invertidos («Martínez García» / «García Martínez») suelen ser personas
    # DISTINTAS en México. Solo se unen: (a) registros sin coma (orden no parseable) con su
    # única forma con coma, o (b) una inversión rara (n <= 2, la otra >= 5 veces más
    # frecuente) que además comparte programa: típico error de captura.
    progs = dict(zip(var["clave"], var["programas"]))
    nvar = dict(zip(var["clave"], var["n"]))
    por_bolsa = collections.defaultdict(set)
    for c, b in zip(var["clave"], var["bolsa"]): por_bolsa[b].add(c)
    for b, cs in por_bolsa.items():
        if len(cs) < 2: continue
        con = sorted((c for c in cs if c[0] == "C"), key=lambda c: -nvar[c])
        sin = [c for c in cs if c[0] == "S"]
        if len(con) == 1:
            for c in sin: union(con[0], c); regla[c] = "R2"
        elif len(con) > 1:
            top = con[0]
            for c in con[1:]:
                if nvar[c] <= 2 and nvar[top] >= 5 * nvar[c] and progs.get(c, set()) & progs.get(top, set()):
                    union(top, c); regla[c] = "R2"

    # --- R3: mismos apellidos, nombre corto compatible con UNA sola forma larga ---
    por_ap = collections.defaultdict(set)
    for c in var["clave"]:
        if c[0] == "C" and len(c[1]) >= 2: por_ap[c[1]].add(c)
    for ap, cs in por_ap.items():
        if len(cs) < 2: continue
        cs = list(cs)
        for c in cs:
            largos = [o for o in cs if o is not c and len(o[2]) > len(c[2]) and compatible(c[2], o[2])]
            # «largos» debe ser una cadena (todas compatibles entre sí): si hay dos ramas, es ambiguo
            maximos = [o for o in largos if not any(p is not o and len(p[2]) > len(o[2]) and compatible(o[2], p[2]) for p in largos)]
            # «Edgar A» y «Edgar Abraham» no son dos ramas: son la misma forma con y sin
            # inicial. Si todos los máximos son compatibles entre sí, queda el más escrito.
            if len(maximos) > 1 and all(compatible(a[2], b[2]) or compatible(b[2], a[2]) for a in maximos for b in maximos):
                maximos = [max(maximos, key=lambda o: (len(" ".join(o[2])), nvar[o]))]
            # un solo nombre de pila («García Benítez, Carlos») puede ser otra persona con
            # apellidos comunes: además se exige un programa en común
            ok_ctx = len(c[2]) > 1 or bool(progs.get(c, set()) & progs.get(maximos[0], set())) if len(maximos) == 1 else False
            if len(maximos) == 1 and c[2] and ok_ctx:
                union(maximos[0], c); regla[c] = "R3"
            # iniciales al mismo largo: «j antonio» ~ «jose antonio»
            iguales = [o for o in cs if o is not c and len(o[2]) == len(c[2]) and o[2] != c[2] and compatible(c[2], o[2])]
            if len(iguales) == 1 and any(len(t) == 1 for t in c[2]):
                union(iguales[0], c); regla[c] = "R3"

    # --- R4: un apellido vs dos, candidato único y programa en común ---
    por_primero = collections.defaultdict(list)
    for c in var["clave"]:
        if c[0] == "C" and c[1]: por_primero[(c[1][0],)].append(c)
    for c in var["clave"]:
        if c[0] != "C" or len(c[1]) != 1: continue
        # solo en un sentido: el nombre del registro con un apellido cabe en el del candidato.
        # Al revés («Juan» del candidato dentro de «Juan Manuel») encadenaba a otra persona:
        # «Sánchez, Juan Manuel» terminaba en «Juan José Sánchez Sosa».
        cands = [o for o in por_primero[(c[1][0],)] if len(o[1]) >= 2 and (o[2] == c[2] or compatible(c[2], o[2]))]
        cands = [o for o in cands if progs.get(o, set()) & progs.get(c, set())]
        if len({find(o) for o in cands}) == 1 and cands:
            union(cands[0], c); regla[c] = "R4"

    # --- R5: errores de dedo («Federicio» / «Federico», «Rancel» / «Rangel») ---
    # Variante rara (n <= 2) a distancia de edición <= 2 (<= 1 si la parte es corta) de una
    # forma al menos 3 veces más frecuente, con candidato único y programa en común.
    # Bloques: mismos apellidos (dedo en el nombre) o mismo nombre y misma inicial de
    # apellido (dedo en el apellido).
    def lev(a, b, tope):
        if abs(len(a) - len(b)) > tope: return tope + 1
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i] + [0] * len(b)
            for j, cb in enumerate(b, 1):
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if min(cur) > tope: return tope + 1
            prev = cur
        return prev[-1]
    con = [c for c in var["clave"] if c[0] == "C" and c[1] and c[2]]
    bloqA, bloqB = collections.defaultdict(list), collections.defaultdict(list)
    for c in con:
        bloqA[c[1]].append(c); bloqB[(c[2], c[1][0][0])].append(c)
    for c in con:
        if nvar[c] > 2: continue
        cands = set()
        for o in bloqA[c[1]]:
            a, b = " ".join(c[2]), " ".join(o[2])
            if o != c and lev(a, b, 2 if len(a) >= 8 else 1) <= (2 if len(a) >= 8 else 1): cands.add(o)
        for o in bloqB[(c[2], c[1][0][0])]:
            a, b = " ".join(c[1]), " ".join(o[1])
            if o != c and lev(a, b, 2 if len(a) >= 8 else 1) <= (2 if len(a) >= 8 else 1): cands.add(o)
        cands = [o for o in cands if nvar[o] >= 3 * nvar[c] and progs.get(o, set()) & progs.get(c, set())]
        if len({find(o) for o in cands}) == 1 and cands and find(cands[0]) != find(c):
            union(cands[0], c); regla[c] = "R5"

    # =================== FASE 2: grupo contra grupo (2026-09-24) ===================
    # pipeline/investigar_asesores.py encontró fallos que las reglas por variante no ven:
    # nombres de pila en otro orden, coma mal puesta, partículas («Carmona y Pardo»),
    # inversiones y errores de dedo comparados contra una variante chica en vez de contra
    # la persona entera, y errores en la primera letra («Juárez/Suarez»). Aquí se compara
    # cada grupo ya formado con los demás. Todas las reglas exigen programa en común y
    # candidato único.
    def sin_part(t):
        return tuple(x for x in t if x not in PARTICULAS)
    freq_tok = collections.Counter(t for c in var["clave"] for t in (c[1] + c[2] if c[0] == "C" else c[1:]))

    def grupos_actuales():
        gs = collections.defaultdict(lambda: {"n": 0, "progs": set(), "formas": set(), "bolsas": set(), "claves": []})
        for c, n_, pr in zip(var["clave"], var["n"], var["programas"]):
            g = gs[find(c)]; g["n"] += n_; g["progs"] |= pr; g["claves"].append(c)
            if c[0] == "C": g["formas"].add((sin_part(c[1]), sin_part(c[2])))
            g["bolsas"].add(tuple(sorted(sin_part(c[1:] if c[0] == "S" else c[1] + c[2]))))
        return gs

    def nombre_max(g):
        nos = [no for ap, no in g["formas"] if no]
        return max(nos, key=len) if nos else ()

    def nombres_compatibles(a, b):
        """Cada palabra del nombre más corto aparece en el largo (igual, como inicial o con
        un error de una letra), sin importar el orden. «Carlos» ~ «Carlos Eduardo», pero
        «Carlos Eduardo» no ~ «Carlos Raymundo»: evita que un grupo con la forma corta
        junte a dos personas distintas."""
        corto, largo = (a, b) if len(a) <= len(b) else (b, a)
        libres = list(largo)
        for t in corto:
            m = next((x for x in libres if x == t or (len(t) == 1 and x.startswith(t)) or (len(x) == 1 and t.startswith(x))
                      or (min(len(t), len(x)) >= 5 and lev(t, x, 1) <= 1)), None)
            if m is None:
                return False
            libres.remove(m)
        return True

    def unir_si_unico(c, cands, gs, etiqueta, revisar_nombres=True, sin_programa=()):
        # sin_programa: candidatos con evidencia de nombre tan fuerte que no se exige programa
        cands = {x for x in cands if x != c and (x in sin_programa or gs[x]["progs"] & gs[c]["progs"])}
        if revisar_nombres:
            cands = {x for x in cands if nombres_compatibles(nombre_max(gs[x]), nombre_max(gs[c]))}
        if not cands:
            return False
        if len(cands) > 1:
            # varios candidatos solo si son la misma persona entre sí («Ricardo», «José
            # Ricardo» y «Ricardo José»): todos compatibles de dos en dos
            if not revisar_nombres: return False
            cs = list(cands)
            if not all(nombres_compatibles(nombre_max(gs[x]), nombre_max(gs[y])) for i, x in enumerate(cs) for y in cs[i + 1:]):
                return False
        for o in sorted(cands, key=lambda x: -gs[x]["n"]):
            c = find(c); o = find(o)
            if c == o: continue
            keep, drop = (o, c) if gs[o]["n"] >= gs[c]["n"] else (c, o)
            union(keep, drop)
            for k in gs[drop]["claves"]:
                if regla.get(k, "R1") == "R1": regla[k] = etiqueta
            # el grupo absorbido ya no es candidato de nadie más en esta pasada
            gs[keep]["n"] += gs[drop]["n"]; gs[keep]["progs"] |= gs[drop]["progs"]
            gs[keep]["formas"] |= gs[drop]["formas"]; gs[keep]["bolsas"] |= gs[drop]["bolsas"]; gs[keep]["claves"] += gs[drop]["claves"]
            c = keep
        return True

    # R6: mismos apellidos (sin partículas) y nombres de pila en otro orden o subconjunto
    # desordenado; por quitar partículas también une «Carmona y Pardo» / «Carmona Pardo»
    gs = grupos_actuales()
    por_ap = collections.defaultdict(set)
    for r, g in gs.items():
        for ap, no in g["formas"]: por_ap[ap].add(r)
    hechos = 0
    for r in sorted(gs, key=lambda x: gs[x]["n"]):
        if find(r) != r: continue
        cands, fuertes = set(), set()
        for ap, no in list(gs[r]["formas"]):
            if not ap or not no: continue
            for o in por_ap[ap]:
                o = find(o)
                if o == r: continue
                for ap2, no2 in gs[o]["formas"]:
                    if ap2 != ap or not no2: continue
                    a, b = set(no), set(no2)
                    if sorted(no) == sorted(no2) or ((a < b or b < a) and max(len(a), len(b)) >= 2):
                        cands.add(o)
                    # mismas >= 4 palabras en otro orden («Irma Zoila» / «Zoila Irma» Tejada
                    # Castañeda, en Nutrición animal y en Veterinaria): la combinación ya es
                    # prácticamente única; basta el nombre, no se exige programa en común
                    if sorted(no) == sorted(no2) and len(ap) + len(no) >= 4:
                        fuertes.add(o)
        if cands and unir_si_unico(r, cands, gs, "R6", sin_programa=fuertes): hechos += 1
    print("R6 orden de nombres y partículas:", hechos)

    # R8: coma mal puesta: misma bolsa de palabras con otro reparto apellido/nombre, que no
    # sea la simple inversión de dos apellidos (esa es R9)
    gs = grupos_actuales()
    por_bolsa = collections.defaultdict(set)
    for r, g in gs.items():
        for b in g["bolsas"]: por_bolsa[b].add(r)

    def invertidos(ga, gb):
        return any(len(a1) == 2 and a1 == a2[::-1] and n1 == n2 for a1, n1 in ga["formas"] for a2, n2 in gb["formas"])
    hechos = 0
    for r in sorted(gs, key=lambda x: gs[x]["n"]):
        if find(r) != r: continue
        cands = {find(o) for b in list(gs[r]["bolsas"]) for o in por_bolsa[b] if find(o) != r}
        cands = {o for o in cands if not invertidos(gs[r], gs[o])}
        # aquí el reparto apellido/nombre es justo lo que está mal: no se comparan nombres
        if cands and unir_si_unico(r, cands, gs, "R8", revisar_nombres=False): hechos += 1
    print("R8 coma mal puesta:", hechos)

    # R9: apellidos invertidos (con o sin un error de dedo), grupo contra grupo: el invertido
    # es raro (el otro tiene >= 10 veces más tesis) y comparten programa
    gs = grupos_actuales()
    por_no = collections.defaultdict(set)
    for r, g in gs.items():
        for ap, no in g["formas"]:
            if len(ap) == 2 and no: por_no[no].add(r)
    hechos = 0
    for r in sorted(gs, key=lambda x: gs[x]["n"]):
        if find(r) != r: continue
        g = gs[r]; cands = set()
        for ap, no in list(g["formas"]):
            if len(ap) != 2: continue
            for o in por_no.get(no, ()):
                o = find(o)
                if o == r or gs[o]["n"] < 10 * g["n"]: continue
                if any(len(a2) == 2 and n2 == no and lev(a2[1], ap[0], 2) <= 1 and lev(a2[0], ap[1], 2) <= 1 for a2, n2 in gs[o]["formas"]):
                    cands.add(o)
        if cands and unir_si_unico(r, cands, gs, "R9"): hechos += 1
    print("R9 apellidos invertidos:", hechos)

    # R10: error de dedo grupo contra grupo, también en la primera letra («Juárez/Suarez»).
    # Bloques: (un apellido, inicial del nombre). Distancia <= 2 en el nombre completo (<= 1
    # si es corto) y el grupo menor tiene <= 1/3 de las tesis del mayor. Salvaguarda: con
    # solo 3 palabras, si las palabras que difieren son nombres/apellidos comunes
    # («Miguel/Manuel»), no es un dedo sino otra persona.
    gs = grupos_actuales()
    bloques = collections.defaultdict(set)
    for r, g in gs.items():
        for ap, no in g["formas"]:
            if len(ap) >= 2 and no:
                bloques[(ap[1], no[0][0])].add(r); bloques[(ap[0], no[0][0])].add(r)

    def comunes(x, y):
        return freq_tok[x] >= 20 and freq_tok[y] >= 20
    hechos = 0
    for r in sorted(gs, key=lambda x: gs[x]["n"]):
        if find(r) != r: continue
        g = gs[r]; cands = set()
        for ap, no in list(g["formas"]):
            if len(ap) < 2 or not no: continue
            full = " ".join(ap + no); tope = 2 if len(full) >= 14 else 1
            for key in ((ap[1], no[0][0]), (ap[0], no[0][0])):
                for o in bloques.get(key, ()):
                    o = find(o)
                    if o == r or o in cands or gs[o]["n"] < 3 * g["n"]: continue
                    for ap2, no2 in gs[o]["formas"]:
                        full2 = " ".join(ap2 + no2)
                        if abs(len(full) - len(full2)) > tope or lev(full, full2, tope) > tope: continue
                        t1, t2 = ap + no, ap2 + no2
                        if len(t1) == len(t2) and len(t1) <= 3:
                            dif = [(x, y) for x, y in zip(t1, t2) if x != y]
                            if dif and all(comunes(x, y) for x, y in dif): continue
                        cands.add(o); break
        if cands and unir_si_unico(r, cands, gs, "R10"): hechos += 1
    print("R10 errores de dedo (grupo):", hechos)

    # R11: misma pronunciación en español (Cortes/Cortez, Yvone/Ivonne, Lizett/Lizzet,
    # Gaussman/Gaussmann, Grynberg/Grinberg, «Rosa Maria»/«Rosamaría»), sin importar cuál es
    # más frecuente. La clave fonética conserva las vocales, así que el género (Francisca /
    # Francisco, Emilia / Emilio) sigue separando personas.
    def fonetica(toks):
        t = "".join(toks)
        t = t.replace("ch", "C").replace("ll", "y").replace("qu", "k").replace("ph", "f")
        t = re.sub(r"c(?=[ei])", "s", t).replace("c", "k").replace("z", "s").replace("v", "b").replace("w", "u").replace("h", "")
        t = t.replace("y", "i")
        return re.sub(r"(.)\1+", r"\1", t)
    gs = grupos_actuales()
    por_fon = collections.defaultdict(set)
    for r, g in gs.items():
        for ap, no in g["formas"]:
            k = fonetica(ap + no)
            if len(k) >= 12 and len(ap) >= 2: por_fon[k].add(r)
    hechos = 0
    for k, rs in por_fon.items():
        rs = {find(x) for x in rs}
        if len(rs) < 2: continue
        rs = sorted(rs, key=lambda x: -gs[x]["n"])
        base = rs[0]
        for o in rs[1:]:
            o, base = find(o), find(base)
            if o != base and unir_si_unico(o, {base}, gs, "R11", revisar_nombres=False): hechos += 1
    print("R11 misma pronunciación:", hechos)

    # --- grupos, id estable y nombre canónico ---
    var["grupo"] = var["clave"].map(find)
    var["regla"] = var["clave"].map(lambda c: regla.get(c, "R1"))
    grupos = []
    for g, sub in var.groupby("grupo", sort=False):
        # nombre: la forma más completa (más palabras) y, entre ellas, la más frecuente con acentos
        sub = sub.assign(largo=sub["bolsa"].map(len), acentos=sub["display"].map(lambda s: sum(1 for ch in s if ord(ch) > 127)))
        frecuentes = sub[sub["n"] >= 0.2 * sub["n"].max()]  # evita que una forma rara (n=1) ponga el nombre
        mejor = frecuentes.sort_values(["largo", "n", "acentos"], ascending=False).iloc[0]
        # misma forma escrita con acentos si existe («Garcia-Benitez» -> «García-Benítez»)
        mismas = sub[sub["bolsa"] == mejor["bolsa"]]
        mejor = mismas.sort_values(["acentos", "n"], ascending=False).iloc[0]
        nombre = re.sub(r"\s*[@#*]+\s*$", "", arreglar_mojibake(mejor["display"])).strip()
        grupos.append((g, nombre, int(sub["n"].sum()), len(sub)))
    cat = pd.DataFrame(grupos, columns=["grupo", "nombre", "n_tesis", "n_variantes"]).sort_values(["n_tesis", "nombre"], ascending=[False, True]).reset_index(drop=True)
    cat["asesor_id"] = cat.index.astype("int32")
    gid = dict(zip(cat["grupo"], cat["asesor_id"]))
    var["asesor_id"] = [gid[g] for g in var["grupo"]]

    t2id = dict(zip(var["tecnico"], var["asesor_id"]))
    m["asesor_id"] = m["tecnico"].map(t2id)
    m = m.dropna(subset=["asesor_id"]).astype({"asesor_id": "int32"})
    m = m.drop_duplicates(["thesis_id", "asesor_id"])

    OUT.mkdir(parents=True, exist_ok=True)
    m[["thesis_id", "orden", "asesor_id"]].to_parquet(OUT / "asesores_canon.v1.parquet", index=False)
    cat[["asesor_id", "nombre", "n_tesis", "n_variantes"]].to_parquet(OUT / "asesores_catalogo.v1.parquet", index=False)
    # tabla completa de variantes (local) para investigar fallos: pipeline/investigar_asesores.py
    var.assign(ap=var["ap"].map(lambda t: " ".join(t) if t else ""), no=var["no"].map(lambda t: " ".join(t) if t else ""),
               bolsa=var["bolsa"].map(" ".join), programas=var["programas"].map(lambda p: "|".join(sorted(p))))[
        ["tecnico", "display", "n", "ap", "no", "bolsa", "programas", "regla", "asesor_id"]].to_parquet(OUT / "asesores_variantes.v1.parquet", index=False)
    aud = var.merge(cat[["asesor_id", "nombre"]], on="asesor_id")
    aud = aud[aud.groupby("asesor_id")["tecnico"].transform("size") > 1]
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    aud.sort_values(["asesor_id", "n"], ascending=[True, False])[["asesor_id", "nombre", "tecnico", "n", "regla"]].to_csv(AUDIT, index=False, encoding="utf-8")

    print("variantes", len(var), "-> asesores", len(cat), "| tesis con asesor", m["thesis_id"].nunique())
    print("variantes fusionadas por regla:", var[var["asesor_id"].map(cat.set_index("asesor_id")["n_variantes"]) > 1]["regla"].value_counts().to_dict())
    print(cat.head(15).to_string())


if __name__ == "__main__":
    main()
