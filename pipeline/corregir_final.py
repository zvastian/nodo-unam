import re
import shutil
from pathlib import Path

ruta_html = Path(r"C:\Users\sebas\Documents\Nodo UNAM\atlas_macro_preview.html")
backup = ruta_html.with_suffix(".html.bak")

print(f"Leyendo {ruta_html}...")
texto = ruta_html.read_text(encoding="utf-8")

# 1. Eliminar bloqueo de zoom out
patron_zoom = r'sigmaInitialRatio = camera\.getState\(\)\.ratio \|\| 1;\s*camera\.on\("updated", \(\) => \{\s*const next = camera\.getState\(\);\s*if \(next\.ratio > sigmaInitialRatio\) \{\s*camera\.setState\(\{ \.\.\.next, ratio: sigmaInitialRatio \}\);\s*\}\s*\}\);\s*const blockZoomOut = event => \{\s*if \(event\.deltaY > 0\) \{\s*event\.preventDefault\(\);\s*event\.stopPropagation\(\);\s*\}\s*\};\s*sigmaStage\.onwheel = blockZoomOut;\s*sigmaStage\.addEventListener\("wheel", blockZoomOut, \{ capture: true, passive: false \}\);\s*'
texto = re.sub(patron_zoom, "// Zoom out blocking removed\n", texto, flags=re.DOTALL)
print("✓ Zoom out desbloqueado")

# 2. Mejorar layoutNodes
layout_original = r'function layoutNodes\(nodes, width, height\) \{[^}]*return new Map\(points\.map\(p => \[p\.id, p\]\)\);\s*\}'
def nuevo_layout():
    return '''function layoutNodes(nodes, width, height) {
  const pad = Math.min(width, height) * 0.08;
  let points = nodes.map(node => {
    const projected = project(node.position, width, height);
    const r = getRadius(node);
    return {
      id: node.id,
      node,
      x: projected.x,
      y: projected.y,
      anchorX: projected.x,
      anchorY: projected.y,
      r,
    };
  });

  for (let iter = 0; iter < 200; iter++) {
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        const a = points[i];
        const b = points[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dist = Math.hypot(dx, dy);
        if (dist < 0.001) {
          const angle = ((i + 1) * 1.618 + j) % Math.PI;
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          dist = 1;
        }
        const minDist = a.r + b.r + 24;
        if (dist < minDist) {
          const push = (minDist - dist) * 0.48;
          const ux = dx / dist;
          const uy = dy / dist;
          a.x -= ux * push;
          a.y -= uy * push;
          b.x += ux * push;
          b.y += uy * push;
        }
      }
    }
    for (const p of points) {
      p.x += (p.anchorX - p.x) * 0.035;
      p.y += (p.anchorY - p.y) * 0.035;
      p.x = Math.max(pad + p.r, Math.min(width - pad - p.r, p.x));
      p.y = Math.max(pad + p.r, Math.min(height - pad - p.r, p.y));
    }
  }
  return new Map(points.map(p => [p.id, p]));
}'''
# Buscar la función completa (más complejo). Usaremos un reemplazo más simple: buscar la función original y reemplazarla.
# Como la función original tiene una estructura fija, podemos hacer:
patron_layout = r'(function layoutNodes\(nodes, width, height\) \{)([\s\S]*?)(return new Map\(points\.map\(p => \[p\.id, p\]\)\);\s*\})'
nuevo_texto_layout = r'\1' + nuevo_layout() + r'\3'  # No funciona directamente, mejor usar un enfoque de reemplazo de todo el bloque.
# Voy a simplificar: buscar el inicio y el final de la función con un balance de llaves.
inicio = texto.find("function layoutNodes(nodes, width, height) {")
if inicio != -1:
    brace_count = 0
    i = inicio
    while i < len(texto):
        if texto[i] == '{':
            brace_count += 1
        elif texto[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                fin = i + 1
                break
        i += 1
    funcion_antigua = texto[inicio:fin]
    texto = texto.replace(funcion_antigua, nuevo_layout())
    print("✓ Layout actualizado")
else:
    print("⚠ No se encontró la función layoutNodes")

# 3. Mejorar etiquetas SVG
patron_label = r'(const label = document\.createElementNS\("http://www\.w3\.org/2000/svg", "text"\);)\s*(label\.setAttribute\("y",.*?\);)\s*(label\.setAttribute\("text-anchor", "middle"\);)\s*(label\.textContent = .*?;)'
def repl_label(m):
    return f'''{m.group(1)}
{m.group(2)}
label.setAttribute("text-anchor", "middle");
label.setAttribute("font-size", "12px");
label.setAttribute("font-weight", "bold");
label.setAttribute("paint-order", "stroke");
label.setAttribute("stroke", "#0a0f1a");
label.setAttribute("stroke-width", "3");
label.setAttribute("fill", "#f0f9ff");
{m.group(4)}'''
texto = re.sub(patron_label, repl_label, texto, flags=re.DOTALL)
print("✓ Etiquetas SVG mejoradas")

# 4. Mejorar círculos
patron_circle = r'(const c = document\.createElementNS\("http://www\.w3\.org/2000/svg", "circle"\);)\s*(c\.setAttribute\("r", r\);)\s*(c\.setAttribute\("fill",.*?\);)\s*(const interdisciplinarity.*?\);)\s*(c\.setAttribute\("fill-opacity".*?\);)\s*'
def repl_circ(m):
    return f'''{m.group(1)}
{m.group(2)}
{m.group(3)}
{m.group(4)}
{m.group(5)}
c.setAttribute("stroke", "#ffffff");
c.setAttribute("stroke-width", "1.5");
c.setAttribute("filter", "drop-shadow(0 2px 3px rgba(0,0,0,0.3))");'''
texto = re.sub(patron_circle, repl_circ, texto, flags=re.DOTALL)
print("✓ Nodos con borde blanco y sombra")

# Crear backup
if not backup.exists():
    shutil.copy(ruta_html, backup)
    print(f"Backup creado: {backup.name}")

# Guardar
ruta_html.write_text(texto, encoding="utf-8")
print(f"\n✅ Archivo corregido en: {ruta_html}")