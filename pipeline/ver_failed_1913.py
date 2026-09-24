import pandas as pd

p = "recovery/details/status/year_1913_detail_status.csv"
df = pd.read_csv(p, dtype=str).fillna("")

failed = df[df["download_status"] == "failed"]

print("FAILED:", len(failed))
print(failed[["biblionumber", "detail_url", "title_result", "error"]].to_string(index=False))
