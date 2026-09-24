import re
from pathlib import Path

html_path = Path("atlas_macro_preview.html")
if not html_path.exists():
    print("❌ Archivo no encontrado")
    exit(1)

contenido = html_path.read_text(encoding="utf-8")

# Patrón para encontrar la función corrupta (diferentes variaciones)
patron_corrupto = r'function\s+Math\.min\s*\([^)]*\)\s*\{[^}]*\}[;\s]*'

# Nueva función correcta
nueva_funcion = '''function edgeOpacity(edge) {
  if (state.selected && (edge.source === state.selected || edge.target === state.selected)) return 0.72;
  if (state.selected) return 0.06;
  if (edge.tier === "strong") return 0.34;
  if (edge.tier === "medium") return 0.18;
  return 0.06;
}'''

# Reemplazar
nuevo_contenido = re.sub(patron_corrupto, nueva_funcion + "\n", contenido, flags=re.DOTALL)

if nuevo_contenido == contenido:
    print("⚠ No se encontró la función corrupta. Revisa manualmente.")
else:
    # También ajustar la línea de stroke-opacity si está mal
    nuevo_contenido = re.sub(
        r'path\.setAttribute\("stroke-opacity",\s*Math\.min\([^,]+,\s*edgeOpacity\(edge\)\s*\*\s*[^)]+\)\)',
        'path.setAttribute("stroke-opacity", edgeOpacity(edge))',
        nuevo_contenido
    )
    html_path.write_text(nuevo_contenido, encoding="utf-8")
    print("✅ Archivo corregido. Recarga la página (Ctrl+F5).")