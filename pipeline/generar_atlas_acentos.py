"""Diccionario de escritura para los nombres del atlas (acentos, siglas y mayúsculas).

Los nombres de subtema y tema fino son keywords c-TF-IDF sobre texto normalizado
(minúsculas, sin acentos): «deficit atencion · hiperactividad». Lo mismo pasa con
programas, planteles y los títulos de `vecindario_preview`. Este script aprende, de los
títulos originales del catálogo (teselas, 609k títulos con su escritura real), la forma
más frecuente de cada palabra:

- «atencion» -> «atención»  (acentos)
- «vih» -> «VIH», «covid» -> «COVID»  (siglas: casi siempre en mayúsculas dentro de
  títulos que NO están enteros en mayúsculas)

Solo guarda palabras cuya forma cambia. Salida: `data/escritura.v1.json`
{"v": {palabra_normalizada: forma}}. La interfaz la aplica al mostrar (no toca los datos).

Uso: python pipeline/generar_atlas_acentos.py
"""
import collections
import json
import os
import re
import unicodedata

D = os.path.join(os.path.dirname(__file__), '..', 'prototypes', 'atlas_vecindario_mvp', 'data')
TOK = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")


# Pares en que la forma sin tilde también es una palabra válida: no se acentúan.
AMBIGUAS = set('''esta este estas estos ese esa esos esas aquel aquella mas solo el si se tu te mi de aun
como que cual cuales donde cuando quien quienes cuanto cuanta porque practica practicas publico publica
calculo termino terminos transito deposito limite limites critica criticas continuo continua habito
animo'''.split())


def norm(w):
    return ''.join(c for c in unicodedata.normalize('NFD', w.lower()) if unicodedata.category(c) != 'Mn')


def vocab_objetivo():
    """Palabras que la interfaz muestra en minúsculas: labels de meso/micro, programas y títulos del preview."""
    v = set()
    for sub in ('meso_by_macro', 'micro_by_macro'):
        for fn in os.listdir(os.path.join(D, sub)):
            for n in json.load(open(os.path.join(D, sub, fn), encoding='utf8')).get('nodes', []):
                v.update(norm(t) for t in TOK.findall(n.get('label', '') + ' ' + n.get('programsTop', '')))
    for fn in os.listdir(os.path.join(D, 'tesis_por_micro')):
        for r in json.load(open(os.path.join(D, 'tesis_por_micro', fn), encoding='utf8'))['rows']:
            v.update(norm(t) for t in TOK.findall((r[3] or '') + ' ' + (r[4] or '')))
    pv = json.load(open(os.path.join(D, 'vecindario_preview.v1.json'), encoding='utf8'))
    for t in pv['theses'].values():
        v.update(norm(x) for x in TOK.findall(t.get('title', '')))
        for nb in t.get('neighbors', []):
            v.update(norm(x) for x in TOK.findall(nb.get('title', '')))
    return v


def main():
    objetivo = vocab_objetivo()
    formas = collections.defaultdict(collections.Counter)   # norm -> Counter(forma en minúsculas)
    siglas = collections.Counter(); propios = collections.Counter(); total = collections.Counter()
    tdir = os.path.join(D, 'titulos_teselas')
    for fn in os.listdir(tdir):
        if fn == 'manifest.json': continue
        for t in json.load(open(os.path.join(tdir, fn), encoding='utf8')).get('t', []):
            if not isinstance(t, str) or '�' in t: continue
            letras = [c for c in t if c.isalpha()]
            todo_mayus = letras and sum(c.isupper() for c in letras) / len(letras) > 0.6
            for i, w in enumerate(TOK.findall(t)):
                k = norm(w)
                if k not in objetivo or k.isdigit(): continue
                formas[k][w.lower()] += 1
                if not todo_mayus:
                    total[k] += 1
                    if len(w) > 1 and w.isupper(): siglas[k] += 1
                    elif i > 0 and w[0].isupper(): propios[k] += 1   # capitalizada a media frase
    out = {}
    for k, c in formas.items():
        if total[k] >= 3 and siglas[k] / total[k] >= 0.7 and len(k) <= 8:
            out[k] = c.most_common(1)[0][0].upper()
            continue
        # Muchos títulos del catálogo vienen sin acentos, así que la forma sin tilde casi
        # siempre es mayoría aunque sea errónea («psicologia»). Gana la variante con tilde
        # más frecuente si aparece en al menos el 20% de los casos. Se excluyen los pares
        # en que ambas formas son palabras válidas («esta/está», «publico/público»...).
        con = [(f, n) for f, n in c.most_common() if f != k]
        if con and k not in AMBIGUAS and con[0][1] >= 2 and con[0][1] >= 0.2 * sum(c.values()):
            out[k] = con[0][0]
        # nombres propios (México, Aragón, Iztacala): capitalizados a media frase en >=96.5%
        # de los casos; «Hospital», «Instituto», «Facultad» (85-94%) quedan en minúscula
        if total[k] >= 5 and propios[k] / total[k] >= 0.965 and k not in AMBIGUAS:
            f = out.get(k, c.most_common(1)[0][0])
            out[k] = f[0].upper() + f[1:]
    if os.environ.get('DEBUG_PROPIOS'):
        for k in os.environ['DEBUG_PROPIOS'].split(','): print(k, total[k], round(propios[k] / max(1, total[k]), 3))
    json.dump({'version': 'escritura-v1', 'v': dict(sorted(out.items()))},
              open(os.path.join(D, 'escritura.v1.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    print('objetivo:', len(objetivo), 'entradas:', len(out), 'siglas:', sum(1 for x in out.values() if x.isupper()))


if __name__ == '__main__':
    main()
