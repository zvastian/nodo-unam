from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import argparse
import json
import random
import re
import threading
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import pyarrow.parquet as pq
except Exception:
    pq = None

BASE_URL = "https://tesiunam.dgb.unam.mx"
MANIFEST_DIR = Path("recovery/manifests")
OUT_DIR = Path("recovery/details")
JSONL_DIR = OUT_DIR / "jsonl"
STATUS_DIR = OUT_DIR / "status"
FAILED_DIR = OUT_DIR / "failed"
RAW_DIR = OUT_DIR / "raw_detail_pages"

for d in [OUT_DIR, JSONL_DIR, STATUS_DIR, FAILED_DIR, RAW_DIR]:
    d.mkdir(parents=True, exist_ok=True)

TIMEOUT = 15
DEFAULT_WORKERS = 12

thread_local = threading.local()
write_lock = threading.Lock()

def get_session():
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tesiunam-detail-recovery/0.1",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.6",
        })
        thread_local.session = s
    return thread_local.session

def norm(x):
    if not x:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def safe_key(x):
    x = norm(x).lower()
    x = x.strip(":：")
    x = re.sub(r"\s+", " ", x)
    return x

def fetch(url, retries=2):
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            s = get_session()
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code == 200 and r.text and len(r.text) > 1000:
                return r.text

            last_err = f"status={r.status_code}, len={len(r.text) if r.text else 0}"

        except Exception as e:
            last_err = repr(e)

            # Si el servidor corta SSL, destruye la sesión del thread.
            if "SSLEOFError" in last_err or "SSL" in last_err or "Connection" in last_err:
                try:
                    thread_local.session.close()
                    del thread_local.session
                except Exception:
                    pass

        wait = min(10, attempt * 3) + random.random()
        time.sleep(wait)

    # Fallback técnico: request nuevo, sin sesión persistente y sin verificar SSL.
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        r = requests.get(
            url,
            timeout=TIMEOUT,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tesiunam-detail-recovery/0.1",
                "Accept-Language": "es-MX,es;q=0.9,en;q=0.6",
                "Connection": "close",
            },
        )

        if r.status_code == 200 and r.text and len(r.text) > 1000:
            return r.text

        last_err = f"fallback status={r.status_code}, len={len(r.text) if r.text else 0}"

    except Exception as e:
        last_err = f"fallback error={repr(e)}"

    raise RuntimeError(f"Fetch failed fast: {url} | {last_err}")    
    last_err = None
    s = get_session()

    for attempt in range(1, retries + 1):
        try:
            r = s.get(url, timeout=TIMEOUT)
            if r.status_code == 200 and r.text and len(r.text) > 1000:
                return r.text
            last_err = f"status={r.status_code}, len={len(r.text) if r.text else 0}"
        except Exception as e:
            last_err = repr(e)

        wait = min(45, attempt * 4) + random.random()
        time.sleep(wait)

    raise RuntimeError(f"Fetch failed: {url} | {last_err}")

def extract_doc_number(text):
    if not text:
        return ""
    m = re.search(r"doc_number=(\d+)", text)
    if m:
        return m.group(1)
    return ""

def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")

    full_text = norm(soup.get_text(" "))

    title = ""
    h1 = soup.select_one("h1.title")
    if h1:
        title = norm(h1.get_text(" ", strip=True))
    else:
        title_tag = soup.select_one("title")
        title = norm(title_tag.get_text(" ", strip=True)) if title_tag else ""

    # Extraer links electrónicos y doc_number
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        txt = norm(a.get_text(" ", strip=True))
        abs_href = urljoin(BASE_URL, href)
        if "doc_number=" in abs_href or "WEB-FULL" in abs_href or "service_type=MEDIA" in abs_href:
            links.append({
                "text": txt,
                "href": abs_href,
            })

    link_extraido_regex = ""
    doc_number = ""

    for item in links:
        href = item["href"]
        if not link_extraido_regex:
            link_extraido_regex = href
        if not doc_number:
            doc_number = extract_doc_number(href)

    if not doc_number:
        doc_number = extract_doc_number(html)

    # Extraer campos tipo etiqueta: valor de forma genérica
    raw_fields = {}

    # Koha suele tener labels dentro de spans/strongs; tomamos el texto del padre
    for tag in soup.find_all(["span", "strong", "label"]):
        label = norm(tag.get_text(" ", strip=True))
        if not label:
            continue

        # labels bibliográficos suelen terminar con :
        if not label.endswith(":"):
            continue

        parent = tag.find_parent(["li", "p", "div", "tr"])
        if not parent:
            continue

        parent_text = norm(parent.get_text(" ", strip=True))
        value = parent_text.replace(label, "", 1).strip(" :")

        key = safe_key(label)
        if key and value and len(value) > 0:
            if key in raw_fields:
                if value not in raw_fields[key]:
                    raw_fields[key] = raw_fields[key] + " | " + value
            else:
                raw_fields[key] = value

    # Autores/asesores/instituciones si aparecen como lista de autores
    authors = []
    advisors = []
    institutions = []

    for li in soup.select("ul.author li"):
        txt = norm(li.get_text(" ", strip=True))
        low = txt.lower()
        if "[sustentante]" in low:
            authors.append(txt.replace("[sustentante]", "").strip())
        elif "[asesor]" in low:
            advisors.append(txt.replace("[asesor]", "").strip())
        elif "[institución" in low or "[entidad participante]" in low:
            institutions.append(txt)

    # Año visible
    year_detail = ""
    y = soup.select_one(".rda264_date")
    if y:
        m = re.search(r"\d{4}", y.get_text(" ", strip=True))
        if m:
            year_detail = m.group(0)

    if not year_detail:
        # fallback con texto completo
        m = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", full_text)
        if m:
            year_detail = m.group(1)

    return {
        "title_detail": title,
        "year_detail": year_detail,
        "doc_number": doc_number,
        "link_extraido_regex": link_extraido_regex,
        "authors_detail": " | ".join(authors),
        "advisors_detail": " | ".join(advisors),
        "institutions_detail": " | ".join(institutions),
        "raw_fields": raw_fields,
        "detail_text_sample": full_text[:8000],
    }

def load_existing_doc_numbers(base_path):
    existing = set()

    if not base_path:
        return existing

    p = Path(base_path)
    if not p.exists():
        print(f"Base no encontrada para comparar doc_number: {p}")
        return existing

    if pq is None:
        print("pyarrow no disponible; no se comparará contra base.")
        return existing

    print(f"Cargando doc_numbers existentes desde {p} ...")

    pf = pq.ParquetFile(p)

    if "link_extraido_regex" not in pf.schema_arrow.names:
        print("La base no tiene link_extraido_regex; no se podrá comparar doc_number.")
        return existing

    for batch in pf.iter_batches(batch_size=50_000, columns=["link_extraido_regex"]):
        arr = batch.column(0).to_pylist()
        for v in arr:
            if not v:
                continue
            m = re.search(r"doc_number=(\d+)", str(v))
            if m:
                existing.add(m.group(1))

    print(f"doc_numbers existentes cargados: {len(existing):,}")
    return existing

def load_done_biblionumbers(status_path):
    done = set()

    if not status_path.exists():
        return done

    try:
        df = pd.read_csv(status_path, dtype=str).fillna("")
        if "biblionumber" in df.columns:
            ok = df[df["download_status"].isin(["success", "already_in_base_by_doc_number", "new_or_missing_by_doc_number", "no_doc_number"])]
            done = set(ok["biblionumber"].astype(str))
    except Exception:
        pass

    return done

def append_jsonl(path, obj):
    with write_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def append_status(path, row):
    with write_lock:
        exists = path.exists()
        pd.DataFrame([row]).to_csv(
            path,
            mode="a",
            header=not exists,
            index=False,
            encoding="utf-8"
        )

def process_one(row, existing_doc_numbers, out_jsonl, out_failed, out_status, save_raw=False):
    biblionumber = str(row.get("biblionumber", "")).strip()
    url = str(row.get("detail_url", "")).strip()

    if not url and biblionumber:
        url = f"{BASE_URL}/cgi-bin/koha/opac-detail.pl?biblionumber={biblionumber}"

    base_status = {
        "target_year": row.get("target_year", ""),
        "biblionumber": biblionumber,
        "detail_url": url,
        "title_result": row.get("title_result", ""),
        "year_result": row.get("year_result", ""),
        "authors_result": row.get("authors_result", ""),
    }

    try:
        html = fetch(url)
        parsed = parse_detail(html)

        doc_number = parsed.get("doc_number", "")

        if doc_number and doc_number in existing_doc_numbers:
            download_status = "already_in_base_by_doc_number"
        elif doc_number:
            download_status = "new_or_missing_by_doc_number"
        else:
            download_status = "no_doc_number"

        if save_raw and biblionumber:
            raw_path = RAW_DIR / f"{biblionumber}.html"
            raw_path.write_text(html, encoding="utf-8", errors="ignore")
        else:
            raw_path = ""

        obj = {
            **base_status,
            **parsed,
            "download_status": download_status,
            "raw_detail_path": str(raw_path) if raw_path else "",
            "downloaded_at_unix": time.time(),
        }

        append_jsonl(out_jsonl, obj)

        status_row = {
            **base_status,
            "download_status": download_status,
            "doc_number": doc_number,
            "title_detail": parsed.get("title_detail", ""),
            "year_detail": parsed.get("year_detail", ""),
            "raw_detail_path": str(raw_path) if raw_path else "",
            "error": "",
        }
        append_status(out_status, status_row)

        return download_status

    except Exception as e:
        fail = {
            **base_status,
            "download_status": "failed",
            "doc_number": "",
            "title_detail": "",
            "year_detail": "",
            "raw_detail_path": "",
            "error": repr(e),
        }
        append_jsonl(out_failed, fail)
        append_status(out_status, fail)
        return "failed"

def run_year(year, workers, base_path, limit=None, save_raw=False):
    manifest_path = MANIFEST_DIR / f"year_{year}_manifest.csv"

    if not manifest_path.exists():
        raise FileNotFoundError(f"No encontré manifest: {manifest_path}")

    out_jsonl = JSONL_DIR / f"year_{year}_details.jsonl"
    out_failed = FAILED_DIR / f"year_{year}_failed.jsonl"
    out_status = STATUS_DIR / f"year_{year}_detail_status.csv"

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")

    if "manifest_status" in manifest.columns:
        todo = manifest[manifest["manifest_status"] == "pending_detail"].copy()
    else:
        todo = manifest.copy()

    done = load_done_biblionumbers(out_status)
    if done:
        before = len(todo)
        todo = todo[~todo["biblionumber"].astype(str).isin(done)].copy()
        print(f"Year {year}: ya había {len(done):,} descargados; quedan {len(todo):,} de {before:,}")

    if limit:
        todo = todo.head(limit).copy()

    existing_doc_numbers = load_existing_doc_numbers(base_path)

    print(f"\nYEAR {year}")
    print(f"Manifest rows pending: {len(todo):,}")
    print(f"Workers: {workers}")
    print(f"Output JSONL: {out_jsonl}")
    print(f"Output status: {out_status}")

    if todo.empty:
        print("Nada que descargar.")
        return

    counts = {}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [
            ex.submit(
                process_one,
                row.to_dict(),
                existing_doc_numbers,
                out_jsonl,
                out_failed,
                out_status,
                save_raw
            )
            for _, row in todo.iterrows()
        ]

        total = len(futures)

        for i, fut in enumerate(as_completed(futures), start=1):
            status = fut.result()
            counts[status] = counts.get(status, 0) + 1

            if i % 25 == 0 or i == total:
                print(f"YEAR={year} done={i:,}/{total:,} counts={counts}", flush=True)

    print(f"\nYEAR {year} terminado.")
    print(counts)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--base", type=str, default="base6.parquet")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--save-raw", action="store_true")
    args = parser.parse_args()

    base_path = args.base if Path(args.base).exists() else None
    if base_path is None:
        print("No se encontró base local. Se descargará detalle, pero no se clasificará contra doc_number existente.")

    for year in args.years:
        run_year(
            year=year,
            workers=args.workers,
            base_path=base_path,
            limit=args.limit,
            save_raw=args.save_raw
        )

if __name__ == "__main__":
    main()
