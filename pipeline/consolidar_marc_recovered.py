from pathlib import Path
import json
import pandas as pd

IN_DIR = Path("recovery/marc_details/jsonl")
OUT_DIR = Path("recovery/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PARQUET = OUT_DIR / "marc_recovered_all.parquet"
OUT_CSV_SAMPLE = OUT_DIR / "marc_recovered_sample_1000.csv"
OUT_REPORT = OUT_DIR / "marc_recovered_summary.csv"

rows = []

for p in sorted(IN_DIR.glob("year_*_marc_details.jsonl")):
    print("Leyendo:", p)

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            obj = json.loads(line)

            # No guardar marc_fields_json completo en este parquet inicial ligero.
            # Si lo quieres conservar después, hacemos versión raw aparte.
            obj_light = {k: v for k, v in obj.items() if k != "marc_fields_json"}

            rows.append(obj_light)

df = pd.DataFrame(rows)

# Deduplicar por biblionumber, conservando último
df["biblionumber"] = df["biblionumber"].astype(str)
df = df.drop_duplicates(subset=["biblionumber"], keep="last")

# Orden útil
preferred = [
    "target_year",
    "biblionumber",
    "system_number",
    "download_status",
    "titulo_marc",
    "responsabilidad_marc",
    "autor_marc",
    "sustentantes_marc",
    "asesores_marc",
    "anio_produccion_marc",
    "tipo_estudios_marc",
    "institucion_otorgante_502_marc",
    "anio_obtencion_marc",
    "plantel_marc",
    "instituciones_otorgantes_marc",
    "entidades_participantes_marc",
    "extension_marc",
    "otros_detalles_fisicos_marc",
    "tipo_soporte_marc",
    "archivo_tipo_marc",
    "archivo_formato_marc",
    "archivo_tamano_marc",
    "restricciones_marc",
    "texto_completo_url",
    "texto_completo_label",
    "texto_completo_nota",
    "has_texto_completo_url",
    "temas_marc",
    "title_result",
    "authors_result",
    "advisors_result",
    "institutions_result",
    "marc_url",
    "detail_url",
    "raw_marc_path",
    "downloaded_at_unix",
]

cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
df = df[cols]

df.to_parquet(OUT_PARQUET, index=False)
df.head(1000).to_csv(OUT_CSV_SAMPLE, index=False, encoding="utf-8")

summary = (
    df.groupby("target_year", dropna=False)
      .agg(
          n=("biblionumber", "count"),
          texto_url=("texto_completo_url", lambda x: (x.astype(str).str.strip() != "").sum()),
          system_number=("system_number", lambda x: (x.astype(str).str.strip() != "").sum()),
      )
      .reset_index()
)

summary["pct_texto_url"] = summary["texto_url"] / summary["n"] * 100
summary.to_csv(OUT_REPORT, index=False, encoding="utf-8")

print("\nLISTO")
print("Parquet:", OUT_PARQUET)
print("Sample:", OUT_CSV_SAMPLE)
print("Report:", OUT_REPORT)
print("Rows:", len(df))
print("Cols:", len(df.columns))
print(summary.to_string(index=False))
