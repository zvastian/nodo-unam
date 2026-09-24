import subprocess
import time
import random
from pathlib import Path
import pandas as pd
from datetime import datetime

# =========================
# CONFIGURACIÓN
# =========================

YEARS = [
    1913,
    1960,
    1980,
    1985,
    1987,
    1989,
    1995,
    2026,
]

WORKERS = 3
BATCH_LIMIT = 500

SLEEP_MIN_SECONDS = 30
SLEEP_MAX_SECONDS = 90

LONG_PAUSE_MIN_SECONDS = 600
LONG_PAUSE_MAX_SECONDS = 1200

FAILED_RATE_THRESHOLD = 0.10

# Máximo de batches por corrida completa del orquestador.
# Puedes subirlo o poner None si quieres que siga hasta terminar.
MAX_TOTAL_BATCHES = None

PYTHON = "python"
DOWNLOADER = "tesiunam_marc_downloader.py"

MANIFEST_DIR = Path("recovery/manifests")
STATUS_DIR = Path("recovery/marc_details/status")
LOG_DIR = Path("recovery/marc_details/orchestrator_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_year_progress(year):
    manifest_path = MANIFEST_DIR / f"year_{year}_manifest.csv"
    status_path = STATUS_DIR / f"year_{year}_marc_status.csv"

    if not manifest_path.exists():
        return {
            "year": year,
            "total": 0,
            "ok": 0,
            "failed": 0,
            "remaining": 0,
            "manifest_exists": False,
        }

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")

    if "manifest_status" in manifest.columns:
        total = int((manifest["manifest_status"] == "pending_detail").sum())
    else:
        total = len(manifest)

    ok = 0
    failed = 0

    if status_path.exists():
        st = pd.read_csv(status_path, dtype=str).fillna("")
        latest = st.drop_duplicates(subset=["biblionumber"], keep="last")
        ok = int((latest["download_status"] == "success_metadata").sum())
        failed = int((latest["download_status"] == "failed").sum())

    remaining = max(total - ok, 0)

    return {
        "year": year,
        "total": total,
        "ok": ok,
        "failed": failed,
        "remaining": remaining,
        "manifest_exists": True,
    }


def run_batch(year):
    before = get_year_progress(year)

    cmd = [
        PYTHON,
        DOWNLOADER,
        "--years",
        str(year),
        "--workers",
        str(WORKERS),
        "--limit",
        str(BATCH_LIMIT),
    ]

    log(f"RUN year={year} cmd={' '.join(cmd)}")
    log(
        f"BEFORE year={year} total={before['total']:,} "
        f"ok={before['ok']:,} failed={before['failed']:,} remaining={before['remaining']:,}"
    )

    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

        duration = round(time.time() - start, 1)

        log(f"RETURN year={year} code={result.returncode} duration={duration}s")

        if result.stdout:
            log("STDOUT:")
            for line in result.stdout.splitlines()[-20:]:
                log("  " + line)

        if result.stderr:
            log("STDERR:")
            for line in result.stderr.splitlines()[-20:]:
                log("  " + line)

    except KeyboardInterrupt:
        log("Interrumpido por usuario.")
        raise
    except Exception as e:
        log(f"ERROR ejecutando batch year={year}: {repr(e)}")

    after = get_year_progress(year)

    new_ok = after["ok"] - before["ok"]
    new_failed = max(after["failed"] - before["failed"], 0)
    attempted = max(new_ok + new_failed, 1)
    failed_rate = new_failed / attempted

    log(
        f"AFTER year={year} total={after['total']:,} "
        f"ok={after['ok']:,} failed={after['failed']:,} remaining={after['remaining']:,} "
        f"new_ok={new_ok:,} new_failed={new_failed:,} failed_rate={failed_rate:.2%}"
    )

    return after, new_ok, new_failed, failed_rate


def dedupe_status_files():
    for p in STATUS_DIR.glob("year_*_marc_status.csv"):
        try:
            df = pd.read_csv(p, dtype=str).fillna("")
            latest = df.drop_duplicates(subset=["biblionumber"], keep="last")
            if len(latest) < len(df):
                backup = p.with_suffix(".before_orchestrator_dedup.csv")
                df.to_csv(backup, index=False, encoding="utf-8")
                latest.to_csv(p, index=False, encoding="utf-8")
                log(f"DEDUP {p}: {len(df):,} -> {len(latest):,}")
        except Exception as e:
            log(f"DEDUP ERROR {p}: {repr(e)}")


def sleep_normal():
    seconds = random.randint(SLEEP_MIN_SECONDS, SLEEP_MAX_SECONDS)
    log(f"SLEEP normal {seconds}s")
    time.sleep(seconds)


def sleep_long():
    seconds = random.randint(LONG_PAUSE_MIN_SECONDS, LONG_PAUSE_MAX_SECONDS)
    log(f"SLEEP largo por posible bloqueo {seconds}s")
    time.sleep(seconds)


def main():
    log("=== ORQUESTADOR MARC TESIUNAM INICIADO ===")
    log(f"YEARS={YEARS}")
    log(f"WORKERS={WORKERS} BATCH_LIMIT={BATCH_LIMIT}")
    log(f"LOG_FILE={LOG_FILE}")

    total_batches = 0

    while True:
        dedupe_status_files()

        progress_all = [get_year_progress(y) for y in YEARS]
        pending_years = [p for p in progress_all if p["manifest_exists"] and p["remaining"] > 0]

        log("=== PROGRESO GLOBAL ===")
        for p in progress_all:
            log(
                f"year={p['year']} total={p['total']:,} "
                f"ok={p['ok']:,} failed={p['failed']:,} remaining={p['remaining']:,}"
            )

        if not pending_years:
            log("No quedan pendientes. FIN.")
            break

        for p in pending_years:
            year = p["year"]

            if MAX_TOTAL_BATCHES is not None and total_batches >= MAX_TOTAL_BATCHES:
                log(f"MAX_TOTAL_BATCHES alcanzado: {MAX_TOTAL_BATCHES}. FIN.")
                return

            after, new_ok, new_failed, failed_rate = run_batch(year)
            total_batches += 1

            if after["remaining"] <= 0:
                log(f"YEAR {year} completado.")
                continue

            # Si no avanzó nada, dormir largo.
            if new_ok == 0:
                log(f"Sin avances en year={year}. Posible bloqueo o todos fallando.")
                sleep_long()
            elif failed_rate >= FAILED_RATE_THRESHOLD:
                log(f"Failed rate alto en year={year}: {failed_rate:.2%}")
                sleep_long()
            else:
                sleep_normal()

        # pausa corta al terminar una vuelta por todos los años
        log("Vuelta completa por años pendientes.")
        sleep_normal()


if __name__ == "__main__":
    main()
