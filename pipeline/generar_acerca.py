"""Datos reales para las ilustraciones de acerca.html (v4.30).

Toma una tesis de ejemplo y reúne, en un archivo pequeño (data/acerca.v1.json):
  - sus 3 tesis más parecidas (data/vecinas/);
  - una muestra de los puntos de todo el mapa, con su campo (-1 = sin grupo);
  - la jerarquía de su campo: temas con su tamaño y los subtemas de su tema;
  - las palabras clave (c-TF-IDF) de su subtema.
Los nombres legibles de temas y subtemas los arma el mapa al cargar; acerca.html los toma de
aquí tal como los calcula index.html (ver NOMBRES abajo, verificados en el mapa).
Uso:  python pipeline/generar_acerca.py
"""
import glob
import random
import json
import os
import struct

D = os.path.join(os.path.dirname(__file__), '..', 'prototypes', 'atlas_vecindario_mvp', 'data')
EJ = 'TH_0462868'
N_MUESTRA = 9000
# nombres tal como los muestra el mapa (index.html los arma de las palabras clave y del
# diccionario de escritura); verificados en el mapa el 2026-09-28
NOMBRES = {244: 'Coli – Escherichia', 245: 'Arabidopsis – Thaliana', 246: 'Haemonchus contortus – Microplus',
           247: 'Melanogaster – Drosophila', 248: 'Vanadio – Linfocitos humanos', 249: 'Células – Cáncer',
           250: 'Virus – Taenia', 251: 'Gen – Polimorfismos', 252: 'Cepas – Candida', 253: 'Entamoeba – Trofozoítos'}
NOMBRES_SUB = {459: 'Coli – Escherichia', 460: 'Cerevisiae – Saccharomyces', 456: 'Rhizobium – Etli', 447: 'Bacillus – Subtilis'}


def cargar(p):
    return json.load(open(os.path.join(D, p), encoding='utf-8'))


man = cargar('atlas_chaos_mode.v1.json')
buf = open(os.path.join(D, 'atlas_chaos_mode.v1.bin'), 'rb').read()
f = man['fields']
ids = buf[f['thesisIdsBlob']['byteOffset']:f['thesisIdsBlob']['byteOffset'] + f['thesisIdsBlob']['byteLength']].decode('utf-8').split('\n')
n = len(ids)
xs = struct.unpack_from('<%df' % n, buf, f['x']['byteOffset'])
ys = struct.unpack_from('<%df' % n, buf, f['y']['byteOffset'])
mc = struct.unpack_from('<%di' % n, buf, f['macroCode']['byteOffset'])
i0 = ids.index(EJ)

# vecinas: por bloque, k int32 por tesis y luego k uint8 por tesis
vm = cargar('vecinas.v1.json'); k, B = vm['k'], vm['bloque']
b, j = divmod(i0, B)
vb = open(os.path.join(D, 'vecinas', '%d.bin' % b), 'rb').read()
filas = len(vb) // (k * 5)
vec = struct.unpack_from('<%di' % k, vb, j * k * 4)
qs = struct.unpack_from('<%dB' % k, vb, filas * k * 4 + j * k)
top = [(v, 0.5 + q / 510) for v, q in zip(vec, qs) if v >= 0][:3]

# títulos: teselas del mapa
tm = cargar('titulos_teselas/manifest.json')
def titulo(idx):
    tx = min(tm['grid'] - 1, max(0, int((xs[idx] - tm['x0']) // tm['cell'])))
    ty = min(tm['grid'] - 1, max(0, int((ys[idx] - tm['y0']) // tm['cell'])))
    t = cargar('titulos_teselas/%d_%d.json' % (tx, ty))
    p = t['i'].index(idx)
    return t['t'][p], t['y'][p]

vecinas = []
for v, s in top:
    t, a = titulo(v)
    vecinas.append({'id': ids[v], 'titulo': t, 'anio': a, 'sim': round(s, 3)})

# puntos: una muestra al azar de todo el mapa, con su campo (-1 = sin grupo), en enteros 0-1000
# sobre los percentiles 0.5-99.5. A escala local el plano no deja ver los grupos (HDBSCAN agrupa
# en 1,024 dimensiones); a escala del mapa sí.
random.seed(7)
muestra = random.sample(range(n), N_MUESTRA)
def q(v, f): v = sorted(v); return v[int(f * (len(v) - 1))]
sx = [xs[i] for i in muestra]; sy = [ys[i] for i in muestra]
bx0, bx1, by0, by1 = q(sx, 0.005), q(sx, 0.995), q(sy, 0.005), q(sy, 0.995)
esc_ = 1000 / max(bx1 - bx0, by1 - by0)
def cuant(i): return [round((xs[i] - bx0) * esc_), round((ys[i] - by0) * esc_)]
puntos = [cuant(i) + [mc[i]] for i in muestra if bx0 <= xs[i] <= bx1 and by0 <= ys[i] <= by1]
yo = cuant(i0)

# jerarquía del campo y su tema
macro = mc[i0]
meso = cargar('meso_by_macro/M%d.json' % macro)['nodes']
micros = {}
for p in glob.glob(os.path.join(D, 'tesis_por_micro', '*.json')):
    d = json.load(open(p, encoding='utf-8'))
    if d['macroId'] == macro:
        micros[d['clusterId']] = (d['mesoId'], [r_[0] for r_ in d['rows']])
mi_micro = next(c for c, (_, ts) in micros.items() if EJ in ts)
mi_meso = micros[mi_micro][0]
micro_nodes = {m['clusterId']: m for m in cargar('micro_by_macro/M%d.json' % macro)['nodes']}
temas = sorted(({'id': m['clusterId'], 'nombre': NOMBRES.get(m['clusterId']), 'tesis': m['size']} for m in meso), key=lambda t: -t['tesis'])
subtemas = sorted(({'id': c, 'nombre': NOMBRES_SUB.get(c), 'tesis': micro_nodes[c]['size']} for c, (ms, _) in micros.items() if ms == mi_meso), key=lambda t: -t['tesis'])

out = {
    'version': 'acerca-v1',
    'ejemplo': {'id': EJ, 'idx': i0, 'macro': macro, 'meso': mi_meso, 'micro': mi_micro, 'xy': yo, 'ancho': round((bx1 - bx0) * esc_), 'alto': round((by1 - by0) * esc_)},
    'vecinas': vecinas,
    'puntos': puntos,
    'temas': temas,
    'subtemas': subtemas,
    'palabras': [w.strip() for w in micro_nodes[mi_micro]['label'].split('·')],
}
# c-TF-IDF (paso 8): cuantas veces aparece cada palabra en los titulos del subtema de la tesis y
# en cuantos de todos los subtemas aparece al menos una vez. Cifras reales, contadas aqui.
import collections, math, re
_tf, _df, _tot, _nsub, _nw = None, collections.Counter(), collections.Counter(), 0, 0
for p in glob.glob(os.path.join(D, 'tesis_por_micro', '*.json')):
    d = json.load(open(p, encoding='utf-8'))
    c = collections.Counter(w for r_ in d['rows'] for w in re.findall(r'[^\W\d_]+', r_[1].lower()))
    _nsub += 1
    _df.update(c.keys()); _tot.update(c); _nw += sum(c.values())
    if d['clusterId'] == mi_micro:
        _tf = c
out['ctfidf'] = {'subtemas': _nsub, 'tesis': micro_nodes[mi_micro]['size'],
                 'palabras': [{'p': w, 'veces': _tf[w], 'subtemas': _df[w],
                               # c-TF-IDF: veces en el subtema x log(1 + palabras promedio por subtema / veces en todo el mapa)
                               'puntaje': round(_tf[w] * math.log(1 + (_nw / _nsub) / _tot[w]), 1)}
                              for w in ['cerevisiae', 'saccharomyces', 'levadura', 'análisis', 'de', 'la']]}
# el ejemplo del Laboratorio: entrada, votos por campo y dos salidas reales de la IA
L = os.path.join(D, '..', 'lab', 'ejemplos', 'repartidores')
ent = json.load(open(os.path.join(L, 'entrada.json'), encoding='utf-8'))
dat = json.load(open(os.path.join(L, 'datos.json'), encoding='utf-8'))
ia = json.load(open(os.path.join(L, 'ia.json'), encoding='utf-8'))
out['laboratorio'] = {
    'titulo': ent['title'], 'palabras': ent['keywords'],
    'votos': [{'campo': c['nombre'], 'peso': c['peso']} for c in dat['ubicacion']['campo']],
    'enfoque': ia['nota']['interpretive_angle'],
    'pregunta': ia['preguntas']['items'][0]['question'],
}
json.dump(out, open(os.path.join(D, 'acerca.v1.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps({k_: v for k_, v in out.items() if k_ != 'puntos'}, ensure_ascii=False, indent=1))
print('puntos:', len(puntos), 'sin grupo:', sum(1 for p in puntos if p[2] < 0))
