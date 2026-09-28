// Prueba de humo de extremo a extremo (v4.28): abre cada página en Chrome headless con tools/cdp.mjs,
// comprueba que cargó lo esencial y falla si la consola trae errores o excepciones.
// Uso: node tools/prueba_humo.mjs [base]   (base por defecto: http://127.0.0.1:8765/)
// Requiere el sitio servido (python -m http.server 8765 en prototypes/atlas_vecindario_mvp) y CHROME.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const base = process.argv[2] || 'http://127.0.0.1:8765/';
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'humo-'));
const cerrarIntro = "var c=document.getElementById('story-close');if(c)c.click();";
const PAGINAS = [
  { pagina: 'index.html', espera: 15000, listo: cerrarIntro + "window.__debugAtlas&&__debugAtlas.state.scatterplot&&__debugAtlas.state.macros.length===130" },
  { pagina: 'index.html?tesis=TH_0462868', espera: 15000, listo: "document.getElementById('ms-title').getAttribute('data-idx')==='462866'&&!!document.querySelector('#ms-title a.leer')" },
  { pagina: 'laboratorio.html', espera: 6000, listo: "!!document.getElementById('pr-titulo')&&typeof NodosAjustes==='object'" },
  { pagina: 'espacio.html', espera: 5000, listo: "!document.getElementById('esp-vacio').hidden" },
  { pagina: 'acerca.html', espera: 4000, listo: "document.querySelectorAll('#mini circle').length===130" },
  { pagina: 'privacidad.html', espera: 3000, listo: "document.querySelectorAll('.legal h2').length===9" },
];
// ruido de Chrome headless que no viene de la página
const IGNORAR = [/GPU stall due to ReadPixels/i, /WebGL.*software/i];

let fallas = 0;
for (const [i, p] of PAGINAS.entries()) {
  const pasos = path.join(dir, `p${i}.json`);
  // la comprobación se repite hasta 3 veces más, cada 4 s: en headless sin GPU la carga varía
  const comprobar = `(function(){try{return (0,eval)(${JSON.stringify(p.listo)})?'LISTO':'FALTA'}catch(e){return 'ERROR '+e.message}})()`;
  fs.writeFileSync(pasos, JSON.stringify([p.espera, 4000, 4000, 4000].map((wait) => ({ wait, eval: comprobar }))));
  const r = spawnSync(process.execPath, [path.join('tools', 'cdp.mjs'), base + p.pagina, pasos, path.join(dir, `o${i}`)], { encoding: 'utf8', timeout: 120000 });
  const out = (r.stdout || '') + (r.stderr || '');
  const listo = /EVAL\s+"LISTO"/.test(out);
  const consola = out.split('--- console ---')[1] || '';
  const errores = consola.split('\n').filter((l) => /^\[(error|exception)\]/.test(l) && !IGNORAR.some((rx) => rx.test(l)));
  const ok = listo && errores.length === 0;
  if (!ok) fallas++;
  console.log(`${ok ? 'ok   ' : 'FALLA'} ${p.pagina}${listo ? '' : '  (no terminó de cargar)'}`);
  errores.forEach((e) => console.log('      ' + e.slice(0, 300)));
  if (!listo) console.log(out.split('\n').filter((l) => l.startsWith('EVAL')).join('\n'));
}
fs.rmSync(dir, { recursive: true, force: true });
process.exit(fallas ? 1 : 0);
