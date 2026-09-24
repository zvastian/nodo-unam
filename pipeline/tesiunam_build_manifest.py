from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
import re
import time
import random
import argparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tesiunam.dgb.unam.mx"
SEARCH_PATH = "/cgi-bin/koha/opac-search.pl"

OUT_DIR = Path("recovery")
MANIFEST_DIR = OUT_DIR / "manifests"
RAW_DIR = OUT_DIR / "raw_manifest_pages"

for d in [OUT_DIR, MANIFEST_DIR, RAW_DIR]:
    d.mkdir(parents=True, exist_ok=True)

COUNT = 50
TIMEOUT = 40

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tesiunam-recovery-manifest/0.1",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.6",
})

def sleep_polite():
    time.sleep(random.uniform(0.8, 1.8))

def make_url(year, offset):
    # Para 2026 usamos q=de + limit=yr:2026 porque pubdate_direct mezcló años.
    if year == 2026:
        params = {
            "idx": "",
            "q": "de",
            "weight_search": "1",
            "count": str(COUNT),
            "sort_by": "relevance",
            "limit": f"yr:{year}",
            "offset": str(offset),
        }
    else:
        params = {
            "idx": "pubdate",
            "q": str(year),
            "weight_search": "1",
            "count": str(COUNT),
            "sort_by": "relevance",
            "offset": str(offset),
        }

    return BASE_URL + SEARCH_PATH + "?" + urlencode(params, doseq=True)

def fetch(url, retries=5):
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200 and r.text and len(r.text) > 1000:
                return r.text
            last_err = f"status={r.status_code}, len={len(r.text) if r.text else 0}"
        except Exception as e:
            last_err = repr(e)

        wait = min(40, attempt * 4) + random.random()
        print(f"  retry {attempt}/{retries}: {last_err}. wait={wait:.1f}s", flush=True)
        time.sleep(wait)

    raise RuntimeError(f"Fetch failed: {url} | {last_err}")

def norm(x):
    if not x:
        return ""
    return re.sub(r"\s+", " ", x).strip()

def page_signature(records):
    bits = []
    for r in records[:5]:
        bits.append(
            f"{r.get('biblionumber','')}|"
            f"{r.get('title_result','')[:60]}|"
            f"{r.get('authors_result','')[:60]}"
        )
    return " || ".join(bits)

def parse_results(html, target_year):
    soup = BeautifulSoup(html, "html.parser")
    full_text = norm(soup.get_text(" "))

    m_pages = re.search(r"página\s+(\d+)\s+de\s+(\d+)", full_text, flags=re.I)
    page_num = int(m_pages.group(1)) if m_pages else None
    total_pages = int(m_pages.group(2)) if m_pages else None

    last_offset = None
    for a in soup.select("a.page-link[href*='offset=']"):
        href = a.get("href") or ""
        text = a.get_text(" ", strip=True).lower()
        aria = (a.get("aria-label") or "").lower()
        if "último" in text or "ultimo" in text or "última" in aria or "ultima" in aria:
            qs = parse_qs(urlparse(href).query)
            if "offset" in qs:
                try:
                    last_offset = int(qs["offset"][0])
                except Exception:
                    pass

    has_next = False
    for a in soup.select("a.page-link[href*='offset=']"):
        txt = a.get_text(" ", strip=True).lower()
        aria = (a.get("aria-label") or "").lower()
        if "siguiente" in txt or "siguiente" in aria:
            has_next = True

    records = []

    for title_div in soup.select("div[id^='title_summary_']"):
        id_attr = title_div.get("id", "")
        m = re.search(r"title_summary_(\d+)", id_attr)
        biblionumber = m.group(1) if m else ""

        a_title = title_div.select_one("a.title")
        title_text = norm(a_title.get_text(" ", strip=True)) if a_title else ""
        detail_url = urljoin(BASE_URL, a_title.get("href")) if a_title and a_title.get("href") else ""

        row = title_div.find_parent("tr") or title_div.find_parent("div")

        year_result = None
        authors = []
        advisors = []
        institutions = []

        if row:
            y = row.select_one(".rda264_date")
            if y:
                yy = re.search(r"\d{4}", y.get_text(" ", strip=True))
                if yy:
                    year_result = int(yy.group(0))

            for li in row.select("ul.author li"):
                txt = norm(li.get_text(" ", strip=True))
                low = txt.lower()
                if "[sustentante]" in low:
                    authors.append(txt.replace("[sustentante]", "").strip())
                elif "[asesor]" in low:
                    advisors.append(txt.replace("[asesor]", "").strip())
                elif "[institución" in low or "[entidad participante]" in low:
                    institutions.append(txt)

        records.append({
            "target_year": target_year,
            "biblionumber": biblionumber,
            "detail_url": detail_url or f"{BASE_URL}/cgi-bin/koha/opac-detail.pl?biblionumber={biblionumber}",
            "title_result": title_text,
            "year_result": year_result,
            "authors_result": " | ".join(authors),
            "advisors_result": " | ".join(advisors),
            "institutions_result": " | ".join(institutions),
        })

    # Fallback por checkbox
    seen = {r["biblionumber"] for r in records if r["biblionumber"]}
    for cb in soup.select("input[name='biblionumber'][value]"):
        b = cb.get("value")
        if b and b not in seen:
            records.append({
                "target_year": target_year,
                "biblionumber": b,
                "detail_url": f"{BASE_URL}/cgi-bin/koha/opac-detail.pl?biblionumber={b}",
                "title_result": "",
                "year_result": None,
                "authors_result": "",
                "advisors_result": "",
                "institutions_result": "",
            })

    return {
        "page_num": page_num,
        "total_pages": total_pages,
        "last_offset": last_offset,
        "has_next": has_next,
        "records": records,
    }

def build_manifest_for_year(year, max_pages=None):
    out_csv = MANIFEST_DIR / f"year_{year}_manifest.csv"
    out_progress = MANIFEST_DIR / f"year_{year}_manifest_progress.csv"

    existing_biblios = set()
    if out_csv.exists():
        prev = pd.read_csv(out_csv, dtype=str).fillna("")
        if "biblionumber" in prev.columns:
            existing_biblios = set(prev["biblionumber"].astype(str))
        print(f"Manifest existente {year}: {len(existing_biblios):,} biblionumbers. Se continuará/actualizará.")

    rows = []
    offset = 0
    empty_pages = 0
    repeated_signatures = {}
    page_i = 0
    last_offset_seen = None

    while True:
        page_i += 1
        if max_pages and page_i > max_pages:
            print(f"MAX_PAGES alcanzado year={year}")
            break

        url = make_url(year, offset)
        print(f"YEAR={year} offset={offset} url={url}", flush=True)

        try:
            html = fetch(url)
        except Exception as e:
            print(f"ERROR year={year} offset={offset}: {e}", flush=True)
            empty_pages += 1
            if empty_pages >= 3:
                break
            offset += COUNT
            continue

        raw_path = RAW_DIR / f"year_{year}_offset_{offset}.html"
        raw_path.write_text(html, encoding="utf-8", errors="ignore")

        parsed = parse_results(html, year)
        recs = parsed["records"]

        last_offset = parsed["last_offset"]
        if last_offset is not None:
            last_offset_seen = last_offset

        sig = page_signature(recs)
        repeated_signatures[sig] = repeated_signatures.get(sig, 0) + 1

        valid_recs = []
        for r in recs:
            r["offset"] = offset
            r["page_num"] = parsed["page_num"]
            r["total_pages"] = parsed["total_pages"]
            r["last_offset"] = parsed["last_offset"]
            r["raw_path"] = str(raw_path)

            if r["year_result"] != year:
                r["manifest_status"] = "out_of_year"
            elif not r["biblionumber"]:
                r["manifest_status"] = "missing_biblionumber"
            elif r["biblionumber"] in existing_biblios:
                r["manifest_status"] = "already_in_manifest"
            else:
                r["manifest_status"] = "pending_detail"
                existing_biblios.add(r["biblionumber"])
                valid_recs.append(r)

            rows.append(r)

        print(
            f"  page_records={len(recs)} new_pending={len(valid_recs)} "
            f"page={parsed['page_num']} total_pages={parsed['total_pages']} "
            f"last_offset={parsed['last_offset']} has_next={parsed['has_next']}",
            flush=True
        )

        # Guardado incremental
        if rows:
            df_new = pd.DataFrame(rows)
            if out_csv.exists():
                old = pd.read_csv(out_csv, dtype=str).fillna("")
                df_all = pd.concat([old, df_new], ignore_index=True)
                df_all = df_all.drop_duplicates(subset=["biblionumber"], keep="first")
            else:
                df_all = df_new.drop_duplicates(subset=["biblionumber"], keep="first")

            df_all.to_csv(out_csv, index=False, encoding="utf-8")

            progress = pd.DataFrame([{
                "year": year,
                "offset": offset,
                "rows_in_manifest": len(df_all),
                "pending_detail": int((df_all["manifest_status"] == "pending_detail").sum()) if "manifest_status" in df_all else None,
                "out_of_year": int((df_all["manifest_status"] == "out_of_year").sum()) if "manifest_status" in df_all else None,
                "last_offset_seen": last_offset_seen,
            }])
            progress.to_csv(out_progress, index=False, encoding="utf-8")

            rows = []

        if len(recs) == 0:
            empty_pages += 1
        else:
            empty_pages = 0

        if empty_pages >= 3:
            print(f"STOP year={year}: 3 páginas vacías.")
            break

        if sig and repeated_signatures[sig] >= 3:
            print(f"STOP year={year}: firma repetida 3 veces.")
            break

        if last_offset_seen is not None and offset >= last_offset_seen:
            print(f"STOP year={year}: offset >= last_offset ({offset} >= {last_offset_seen}).")
            break

        if not parsed["has_next"] and parsed["total_pages"] is not None and parsed["page_num"] == parsed["total_pages"]:
            print(f"STOP year={year}: última página detectada.")
            break

        # Caso año chico sin paginación
        if parsed["total_pages"] is None and len(recs) < COUNT:
            print(f"STOP year={year}: menos de COUNT resultados y sin paginación.")
            break

        offset += COUNT
        sleep_polite()

    final = pd.read_csv(out_csv, dtype=str).fillna("")
    print(f"\nMANIFEST YEAR {year} listo: {out_csv}")
    print(final["manifest_status"].value_counts(dropna=False).to_string())
    print(f"Total unique biblionumber rows: {len(final):,}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()

    for year in args.years:
        build_manifest_for_year(year, max_pages=args.max_pages)

if __name__ == "__main__":
    main()
