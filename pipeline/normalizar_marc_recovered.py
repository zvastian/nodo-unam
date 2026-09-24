from pathlib import Path
import re
import unicodedata
import pandas as pd

IN = Path("recovery/processed/marc_recovered_all.parquet")
OUT_DIR = Path("recovery/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT = OUT_DIR / "marc_recovered_normalized.parquet"
OUT_SAMPLE = OUT_DIR / "marc_recovered_normalized_sample_1000.csv"
OUT_AUDIT_PLANTELES = OUT_DIR / "marc_planteles_normalizados_auditoria.csv"
OUT_AUDIT_NIVELES = OUT_DIR / "marc_niveles_auditoria.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

print("Leyendo:", IN)
df = pd.read_parquet(IN)

def clean_str(x):
    if pd.isna(x):
        return ""
    x = str(x)
    x = x.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def strip_accents(s):
    s = clean_str(s)
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def normalize_key(s):
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def title_normalized(s):
    s = clean_str(s)
    s = re.sub(r"\s*/\s*$", "", s).strip()
    return s

def titulo_limpio_from_marc(titulo, responsabilidad):
    titulo = title_normalized(titulo)
    # MARC 245 ya trae el título sin la mención larga en muchos casos.
    # Si viene vacío, usamos responsabilidad como fallback muy conservador.
    if titulo:
        return titulo
    return clean_str(responsabilidad)

def titulo_normalizado_for_search(s):
    s = normalize_key(s)
    return s

def first_nonempty(*vals):
    for v in vals:
        v = clean_str(v)
        if v:
            return v
    return ""

def split_people(s):
    s = clean_str(s)
    if not s:
        return []
    parts = [clean_str(x).strip(" ,;") for x in re.split(r"\s*\|\s*", s)]
    return [p for p in parts if p]

def normalize_person_name(s):
    s = clean_str(s).strip(" ,;")
    return s

def normalize_people_pipe(s):
    people = split_people(s)
    seen = []
    for p in people:
        p = normalize_person_name(p)
        if p and p not in seen:
            seen.append(p)
    return " | ".join(seen)

def nivel_from_tipo_estudios(tipo):
    k = normalize_key(tipo)

    if not k:
        return ""

    if "doctor" in k:
        return "doctorado"

    if "maestr" in k or "master" in k:
        return "maestria"

    if "especialidad" in k or "especialista" in k or "especializacion" in k:
        return "especialidad"

    if "licenciatura" in k or "licenciado" in k or "ingeniero" in k or "medico cirujano" in k or "cirujano dentista" in k:
        return "licenciatura"

    return ""

def grado_norm(tipo):
    return normalize_key(tipo)

def programa_from_tipo_estudios(tipo):
    tipo = clean_str(tipo)

    if not tipo:
        return ""

    # Quitar prefijos de nivel conservando el programa
    patterns = [
        r"^Licenciatura en\s+",
        r"^Licenciado en\s+",
        r"^Licenciada en\s+",
        r"^Maestría en\s+",
        r"^Maestro en\s+",
        r"^Maestra en\s+",
        r"^Doctorado en\s+",
        r"^Doctor en\s+",
        r"^Doctora en\s+",
        r"^Especialidad en\s+",
        r"^Especialista en\s+",
    ]

    out = tipo
    for pat in patterns:
        out = re.sub(pat, "", out, flags=re.I).strip()

    return out

def fix_display_accents(s):
    s = clean_str(s)

    repl = {
        "Odontologia": "Odontología",
        "Quimica": "Química",
        "Filosofia": "Filosofía",
        "Economia": "Economía",
        "Contaduria": "Contaduría",
        "Administracion": "Administración",
        "Enfermeria": "Enfermería",
        "Pedagogia": "Pedagogía",
        "Psicologia": "Psicología",
        "Ingenieria": "Ingeniería",
        "Medico": "Médico",
        "Medica": "Médica",
        "Veterinaria": "Veterinaria",
        "Zootecnia": "Zootecnia",
        "Biologicas": "Biológicas",
        "Biologia": "Biología",
        "Fisica": "Física",
        "Matematicas": "Matemáticas",
        "Politicas": "Políticas",
        "Plasticas": "Plásticas",
        "Acatlan": "Acatlán",
        "Aragon": "Aragón",
        "Cuautitlan": "Cuautitlán",
        "Iztacala": "Iztacala",
        "Zaragoza": "Zaragoza",
        "Academica": "Académica",
        "Mecanica": "Mecánica",
        "Electrica": "Eléctrica",
        "Quimicas": "Químicas",
        "Mexicana": "Mexicana",
    }

    for a, b in repl.items():
        s = s.replace(a, b)

    return s

def plantel_standard_and_display(plantel, entidades=""):
    raw = clean_str(plantel)
    ent = clean_str(entidades)

    source = raw or ent
    k = normalize_key(source)

    if not k:
        return "no especificado unam", "No especificado"

    # Quitar prefijos UNAM frecuentes para normalizar
    k = re.sub(r"^universidad nacional autonoma de mexico\s+", "", k).strip()
    k = re.sub(r"\s+universidad nacional autonoma de mexico$", "", k).strip()

    # FES / ENEP históricas
    fes_map = {
        "escuela nacional de estudios profesionales acatlan": ("facultad de estudios superiores acatlan unam", "FES Acatlán"),
        "escuela nacional de estudios profesionales aragon": ("facultad de estudios superiores aragon unam", "FES Aragón"),
        "escuela nacional de estudios profesionales iztacala": ("facultad de estudios superiores iztacala unam", "FES Iztacala"),
        "escuela nacional de estudios profesionales cuautitlan": ("facultad de estudios superiores cuautitlan unam", "FES Cuautitlán"),
        "facultad de estudios superiores acatlan": ("facultad de estudios superiores acatlan unam", "FES Acatlán"),
        "facultad de estudios superiores aragon": ("facultad de estudios superiores aragon unam", "FES Aragón"),
        "facultad de estudios superiores iztacala": ("facultad de estudios superiores iztacala unam", "FES Iztacala"),
        "facultad de estudios superiores cuautitlan": ("facultad de estudios superiores cuautitlan unam", "FES Cuautitlán"),
        "facultad de estudios superiores zaragoza": ("facultad de estudios superiores zaragoza unam", "FES Zaragoza"),
    }

    if k in fes_map:
        return fes_map[k]

    # Facultades centrales
    faculty_map = {
        "facultad de medicina": ("facultad de medicina unam", "Facultad de Medicina"),
        "facultad de derecho": ("facultad de derecho unam", "Facultad de Derecho"),
        "facultad de ingenieria": ("facultad de ingenieria unam", "Facultad de Ingeniería"),
        "facultad de odontologia": ("facultad de odontologia unam", "Facultad de Odontología"),
        "facultad de quimica": ("facultad de quimica unam", "Facultad de Química"),
        "facultad de ciencias": ("facultad de ciencias unam", "Facultad de Ciencias"),
        "facultad de arquitectura": ("facultad de arquitectura unam", "Facultad de Arquitectura"),
        "facultad de contaduria y administracion": ("facultad de contaduria y administracion unam", "Facultad de Contaduría y Administración"),
        "facultad de medicina veterinaria y zootecnia": ("facultad de medicina veterinaria y zootecnia unam", "Facultad de Medicina Veterinaria y Zootecnia"),
        "facultad de ciencias politicas y sociales": ("facultad de ciencias politicas y sociales unam", "Facultad de Ciencias Políticas y Sociales"),
        "facultad de filosofia y letras": ("facultad de filosofia y letras unam", "Facultad de Filosofía y Letras"),
        "facultad de psicologia": ("facultad de psicologia unam", "Facultad de Psicología"),
        "facultad de economia": ("facultad de economia unam", "Facultad de Economía"),
        "facultad de artes y diseno": ("facultad de artes y diseno unam", "Facultad de Artes y Diseño"),
        "facultad de enfermeria y obstetricia": ("facultad de enfermeria y obstetricia unam", "Facultad de Enfermería y Obstetricia"),
    }

    if k in faculty_map:
        return faculty_map[k]

    # Escuelas históricas o incorporadas con equivalencias simples
    escuela_map = {
        "escuela nacional de enfermeria y obstetricia": ("escuela nacional de enfermeria y obstetricia unam", "Escuela Nacional de Enfermería y Obstetricia"),
        "escuela nacional de trabajo social": ("escuela nacional de trabajo social unam", "ENTS"),
        "escuela nacional de artes plasticas": ("escuela nacional de artes plasticas unam", "Escuela Nacional de Artes Plásticas"),
        "colegio de ciencias y humanidades unidad academica de los ciclos profesional y de posgrado": (
            "colegio de ciencias y humanidades unam",
            "CCH"
        ),
    }

    if k in escuela_map:
        return escuela_map[k]

    # Programas de posgrado: no son plantel exactamente; conservar como no especificado o como entidad.
    if k.startswith("programa de posgrado"):
        disp = fix_display_accents(source)
        return k + " unam", disp

    # Universidades externas/incorporadas o escuelas externas: conservar nombre normalizado sin forzar UNAM
    external_indicators = [
        "universidad ",
        "escuela ",
        "instituto ",
        "centro ",
        "hospital ",
        "colegio ",
    ]

    display = fix_display_accents(source)

    if any(k.startswith(x) for x in external_indicators):
        # Si ya parece entidad externa/histórica, no añadimos UNAM salvo que explícitamente sea UNAM.
        if "unam" in k or "universidad nacional autonoma de mexico" in normalize_key(source):
            std = k if k.endswith("unam") else k + " unam"
        else:
            std = k
        return std, display

    # Fallback conservador
    std = k
    if "unam" not in std and "facultad" in std:
        std = std + " unam"

    return std, display

def area_from_programa(programa, plantel):
    k = normalize_key(programa + " " + plantel)

    if any(x in k for x in ["medicina", "medico", "cirugia", "pediatria", "ginecologia", "anestesiologia", "nefrologia", "cardiologia", "psiquiatria"]):
        return "Ciencias Biológicas, Químicas y de la Salud"
    if any(x in k for x in ["derecho", "jurid"]):
        return "Ciencias Sociales"
    if any(x in k for x in ["economia", "administracion", "contaduria", "relaciones internacionales", "sociologia", "ciencias politicas"]):
        return "Ciencias Sociales"
    if any(x in k for x in ["ingenieria", "arquitectura", "computacion", "matematicas", "fisica", "quimica", "actuaria"]):
        return "Ciencias Físico-Matemáticas e Ingenierías"
    if any(x in k for x in ["filosofia", "letras", "historia", "pedagogia", "diseno", "artes", "geografia"]):
        return "Humanidades y Artes"
    return ""

# Construcción de columnas normalizadas
out = pd.DataFrame()

out["source_record"] = "marc_recovered"
out["target_year"] = df.get("target_year", "").astype(str)
out["biblionumber"] = df.get("biblionumber", "").astype(str)
out["system_number"] = df.get("system_number", "").map(clean_str)

out["Año"] = pd.to_numeric(
    df.get("anio_produccion_marc", df.get("target_year", "")),
    errors="coerce"
).fillna(pd.to_numeric(df.get("target_year", ""), errors="coerce")).astype("Int64")

out["título"] = df.get("titulo_marc", "").map(title_normalized)
out["responsabilidad_marc"] = df.get("responsabilidad_marc", "").map(clean_str)
out["titulo_limpio"] = [
    titulo_limpio_from_marc(t, r)
    for t, r in zip(out["título"], out["responsabilidad_marc"])
]
out["titulo_normalizado"] = out["titulo_limpio"].map(titulo_normalizado_for_search)

out["autor_limpio_v2"] = [
    first_nonempty(a, s, ar)
    for a, s, ar in zip(
        df.get("autor_marc", ""),
        df.get("sustentantes_marc", ""),
        df.get("authors_result", "")
    )
]
out["autor_limpio_v2"] = out["autor_limpio_v2"].map(normalize_person_name)

out["asesores_limpios_v2"] = [
    normalize_people_pipe(first_nonempty(a, ar))
    for a, ar in zip(df.get("asesores_marc", ""), df.get("advisors_result", ""))
]
out["asesor_limpio_v2"] = out["asesores_limpios_v2"].map(lambda x: split_people(x)[0] if split_people(x) else "")

out["num_autores"] = out["autor_limpio_v2"].map(lambda x: 1 if clean_str(x) else 0)
out["num_asesores"] = out["asesores_limpios_v2"].map(lambda x: len(split_people(x)))

out["grado"] = df.get("tipo_estudios_marc", "").map(clean_str)
out["grado_norm"] = out["grado"].map(grado_norm)
out["nivel_estandar"] = out["grado"].map(nivel_from_tipo_estudios)
out["programa"] = out["grado"].map(programa_from_tipo_estudios)

out["plantel_marc_original"] = df.get("plantel_marc", "").map(clean_str)

plantel_results = [
    plantel_standard_and_display(p, e)
    for p, e in zip(
        df.get("plantel_marc", ""),
        df.get("entidades_participantes_marc", "")
    )
]

out["plantel_estandarizado"] = [x[0] for x in plantel_results]
out["plantel_display"] = [x[1] for x in plantel_results]

out["universidad_nota"] = df.get("institucion_otorgante_502_marc", "").map(clean_str)
out["entidad_clean"] = df.get("entidades_participantes_marc", "").map(clean_str)

out["origen"] = out["universidad_nota"].map(
    lambda x: "UNAM" if "Universidad Nacional Autónoma de México" in x else ("externa/incorporada" if clean_str(x) else "")
)

out["area"] = [
    area_from_programa(p, pl)
    for p, pl in zip(out["programa"], out["plantel_estandarizado"])
]

out["link_extraido_regex"] = df.get("texto_completo_url", "").map(clean_str)
out["texto_completo_url"] = df.get("texto_completo_url", "").map(clean_str)
out["restricciones"] = df.get("restricciones_marc", "").map(clean_str)
out["descr física"] = df.get("extension_marc", "").map(clean_str)
out["soporte"] = df.get("tipo_soporte_marc", "").map(clean_str)
out["archivo_tipo_marc"] = df.get("archivo_tipo_marc", "").map(clean_str)
out["archivo_formato_marc"] = df.get("archivo_formato_marc", "").map(clean_str)
out["archivo_tamano_marc"] = df.get("archivo_tamano_marc", "").map(clean_str)

out["materia general"] = df.get("temas_marc", "").map(clean_str)
out["palabras clave"] = df.get("temas_marc", "").map(clean_str)
out["resumen"] = ""

out["marc_url"] = df.get("marc_url", "").map(clean_str)
out["detail_url"] = df.get("detail_url", "").map(clean_str)
out["download_status"] = df.get("download_status", "").map(clean_str)
out["downloaded_at_unix"] = df.get("downloaded_at_unix", "")

# Auditorías
plantel_audit = (
    out.groupby(["plantel_marc_original", "plantel_estandarizado", "plantel_display"], dropna=False)
       .size()
       .reset_index(name="n")
       .sort_values("n", ascending=False)
)

nivel_audit = (
    out.groupby(["grado", "nivel_estandar", "programa"], dropna=False)
       .size()
       .reset_index(name="n")
       .sort_values("n", ascending=False)
)

out.to_parquet(OUT, index=False)
out.head(1000).to_csv(OUT_SAMPLE, index=False, encoding="utf-8")
plantel_audit.to_csv(OUT_AUDIT_PLANTELES, index=False, encoding="utf-8")
nivel_audit.to_csv(OUT_AUDIT_NIVELES, index=False, encoding="utf-8")

print("\nLISTO")
print("Input:", IN)
print("Output:", OUT)
print("Sample:", OUT_SAMPLE)
print("Auditoría planteles:", OUT_AUDIT_PLANTELES)
print("Auditoría niveles:", OUT_AUDIT_NIVELES)
print("Rows:", len(out))
print("Cols:", len(out.columns))

print("\nTop plantel_display:")
print(out["plantel_display"].value_counts(dropna=False).head(30).to_string())

print("\nTop nivel_estandar:")
print(out["nivel_estandar"].value_counts(dropna=False).head(20).to_string())

print("\nCobertura clave:")
for c in ["system_number", "título", "autor_limpio_v2", "asesores_limpios_v2", "grado", "nivel_estandar", "plantel_estandarizado", "texto_completo_url"]:
    nn = (out[c].astype(str).str.strip() != "").sum()
    print(f"{c}: {nn:,}/{len(out):,} = {nn/len(out)*100:.2f}%")
