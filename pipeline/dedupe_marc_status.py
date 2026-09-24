import pandas as pd
from pathlib import Path

for p in Path("recovery/marc_details/status").glob("year_*_marc_status.csv"):
    df = pd.read_csv(p, dtype=str).fillna("")
    backup = p.with_suffix(".before_dedup.csv")
    df.to_csv(backup, index=False, encoding="utf-8")

    latest = df.drop_duplicates(subset=["biblionumber"], keep="last")
    latest.to_csv(p, index=False, encoding="utf-8")

    print(p)
    print("antes:", len(df), "después:", len(latest))
    print(latest["download_status"].value_counts(dropna=False))
