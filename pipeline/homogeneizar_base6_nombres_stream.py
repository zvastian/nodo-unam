from pathlib import Path
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

IN = Path("base6.parquet")
OUT = Path("base6_homogeneizada_stream.parquet")
OUT_DIR = Path("outputs/base6_homologacion")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOG = OUT_DIR / "base6_homogeneizada_stream_log.csv"
FREQ = OUT_DIR / "base6_homogeneizada_stream_asesores_freq.csv"
SAMPLE = OUT_DIR / "base6_homogeneizada_stream_sample.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

if OUT.exists():
    raise FileExistsError(f"Ya existe {OUT}. Renómbralo o bórralo si quieres regenerarlo.")

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def clean_one_name(name):
    s = clean_str(name)

    if not s:
        return ""

    # Quitar residuos MARC/Aleph tipo $easesor
    s = re.sub(r",?\s*\$e\s*(asesor|asesora|sustentante|tutor|tutora|director|directora)\b", "", s, flags=re.I)
    s = re.sub(r",?\s*\$e[a-záéíóúñ ]+", "", s, flags=re.I)

    # Quitar etiquetas textuales residuales
    s = re.sub(
        r"\b(asesor|asesora|director de tesis|directora de tesis|director|directora|tutor|tutora|sustentante)\b\s*[:\-]?",
        "",
        s,
        flags=re.I
    )

    # Quitar fechas biográficas al final:
    # "Apellido, Nombre, 1954-" -> "Apellido, Nombre"
    # "Apellido, Nombre, 1954-2010" -> "Apellido, Nombre"
    s = re.sub(r",?\s+\d{4}\s*-\s*(\d{4})?\s*$", "", s)
    s = re.sub(r"\s+\d{4}\s*-\s*(\d{4})?\s*$", "", s)

    # Limpiar puntuación/espacios
    s = s.replace("\\", " ")
    s = re.sub(r"[<>]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[,;:.]+$", "", s).strip()
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s

def split_asesores_base6(value):
    value = clean_str(value)
    if not value:
        return []

    # Base6 usa principalmente ;. También aceptamos |.
    parts = re.split(r"\s*(?:\||;)\s*", value)

    out = []
    for p in parts:
        p = clean_one_name(p)
        if p and p not in out:
            out.append(p)

    return out

def pipe_from_asesores(value):
    return " | ".join(split_asesores_base6(value))

def invert_name_for_display(name):
    name = clean_one_name(name).strip(" ,;")

    if not name:
        return ""

    if "," not in name:
        return name

    left, right = name.split(",", 1)
    left = clean_str(left).strip(" ,;")
    right = clean_str(right).strip(" ,;")

    if not left or not right:
        return name

    return clean_str(f"{right} {left}")

def display_pipe_from_pipe(value):
    value = clean_str(value)
    if not value:
        return ""

    parts = [p.strip() for p in value.split("|") if p.strip()]
    out = []

    for p in parts:
        d = invert_name_for_display(p)
        if d and d not in out:
            out.append(d)

    return " | ".join(out)

def asesor_ui_from_row(asesor_display, num_asesores):
    asesor_display = clean_str(asesor_display)
    try:
        n = int(num_asesores)
    except Exception:
        n = 0

    if n == 0 or not asesor_display:
        return "Asesor no registrado"

    if n == 1:
        return asesor_display

    return f"{asesor_display} · +{n - 1} más"

pf = pq.ParquetFile(IN)

print("Input:", IN)
print("Rows:", pf.metadata.num_rows)
print("Row groups:", pf.num_row_groups)
print("Output:", OUT)

writer = None
rows_written = 0
freq_counts = {}
sample_parts = []
log_rows = []

for rg in range(pf.num_row_groups):
    table = pf.read_row_group(rg)
    df = table.to_pandas()

    n = len(df)

    # Crear raw solo si no existen
    if "autor_limpio_v2" in df.columns and "autor_limpio_v2_raw" not in df.columns:
        df["autor_limpio_v2_raw"] = df["autor_limpio_v2"]

    if "asesor_limpio_v2" in df.columns and "asesor_limpio_v2_raw" not in df.columns:
        df["asesor_limpio_v2_raw"] = df["asesor_limpio_v2"]

    if "asesores_limpios_v2" in df.columns and "asesores_limpios_v2_raw" not in df.columns:
        df["asesores_limpios_v2_raw"] = df["asesores_limpios_v2"]

    # Garantizar columnas base
    if "autor_limpio_v2" not in df.columns:
        df["autor_limpio_v2"] = ""

    if "asesor_limpio_v2" not in df.columns:
        df["asesor_limpio_v2"] = ""

    if "asesores_limpios_v2" not in df.columns:
        df["asesores_limpios_v2"] = df["asesor_limpio_v2"]

    # Limpieza vectorizada con map
    df["autor_limpio_v2"] = df["autor_limpio_v2"].fillna("").astype(str).map(clean_one_name)

    # Lista completa homologada a |
    df["asesores_limpios_v2"] = df["asesores_limpios_v2"].fillna("").astype(str).map(pipe_from_asesores)

    # Asesor principal desde lista
    df["asesor_limpio_v2"] = df["asesores_limpios_v2"].map(
        lambda x: next((p.strip() for p in str(x).split("|") if p.strip()), "")
    )

    # Conteos
    df["num_autores"] = df["autor_limpio_v2"].map(lambda x: 1 if clean_str(x) else 0)
    df["num_asesores"] = df["asesores_limpios_v2"].map(
        lambda x: len([p for p in str(x).split("|") if p.strip()])
    )

    # Display
    df["autor_display"] = df["autor_limpio_v2"].map(invert_name_for_display)
    df["asesor_display"] = df["asesor_limpio_v2"].map(invert_name_for_display)
    df["asesores_display"] = df["asesores_limpios_v2"].map(display_pipe_from_pipe)

    df["flag_sin_asesor"] = df["num_asesores"] == 0
    df["flag_multiples_asesores"] = df["num_asesores"] > 1
    df["flag_asesores_4plus"] = df["num_asesores"] >= 4

    df["asesor_ui"] = [
        asesor_ui_from_row(a, n)
        for a, n in zip(df["asesor_display"], df["num_asesores"])
    ]

    # texto_completo_url homologado
    if "texto_completo_url" not in df.columns:
        if "link_extraido_regex" in df.columns:
            df["texto_completo_url"] = df["link_extraido_regex"]
        else:
            df["texto_completo_url"] = ""

    # Frecuencia acumulada
    vc = df["num_asesores"].value_counts().to_dict()
    for k, v in vc.items():
        freq_counts[int(k)] = freq_counts.get(int(k), 0) + int(v)

    # Sample pequeño
    if len(sample_parts) < 3:
        sample_cols = [
            "thesis_id", "Año", "título",
            "autor_limpio_v2_raw", "autor_limpio_v2", "autor_display",
            "asesor_limpio_v2_raw", "asesores_limpios_v2_raw",
            "asesor_limpio_v2", "asesor_display",
            "asesores_limpios_v2", "asesores_display",
            "num_asesores", "asesor_ui",
        ]
        sample_cols = [c for c in sample_cols if c in df.columns]
        sample_parts.append(df[sample_cols].head(200))

    out_table = pa.Table.from_pandas(df, preserve_index=False)

    if writer is None:
        writer = pq.ParquetWriter(
            OUT,
            out_table.schema,
            compression="zstd",
            use_dictionary=True
        )

    writer.write_table(out_table)

    rows_written += n

    log_rows.append({
        "row_group": rg + 1,
        "rows_batch": n,
        "rows_written": rows_written,
    })

    print(
        f"row_group={rg+1}/{pf.num_row_groups} "
        f"batch_rows={n:,} rows_written={rows_written:,}",
        flush=True
    )

if writer:
    writer.close()

freq = pd.DataFrame([
    {"num_asesores": k, "n_tesis": v}
    for k, v in sorted(freq_counts.items())
])
freq["pct"] = freq["n_tesis"] / freq["n_tesis"].sum() * 100
freq.to_csv(FREQ, index=False, encoding="utf-8")

pd.DataFrame(log_rows).to_csv(LOG, index=False, encoding="utf-8")

if sample_parts:
    pd.concat(sample_parts, ignore_index=True).to_csv(SAMPLE, index=False, encoding="utf-8")

print("\nLISTO")
print("Output:", OUT)
print("Rows written:", rows_written)
print("Freq:", FREQ)
print("Sample:", SAMPLE)
print("Log:", LOG)
print("\nDistribución num_asesores:")
print(freq.to_string(index=False))
