from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import random
import re
import threading
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tesiunam.dgb.unam.mx"
MANIFEST_DIR = Path("recovery/manifests")
OUT_DIR = Path("recovery/marc_details")
JSONL_DIR = OUT_DIR / "jsonl"
STATUS_DIR = OUT_DIR / "status"
FAILED_DIR = OUT_DIR / "failed"
RAW_DIR = OUT_DIR / "raw_marc_pages"

for d in [OUT_DIR, JSONL_DIR, STATUS_DIR, FAILED_DIR, RAW_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MIN_SLEEP_BETWEEN_REQUESTS = 0.3
MAX_SLEEP_BETWEEN_REQUESTS = 1.2
PAUSE_EVERY_N_SUCCESS = 50
PAUSE_SECONDS_MIN = 60
PAUSE_SECONDS_MAX = 120
TIMEOUT = 12
DEFAULT_WORKERS = 3

thread_local = threading.local()
write_lock = threading.Lock()

def get_session():
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tesiunam-marc-recovery/0.2",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.6",
            "Connection": "close",
        })
        thread_local.session = s
    return thread_local.session

def norm(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

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

            if "SSLEOFError" in last_err or "SSL" in last_err or "Connection" in last_err:
                try:
                    thread_local.session.close()
                    del thread_local.session
                except Exception:
                    pass

        wait = min(10, attempt * 3) + random.random()
        time.sleep(wait)

    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        r = requests.get(
            url,
            timeout=TIMEOUT,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tesiunam-marc-recovery/0.2",
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

def marc_url(biblionumber):
    return f"{BASE_URL}/cgi-bin/koha/opac-MARCdetail.pl?biblionumber={biblionumber}"

def parse_marc_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.marc")

    if table is None:
        table = soup.find("table")

    rows = []
    if table:
        for tr in table.find_all("tr"):
            txt = norm(tr.get_text(" ", strip=True))
            if txt:
                rows.append(txt)

    fields = []
    current = None

    # Ejemplo de header:
    # 245 10 - TITULO
    # 856 4# - ACCESO ELECTRÓNICO
    # 000 -LIDER
    header_re = re.compile(r"^(\d{3})\s*([0-9A-Za-z# ]{0,3})\s*-\s*(.+)$")

    for row in rows:
        m = header_re.match(row)
        if m:
            if current:
                fields.append(current)
            current = {
                "tag": m.group(1),
                "ind": norm(m.group(2)),
                "label": norm(m.group(3)),
                "subfields": []
            }
        else:
            if current is None:
                continue

            # Separar "Etiqueta valor" de forma conservadora.
            # Como Koha ya imprime algo tipo:
            # "Título Caracterización..."
            current["subfields"].append(row)

    if current:
        fields.append(current)

    return fields

def first_subfield(fields, tag, startswith=None, contains=None):
    vals = []
    for f in fields:
        if f["tag"] != tag:
            continue
        for sf in f["subfields"]:
            s = norm(sf)
            if startswith and not s.lower().startswith(startswith.lower()):
                continue
            if contains and contains.lower() not in s.lower():
                continue
            vals.append(s)
    return vals[0] if vals else ""

def all_subfields(fields, tag, startswith=None, contains=None):
    vals = []
    for f in fields:
        if f["tag"] != tag:
            continue
        for sf in f["subfields"]:
            s = norm(sf)
            if startswith and not s.lower().startswith(startswith.lower()):
                continue
            if contains and contains.lower() not in s.lower():
                continue
            vals.append(s)
    return vals

def strip_prefix(s, prefixes):
    s = norm(s)
    for p in prefixes:
        if s.lower().startswith(p.lower()):
            return norm(s[len(p):])
    return s

def extract_name_and_role_from_field(field):
    name = ""
    role = ""

    for sf in field.get("subfields", []):
        s = norm(sf)
        low = s.lower()

        if low.startswith("nombre personal "):
            name = strip_prefix(s, ["Nombre personal "]).strip(" ,")
        elif low.startswith("término relacionador "):
            role = strip_prefix(s, ["Término relacionador "]).strip()
        elif low.startswith("término de relación "):
            role = strip_prefix(s, ["Término de relación "]).strip()

    return name, role

def extract_corp_and_role_from_field(field):
    name = ""
    role = ""

    for sf in field.get("subfields", []):
        s = norm(sf)
        low = s.lower()

        if low.startswith("nombre corporativo"):
            # "Nombre corporativo o de jurisdicción como elemento de entrada Universidad..."
            marker = "como elemento de entrada "
            if marker in low:
                idx = low.find(marker)
                name = s[idx + len(marker):].strip(" ,")
            else:
                name = s
        elif low.startswith("término de relación "):
            role = strip_prefix(s, ["Término de relación "]).strip()

    return name, role

def parse_marc_detail(html):
    fields = parse_marc_rows(html)

    system_number = strip_prefix(
        first_subfield(fields, "035", startswith="Número de control del sistema"),
        ["Número de control del sistema "]
    )

    autor = ""
    sustentantes = []
    asesores = []
    otros_personales = []

    for f in fields:
        if f["tag"] in {"100", "700"}:
            name, role = extract_name_and_role_from_field(f)
            if not name:
                continue

            role_low = role.lower()

            if f["tag"] == "100":
                autor = name

            if "sustentante" in role_low:
                sustentantes.append(name)
            elif "asesor" in role_low or "director" in role_low or "tutor" in role_low:
                asesores.append(name)
            else:
                otros_personales.append({"name": name, "role": role, "tag": f["tag"]})

    titulo = strip_prefix(
        first_subfield(fields, "245", startswith="Título"),
        ["Título "]
    )

    responsabilidad = strip_prefix(
        first_subfield(fields, "245", startswith="Mención de responsabilidad"),
        ["Mención de responsabilidad, etc. ", "Mención de responsabilidad "]
    )

    anio_produccion = strip_prefix(
        first_subfield(fields, "264", startswith="Año de producción"),
        ["Año de producción "]
    )

    extension = strip_prefix(
        first_subfield(fields, "300", startswith="Extensión"),
        ["Extensión "]
    )

    otros_detalles_fisicos = strip_prefix(
        first_subfield(fields, "300", startswith="Otros detalles físicos"),
        ["Otros detalles físicos "]
    )

    tipo_soporte = strip_prefix(
        first_subfield(fields, "338", startswith="Término de tipo de transporte"),
        ["Término de tipo de transporte "]
    )

    archivo_tipo = strip_prefix(
        first_subfield(fields, "347", startswith="Tipo de archivo"),
        ["Tipo de archivo "]
    )

    archivo_formato = strip_prefix(
        first_subfield(fields, "347", startswith="Formato de codificación"),
        ["Formato de codificación "]
    )

    archivo_tamano = strip_prefix(
        first_subfield(fields, "347", startswith="Tamaño del archivo"),
        ["Tamaño del archivo "]
    )

    tipo_estudios = strip_prefix(
        first_subfield(fields, "502", startswith="Tipo de estudios"),
        ["Tipo de estudios "]
    )

    institucion_otorgante_502 = strip_prefix(
        first_subfield(fields, "502", startswith="Nombre de la institución otorgante"),
        ["Nombre de la institución otorgante "]
    ).strip(" ,")

    anio_obtencion = strip_prefix(
        first_subfield(fields, "502", startswith="Año de obtención del título"),
        ["Año de obtención del título "]
    )

    plantel_marc = strip_prefix(
        first_subfield(fields, "502", startswith="Escuela/Facultad/Programa"),
        ["Escuela/Facultad/Programa "]
    ).strip(" ,")

    restricciones = strip_prefix(
        first_subfield(fields, "506", startswith="Terminología normalizada"),
        ["Terminología normalizada para restricción de acceso "]
    )

    corporativos = []
    instituciones_otorgantes = []
    entidades_participantes = []

    for f in fields:
        if f["tag"] == "710":
            name, role = extract_corp_and_role_from_field(f)
            if not name:
                continue

            corporativos.append({"name": name, "role": role})
            role_low = role.lower()

            if "otorga" in role_low:
                instituciones_otorgantes.append(name)
            elif "entidad participante" in role_low:
                entidades_participantes.append(name)

    temas = []
    for tag in ["650", "651", "653", "600", "610", "611", "630"]:
        for sf in all_subfields(fields, tag):
            temas.append(sf)

    texto_completo_url = ""
    texto_completo_label = ""
    texto_completo_nota = ""

    for f in fields:
        if f["tag"] == "856":
            for sf in f["subfields"]:
                s = norm(sf)
                low = s.lower()

                if low.startswith("identificador uniforme del recurso"):
                    # "Identificador Uniforme del Recurso (“URI”) https://..."
                    m = re.search(r"https?://\S+", s)
                    if m:
                        texto_completo_url = m.group(0)
                elif low.startswith("texto del vínculo") or low.startswith("texto del vinculo"):
                    texto_completo_label = strip_prefix(s, ["Texto del vínculo ", "Texto del vinculo "])
                elif low.startswith("nota dirigida al público") or low.startswith("nota dirigida al publico"):
                    texto_completo_nota = strip_prefix(s, ["Nota dirigida al público ", "Nota dirigida al publico "])

    return {
        "system_number": system_number,
        "autor_marc": autor,
        "sustentantes_marc": " | ".join(dict.fromkeys(sustentantes)),
        "asesores_marc": " | ".join(dict.fromkeys(asesores)),
        "otros_personales_marc_json": json.dumps(otros_personales, ensure_ascii=False),
        "titulo_marc": titulo,
        "responsabilidad_marc": responsabilidad,
        "anio_produccion_marc": anio_produccion,
        "extension_marc": extension,
        "otros_detalles_fisicos_marc": otros_detalles_fisicos,
        "tipo_soporte_marc": tipo_soporte,
        "archivo_tipo_marc": archivo_tipo,
        "archivo_formato_marc": archivo_formato,
        "archivo_tamano_marc": archivo_tamano,
        "tipo_estudios_marc": tipo_estudios,
        "institucion_otorgante_502_marc": institucion_otorgante_502,
        "anio_obtencion_marc": anio_obtencion,
        "plantel_marc": plantel_marc,
        "restricciones_marc": restricciones,
        "instituciones_otorgantes_marc": " | ".join(dict.fromkeys(instituciones_otorgantes)),
        "entidades_participantes_marc": " | ".join(dict.fromkeys(entidades_participantes)),
        "corporativos_marc_json": json.dumps(corporativos, ensure_ascii=False),
        "temas_marc": " | ".join(dict.fromkeys(temas)),
        "texto_completo_url": texto_completo_url,
        "texto_completo_label": texto_completo_label,
        "texto_completo_nota": texto_completo_nota,
        "has_texto_completo_url": bool(texto_completo_url),
        "marc_fields_json": json.dumps(fields, ensure_ascii=False),
    }

def load_done_biblionumbers(status_path):
    if not status_path.exists():
        return set()

    try:
        df = pd.read_csv(status_path, dtype=str).fillna("")
        latest = df.drop_duplicates(subset=["biblionumber"], keep="last")
        ok = latest[latest["download_status"].isin(["success_metadata"])]
        return set(ok["biblionumber"].astype(str))
    except Exception:
        return set()

def process_one(row, out_jsonl, out_failed, out_status, save_raw=False):
    biblionumber = str(row.get("biblionumber", "")).strip()
    url = marc_url(biblionumber)

    base = {
        "target_year": row.get("target_year", ""),
        "biblionumber": biblionumber,
        "marc_url": url,
        "detail_url": row.get("detail_url", ""),
        "title_result": row.get("title_result", ""),
        "year_result": row.get("year_result", ""),
        "authors_result": row.get("authors_result", ""),
        "advisors_result": row.get("advisors_result", ""),
        "institutions_result": row.get("institutions_result", ""),
    }

    try:
        time.sleep(random.uniform(MIN_SLEEP_BETWEEN_REQUESTS, MAX_SLEEP_BETWEEN_REQUESTS))
        html = fetch(url)
        parsed = parse_marc_detail(html)

        raw_path = ""
        if save_raw and biblionumber:
            raw_path = RAW_DIR / f"{biblionumber}_marc.html"
            raw_path.write_text(html, encoding="utf-8", errors="ignore")

        obj = {
            **base,
            **parsed,
            "download_status": "success_metadata",
            "raw_marc_path": str(raw_path) if raw_path else "",
            "downloaded_at_unix": time.time(),
        }

        append_jsonl(out_jsonl, obj)

        status_row = {
            **base,
            "download_status": "success_metadata",
            "system_number": parsed.get("system_number", ""),
            "titulo_marc": parsed.get("titulo_marc", ""),
            "anio_produccion_marc": parsed.get("anio_produccion_marc", ""),
            "tipo_estudios_marc": parsed.get("tipo_estudios_marc", ""),
            "plantel_marc": parsed.get("plantel_marc", ""),
            "texto_completo_url": parsed.get("texto_completo_url", ""),
            "has_texto_completo_url": parsed.get("has_texto_completo_url", False),
            "error": "",
        }

        append_status(out_status, status_row)
        return "success_metadata"

    except Exception as e:
        fail = {
            **base,
            "download_status": "failed",
            "system_number": "",
            "titulo_marc": "",
            "anio_produccion_marc": "",
            "tipo_estudios_marc": "",
            "plantel_marc": "",
            "texto_completo_url": "",
            "has_texto_completo_url": False,
            "error": repr(e),
        }
        append_jsonl(out_failed, fail)
        append_status(out_status, fail)
        return "failed"

def run_year(year, workers, limit=None, save_raw=False):
    manifest_path = MANIFEST_DIR / f"year_{year}_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No encontré manifest: {manifest_path}")

    out_jsonl = JSONL_DIR / f"year_{year}_marc_details.jsonl"
    out_failed = FAILED_DIR / f"year_{year}_marc_failed.jsonl"
    out_status = STATUS_DIR / f"year_{year}_marc_status.csv"

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")

    if "manifest_status" in manifest.columns:
        todo = manifest[manifest["manifest_status"] == "pending_detail"].copy()
    else:
        todo = manifest.copy()

    done = load_done_biblionumbers(out_status)
    if done:
        before = len(todo)
        todo = todo[~todo["biblionumber"].astype(str).isin(done)].copy()
        print(f"Year {year}: ya había {len(done):,} success_metadata; quedan {len(todo):,} de {before:,}")

    if limit:
        todo = todo.head(limit).copy()

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
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--save-raw", action="store_true")
    args = parser.parse_args()

    for year in args.years:
        run_year(
            year=year,
            workers=args.workers,
            limit=args.limit,
            save_raw=args.save_raw
        )

if __name__ == "__main__":
    main()
