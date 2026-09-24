from pathlib import Path
import re
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

IN = Path("base6_homogeneizada_stream_v4.parquet")
OUT = Path("base6_homogeneizada_stream_v4_1.parquet")

OUT_DIR = Path("outputs/base6_homologacion")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOG = OUT_DIR / "base6_homogeneizada_stream_v4_1_author_manual_patch_log.csv"
FREQ = OUT_DIR / "base6_homogeneizada_stream_v4_1_autores_freq.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

if OUT.exists():
    raise FileExistsError(f"Ya existe {OUT}. Renómbralo o bórralo si quieres regenerarlo.")

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def clean_one_author(name):
    s = clean_str(name)

    if not s:
        return ""

    if re.fullmatch(r"(?i)\s*(sin autor|registro en proceso|asesor)\s*", s):
        return ""

    s = re.sub(r",?\s*\$e\s*(sustentante|autor|coautor|asesor|asesora)\b", "", s, flags=re.I)
    s = re.sub(r",?\s*\$e[a-záéíóúñ ]+", "", s, flags=re.I)

    s = re.sub(r",?\s*(sustentante|coautor|autor|asesor|asesora)\.?\s*$", "", s, flags=re.I)
    s = re.sub(r"(sustentante|coautor|autor|asesor|asesora)\.+", "", s, flags=re.I)

    s = re.sub(r",?\s*(18|19|20)\d{2}\s*-\s*((18|19|20)\d{2})?\s*$", "", s)

    s = s.replace("Delfin0", "Delfino")
    s = s.replace("Enriqu3", "Enrique")
    s = s.replace("Roberta1", "Roberta")

    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[,;:.]+$", "", s).strip()
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    return s.strip()

def split_authors(value):
    value = clean_str(value)
    if not value:
        return []

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

def display_pipe(value):
    parts = [p.strip() for p in str(value).split("|") if p.strip()]
    out = []

    for p in parts:
        d = invert_name_for_display(p)
        if d and d not in out:
            out.append(d)

    return " | ".join(out)

def autor_ui(row):
    n = int(row["num_autores"])
    principal = clean_str(row["autor_display"])

    if n == 0 or not principal:
        return "Autor no registrado"
    if n == 1:
        return principal
    return f"{principal} · +{n - 1} más"

pf = pq.ParquetFile(IN)
writer = None
rows_written = 0
logs = []
freq_counts = {}

for rg in range(pf.num_row_groups):
    df = pf.read_row_group(rg).to_pandas()

    for idx in df.index:
        thesis_id = str(df.at[idx, "thesis_id"]) if "thesis_id" in df.columns else ""
        raw = clean_str(df.at[idx, "autor_limpio_v2_raw"]) if "autor_limpio_v2_raw" in df.columns else ""
        current = clean_str(df.at[idx, "autores_limpios_v2"]) if "autores_limpios_v2" in df.columns else ""

        new_raw = raw
        reason = ""

        # Caso 1: pipe usado como sustituto de ñ/n en un solo apellido.
        if "Ure|a" in new_raw:
            new_raw = new_raw.replace("Ure|a", "Urea")
            reason = "replace_Ure_pipe_a"

        # Caso 2: basura truncada antes del autor real.
        if thesis_id == "TH_0539823":
            new_raw = "Ruiz Téllez, Arturo"
            reason = "manual_drop_truncated_Tellez"

        if reason:
            old_autores = current
            new_autores = pipe_authors(new_raw)

            df.at[idx, "autor_limpio_v2_raw"] = new_raw
            df.at[idx, "autores_limpios_v2"] = new_autores
            df.at[idx, "autor_limpio_v2"] = next((p.strip() for p in new_autores.split("|") if p.strip()), "")

            df.at[idx, "num_autores"] = len([p for p in new_autores.split("|") if p.strip()])
            df.at[idx, "autor_display"] = invert_name_for_display(df.at[idx, "autor_limpio_v2"])
            df.at[idx, "autores_display"] = display_pipe(new_autores)
            df.at[idx, "flag_sin_autor"] = df.at[idx, "num_autores"] == 0
            df.at[idx, "flag_multiples_autores"] = df.at[idx, "num_autores"] > 1
            df.at[idx, "flag_autores_4plus"] = df.at[idx, "num_autores"] >= 4
            df.at[idx, "autor_ui"] = autor_ui(df.loc[idx])

            logs.append({
                "row_group": rg + 1,
                "row_index": int(idx),
                "thesis_id": thesis_id,
                "reason": reason,
                "old_raw": raw,
                "new_raw": new_raw,
                "old_autores_limpios_v2": old_autores,
                "new_autores_limpios_v2": new_autores,
                "new_autor_display": df.at[idx, "autor_display"],
                "new_num_autores": df.at[idx, "num_autores"],
            })

    vc = df["num_autores"].value_counts().to_dict()
    for k, v in vc.items():
        freq_counts[int(k)] = freq_counts.get(int(k), 0) + int(v)

    table = pa.Table.from_pandas(df, preserve_index=False)

    if writer is None:
        writer = pq.ParquetWriter(
            OUT,
            table.schema,
            compression="zstd",
            use_dictionary=True
        )

    writer.write_table(table)
    rows_written += len(df)

    print(f"row_group={rg+1}/{pf.num_row_groups} rows_written={rows_written:,}", flush=True)

if writer:
    writer.close()

pd.DataFrame(logs).to_csv(LOG, index=False, encoding="utf-8")

freq = pd.DataFrame([
    {"num_autores": k, "n_tesis": v}
    for k, v in sorted(freq_counts.items())
])
freq["pct"] = freq["n_tesis"] / freq["n_tesis"].sum() * 100
freq.to_csv(FREQ, index=False, encoding="utf-8")

print("\nLISTO v4.1")
print("Output:", OUT)
print("Rows written:", rows_written)
print("Cambios:", len(logs))
print("Log:", LOG)
print("Freq:", FREQ)
print(freq.to_string(index=False))
