from pathlib import Path
import re

# ============================================================
# PATCH 1: tesiunam_marc_downloader.py
# ============================================================

p = Path("tesiunam_marc_downloader.py")

if not p.exists():
    raise FileNotFoundError("No encontré tesiunam_marc_downloader.py")

s = p.read_text(encoding="utf-8")

# Backup
backup = Path("tesiunam_marc_downloader.before_fast_patch.py")
backup.write_text(s, encoding="utf-8")

# Ajustar timeout y workers default
s = re.sub(r"TIMEOUT\s*=\s*\d+", "TIMEOUT = 12", s)
s = re.sub(r"DEFAULT_WORKERS\s*=\s*\d+", "DEFAULT_WORKERS = 3", s)

# Agregar constantes de sleep si no existen
if "MIN_SLEEP_BETWEEN_REQUESTS" not in s:
    s = s.replace(
        "DEFAULT_WORKERS = 3",
        """DEFAULT_WORKERS = 3

# Pausa corta por request para no martillar TESIUNAM.
# El orquestador controla las pausas grandes.
MIN_SLEEP_BETWEEN_REQUESTS = 0.3
MAX_SLEEP_BETWEEN_REQUESTS = 1.2"""
    )

# Insertar sleep antes del fetch dentro de process_one
old = """        html = fetch(url)
        parsed = parse_marc_detail(html)"""

new = """        time.sleep(random.uniform(MIN_SLEEP_BETWEEN_REQUESTS, MAX_SLEEP_BETWEEN_REQUESTS))
        html = fetch(url)
        parsed = parse_marc_detail(html)"""

if old in s and "time.sleep(random.uniform(MIN_SLEEP_BETWEEN_REQUESTS, MAX_SLEEP_BETWEEN_REQUESTS))" not in s:
    s = s.replace(old, new)

p.write_text(s, encoding="utf-8")

print("OK patch:", p)
print("Backup:", backup)


# ============================================================
# PATCH 2: run_marc_batches_auto.py
# ============================================================

p = Path("run_marc_batches_auto.py")

if not p.exists():
    raise FileNotFoundError("No encontré run_marc_batches_auto.py")

s = p.read_text(encoding="utf-8")

# Backup
backup = Path("run_marc_batches_auto.before_fast_patch.py")
backup.write_text(s, encoding="utf-8")

# Cambiar configuración principal
replacements = {
    r"WORKERS\s*=\s*\d+": "WORKERS = 3",
    r"BATCH_LIMIT\s*=\s*\d+": "BATCH_LIMIT = 500",
    r"SLEEP_MIN_SECONDS\s*=\s*\d+": "SLEEP_MIN_SECONDS = 30",
    r"SLEEP_MAX_SECONDS\s*=\s*\d+": "SLEEP_MAX_SECONDS = 90",
    r"LONG_PAUSE_MIN_SECONDS\s*=\s*\d+": "LONG_PAUSE_MIN_SECONDS = 600",
    r"LONG_PAUSE_MAX_SECONDS\s*=\s*\d+": "LONG_PAUSE_MAX_SECONDS = 1200",
    r"FAILED_RATE_THRESHOLD\s*=\s*[0-9.]+": "FAILED_RATE_THRESHOLD = 0.10",
}

for pat, repl in replacements.items():
    s = re.sub(pat, repl, s)

# Reemplazar lógica de pausa si encuentra el bloque original
old_block = """            if new_ok == 0:
                log(f"Sin avances en year={year}. Posible bloqueo o todos fallando.")
                sleep_long()
            elif failed_rate >= FAILED_RATE_THRESHOLD:
                log(f"Failed rate alto en year={year}: {failed_rate:.2%}")
                sleep_long()
            else:
                sleep_normal()"""

new_block = """            if new_ok == 0:
                log(f"Sin avances en year={year}. Posible bloqueo o todos fallando.")
                sleep_long()

            elif failed_rate >= FAILED_RATE_THRESHOLD:
                log(f"Failed rate alto en year={year}: {failed_rate:.2%}")
                sleep_long()

            elif failed_rate > 0:
                seconds = random.randint(120, 300)
                log(f"SLEEP medio por algunos fallos {seconds}s")
                time.sleep(seconds)

            else:
                sleep_normal()"""

if old_block in s:
    s = s.replace(old_block, new_block)
elif "SLEEP medio por algunos fallos" in s:
    print("La lógica adaptativa de pausas ya parecía estar aplicada.")
else:
    print("AVISO: no encontré el bloque exacto de pausas. Revisa manualmente la sección if new_ok == 0.")

p.write_text(s, encoding="utf-8")

print("OK patch:", p)
print("Backup:", backup)

print("\nLISTO.")
print("Ahora puedes correr:")
print("python run_marc_batches_auto.py")
