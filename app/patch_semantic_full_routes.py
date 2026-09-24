from pathlib import Path
import time

path = Path("atlas_macro_preview.html")

if not path.exists():
    raise FileNotFoundError(path)

stamp = int(time.time())
backup = path.with_name(f"atlas_macro_preview.before_semantic_full_routes_{stamp}.html")

text = path.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

replacements = [
    (
        '`./atlas_preview_data/meso_by_macro/${node.id}.json`',
        '`./semantic_full/meso_by_macro/${node.id}.json`'
    ),
    (
        '`./atlas_preview_data/micro_by_macro/${node.id}.json`',
        '`./semantic_full/micro_by_macro/${node.id}.json`'
    ),
    (
        '`./atlas_preview_data/${level}_by_macro/${macroId}.json`',
        '`./semantic_full/${level}_by_macro/${macroId}.json`'
    ),
    (
        '`./atlas_preview_data/theses_by_micro/${node.id}.json`',
        '`./semantic_full/theses_by_micro/${node.id}.json`'
    ),
    (
        '`./atlas_preview_data/neighborhood_by_thesis/${thesisId}.json`',
        '`./semantic_full/neighborhood_by_thesis/${thesisId}.json`'
    ),
]

changed = 0

for old, new in replacements:
    if old in text:
        text = text.replace(old, new)
        changed += 1
        print("Reemplazado:", old, "=>", new)
    else:
        print("NO ENCONTRÉ:", old)

path.write_text(text, encoding="utf-8")

print()
print("Backup:", backup)
print("Patched:", path)
print("Cambios:", changed)
