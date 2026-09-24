from pathlib import Path
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

IN = Path("base6_homogeneizada_stream_v2.parquet")
OUT = Path("base6_homogeneizada_stream_v4.parquet")

OUT_DIR = Path("outputs/base6_homologacion")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FREQ = OUT_DIR / "base6_homogeneizada_stream_v4_autores_freq.csv"
SAMPLE = OUT_DIR / "base6_homogeneizada_stream_v4_author_sample.csv"
LOG = OUT_DIR / "base6_homogeneizada_stream_v4_author_log.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

if OUT.exists():
    raise FileExistsError(f"Ya existe {OUT}. Renómbralo o bórralo si quieres regenerarlo.")

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def fix_mojibake_light(s):
    s = clean_str(s)
    replacements = {
        "MagaÃ±a": "Magaña",
        "Ã±": "ñ",
        "Ã¡": "á",
        "Ã©": "é",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãº": "ú",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    return s

def clean_one_author(name):
    s = fix_mojibake_light(name)

    if not s:
        return ""

    if re.fullmatch(r"(?i)\s*(sin autor|registro en proceso|asesor)\s*", s):
        return ""

    s = re.sub(r",?\s*\$e\s*(sustentante|autor|coautor|asesor|asesora)\b", "", s, flags=re.I)
    s = re.sub(r",?\s*\$e[a-záéíóúñ ]+", "", s, flags=re.I)

    s = re.sub(r",?\s*(sustentante|coautor|autor|asesor|asesora)\.?\s*$", "", s, flags=re.I)
    s = re.sub(r"(sustentante|coautor|autor|asesor|asesora)\.+", "", s, flags=re.I)

    s = re.sub(r",?\s*(18|19|20)\d{2}\s*-\s*((18|19|20)\d{2})?\s*$", "", s)
    s = re.sub(r",?\s*(18|19|20)\d{2}\s*-\s*,?\s*\d{3,4}\s*-\s*$", "", s)

    s = s.replace("Delfin0", "Delfino")
    s = s.replace("Enriqu3", "Enrique")
    s = s.replace("Roberta1", "Roberta")

    s = s.replace("\\", " ")
    s = re.sub(r"[<>]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[,;:.]+$", "", s).strip()
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s

def split_authors(value):
    value = clean_str(value)
    if not value:
        return []

    # IMPORTANTE:
    # Para autores solo partimos por |.
    # No partimos por ; porque generó falsos múltiples autores.
    parts = re.split(r"\s*\|\s*", value)

    out = []
    for p in parts:
        p = clean_one_author(p)
        if p and p not in out:
            out.append(p)

    return out

def pipe_authors(value):
    return " | ".join(split_authors(value))

def invert_name_for_display(name):
    name = clean_one_author(name).strip(" ,;")
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

def autor_ui_from_row(autor_display, num_autores):
    autor_display = clean_str(autor_display)
    try:
        n = int(num_autores)
    except Exception:
        n = 0

    if n == 0 or not autor_display:
        return "Autor no registrado"

    if n == 1:
        return autor_display

    return f"{autor_display} · +{n - 1} más"

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

    if "autor_limpio_v2_raw" not in df.columns:
        df["autor_limpio_v2_raw"] = df["autor_limpio_v2"] if "autor_limpio_v2" in df.columns else ""

    if "autor_limpio_v2" not in df.columns:
        df["autor_limpio_v2"] = ""

    source = df["autor_limpio_v2_raw"].fillna("").astype(str)
    fallback = df["autor_limpio_v2"].fillna("").astype(str)

    chosen = [
        clean_str(a) if clean_str(a) else clean_str(b)
        for a, b in zip(source, fallback)
    ]

    df["autores_limpios_v2"] = [pipe_authors(x) for x in chosen]

    df["autor_limpio_v2"] = df["autores_limpios_v2"].map(
        lambda x: next((p.strip() for p in str(x).split("|") if p.strip()), "")
    )

    df["num_autores"] = df["autores_limpios_v2"].map(
        lambda x: len([p for p in str(x).split("|") if p.strip()])
    )

    df["autor_display"] = df["autor_limpio_v2"].map(invert_name_for_display)
    df["autores_display"] = df["autores_limpios_v2"].map(display_pipe_from_pipe)

    df["flag_sin_autor"] = df["num_autores"] == 0
    df["flag_multiples_autores"] = df["num_autores"] > 1
    df["flag_autores_4plus"] = df["num_autores"] >= 4

    df["autor_ui"] = [
        autor_ui_from_row(a, n)
        for a, n in zip(df["autor_display"], df["num_autores"])
    ]

    vc = df["num_autores"].value_counts().to_dict()
    for k, v in vc.items():
        freq_counts[int(k)] = freq_counts.get(int(k), 0) + int(v)

    if len(sample_parts) < 5:
        sample_cols = [
            "thesis_id", "Año", "título",
            "autor_limpio_v2_raw",
            "autores_limpios_v2",
            "autor_limpio_v2",
            "autores_display",
            "autor_display",
            "num_autores",
            "autor_ui",
            "asesor_ui",
            "num_asesores",
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
    {"num_autores": k, "n_tesis": v}
    for k, v in sorted(freq_counts.items())
])
freq["pct"] = freq["n_tesis"] / freq["n_tesis"].sum() * 100
freq.to_csv(FREQ, index=False, encoding="utf-8")

pd.DataFrame(log_rows).to_csv(LOG, index=False, encoding="utf-8")

if sample_parts:
    pd.concat(sample_parts, ignore_index=True).to_csv(SAMPLE, index=False, encoding="utf-8")

print("\nLISTO V4 autores")
print("Output:", OUT)
print("Rows written:", rows_written)
print("Freq:", FREQ)
print("Sample:", SAMPLE)
print("Log:", LOG)
print("\nDistribución num_autores:")
print(freq.to_string(index=False))
