import json
from pathlib import Path

p = Path("recovery/details/jsonl/year_1905_details.jsonl")

with p.open("r", encoding="utf-8") as f:
    for i, line in enumerate(f, start=1):
        obj = json.loads(line)
        print("biblionumber:", obj.get("biblionumber"))
        print("status:", obj.get("download_status"))
        print("doc_number:", obj.get("doc_number"))
        print("title_detail:", obj.get("title_detail"))
        print("year_detail:", obj.get("year_detail"))
        print("authors_detail:", obj.get("authors_detail"))
        print("advisors_detail:", obj.get("advisors_detail"))
        print("institutions_detail:", obj.get("institutions_detail"))
        print("raw_fields keys:", list(obj.get("raw_fields", {}).keys())[:30])
        print("text sample:", obj.get("detail_text_sample", "")[:500])
        print("-" * 80)

        if i >= 2:
            break
