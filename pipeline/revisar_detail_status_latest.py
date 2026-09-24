import pandas as pd
from pathlib import Path

for p in sorted(Path("recovery/details/status").glob("year_*_detail_status.csv")):
    df = pd.read_csv(p, dtype=str).fillna("")

    # último estado por biblionumber
    latest = df.drop_duplicates(subset=["biblionumber"], keep="last")

    print("\n", p)
    print("rows totales:", len(df))
    print("biblionumbers únicos:", latest["biblionumber"].nunique())
    print(latest["download_status"].value_counts(dropna=False))
    print("doc_number no vacío:", (latest["doc_number"].astype(str).str.strip() != "").sum())

    failed = latest[latest["download_status"] == "failed"]
    if len(failed):
        print("\nFAILED únicos:")
        print(failed[["biblionumber", "title_result", "error"]].to_string(index=False))
