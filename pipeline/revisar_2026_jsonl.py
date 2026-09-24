import json
from pathlib import Path

p = Path("recovery/details/jsonl/year_2026_details.jsonl")

with p.open("r", encoding="utf-8") as f:
    for i, line in enumerate(f, start=1):
        obj = json.loads(line)

        print("\n" + "="*100)
        print("biblionumber:", obj.get("biblionumber"))
        print("status:", obj.get("download_status"))
        print("doc_number:", obj.get("doc_number"))
        print("title_result:", obj.get("title_result"))
        print("title_detail:", obj.get("title_detail"))
        print("year_detail:", obj.get("year_detail"))
        print("authors_result:", obj.get("authors_result"))
        print("authors_detail:", obj.get("authors_detail"))
        print("institutions_detail:", obj.get("institutions_detail"))

        raw = obj.get("raw_fields", {})
        print("\nRAW FIELD KEYS:")
        print(list(raw.keys()))

        print("\nRAW FIELDS SELECTED:")
        for k, v in raw.items():
            lk = k.lower()
            if (
                "recurso" in lk
                or "electr" in lk
                or "texto" in lk
                or "url" in lk
                or "acceso" in lk
                or "dispon" in lk
                or "nota" in lk
                or "descrip" in lk
                or "tipo" in lk
            ):
                print(f"{k}: {str(v)[:500]}")

        sample = obj.get("detail_text_sample", "")
        print("\nTEXT SAMPLE HAS doc_number?", "doc_number=" in sample)
        print("TEXT SAMPLE HAS WEB-FULL?", "WEB-FULL" in sample)
        print("TEXT SAMPLE HAS Texto completo?", "Texto completo" in sample or "texto completo" in sample.lower())

        if i >= 3:
            break
