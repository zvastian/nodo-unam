"""Título legible sin mención de responsabilidad (MARC 245 $c): nunca el autor.

El título del catálogo trae pegada la mención de responsabilidad en el 92% de las
tesis: "Título / tesis que para obtener el título de ..., presenta NOMBRE ; asesor
NOMBRE". El autor es estudiante, persona privada: se corta todo lo que sigue.

Regla: se corta en la PRIMERA barra (o frase "tesis que para obtener...") cuyo texto
siguiente arranca como mención de responsabilidad (tipo de trabajo, "presenta",
"por", o un nombre propio de dos o más palabras). Una barra que separa palabras del
título ("estireno / butadieno/ acido") no se corta. Después pasa la limpieza de
`limpiar_autores_atlas.limpiar`, que cubre las variantes sin barra.

Uso:
    python pipeline/titulo_sin_autor.py            # reescribe data/public/data_unam.parquet
    python pipeline/titulo_sin_autor.py --dry-run  # solo mide y muestra ejemplos
`generar_data_unam.py` importa `titulo_legible` para que el export salga limpio.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from limpiar_autores_atlas import limpiar  # noqa: E402

MAY = "A-ZÁÉÍÓÚÑÜ"
MIN = "a-záéíóúñü"
TRABAJO = r"(?:tesis|thesis|tesina|informe|reporte|trabajo|memoria|ensayo|monograf[ií]a|proyecto|seminario|caso\s+pr[aá]ctico|presentaci[oó]n\s+de\s+casos|titulaci[oó]n)"
# Lo que sigue a la barra: ¿empieza como mención de responsabilidad?
INICIO_RESP = re.compile(
    r"\s*(?:"
    r";|(?i:" + TRABAJO + r")\b"
    r"|\[|(?i:que|para\s+(?:su|el|obtener|obtner|optar|sustentar)|obtener|estudio\s+(?:que|presentado)|(?:doctorado|maestr[ií]a|licenciatura|especialidad|posgrado|carrera)\b|tesista|(?:lic|dr|dra|ing|mtro|mtra|arq|c\.p)\.)\b"
    r"|(?i:presentan?|pesenta|presentad[oa]|prueba|examen|asesores|por|sustentante|elaborad[oa]|realizad[oa]|autor[ae]?s?|alumn[oa]s?|pasantes?|asesor|director|tutor|coordinador)\b"
    r"|(?:[" + MAY + r"][" + MIN + r"]+\.?|[" + MAY + r"]\.)(?:\s+(?:de|del|la|las|los|y|De|Del|La)?\s*(?:[" + MAY + r"][" + MIN + r"'-]+|[" + MAY + r"]\.)){1,5}\s*(?:[;,.]|$)"
    r")"
)
BARRA = re.compile(r"\s*/+\s*")
# Si ninguna barra arranca como mención, se corta en la ÚLTIMA barra cuyo resto trae
# una marca fuerte de persona o de trámite de titulación.
MARCA_FUERTE = re.compile(r"(?i:\bpresentan?\b|\bpresents\b|\basesora?\b|\btutora?\b|\bdirector[a]?\b|\btesista\b|\bautora?\b|\balumn[oa]\b|\bsustentante|examen\s+profesional|para\s+(?:obtener|obtner|optar)|t[ií]tulo\s+de|grado\s+de)")
# Sin barra: "... tesis que para obtener el título de ..."
SIN_BARRA = re.compile(r"[\s,.;:]+(?=(?i:" + TRABAJO + r")[\w\s,()]{0,60}?\s+(?:que\s+)?(?:para\s+)?(?:obtener|optar)\b)")
# Programas de recital: "Notas al programa que presenta NOMBRE ..." -> sin el nombre
RECITAL = re.compile(r"(?i:(notas\s+al\s+programa(?:\s+de\s+mano)?\s+que\s+presentan?))\s+(?:[" + MAY + r"][" + MIN + r"]+\s*){2,5}")

# Ruido de catálogo al inicio: "Sustentante Aspectos jurídicos ..."
SUSTENTANTE = re.compile(r"^(?i:sustentante)\s+")

# Señales de que aún queda una persona en el título (para medir fugas)
FUGA = re.compile(
    r"(?i:\bpresentan?\s*:?\s+(?:el|la|los|las|c\.|p\.|ing\.)?\s*)[" + MAY + r"][" + MIN + r"]+\s+[" + MAY + r"]"
    r"|(?i:\bque\s+para\s+(?:obtener|optar)\b)"
    r"|(?i:;\s*(?:asesora?|asesores|director[a]?|tutor[a]?)\b)"
    r"|(?i:\bsustentantes?\s*:)"
)


def titulo_legible(t):
    t = (t or "").strip()
    if not t:
        return t
    cut = len(t)
    barras = [m for m in BARRA.finditer(t) if m.start() >= 2]
    for m in barras:
        if INICIO_RESP.match(t, m.end()):
            cut = m.start()
            break
    else:
        for m in reversed(barras):
            if MARCA_FUERTE.search(t, m.end()):
                cut = m.start()
                break
    m = SIN_BARRA.search(t)
    if m and 2 <= m.start() < cut:
        cut = m.start()
    t = t[:cut].strip().rstrip(" :;,./").strip()
    t = RECITAL.sub(r"\1 ", t)
    t = SUSTENTANTE.sub("", t)
    return limpiar(t)


def main(dry):
    import pandas as pd

    path = Path(__file__).resolve().parents[1] / "data" / "public" / "data_unam.parquet"
    df = pd.read_parquet(path)
    if "titulo_original" not in df.columns:
        print("data_unam.parquet ya no tiene titulo_original; nada que hacer.")
        return
    orig = df["titulo_original"].fillna("")
    nuevo = orig.map(titulo_legible)

    cambiadas = (nuevo != orig).sum()
    fugas = nuevo[nuevo.str.contains(FUGA)]
    vacios = ((nuevo.str.len() < 5) & (orig.str.len() >= 5)).sum()
    print(f"filas {len(df):,}  cortadas {cambiadas:,} ({cambiadas / len(df):.1%})")
    print(f"fugas restantes {len(fugas):,}  títulos casi vacíos {vacios:,}")
    for a, b in zip(orig[(nuevo.str.len() < 5) & (orig.str.len() >= 5)], nuevo[(nuevo.str.len() < 5) & (orig.str.len() >= 5)]):
        print("  CORTO", repr(b), "<-", a[:120])
    for t in fugas.head(25):
        print("  FUGA ", t[:200])
    if dry:
        muestra = df.assign(n=nuevo)[nuevo != orig].sample(15, random_state=3)
        for a, b in zip(muestra["titulo_original"], muestra["n"]):
            print("  -", a[:160], "\n    ->", b[:160])
        intactas = df.assign(n=nuevo)[(nuevo == orig) & orig.str.contains("/", regex=False)]
        print(f"con barra y sin cortar: {len(intactas):,}")
        for t in intactas["titulo_original"].sample(min(15, len(intactas)), random_state=3):
            print("  =", t[:200])
        return

    pos = list(df.columns).index("titulo_original")
    df = df.drop(columns=["titulo_original"])
    df.insert(pos, "titulo_legible", nuevo)
    df.to_parquet(path, index=False)
    print(f"escrito {path} (titulo_original -> titulo_legible)")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
