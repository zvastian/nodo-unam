from pathlib import Path
import time
import re

path = Path("atlas_macro_preview.html")

if not path.exists():
    raise FileNotFoundError(path)

stamp = int(time.time())
backup = path.with_name(f"atlas_macro_preview.before_zoomout_area_grid_{stamp}.html")

text = path.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

changed = 0

# ============================================================
# 1) Insertar grid sutil de áreas dentro de .stage
# ============================================================

old_stage = '''    <section class="stage">
      <div id="sigmaStage" aria-label="Vista macro interactiva del atlas semántico"></div>
      <svg id="chart" role="img" aria-label="Vista macro del atlas semántico"></svg>
    </section>'''

new_stage = '''    <section class="stage">
      <div class="area-grid" aria-hidden="true">
        <span class="area-grid-label area-grid-label-a1">Área 1</span>
        <span class="area-grid-label area-grid-label-a2">Área 2</span>
        <span class="area-grid-label area-grid-label-a3">Área 3</span>
        <span class="area-grid-label area-grid-label-a4">Área 4</span>
      </div>
      <div id="sigmaStage" aria-label="Vista macro interactiva del atlas semántico"></div>
      <svg id="chart" role="img" aria-label="Vista macro del atlas semántico"></svg>
    </section>'''

if old_stage in text and 'class="area-grid"' not in text:
    text = text.replace(old_stage, new_stage, 1)
    changed += 1
    print("OK: area-grid insertado en .stage.")
elif 'class="area-grid"' in text:
    print("area-grid ya existe; no lo dupliqué.")
else:
    print("No encontré bloque exacto de .stage; salté inserción HTML.")

# ============================================================
# 2) CSS del grid sutil
# ============================================================

grid_css = r'''
    .area-grid {
      position: absolute;
      inset: 0;
      z-index: 1;
      pointer-events: none;
      opacity: .46;
      background:
        linear-gradient(90deg, transparent calc(50% - .5px), rgba(210,229,255,.16) calc(50% - .5px), rgba(210,229,255,.16) calc(50% + .5px), transparent calc(50% + .5px)),
        linear-gradient(180deg, transparent calc(50% - .5px), rgba(210,229,255,.16) calc(50% - .5px), rgba(210,229,255,.16) calc(50% + .5px), transparent calc(50% + .5px)),
        linear-gradient(90deg, rgba(147,197,253,.045) 1px, transparent 1px),
        linear-gradient(180deg, rgba(147,197,253,.045) 1px, transparent 1px);
      background-size:
        100% 100%,
        100% 100%,
        96px 96px,
        96px 96px;
    }

    .area-grid::before {
      content: "";
      position: absolute;
      inset: 9%;
      border: 1px solid rgba(210,229,255,.11);
      border-radius: 26px;
    }

    .area-grid-label {
      position: absolute;
      color: rgba(210,229,255,.30);
      font-size: 10px;
      font-weight: 900;
      letter-spacing: .16em;
      text-transform: uppercase;
      text-shadow: 0 1px 12px rgba(2,8,23,.7);
      user-select: none;
    }

    .area-grid-label-a1 {
      top: 11%;
      left: 11%;
    }

    .area-grid-label-a2 {
      top: 11%;
      right: 11%;
    }

    .area-grid-label-a3 {
      bottom: 11%;
      right: 11%;
    }

    .area-grid-label-a4 {
      bottom: 11%;
      left: 11%;
    }

    #sigmaStage,
    #chart {
      position: relative;
      z-index: 2;
    }
'''

if ".area-grid {" not in text:
    marker = '''    svg {
      width: 100%;
      height: 100%;
      display: block;
    }'''
    if marker in text:
        text = text.replace(marker, marker + "\n\n" + grid_css, 1)
        changed += 1
        print("OK: CSS de area-grid agregado.")
    else:
        print("No encontré marker CSS svg; salté CSS grid.")
else:
    print("CSS area-grid ya existe; no lo dupliqué.")

# ============================================================
# 3) Permitir zoom out en Sigma
# ============================================================

# Subir maxCameraRatio.
text2 = text.replace(
    'maxCameraRatio: 1,',
    'maxCameraRatio: 8,'
)
if text2 != text:
    text = text2
    changed += 1
    print("OK: maxCameraRatio cambiado de 1 a 8.")
else:
    print("No encontré maxCameraRatio: 1,")

# Eliminar bloque que fuerza ratio <= sigmaInitialRatio.
camera_block = '''      const camera = sigmaRenderer.getCamera();
      sigmaInitialRatio = camera.getState().ratio || 1;
      camera.on("updated", () => {
        const next = camera.getState();
        if (next.ratio > sigmaInitialRatio) {
          camera.setState({ ...next, ratio: sigmaInitialRatio });
        }
      });

      const blockZoomOut = event => {
        if (event.deltaY > 0) {
          event.preventDefault();
          event.stopPropagation();
        }
      };
      sigmaStage.onwheel = blockZoomOut;
      sigmaStage.addEventListener("wheel", blockZoomOut, { capture: true, passive: false });

'''

replacement_block = '''      const camera = sigmaRenderer.getCamera();
      sigmaInitialRatio = camera.getState().ratio || 1;

'''

if camera_block in text:
    text = text.replace(camera_block, replacement_block, 1)
    changed += 1
    print("OK: bloqueo manual de zoom out eliminado.")
else:
    print("No encontré bloque exacto de bloqueo de zoom out. Intentando limpieza parcial...")

    # Limpieza parcial si el bloque fue modificado.
    text2 = re.sub(
        r'\s*camera\.on\("updated",\s*\(\)\s*=>\s*\{[\s\S]*?\n\s*\}\);\s*\n',
        '\n',
        text,
        count=1
    )
    if text2 != text:
        text = text2
        changed += 1
        print("OK: camera.on updated eliminado por regex.")

    text2 = re.sub(
        r'\s*const blockZoomOut\s*=\s*event\s*=>\s*\{[\s\S]*?sigmaStage\.addEventListener\("wheel",\s*blockZoomOut,\s*\{\s*capture:\s*true,\s*passive:\s*false\s*\}\);\s*\n',
        '\n',
        text,
        count=1
    )
    if text2 != text:
        text = text2
        changed += 1
        print("OK: blockZoomOut eliminado por regex.")

path.write_text(text, encoding="utf-8")

print()
print("Backup:", backup)
print("Patched:", path)
print("Cambios:", changed)
