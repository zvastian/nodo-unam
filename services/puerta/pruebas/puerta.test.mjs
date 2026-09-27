// Pruebas de integración del Worker puerta contra `wrangler dev` (puerto 8787) y el servicio de
// datos (8770). Cada corrida usa usuarios nuevos, así que no depende del estado de D1 local.
//   npm run claves   (una vez)   ·   npm run migrar   ·   npm run dev   ·   npm run prueba
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const URL_PUERTA = process.env.PUERTA_URL || 'http://127.0.0.1:8787';
const { emisor, privada } = JSON.parse(readFileSync(new URL('claves.local.json', import.meta.url)));
const ENTRADA = JSON.parse(readFileSync(new URL('../../../prototypes/atlas_vecindario_mvp/bocetos/lab/entrada_ejemplo.json', import.meta.url)));
const ORIGEN = 'http://127.0.0.1:8765';
const TURNSTILE = { 'X-Turnstile': 'XXXX.DUMMY.TOKEN.XXXX' };

const b64 = (x) => Buffer.from(typeof x === 'string' ? x : JSON.stringify(x)).toString('base64url');
const claveFirma = await crypto.subtle.importKey('jwk', privada, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
const ajena = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);

async function token(datos = {}, { clave = claveFirma, cab = {} } = {}) {
  const ahora = Math.floor(Date.now() / 1000);
  const c = b64({ alg: 'ES256', typ: 'JWT', kid: privada.kid, ...cab });
  const p = b64({ iss: emisor, aud: 'authenticated', role: 'authenticated', sub: crypto.randomUUID(), email: 'prueba@ejemplo.mx', iat: ahora, exp: ahora + 3600, ...datos });
  const firma = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, clave, new TextEncoder().encode(c + '.' + p));
  return c + '.' + p + '.' + Buffer.from(firma).toString('base64url');
}

async function api(ruta, { tk, metodo = 'GET', cuerpo, cab = {} } = {}) {
  const h = { ...cab };
  if (tk) h.Authorization = 'Bearer ' + tk;
  if (cuerpo !== undefined) h['Content-Type'] = 'application/json';
  const r = await fetch(URL_PUERTA + ruta, { method: metodo, headers: h, body: cuerpo === undefined ? undefined : typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo) });
  const texto = await r.text();
  return { status: r.status, h: r.headers, json: texto ? JSON.parse(texto) : null };
}

test('salud sin sesión', async () => {
  assert.equal((await api('/api/salud')).status, 200);
});

test('rechaza tokens inválidos', async () => {
  const casos = {
    sin_token: undefined,
    token_malformado: 'abc.def.ghi',
    firma_invalida: await token({}, { clave: ajena.privateKey }),
    token_caducado: await token({ exp: Math.floor(Date.now() / 1000) - 120 }),
    emisor_incorrecto: await token({ iss: 'https://otro.supabase.co/auth/v1' }),
    rol_incorrecto: await token({ role: 'anon' }),
    clave_desconocida: await token({}, { cab: { kid: 'otra' } }),
    algoritmo_no_admitido: await token({}, { cab: { alg: 'none' } }),
  };
  for (const [motivo, tk] of Object.entries(casos)) {
    const r = await api('/api/yo', { tk });
    assert.equal(r.status, 401, motivo);
    assert.equal(r.json.motivo, motivo);
  }
});

test('CORS solo para orígenes permitidos', async () => {
  const bien = await fetch(URL_PUERTA + '/api/yo', { method: 'OPTIONS', headers: { Origin: ORIGEN } });
  assert.equal(bien.status, 204);
  assert.equal(bien.headers.get('access-control-allow-origin'), ORIGEN);
  const mal = await fetch(URL_PUERTA + '/api/yo', { method: 'OPTIONS', headers: { Origin: 'https://ajeno.example' } });
  assert.equal(mal.status, 403);
  assert.equal(mal.headers.get('access-control-allow-origin'), null);
});

test('contexto: turnstile, topes, validación y cuota diaria', async () => {
  const tk = await token();
  assert.equal((await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: ENTRADA })).json.error, 'turnstile_requerido');
  assert.equal((await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: { ...ENTRADA, problematiza: 'x'.repeat(17000) }, cab: TURNSTILE })).status, 413);
  assert.equal((await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: '{no es json', cab: TURNSTILE })).status, 400);

  const invalida = await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: { ...ENTRADA, title: 'a' }, cab: TURNSTILE });
  assert.equal(invalida.status, 422);
  assert.deepEqual(invalida.json.campos, ['title']);
  assert.ok(!JSON.stringify(invalida.json).includes('bancario'), 'el 422 no repite el texto enviado');

  const r1 = await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: ENTRADA, cab: TURNSTILE });
  assert.equal(r1.status, 200);
  assert.equal(r1.h.get('x-cuota-restante'), '1', 'el 422 no gastó cuota');
  assert.equal(r1.json.vecinas.length, 100);
  assert.ok(r1.json.ubicacion);
  const r2 = await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: ENTRADA, cab: TURNSTILE });
  assert.equal(r2.h.get('x-cuota-restante'), '0');
  const r3 = await api('/api/lab/contexto', { tk, metodo: 'POST', cuerpo: ENTRADA, cab: TURNSTILE });
  assert.equal(r3.status, 429);
  assert.equal(r3.json.error, 'cuota_diaria_agotada');
  assert.equal((await api('/api/yo', { tk })).json.analisis_hoy.usados, 2);
});

test('análisis guardados: límite de 2 y sin acceso cruzado', async () => {
  const a = await token(), b = await token();
  const guardar = (tk) => api('/api/analisis', { tk, metodo: 'POST', cuerpo: { entrada: ENTRADA, resultado: { ubicacion: {} } } });
  const g1 = await guardar(a);
  assert.equal(g1.status, 201);
  assert.equal((await guardar(a)).status, 201);
  const g3 = await guardar(a);
  assert.equal(g3.status, 409);
  assert.equal(g3.json.error, 'limite_de_guardados');

  const lista = await api('/api/analisis', { tk: a });
  assert.equal(lista.json.analisis.length, 2);
  assert.equal(lista.json.analisis[0].titulo, ENTRADA.title);

  // B no ve, no borra y no cuenta los de A.
  assert.equal((await api('/api/analisis/' + g1.json.id, { tk: b })).status, 404);
  assert.equal((await api('/api/analisis/' + g1.json.id, { tk: b, metodo: 'DELETE' })).status, 404);
  assert.equal((await api('/api/analisis', { tk: b })).json.analisis.length, 0);
  assert.equal((await guardar(b)).status, 201);

  const uno = await api('/api/analisis/' + g1.json.id, { tk: a });
  assert.equal(uno.json.entrada.title, ENTRADA.title);
  assert.equal((await api('/api/analisis/' + g1.json.id, { tk: a, metodo: 'DELETE' })).status, 204);
  assert.equal((await guardar(a)).status, 201, 'al borrar uno se libera el lugar');
});

test('tesis guardadas: idempotente, id validado y sin acceso cruzado', async () => {
  const a = await token(), b = await token();
  assert.equal((await api('/api/tesis/TH_000123', { tk: a, metodo: 'PUT' })).status, 204);
  assert.equal((await api('/api/tesis/TH_000123', { tk: a, metodo: 'PUT' })).status, 204);
  assert.equal((await api('/api/tesis/' + encodeURIComponent("x' OR 1=1"), { tk: a, metodo: 'PUT' })).status, 400);
  assert.deepEqual((await api('/api/tesis', { tk: a })).json.tesis.map((t) => t.tesis), ['TH_000123']);
  assert.equal((await api('/api/tesis', { tk: b })).json.tesis.length, 0);
  await api('/api/tesis/TH_000123', { tk: b, metodo: 'DELETE' });
  assert.equal((await api('/api/tesis', { tk: a })).json.tesis.length, 1, 'B no borra las de A');
});

test('borrar la cuenta borra sus datos y solo los suyos', async () => {
  const a = await token(), b = await token();
  await api('/api/tesis/TH_1', { tk: a, metodo: 'PUT' });
  await api('/api/tesis/TH_1', { tk: b, metodo: 'PUT' });
  await api('/api/analisis', { tk: a, metodo: 'POST', cuerpo: { entrada: ENTRADA, resultado: {} } });
  assert.equal((await api('/api/cuenta', { tk: a, metodo: 'DELETE' })).status, 204);
  const yo = (await api('/api/yo', { tk: a })).json;
  assert.equal(yo.tesis_guardadas, 0);
  assert.equal(yo.analisis_guardados.usados, 0);
  assert.equal((await api('/api/yo', { tk: b })).json.tesis_guardadas, 1);
});

test('rutas desconocidas y métodos no admitidos', async () => {
  const tk = await token();
  assert.equal((await api('/api/nada', { tk })).status, 404);
  assert.equal((await api('/api/analisis/no-es-uuid', { tk })).status, 404);
  assert.equal((await api('/api/yo', { tk, metodo: 'DELETE' })).status, 404);
});
