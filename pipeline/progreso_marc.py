import pandas as pd
from pathlib import Path

manifest_dir = Path("recovery/manifests")
status_dir = Path("recovery/marc_details/status")

print("\n=== PROGRESO MARC ===\n")

total_all = 0
ok_all = 0
failed_all = 0
remaining_all = 0
url_all = 0

for manifest_path in sorted(manifest_dir.glob("year_*_manifest.csv")):
    year = manifest_path.stem.split("_")[1]

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")

    if "manifest_status" in manifest.columns:
        total = int((manifest["manifest_status"] == "pending_detail").sum())
    else:
        total = len(manifest)

    status_path = status_dir / f"year_{year}_marc_status.csv"

    ok = 0
    failed = 0
    urls = 0
    rows_status = 0
    unique_status = 0

    if status_path.exists():
        st = pd.read_csv(status_path, dtype=str).fillna("")
        rows_status = len(st)

        if "biblionumber" in st.columns:
            latest = st.drop_duplicates(subset=["biblionumber"], keep="last")
        else:
            latest = st

        unique_status = len(latest)

        if "download_status" in latest.columns:
            ok = int((latest["download_status"] == "success_metadata").sum())
            failed = int((latest["download_status"] == "failed").sum())

        if "texto_completo_url" in latest.columns:
            urls = int((latest["texto_completo_url"].astype(str).str.strip() != "").sum())

    remaining = max(total - ok, 0)
    pct = (ok / total * 100) if total else 0

    total_all += total
    ok_all += ok
    failed_all += failed
    remaining_all += remaining
    url_all += urls

    print(
        f"{year}: "
        f"total={total:,} | "
        f"ok={ok:,} | "
        f"failed_latest={failed:,} | "
        f"remaining={remaining:,} | "
        f"avance={pct:.2f}% | "
        f"texto_url={urls:,} | "
        f"status_rows={rows_status:,} | "
        f"status_unique={unique_status:,}"
    )

pct_all = (ok_all / total_all * 100) if total_all else 0

print("\n=== TOTAL ===")
print(
    f"total={total_all:,} | "
    f"ok={ok_all:,} | "
    f"failed_latest={failed_all:,} | "
    f"remaining={remaining_all:,} | "
    f"avance={pct_all:.2f}% | "
    f"texto_url={url_all:,}"
)
