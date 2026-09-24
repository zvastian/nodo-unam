import pandas as pd
from pathlib import Path

for p in sorted(Path("recovery/marc_details/status").glob("year_*_marc_status.csv")):
    df = pd.read_csv(p, dtype=str).fillna("")
    latest = df.drop_duplicates(subset=["biblionumber"], keep="last")

    print("\n", p)
    print("rows:", len(latest))
    print(latest["download_status"].value_counts(dropna=False))
    print("texto_completo_url no vacío:", (latest["texto_completo_url"].astype(str).str.strip() != "").sum())

    print("\nSample:")
    cols = [
        "biblionumber",
        "system_number",
        "titulo_marc",
        "anio_produccion_marc",
        "tipo_estudios_marc",
        "plantel_marc",
        "texto_completo_url",
    ]
    print(latest[cols].head(5).to_string(index=False))
