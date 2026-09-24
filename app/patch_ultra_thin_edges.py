from pathlib import Path
import time
import re

path = Path("atlas_macro_preview.html")

if not path.exists():
    raise FileNotFoundError(path)

stamp = int(time.time())
backup = path.with_name(f"atlas_macro_preview.before_ultra_thin_edges_{stamp}.html")

text = path.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

changed = 0

# 1) Cambiar default del selector de edges a "Solo strong"
old = '<option value="default">Strong + medium</option>'
new = '<option value="default">Strong + medium</option>'
# Conservamos opción, pero cambiamos estado inicial JS más abajo.

# 2) Estado inicial: de default a strong
text2 = text.replace(
    'edgeMode: "default",',
    'edgeMode: "strong",'
)
if text2 != text:
    changed += 1
    print("OK: edgeMode inicial ahora es strong.")
text = text2

# 3) Hacer edges Sigma mucho más delgados.
# Reemplaza cualquier línea tipo:
# size: Math.max(0.25, Number(edge.strokeWidth || 1) * 0.34),
pattern = r'size:\s*Math\.max\([^)]+Number\(edge\.strokeWidth\s*\|\|\s*1\)\s*\*\s*[0-9.]+\),'
replacement = 'size: Math.max(0.035, Math.min(0.16, Number(edge.strokeWidth || 1) * 0.055)),'
text2, n = re.subn(pattern, replacement, text)
if n:
    changed += n
    print(f"OK: grosor Sigma reemplazado ({n}).")
text = text2

# 4) Hacer edges SVG fallback mucho más delgados.
pattern = r'path\.setAttribute\("stroke-width",\s*Math\.max\([^)]+edgeWidth\s*\*\s*[0-9.]+\)\);'
replacement = 'path.setAttribute("stroke-width", Math.max(.08, Math.min(.22, edgeWidth * .08)));'
text2, n = re.subn(pattern, replacement, text)
if n:
    changed += n
    print(f"OK: grosor SVG reemplazado ({n}).")
text = text2

# 5) Bajar opacidad/color de Sigma macro.
repls = [
    (
        'if (edge.isCrossArea) return "rgba(209, 213, 255, 0.24)";',
        'if (edge.isCrossArea) return "rgba(209, 213, 255, 0.075)";'
    ),
    (
        'if (tier === "strong") return "rgba(186, 230, 253, 0.32)";',
        'if (tier === "strong") return "rgba(186, 230, 253, 0.13)";'
    ),
    (
        'if (tier === "medium") return "rgba(147, 197, 253, 0.18)";',
        'if (tier === "medium") return "rgba(147, 197, 253, 0.055)";'
    ),
    (
        'return "rgba(148, 163, 184, 0.08)";',
        'return "rgba(148, 163, 184, 0.025)";'
    ),
]

for old, new in repls:
    if old in text:
        text = text.replace(old, new, 1)
        changed += 1
        print("OK:", old, "=>", new)
    else:
        print("No encontré color exacto:", old)

# 6) Bajar opacidad SVG fallback también.
repls = [
    (
        'if (state.selected && (edge.source === state.selected || edge.target === state.selected)) return 0.72;',
        'if (state.selected && (edge.source === state.selected || edge.target === state.selected)) return 0.42;'
    ),
    (
        'if (state.selected) return 0.06;',
        'if (state.selected) return 0.025;'
    ),
    (
        'if (edge.tier === "strong") return 0.34;',
        'if (edge.tier === "strong") return 0.13;'
    ),
    (
        'if (edge.tier === "medium") return 0.18;',
        'if (edge.tier === "medium") return 0.055;'
    ),
    (
        'return 0.06;',
        'return 0.025;'
    ),
]

for old, new in repls:
    if old in text:
        text = text.replace(old, new, 1)
        changed += 1
        print("OK opacity:", old, "=>", new)

path.write_text(text, encoding="utf-8")

print()
print("Backup:", backup)
print("Patched:", path)
print("Cambios:", changed)
