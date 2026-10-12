// Pruebas del carril de IA y del tope de subpeticiones (1.0.8). Sin Worker, sin servicio y sin IA:
// D1 es una base SQLite en memoria con las migraciones de verdad, y Groq, Workers AI y el servicio de
// datos son simulados. El simulador de fetch imita el plan gratuito: a partir de la subpetición 51
// de una invocación, toda llamada falla con el error de Cloudflare.
//   npm run prueba:carril
import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { Fila } from '../src/fila.js';
import { correrIA, planIA } from '../src/analisis.js';
import { SinSubpeticiones, pedirIA } from '../src/ia/proveedores.js';
import { ESQUEMAS } from '../src/ia/esquemas.js';
import { clasificarObjetivos } from '../../../prototypes/atlas_vecindario_mvp/compartido/bloom.js';

const EJEMPLO = new URL('../../../prototypes/atlas_vecindario_mvp/lab/ejemplos/acuifero/', import.meta.url);
const leer = (f) => JSON.parse(readFileSync(new URL(f, EJEMPLO), 'utf8'));
const ENTRADA = leer('entrada.json'), DATOS = leer('datos.json'), IA = leer('ia.json');
const ERROR_CF = 'Too many subrequests by single Worker invocation. To configure this limit, refer to https://developers.cloudflare.com/workers/wrangler/configuration/#limits';
const TOKENS_POR_LLAMADA = 3000;

// --- D1 sobre SQLite en memoria ---
function nuevaD1() {
  const db = new DatabaseSync(':memory:');
  const dir = new URL('../migrations/', import.meta.url);
  for (const f of readdirSync(dir).filter((x) => x.endsWith('.sql')).sort()) db.exec(readFileSync(new URL(f, dir), 'utf8'));
  const sentencia = (sql, args = []) => ({
    bind: (...a) => sentencia(sql, a),
    run: async () => ({ meta: { changes: Number(db.prepare(sql).run(...args).changes) } }),
    first: async () => db.prepare(sql).get(...args) ?? null,
    all: async () => ({ results: db.prepare(sql).all(...args) }),
  });
  return { db, prepare: (sql) => sentencia(sql), batch: async (q) => Promise.all(q.map((x) => x.run())) };
}

// --- Subpeticiones por invocación y proveedores simulados ---
let usadas = 0, tope = 50, rechazadas = 0, llamadasGroq = 0, llamadasAI = 0, datosPedidos = 0;
const nuevaInvocacion = () => { usadas = 0; };
function subpeticion() { if (++usadas > tope) { rechazadas++; throw new Error(ERROR_CF); } }
globalThis.fetch = async (url, op) => {
  subpeticion();
  if (String(url).startsWith('https://api.groq.com/')) {
    llamadasGroq++;
    const tarea = JSON.parse(op.body).response_format.json_schema.name;
    return Response.json({ choices: [{ message: { content: JSON.stringify(IA[tarea]) }, finish_reason: 'stop' }], usage: { total_tokens: TOKENS_POR_LLAMADA } });
  }
  if (String(url).endsWith('/v1/contexto')) { datosPedidos++; return new Response(JSON.stringify(DATOS), { headers: { 'Content-Type': 'application/json' } }); }
  throw new Error('fetch inesperado: ' + url);
};
const AI = { run: async () => { subpeticion(); llamadasAI++; throw new Error('Workers AI no debería usarse en esta prueba'); } };

// --- Durable Object simulado ---
function estadoDO() {
  const datos = new Map();
  let alarma = null;
  return {
    storage: {
      get: async (k) => structuredClone(datos.get(k)),
      put: async (k, v) => { datos.set(k, structuredClone(v)); },
      getAlarm: async () => alarma,
      setAlarm: async (t) => { alarma = t; },
    },
    alarma: () => alarma,
    limpiarAlarma: () => { alarma = null; },
  };
}

let env, estado, fila;
beforeEach(() => {
  usadas = 0; tope = 50; rechazadas = 0; llamadasGroq = 0; llamadasAI = 0; datosPedidos = 0;
  env = {
    DB: nuevaD1(), AI, GROQ_API_KEY: 'prueba', LAB_URL: 'http://servicio', LAB_CLAVE: 'x',
    IA_INTERVALO_S: '0', TOPE_IA_DIA: '55', GROQ_TOKENS_DIA: '180000', WORKERS_AI_NEURONAS_DIA: '9000', FILA_SIMULTANEOS: '2',
  };
  estado = estadoDO();
  fila = new Fila(estado, env);
});
// Una alarma = una invocación: trae sus propias 50 subpeticiones.
async function alarma() { nuevaInvocacion(); estado.limpiarAlarma(); await fila.alarm(); return estado.alarma(); }

function pendiente(n, extra = {}) {
  for (let i = 0; i < n; i++) {
    env.DB.db.prepare(
      `INSERT INTO analisis (id, usuario, titulo, entrada, resultado, estado, ia_pendiente, creado)
       VALUES (?1, ?2, 't', ?3, ?4, 'listo', 1, ?5)`,
    ).run('a' + i, 'u' + i, JSON.stringify(ENTRADA), JSON.stringify({ datos: DATOS, ia: extra.ia || null }), `2026-10-02T17:${String(i).padStart(2, '0')}:00Z`);
  }
}
const filas = () => env.DB.db.prepare('SELECT id, ia_pendiente, ia_intentos, ia_siguiente, resultado FROM analisis ORDER BY creado').all();
const contador = (tipo) => env.DB.db.prepare('SELECT coalesce(sum(n), 0) AS n FROM cuota_sitio WHERE tipo = ?1').get(tipo).n;

test('el ejemplo pasa las revisiones de las tres secciones (si no, el resto no prueba nada)', async () => {
  const lexico = clasificarObjetivos(ENTRADA.objectives, ENTRADA.degree);
  const r = await correrIA(env, '2026-10-11', ENTRADA, DATOS, lexico);
  assert.deepEqual(r.faltan, [], JSON.stringify(r.fallos));
  assert.equal(llamadasGroq, 3);
});

test('el carril hace una lectura por alarma y programa la siguiente', async () => {
  pendiente(3);
  const siguiente = await alarma();
  assert.equal(llamadasGroq, 3, 'una lectura: nota, preguntas y Bloom');
  assert.deepEqual(filas().map((f) => f.ia_pendiente), [0, 1, 1], 'solo el más antiguo');
  assert.ok(siguiente !== null, 'deja programada la siguiente alarma');
  await alarma(); await alarma();
  assert.deepEqual(filas().map((f) => f.ia_pendiente), [0, 0, 0]);
  assert.equal(await alarma(), null, 'sin pendientes, no se programa nada');
});

test('el Worker sin subpeticiones a mitad de una lectura: no es un fallo ni gasta cupo', async () => {
  pendiente(1);
  tope = 1;   // la primera llamada sale; las otras dos se topan con el límite
  await alarma();
  const [f] = filas();
  const res = JSON.parse(f.resultado);
  assert.equal(f.ia_pendiente, 1, 'sigue pendiente');
  assert.equal(f.ia_intentos, 0, 'no cuenta como intento');
  assert.equal(f.ia_siguiente, null, 'sin espera de 6 horas');
  assert.equal(res.fallos, undefined, 'sin motivo de fallo');
  assert.equal(Object.keys(res.ia).length, 1, 'se guarda la sección que sí salió');
  assert.equal(contador('groq_tokens'), TOKENS_POR_LLAMADA, 'solo cuenta lo que Groq cobró: las reservas de las llamadas que no salieron se devuelven');
  assert.equal(contador('workers_ai_neuronas'), 0, 'no se intenta Workers AI: fallaría igual');
  assert.equal(llamadasAI, 0);
  assert.equal(contador('ia'), 0, 'el lugar del tope diario vuelve: el reintento toma el suyo');
  assert.ok(!fila.s.iaPausaHasta, 'el carril no se pausa hasta mañana');

  tope = 50;
  await alarma();
  assert.equal(filas()[0].ia_pendiente, 0, 'la siguiente alarma completa lo que faltaba');
  assert.equal(llamadasGroq, 3, 'solo pidió las dos secciones que faltaban');
});

test('Workers AI sin subpeticiones: devuelve sus neuronas', async () => {
  const sinGroq = { ...env, GROQ_API_KEY: '' };
  tope = 0;
  await assert.rejects(pedirIA(sinGroq, null, 'nota', [{ role: 'user', content: 'x' }], ESQUEMAS.nota), SinSubpeticiones);
  assert.equal(contador('workers_ai_neuronas'), 0);
});

test('un error real del proveedor sigue contando intento (1.0.6 sin cambios)', () => {
  const plan = planIA(env, { faltan: ['nota'], agotada: false, cortada: false, fallos: { nota: { error: 'ia_fallo' } } }, 0);
  assert.equal(plan.intentos, 1);
  assert.ok(plan.siguiente);
  // cortada y además un fallo real en la misma corrida: cuenta, para que nada se reintente sin tope
  assert.equal(planIA(env, { faltan: ['nota', 'bloom'], agotada: false, cortada: true, fallos: { nota: {} } }, 0).intentos, 1);
  assert.equal(planIA(env, { faltan: ['nota'], agotada: false, cortada: true, fallos: {} }, 2).intentos, 2);
});

test('30 pendientes con el tope real de 50: todos se completan, sin intentos ni pausa', async () => {
  env.GROQ_TOKENS_DIA = '10000000';   // aquí se prueba el tope de subpeticiones, no el cupo del día
  pendiente(30);
  for (let i = 0; i < 40 && filas().some((f) => f.ia_pendiente); i++) await alarma();
  const todas = filas();
  assert.equal(todas.filter((f) => f.ia_pendiente).length, 0);
  assert.equal(todas.filter((f) => f.ia_intentos).length, 0);
  assert.equal(contador('groq_tokens'), 30 * 3 * TOKENS_POR_LLAMADA, 'el contador refleja solo lo cobrado');
  assert.ok(!fila.s.iaPausaHasta);
  assert.equal(rechazadas, 0, 'ninguna llamada se topó con el límite de 50');
});

test('la fila de datos corre a lo más 20 análisis por alarma y deja el carril para otra', async () => {
  const dia = '2026-10-11';
  for (let i = 0; i < 25; i++) {
    env.DB.db.prepare(`INSERT INTO analisis (id, usuario, titulo, entrada, resultado, estado) VALUES (?1, ?2, 't', ?3, 'null', 'fila')`)
      .run('f' + i, 'u' + i, JSON.stringify(ENTRADA));
    fila.s = null; await fila.cargar();
    fila.s.cola.push({ id: 'f' + i, usuario: 'u' + i, dia });
    await fila.guardar();
  }
  fila.s = null;
  const siguiente = await alarma();
  assert.equal(datosPedidos, 20);
  assert.equal(fila.s.cola.length, 5);
  assert.ok(siguiente !== null && siguiente <= Date.now(), 'la siguiente alarma, enseguida');
  await alarma();
  assert.equal(datosPedidos, 25);
  assert.equal(llamadasGroq, 0, 'la alarma que corrió datos no hace IA');
  const listos = env.DB.db.prepare(`SELECT count(*) AS n FROM analisis WHERE estado = 'listo' AND ia_pendiente = 1`).get().n;
  assert.equal(listos, 25, 'ninguno se perdió');
  await alarma();
  assert.equal(llamadasGroq, 3, 'la siguiente alarma ya es del carril de IA');
});
