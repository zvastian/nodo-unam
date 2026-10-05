// Revisión humana de los análisis del Laboratorio: lee D1 de producción y escribe un .md con la
// entrada del usuario y la salida de la IA tal cual (sin resumir ni interpretar), con casillas
// para anotar la revisión. Lo que falta se marca «FALTA»; lo que no se reconoce va en JSON crudo.
//
// La salida tiene textos de usuarios reales: va a docs/revision_lab/, que git ignora (docs/*).
// No se versiona ni se publica.
//
// Uso, desde la raíz del repo:
//   node tools/revisar_lab.mjs --desde 2026-10-01 --hasta 2026-10-04 --n 5 --azar
//   node tools/revisar_lab.mjs --ids 7d3bdd1a,8e09624b
//   node tools/revisar_lab.mjs --desde 2026-10-01 --parciales     (solo los que tienen IA incompleta)
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..');
const PUERTA = join(RAIZ, 'services', 'puerta');
const CUENTA = '98c2acfaa077d8350511cb2b8ac275c0';   // cuenta «NodOS»; sin ella wrangler prueba la personal (7403)

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return acc;
}, []));

const fecha = (s) => { if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) throw new Error('fecha inválida: ' + s); return s; };
const filtros = ["json_extract(resultado,'$.ia') IS NOT NULL"];
if (args.ids) {
  const ids = String(args.ids).split(',').map((x) => x.trim()).filter((x) => /^[0-9a-f-]{4,36}$/.test(x));
  filtros.push('(' + ids.map((x) => `id LIKE '${x}%'`).join(' OR ') + ')');
}
if (args.desde) filtros.push(`creado >= '${fecha(args.desde)}'`);
if (args.hasta) filtros.push(`creado < '${fecha(args.hasta)}'`);
if (args.parciales) filtros.push("(json_extract(resultado,'$.ia.nota') IS NULL OR json_extract(resultado,'$.ia.preguntas') IS NULL OR json_extract(resultado,'$.ia.bloom') IS NULL)");
const n = Math.min(parseInt(args.n, 10) || 5, 200);
const sql = `SELECT id, creado, entrada, json_extract(resultado,'$.ia') AS ia FROM analisis WHERE ${filtros.join(' AND ')} ` +
  `ORDER BY ${args.azar ? 'random()' : 'creado'} LIMIT ${n}`;

const r = spawnSync(process.execPath, [join(PUERTA, 'node_modules', 'wrangler', 'bin', 'wrangler.js'),
  'd1', 'execute', 'nodos', '--env', 'produccion', '--remote', '--json', '--command', sql],
{ cwd: PUERTA, env: { ...process.env, CLOUDFLARE_ACCOUNT_ID: CUENTA }, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
let filas;
try { filas = JSON.parse(r.stdout)[0].results; } catch { console.error(r.stdout || r.stderr); process.exit(1); }

// --- render: texto tal cual; solo se acomoda en secciones ---
const FALTA = '**FALTA** (la IA no generó esta sección)';
const v = (x) => (x === null || x === undefined || x === '' ? '_(vacío)_' : String(x).replace(/\n/g, ' ⏎ '));
const lista = (xs) => (Array.isArray(xs) && xs.length ? xs.map((x) => '- ' + v(x)).join('\n') : '_(vacío)_');
const crudo = (o) => '```json\n' + JSON.stringify(o, null, 1) + '\n```';
const sobrantes = (o, conocidas) => {
  const extra = Object.fromEntries(Object.entries(o || {}).filter(([k]) => !conocidas.includes(k)));
  return Object.keys(extra).length ? '\n**Campos no reconocidos (crudo):**\n' + crudo(extra) + '\n' : '';
};

function entrada(e) {
  const p = e.study_period || {};
  return [
    `**Título:** ${v(e.title)}`,
    `**Programa:** ${v(e.program)}  |  **Grado:** ${v(e.degree)}  |  **Periodo:** ${p.applies ? v(p.label) : 'no aplica'}`,
    `**Problematiza:** ${v(e.problematiza)}`,
    `**Objetivos:**\n${lista(e.objectives)}`,
    `**Palabras clave:** ${Array.isArray(e.keywords) && e.keywords.length ? e.keywords.map(v).join('; ') : '_(vacío)_'}`,
    sobrantes(e, ['title', 'program', 'degree', 'study_period', 'problematiza', 'objectives', 'keywords']),
  ].join('\n\n');
}

function nota(x) {
  if (!x) return FALTA;
  const t = x.scope?.temporal || {}, g = x.scope?.geographic || {};
  return [
    `**Ángulo interpretativo:** ${v(x.interpretive_angle)}`,
    `**Objetos principales:** ${(x.main_objects || []).map(v).join('; ') || '_(vacío)_'}`,
    `**Alcance temporal** (aplica: ${t.applies ? 'sí' : 'no'}${t.applies ? `, ${v(t.start)}–${v(t.end)}` : ''}): ${v(t.text)}`,
    `**Alcance geográfico** (aplica: ${g.applies ? 'sí' : 'no'}${g.units?.length ? ', ' + g.units.map(v).join('; ') : ''}): ${v(g.text)}`,
    sobrantes(x, ['interpretive_angle', 'main_objects', 'scope']),
  ].join('\n\n');
}

function preguntas(x) {
  if (!x) return FALTA;
  const items = (x.items || []).map((q, i) => `${i + 1}. **[${v(q.type)}]** ${v(q.question)}\n   - _Ángulo metodológico:_ ${v(q.methodological_angle)}`);
  return (items.join('\n') || '_(sin preguntas)_') + sobrantes(x, ['items']);
}

function bloom(x) {
  if (!x) return FALTA;
  const objs = (x.objectives || []).map((o, i) => [
    `${i + 1}. **Original:** ${v(o.original)}`,
    `   - _Nivel:_ ${v(o.level)}`,
    `   - _Diagnóstico:_ ${v(o.diagnosis)}`,
    `   - _Mejora:_ ${v(o.improvement)}`,
  ].join('\n'));
  return [
    `**Riesgo principal:** ${v(x.main_risk)}`,
    `**Objetivos evaluados:**\n${objs.join('\n') || '_(vacío)_'}`,
    `**Objetivos revisados:**\n${lista((x.revised || []).map((o) => o.text ?? JSON.stringify(o)))}`,
    `**Nota final:** ${v(x.final_note)}`,
    sobrantes(x, ['main_risk', 'objectives', 'revised', 'final_note']),
  ].join('\n\n');
}

const casilla = (s) => `- [ ] ${s} correcta y pertinente  — comentario: `;
const md = [
  `# Revisión humana del Laboratorio`,
  ``,
  `Generado: ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC  |  Casos: ${filas.length}  |  Filtro: \`${filtros.slice(1).join(' AND ') || 'ninguno'}\`${args.azar ? '  |  muestra al azar' : ''}`,
  ``,
  `Texto **tal cual** salió de D1. ⏎ marca un salto de línea del original. Datos de usuarios reales: no compartir.`,
  ``,
];
for (const f of filas) {
  let e = {}, ia = {};
  try { e = JSON.parse(f.entrada); } catch { e = { title: f.entrada }; }
  try { ia = JSON.parse(f.ia) || {}; } catch { ia = { crudo: f.ia }; }
  md.push(
    `---`, ``,
    `## ${f.id.slice(0, 8)}  |  ${f.creado.replace('T', ' ').replace('Z', ' UTC')}`, ``,
    `### Entrada del usuario`, ``, entrada(e), ``,
    `### Salida de la IA`, ``,
    `#### Nota`, ``, nota(ia.nota), ``,
    `#### Preguntas`, ``, preguntas(ia.preguntas), ``,
    `#### Bloom`, ``, bloom(ia.bloom), ``,
    sobrantes(ia, ['nota', 'preguntas', 'bloom']),
    `### Revisión`, ``,
    casilla('Nota'), casilla('Preguntas'), casilla('Bloom'),
    `- Veredicto (bueno / aceptable / malo): `, ``,
  );
}

const dir = join(RAIZ, 'docs', 'revision_lab');
mkdirSync(dir, { recursive: true });
const archivo = join(dir, `revision_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.md`);
writeFileSync(archivo, md.join('\n'), 'utf8');
console.log(`${filas.length} casos → ${archivo}`);
