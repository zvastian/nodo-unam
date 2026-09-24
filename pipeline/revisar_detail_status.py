import pandas as pd
from pathlib import Path

for p in sorted(Path("recovery/details/status").glob("year_*_detail_status.csv")):
    df = pd.read_csv(p, dtype=str).fillna("")
    print("\n", p)
    print("rows:", len(df))
    print(df["download_status"].value_counts(dropna=False))
    print("doc_number no vacío:", (df["doc_number"].astype(str).str.strip() != "").sum())
