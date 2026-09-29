// Pruebas de la fila del Laboratorio (src/fila.js) contra `wrangler dev` y el servicio de datos
// (:8770). El Worker corre con la configuración de prueba: UN lugar, sin IA (no gasta Groq) y el
// servicio detrás del proxy lento de esta prueba (:8771), para que el análisis que bloquea ocupe su
// lugar unos segundos seguros (Turnstile tarda de 200 a 800 ms y desordenaba las llegadas):
//   cp .dev.vars pruebas/.dev.vars    (copia ignorada por git; bórrala al terminar)
//   npx wrangler dev -c pruebas/wrangler.fila.jsonc --persist-to .wrangler/state --port 8787 --ip 127.0.0.1
//   node --test pruebas/fila.test.mjs
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import http from 'node:http';

const RETRASO_MS = 4000;
let proxy;
before(() => new Promise((listo) => {
  proxy = http.createServer((req, res) => {
    const partes = [];
    req.on('data', (p) => partes.push(p));
    req.on('end', async () => {
      await new Promise((r) => setTimeout(r, RETRASO_MS));
      const r = await fetch('http://127.0.0.1:8770' + req.url, { method: req.method, headers: { 'Content-Type': 'application/json', 'X-Lab-Clave': req.headers['x-lab-clave'] || '' }, body: req.method === 'POST' ? Buffer.concat(partes) : undefined });
      res.writeHead(r.status, { 'Content-Type': r.headers.get('content-type') || 'application/json' });
      res.end(Buffer.from(await r.arrayBuffer()));
    });
  }).listen(8771, '127.0.0.1', listo);
}));
after(() => proxy.close());

const URL_PUERTA = process.env.PUERTA_URL || 'http://127.0.0.1:8787';
const { emisor, privada } = JSON.parse(readFileSync(new URL('claves.local.json', import.meta.url)));
const ENTRADA = JSON.parse(readFileSync(new URL('../../../prototypes/atlas_vecindario_mvp/lab/entrada_ejemplo.json', import.meta.url)));
const TURNSTILE = { 'X-Turnstile': 'XXXX.DUMMY.TOKEN.XXXX' };
const b64 = (x) => Buffer.from(JSON.stringify(x)).toString('base64url');
const clave = await crypto.subtle.importKey('jwk', privada, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

async function token() {
  const ahora = Math.floor(Date.now() / 1000);
  const c = b64({ alg: 'ES256', typ: 'JWT', kid: privada.kid });
  const p = b64({ iss: emisor, aud: 'authenticated', role: 'authenticated', sub: crypto.randomUUID(), email: 'fila@ejemplo.mx', iat: ahora, exp: ahora + 3600 });
  const f = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, clave, new TextEncoder().encode(c + '.' + p));
  return `${c}.${p}.${Buffer.from(f).toString('base64url')}`;
}
async function api(ruta, tk, op = {}) {
  const h = { Authorization: 'Bearer ' + tk, ...(op.cab || {}) };
  if (op.cuerpo) h['Content-Type'] = 'application/json';
  const r = await fetch(URL_PUERTA + ruta, { method: op.metodo || 'GET', headers: h, body: op.cuerpo ? JSON.stringify(op.cuerpo) : undefined });
  const tipo = r.headers.get('content-type') || '';
  const cuerpo = tipo.startsWith('text/event-stream') ? await r.text() : await r.json().catch(() => null);
  return { status: r.status, cuerpo };
}
const analizar = (tk, titulo) => api('/api/lab/analisis', tk, { metodo: 'POST', cuerpo: { ...ENTRADA, title: titulo || ENTRADA.title }, cab: TURNSTILE });
// Ocupa el único lugar: el análisis en vivo lo tiene mientras el servicio de datos responde (≥ 4 s
// por el proxy). 1.5 s basta para que el bloqueo pase Turnstile y tome el lugar primero.
async function conLugarOcupado(fn) {
  const bloqueo = analizar(await token(), 'Bloqueo de la fila');
  await espera(1500);
  const r = await fn();
  await bloqueo;
  return r;
}
async function hastaListo(tk, id, ms = 120000) {
  for (const fin = Date.now() + ms; Date.now() < fin; await espera(1500)) {
    const a = (await api('/api/analisis', tk)).cuerpo.analisis.find((x) => x.id === id);
    if (!a || a.estado !== 'fila') return a;
  }
  throw new Error('siguió en la fila');
}

test('sin lugar, el análisis entra a la fila, se corre solo y queda como un análisis normal', async () => {
  const tk = await token();
  const r = await conLugarOcupado(() => analizar(tk));
  assert.equal(r.status, 202, 'sin lugar: 202');
  assert.equal(r.cuerpo.en_fila, true);
  assert.ok(r.cuerpo.posicion >= 1);
  const lista = (await api('/api/analisis', tk)).cuerpo.analisis;
  assert.equal(lista.length, 1);
  assert.equal(lista[0].estado, 'fila', 'Mi espacio lo ve «En la fila»');
  assert.equal((await api('/api/yo', tk)).cuerpo.analisis_hoy.usados, 1, 'la fila gasta cuota al entrar');

  const a = await hastaListo(tk, r.cuerpo.id);
  assert.equal(a.estado, 'listo');
  const uno = (await api('/api/analisis/' + r.cuerpo.id, tk)).cuerpo;
  assert.equal(uno.resultado.datos.vecinas.length, 100, 'el mismo contexto que un análisis en vivo');
  assert.equal(uno.resultado.ia, null, 'sin IA en esta corrida (TOPE_IA_DIA=0)');
  assert.equal(uno.entrada.title, ENTRADA.title);
});

test('con 2 guardados no entra a la fila y la cuota se devuelve', async () => {
  const tk = await token();
  for (let i = 0; i < 2; i++) assert.equal((await api('/api/analisis', tk, { metodo: 'POST', cuerpo: { entrada: ENTRADA, resultado: { datos: {} } } })).status, 201);
  const r = await conLugarOcupado(() => analizar(tk));
  assert.equal(r.status, 409);
  assert.equal(r.cuerpo.error, 'limite_de_guardados');
  assert.equal((await api('/api/yo', tk)).cuerpo.analisis_hoy.usados, 0, 'la cuota volvió');
});

test('borrarlo antes de su turno lo saca de la fila y devuelve la cuota', async () => {
  const [a, b] = [await token(), await token()];
  // dos en fila detrás del bloqueo; el segundo se borra antes de que le toque
  const [ra, rb, borrado] = await conLugarOcupado(async () => {
    const [x, y] = await Promise.all([analizar(a, 'Primero en la fila'), analizar(b, 'Segundo en la fila')]);
    // mientras el lugar sigue ocupado: todavía no le toca a nadie
    return [x, y, y.status === 202 ? (await api('/api/analisis/' + y.cuerpo.id, b, { metodo: 'DELETE' })).status : null];
  });
  assert.equal(ra.status, 202);
  assert.equal(rb.status, 202);
  assert.equal(borrado, 204);
  await hastaListo(a, ra.cuerpo.id);
  await espera(3000);
  assert.equal((await api('/api/analisis', b)).cuerpo.analisis.length, 0);
  assert.equal((await api('/api/yo', b)).cuerpo.analisis_hoy.usados, 0, 'la cuota del borrado volvió');
});

test('solo datos (/api/lab/contexto) sin lugar: 503, sin gastar cuota', async () => {
  const tk = await token();
  const r = await conLugarOcupado(() => api('/api/lab/contexto', tk, { metodo: 'POST', cuerpo: ENTRADA, cab: TURNSTILE }));
  assert.equal(r.status, 503);
  assert.equal(r.cuerpo.error, 'servicio_ocupado');
  assert.equal((await api('/api/yo', tk)).cuerpo.analisis_hoy.usados, 0);
});
