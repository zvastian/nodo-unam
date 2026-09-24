from pathlib import Path
import time

path = Path("atlas_macro_preview.html")
stamp = int(time.time())
backup = path.with_name(f"atlas_macro_preview.before_disable_missing_neighborhood_{stamp}.html")

text = path.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

old = '''
          <button class="full" type="button" data-action="open-neighborhood" data-thesis-id="${node.id}">
            Abrir análisis
          </button>
'''

new = '''
          <p class="sub">
            Análisis de vecindario no disponible en este preview estático.
          </p>
'''

if old not in text:
    raise RuntimeError("No encontré el botón Abrir análisis esperado.")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

print("Backup:", backup)
print("Patched:", path)
print("OK: botón de vecindario oculto en tesis individuales.")
