"""Arma dist/ con solo lo que se publica del sitio (v4.28).

Deja fuera las versiones viejas (index.v*.html), los bocetos y las notas internas.
Uso:  python tools/construir_sitio.py
Luego: npx wrangler pages deploy dist --project-name <proyecto>
"""
import os
import shutil
import sys

RAIZ = os.path.join(os.path.dirname(__file__), '..')
SITIO = os.path.join(RAIZ, 'prototypes', 'atlas_vecindario_mvp')
DIST = os.path.join(RAIZ, 'dist')
ARCHIVOS = ['index.html', 'laboratorio.html', 'espacio.html', 'acerca.html', 'privacidad.html',
            'favicon.svg', 'ventanas-dia.svg', 'ventanas-noche.svg', 'mit-license.png', '_headers']
CARPETAS = ['compartido', 'vendor', 'lab', 'data']
FUERA = {'LEEME.md'}
LIMITE_ARCHIVO = 25 * 1024 * 1024  # Cloudflare Pages
LIMITE_ARCHIVOS = 20000

if os.path.exists(DIST):
    shutil.rmtree(DIST)
os.makedirs(DIST)
for a in ARCHIVOS:
    shutil.copy2(os.path.join(SITIO, a), DIST)
for c in CARPETAS:
    shutil.copytree(os.path.join(SITIO, c), os.path.join(DIST, c), ignore=shutil.ignore_patterns(*FUERA, '__pycache__'))

n, total, grandes = 0, 0, []
for raiz, _, archivos in os.walk(DIST):
    for a in archivos:
        t = os.path.getsize(os.path.join(raiz, a)); n += 1; total += t
        if t > LIMITE_ARCHIVO: grandes.append((a, t))
print('dist: %d archivos, %.0f MB' % (n, total / 1e6))
if grandes or n > LIMITE_ARCHIVOS:
    for a, t in grandes: print('excede 25 MiB:', a, t)
    sys.exit(1)
