"""Genera la repo pública de NodOS (ssebastian-diazz/nodos-map) a partir de esta.

Uso, desde la raíz:
    python tools/exportar_repo_publica.py DESTINO [--datos DIR_ZIP]

- Copia solo archivos versionados (git ls-files) de una lista blanca, con las rutas de la repo
  pública: prototypes/atlas_vecindario_mvp/ pasa a sitio/.
- Añade los archivos propios de la repo pública, que viven en publico/ (README, .gitignore, CI,
  descarga de datos y guía del pipeline).
- Adapta rutas, quita los identificadores de la cuenta de producción y los enlaces a documentos
  internos que no se publican (bitácora, ADR, RFC).
- Revisa que no quede nada prohibido (rutas locales, identificadores de cuenta, correos) y falla
  si lo encuentra.
- Con --datos, arma nodos-datos-<VERSION_DATOS>.zip con sitio/data (lo que publica
  construir_sitio.py) para el Release de GitHub y fija su SHA-256 en tools/descargar_datos.py.

DESTINO es una repo git aparte: se reemplazan sus archivos versionados; lo ignorado se queda.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REPO_PUBLICA = "ssebastian-diazz/nodos-map"
VERSION_DATOS = "v1"
SITIO = "prototypes/atlas_vecindario_mvp/"

SITIO_ARCHIVOS = ["index.html", "laboratorio.html", "espacio.html", "acerca.html", "privacidad.html",
                  "terminos.html", "contacto.html", "favicon.svg", "ventanas-dia.svg", "ventanas-noche.svg",
                  "mit-license.png", "_headers"]
SITIO_CARPETAS = ["compartido/", "vendor/", "lab/"]
PIPELINE = ["titulo_sin_autor", "limpiar_autores_atlas", "generar_data_unam", "generar_embeddings_full_e5",
            "clustering_hdbscan", "generar_layout_pacmap", "generar_topicos_ctfidf",
            "construir_jerarquia_macro_meso", "aplicar_correccion_manual_macro", "corregir_layout_manual",
            "generar_vecindario_knn", "generar_atlas_modo_caos", "generar_atlas_macro_graph",
            "generar_atlas_subgraphs", "generar_atlas_titulos_teselas", "mover_teselas_corregidas",
            "generar_atlas_tesis_meta", "generar_atlas_acentos", "generar_atlas_tesis_por_micro",
            "generar_vecinas_tesis", "unificar_asesores", "generar_atlas_busqueda", "generar_atlas_catalogo",
            "generar_acerca", "lab_contexto"]
OTROS = ["LICENSE", ".github/dependabot.yml", "pipeline/curaduria/macro_nombres.v1.json",
         "tools/construir_sitio.py", "tools/cdp.mjs", "tools/prueba_humo.mjs", "tools/sitio.wrangler.jsonc"]
FUERA = set()

TEXTO = {".html", ".js", ".mjs", ".css", ".py", ".md", ".json", ".jsonc", ".yml", ".yaml", ".sql", ".sh",
         ".txt", ".svg", ".toml", ""}

REEMPLAZOS = [
    ("'prototypes', 'atlas_vecindario_mvp'", "'sitio'"),
    ('"prototypes" / "atlas_vecindario_mvp"', '"sitio"'),
    ("prototypes/atlas_vecindario_mvp", "sitio"),
]
REEMPLAZOS_RE = [
    # enlaces a documentos internos que no se publican: queda el texto, sin el enlace
    (re.compile(r"\[([^\]]+)\]\((?:\.\./)*(?:adr|rfc)/[^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\((?:\.\./)*development\.md[^)]*\)"), r"\1"),
    (re.compile(r"`?development\.md`?"), "la bitácora interna"),
    # identificadores de la cuenta de producción
    (re.compile(r'"account_id": "[0-9a-f]{32}"'), '"account_id": "TU_ACCOUNT_ID"'),
    (re.compile(r'"database_id": "[0-9a-f-]{36}"'), '"database_id": "TU_DATABASE_ID"'),
    (re.compile(r"https://[a-z0-9-]+--nodos-lab-servicio\.modal\.run"), "https://TU_WORKSPACE--nodos-lab-servicio.modal.run"),
    # la revisión de las salidas de IA de la evaluación se hizo con un modelo, no con una persona
    (re.compile(r'"revisor": "[^"]*"'), '"revisor": "Revisión hecha con un modelo de lenguaje, no humana: conviene que una persona lea al menos derecho, historia_arte y medicina."'),
]
PROHIBIDO = re.compile(r"claude|anthropic|C:\\\\Users|C:/Users|\\Users\\sebas|sebastiaan-diaz-prado|98c2acfa|c754d30f"
                       r"|zvastian|gmail\.com|CLAUDE\.md|PRODUCT\.md", re.I)


def git_ls():
    r = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True)
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


def destino_de(p):
    """Ruta en la repo pública, o None si el archivo no se publica."""
    if p in FUERA:
        return None
    if p.startswith(SITIO):
        resto = p[len(SITIO):]
        if resto in SITIO_ARCHIVOS or any(resto.startswith(c) for c in SITIO_CARPETAS):
            return "sitio/" + resto
        return None
    if p.startswith("services/puerta/") or p.startswith("services/lab/"):
        return p
    if p.startswith("pipeline/") and p.endswith(".py") and Path(p).stem in PIPELINE and p.count("/") == 1:
        return p
    if p in OTROS:
        return p
    return None


def transformar(texto):
    for a, b in REEMPLAZOS:
        texto = texto.replace(a, b)
    for rx, b in REEMPLAZOS_RE:
        texto = rx.sub(b, texto)
    return texto.replace("\r\n", "\n")


def armar_zip(dir_zip):
    """Zip de los datos del sitio, con los mismos criterios que construir_sitio.py."""
    datos = RAIZ / SITIO / "data"
    fuera = {"LEEME.md", "vecindario_preview.v1.json"}
    dir_zip.mkdir(parents=True, exist_ok=True)
    zip_path = dir_zip / f"nodos-datos-{VERSION_DATOS}.zip"
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(datos.rglob("*")):
            if f.is_file() and f.name not in fuera:
                info = zipfile.ZipInfo(f.relative_to(datos).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes(), compresslevel=9)
                n += 1
    h = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"Datos: {zip_path} ({n:,} archivos, {zip_path.stat().st_size / 2**20:.1f} MB), SHA-256 {h}")
    return h


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    dest = Path(args[0]).resolve()
    if RAIZ in dest.parents or dest == RAIZ:
        sys.exit("DESTINO debe estar fuera de esta repo.")
    if not (dest / ".git").is_dir():
        sys.exit(f"{dest} no es una repo git (git init primero).")
    sha = None
    if "--datos" in args:
        sha = armar_zip(Path(args[args.index("--datos") + 1]).resolve())

    # Se borran solo los archivos versionados en DESTINO: lo ignorado (sitio/data, node_modules,
    # .wrangler, .dev.vars) se queda, y lo que sobre aparece en `git status` para revisarlo.
    r = subprocess.run(["git", "ls-files", "-z"], cwd=dest, capture_output=True, check=True)
    for rel in filter(None, r.stdout.decode("utf-8").split("\0")):
        (dest / rel).unlink(missing_ok=True)

    copiados, errores = 0, []
    pares = [(p, destino_de(p)) for p in git_ls()]
    pares = [(RAIZ / p, d) for p, d in pares if d]
    publico = RAIZ / "publico"
    pares += [(f, f.relative_to(publico).as_posix()) for f in publico.rglob("*") if f.is_file()]
    for origen, rel in pares:
        if not origen.exists():
            continue
        salida = dest / rel
        salida.parent.mkdir(parents=True, exist_ok=True)
        if origen.suffix.lower() in TEXTO or origen.name in {"Dockerfile", "_headers", ".gitignore", ".dockerignore"}:
            t = transformar(origen.read_text(encoding="utf-8"))
            if rel == "tools/descargar_datos.py":
                t = t.replace("__REPO__", REPO_PUBLICA).replace("__VERSION__", VERSION_DATOS)
                if sha:
                    t = t.replace("__SHA256__", sha)
            for m in PROHIBIDO.finditer(t):
                linea = t.count("\n", 0, m.start()) + 1
                errores.append(f"{rel}:{linea}: «{m.group(0)}»")
            salida.write_text(t, encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(origen, salida)
        copiados += 1

    faltan = [s for s in SITIO_ARCHIVOS if not (dest / "sitio" / s).exists()]
    faltan += [f"pipeline/{p}.py" for p in PIPELINE if not (dest / "pipeline" / f"{p}.py").exists()]
    if faltan:
        errores.append("faltan: " + ", ".join(faltan))
    if "__SHA256__" in (dest / "tools/descargar_datos.py").read_text(encoding="utf-8"):
        print("Aviso: sin --datos, tools/descargar_datos.py queda sin la suma SHA-256.")
    print(f"{copiados} archivos en {dest}")
    if errores:
        print("\nPROHIBIDO en la repo pública:\n  " + "\n  ".join(errores))
        sys.exit(1)


if __name__ == "__main__":
    main()
