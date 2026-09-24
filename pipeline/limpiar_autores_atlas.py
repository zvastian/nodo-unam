"""Red de seguridad de privacidad para los datos del prototipo del atlas.

Recorre los JSON de `prototypes/atlas_vecindario_mvp/data/` y corta en cada título
la mención de responsabilidad que el catálogo a veces trae pegada ("… / Nombre
Apellido", "tesis que para obtener el título de …, presenta …", ", por Nombre ;
tutor …"). Complementa el corte en origen de `generar_atlas_tesis_por_micro.py`
(RESP_RE / AUTOR_RE), que no cubre todas las variantes ni todos los archivos
(vecindario_preview y las teselas se generan por otra vía).

Uso:  python pipeline/limpiar_autores_atlas.py [--dry-run]
Se corre después de regenerar cualquier dato del prototipo y antes de versionarlo.
"""
import json
import os
import re
import sys

D = os.path.join(os.path.dirname(__file__), '..', 'prototypes', 'atlas_vecindario_mvp', 'data')
MAY = 'A-ZÁÉÍÓÚÑ'
MIN = 'a-záéíóúñü'
NOMBRE = r'[' + MAY + r'][' + MIN + r']+\.?,?\s+[' + MAY + r'][' + MIN + r'.]*'
# Lo que sigue al corte debe traer una marca de persona; si no, el título se deja
# intacto (p. ej. "procesos ... para obtener el título de licenciado en trabajo social
# a partir de ..." es tema, no mención de responsabilidad).
PERSONA = re.compile(r'(?i:presenta|asesor|tutor|director|sustentante|alumn[oa])|' + NOMBRE + r'\s+[' + MAY + r']')
CORTES = [
    # "... (tesis que) para obtener el título / grado de ..., presenta ..."
    re.compile(r'(?i)[\s,.;:]*(?:\b(?:tesis|tesina|trabajo|informe|reporte|memoria)\b[\w\s,()]{0,40}?\s+)?(?:que\s+)?para\s+(?:obtener|optar)\s+(?:el|al|por\s+el)\s+(?:t[ií]tulo|grado|diploma)'),
    # "... trabajo que presenta el alumno / la pasante ..."
    re.compile(r'(?i)[\s,.;:]*\b(?:tesis|tesina|trabajo|informe|reporte|memoria)\s+(?:profesional\s+)?que\s+presentan?\s+(?:el|la|los|las)\s+(?:alumn[oa]s?|pasantes?|sustentantes?|c\.)'),
    # "... /Nombre Apellido" (espacio antes de la barra) o "/ Nombre Apellido ; asesor ..."
    re.compile(r'\s+/\s*(?!Alcald)(?=' + NOMBRE + r'\s+[' + MAY + r'])|/\s*(?=(?:[' + MAY + r'][\w.]*\s+){1,5}[' + MAY + r'][\w.]*\s*;\s*(?i:asesor|tutor|director))'),
]

# Cuando la mención está al principio (no se puede cortar sin vaciar el título),
# se quita solo el nombre: "trabajo que presenta el alumno NOMBRE para ..." -> "... el alumno para ...".
QUITAR_NOMBRE = re.compile(r'(?i:(que\s+presentan?\s+(?:el|la)\s+(?:alumn[oa]|pasante|sustentante)))\s+' + NOMBRE + r'(?:\s+[' + MAY + r'][' + MIN + r']+)*')


def limpiar(t):
    t = QUITAR_NOMBRE.sub(r'\1', t)
    cut = len(t)
    for rx in CORTES:
        m = rx.search(t)
        if m and m.start() > 15 and PERSONA.search(t, m.end()):  # nunca deja un título casi vacío
            cut = min(cut, m.start())
    return t[:cut].rstrip(' ,.;:/') if cut < len(t) else t


def main(dry):
    cambios = []

    def walk(o, rel):
        if isinstance(o, list):
            for i, x in enumerate(o):
                if isinstance(x, str) and len(x) > 25:
                    y = limpiar(x)
                    if y != x: cambios.append((rel, x, y)); o[i] = y
                else: walk(x, rel)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k == 'title' and isinstance(v, str):
                    y = limpiar(v)
                    if y != v: cambios.append((rel, v, y)); o[k] = y
                else: walk(v, rel)

    for root, _, files in os.walk(D):
        for fn in files:
            if not fn.endswith('.json'): continue
            full = os.path.join(root, fn); rel = os.path.relpath(full, D)
            raw = open(full, encoding='utf8').read()
            data = json.loads(raw); n0 = len(cambios)
            walk(data, rel)
            if len(cambios) > n0 and not dry:
                compact = '\n' not in raw.strip()
                with open(full, 'w', encoding='utf8') as f:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':') if compact else None, indent=None if compact else 1)
    for rel, a, b in cambios:
        print('%-40s %s\n%-40s -> %s' % (rel[:40], a, '', b))
    print('cambios:', len(cambios), '(dry-run)' if dry else '')


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
