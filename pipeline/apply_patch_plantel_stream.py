from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

BASE = Path("base.parquet")
PATCH = Path("outputs/plantel_fix_stream/patch_unidad_posgrado.csv")
OUT = Path("outputs/plantel_fix_stream/base_plantel_corregido_stream.parquet")

BATCH_SIZE = 5_000

if not BASE.exists():
    raise FileNotFoundError(f"No encontré {BASE}")

if not PATCH.exists():
    raise FileNotFoundError(f"No encontré {PATCH}")

OUT.parent.mkdir(parents=True, exist_ok=True)

patch = pd.read_csv(PATCH, dtype=str).fillna("")

def canon(x):
    if x is None:
        return ""
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

patch["key"] = (
    patch["anio"].map(canon)
    + "||"
    + patch["ID_Aleph"].map(canon)
    + "||"
    + patch["plantel_estandarizado"].map(lambda x: canon(x).lower())
)

patch_map = dict(zip(patch["key"], patch["plantel_estandarizado_corregido"]))

print(f"Patch cargado: {len(patch_map):,} registros")

pf = pq.ParquetFile(BASE)
cols = pf.schema_arrow.names
cols_set = set(cols)

if "Año" in cols_set:
    year_col = "Año"
elif "AÃ±o" in cols_set:
    year_col = "AÃ±o"
else:
    raise ValueError("No encontré Año ni AÃ±o")

if "ID_Aleph" not in cols_set:
    raise ValueError("No encontré ID_Aleph")

if "plantel_estandarizado" not in cols_set:
    raise ValueError("No encontré plantel_estandarizado")

writer = None
total = 0
modificados = 0
unidad_sin_patch = 0

for i, batch in enumerate(pf.iter_batches(batch_size=BATCH_SIZE), start=1):
    table = pa.Table.from_batches([batch])

    years = table[year_col].to_pylist()
    ids = table["ID_Aleph"].to_pylist()
    old_planteles = table["plantel_estandarizado"].to_pylist()

    corrected = []

    for anio, id_aleph, old in zip(years, ids, old_planteles):
        old_str = canon(old)
        old_norm = old_str.lower()

        key = canon(anio) + "||" + canon(id_aleph) + "||" + old_norm

        if key in patch_map:
            new = patch_map[key]
        else:
            new = old_str

            if old_norm == "unidad de posgrado unam":
                unidad_sin_patch += 1

        corrected.append(new)

        if old_norm == "unidad de posgrado unam" and new != old_str:
            modificados += 1

    if "plantel_estandarizado_corregido" in table.column_names:
        idx = table.column_names.index("plantel_estandarizado_corregido")
        table = table.remove_column(idx)

    table = table.append_column(
        "plantel_estandarizado_corregido",
        pa.array(corrected, type=pa.string())
    )

    if writer is None:
        writer = pq.ParquetWriter(
            OUT,
            table.schema,
            compression="zstd",
            use_dictionary=True
        )

    writer.write_table(table)
    total += table.num_rows

    print(
        f"batch={i} filas={total:,} modificados={modificados:,} unidad_sin_patch={unidad_sin_patch:,}",
        flush=True
    )

if writer:
    writer.close()

print("\nLISTO")
print(f"Parquet corregido: {OUT}")
print(f"Filas procesadas: {total:,}")
print(f"Casos unidad modificados: {modificados:,}")
print(f"Casos unidad sin patch: {unidad_sin_patch:,}")
