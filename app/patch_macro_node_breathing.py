from pathlib import Path
import time

path = Path("atlas_macro_preview.html")

if not path.exists():
    raise FileNotFoundError(path)

stamp = int(time.time())
backup = path.with_name(f"atlas_macro_preview.before_macro_node_breathing_{stamp}.html")

text = path.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

helper = r'''
    function computeSigmaMacroPositions(nodes) {
      const points = nodes.map((node, index) => {
        const p = node.position || { x: 0, y: 0 };
        return {
          id: node.id,
          node,
          x: Number(p.x || 0),
          y: Number(p.y || 0),
          ox: Number(p.x || 0),
          oy: Number(p.y || 0),
          r: Math.max(0.055, getRadius(node) / 170),
          index,
        };
      });

      // Área 2 está muy concentrada visualmente en el macro.
      // Le damos más distancia mínima sin moverla de su región general.
      const minDistanceFor = (a, b) => {
        const isArea2 = a.node.area === "Area 2" || b.node.area === "Area 2";
        const sameArea = a.node.area && a.node.area === b.node.area;
        if (isArea2 && sameArea) return 0.205;
        if (isArea2) return 0.165;
        if (sameArea) return 0.145;
        return 0.115;
      };

      for (let iter = 0; iter < 95; iter++) {
        for (let i = 0; i < points.length; i++) {
          const a = points[i];

          for (let j = i + 1; j < points.length; j++) {
            const b = points[j];

            let dx = b.x - a.x;
            let dy = b.y - a.y;
            let d = Math.hypot(dx, dy);

            if (d < 0.0001) {
              const angle = ((i + 1) * 2.399963 + j) % (Math.PI * 2);
              dx = Math.cos(angle);
              dy = Math.sin(angle);
              d = 1;
            }

            const minD = minDistanceFor(a, b) + a.r * 0.35 + b.r * 0.35;

            if (d < minD) {
              const push = (minD - d) * 0.42;
              const ux = dx / d;
              const uy = dy / d;

              a.x -= ux * push;
              a.y -= uy * push;
              b.x += ux * push;
              b.y += uy * push;
            }
          }
        }

        // Mantener la forma general del atlas: no queremos destruir el mapa,
        // sólo darle aire a los nodos.
        for (const p of points) {
          p.x += (p.ox - p.x) * 0.035;
          p.y += (p.oy - p.y) * 0.035;
          p.x = Math.max(-1.08, Math.min(1.08, p.x));
          p.y = Math.max(-1.08, Math.min(1.08, p.y));
        }
      }

      return new Map(points.map(p => [p.id, { x: p.x, y: p.y }]));
    }

'''

if "function computeSigmaMacroPositions(" not in text:
    marker = "    function renderSigmaMacro() {"
    if marker not in text:
        raise RuntimeError("No encontré function renderSigmaMacro().")
    text = text.replace(marker, helper + "\n" + marker, 1)
    print("Insertado: computeSigmaMacroPositions")
else:
    print("Ya existía computeSigmaMacroPositions; no lo dupliqué.")

old = '''      const nodes = state.data.nodes || [];
      const edges = visibleEdges(state.data.edges || []);

      for (const node of nodes) {
        const p = node.position || { x: 0, y: 0 };
        graph.addNode(node.id, {'''

new = '''      const nodes = state.data.nodes || [];
      const edges = visibleEdges(state.data.edges || []);
      const sigmaPositions = computeSigmaMacroPositions(nodes);

      for (const node of nodes) {
        const p = sigmaPositions.get(node.id) || node.position || { x: 0, y: 0 };
        graph.addNode(node.id, {'''

if old not in text:
    raise RuntimeError("No encontré el bloque de nodos dentro de renderSigmaMacro esperado.")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("Backup:", backup)
print("Patched:", path)
print("OK: nodos macro con más aire visual en Sigma.")
