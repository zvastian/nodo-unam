import pandas as pd
from pathlib import Path

for p in sorted(Path("recovery/manifests").glob("year_*_manifest.csv")):
    df = pd.read_csv(p, dtype=str).fillna("")
    print("\n", p)
    print("rows:", len(df))
    print(df["manifest_status"].value_counts(dropna=False))
