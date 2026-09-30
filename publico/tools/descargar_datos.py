"""Descarga los datos del mapa y los deja en sitio/data/.

Los datos (110 MB comprimidos, unos 250 MB en disco) no viven en el repositorio: se publican como archivo de un Release de
GitHub, con su suma SHA-256. Este script los baja, verifica la suma y los descomprime.

Uso:
    python tools/descargar_datos.py            # si sitio/data/ ya existe, no hace nada
    python tools/descargar_datos.py --forzar   # vuelve a descargar y reemplaza sitio/data/

Solo usa la biblioteca estándar de Python.
"""
import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "__VERSION__"
URL = f"https://github.com/__REPO__/releases/download/datos-{VERSION}/nodos-datos-{VERSION}.zip"
SHA256 = "__SHA256__"

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "sitio" / "data"


def main():
    forzar = "--forzar" in sys.argv
    if DESTINO.exists() and not forzar:
        print(f"{DESTINO} ya existe; usa --forzar para reemplazarlo.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "datos.zip"
        print(f"Descargando {URL}")
        with urllib.request.urlopen(URL) as r, open(zip_path, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        h = hashlib.sha256()
        with open(zip_path, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        if h.hexdigest() != SHA256:
            sys.exit(f"La suma SHA-256 no coincide ({h.hexdigest()}); no se instaló nada.")
        if DESTINO.exists():
            shutil.rmtree(DESTINO)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(DESTINO)
    n = sum(1 for p in DESTINO.rglob("*") if p.is_file())
    print(f"Listo: {n:,} archivos en {DESTINO}")


if __name__ == "__main__":
    main()
