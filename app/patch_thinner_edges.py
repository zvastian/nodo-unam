from pathlib import Path
import time

path = Path("atlas_macro_preview.html")

if not path.exists():
    raise FileNotFoundError(path)

stamp = int(time.time())
backup = path.with_name(f"atlas_macro_preview.before_thinner_edges_{stamp}.html")

text = path.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

replacements = [
    # Sigma macro edges: versiones posibles
    (
        'size: Math.max(0.25, Number(edge.strokeWidth || 1) * 0.34),',
        'size: Math.max(0.10, Number(edge.strokeWidth || 1) * 0.14),'
    ),
    (
        'size: Math.max(0.12, Number(edge.strokeWidth || 1) * 0.18),',
        'size: Math.max(0.10, Number(edge.strokeWidth || 1) * 0.14),'
    ),
    (
        'size: Math.max(0.08, Number(edge.strokeWidth || 1) * 0.10),',
        'size: Math.max(0.10, Number(edge.strokeWidth || 1) * 0.14),'
    ),

    # SVG fallback / meso / micro / neighborhood: versiones posibles
    (
        'path.setAttribute("stroke-width", Math.max(.6, edgeWidth * .42));',
        'path.setAttribute("stroke-width", Math.max(.18, edgeWidth * .16));'
    ),
    (
        'path.setAttribute("stroke-width", Math.max(.25, edgeWidth * .22));',
        'path.setAttribute("stroke-width", Math.max(.18, edgeWidth * .16));'
    ),
    (
        'path.setAttribute("stroke-width", Math.max(.15, edgeWidth * .12));',
        'path.setAttribute("stroke-width", Math.max(.18, edgeWidth * .16));'
    ),
]

changed = 0

for old, new in replacements:
    if old in text:
        text = text.replace(old, new)
        changed += 1
        print("Reemplazado:")
        print("  ", old)
        print("=>", new)
        print()

path.write_text(text, encoding="utf-8")

print("Backup:", backup)
print("Patched:", path)
print("Cambios:", changed)

if changed == 0:
    print()
    print("No encontré los patrones esperados. Revisa manualmente con:")
    print('Select-String -Path "atlas_macro_preview.html" -Pattern "strokeWidth|stroke-width|edgeWidth|Math.max"')
