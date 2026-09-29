// Pruebas de las defensas del Worker que no necesitan wrangler ni el servicio de datos (29-sep-2026):
// sesión (JWT), límite por IP, configuración de producción, Turnstile, tope del cuerpo y cabeceras.
// node --test pruebas/seguridad.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/index.js';
import { leerJson, responder, validarEntrada } from '../src/comun.js';
import { claveIp, problemasDeConfig, turnstileValido } from '../src/seguridad.js';
import { SinSesion, usuarioDe } from '../src/sesion.js';

const { subtle } = globalThis.crypto;
const EMISOR = 'http://supabase.local/auth/v1';
const SUB = '0f0e0d0c-0b0a-4908-8706-050403020100';

// Un solo par de claves para todo el archivo: la caché del JWKS es del módulo.
const par = await subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
const KID = 'prueba-1';
const JWKS = JSON.stringify({ keys: [{ ...(await subtle.exportKey('jwk', par.publicKey)), kid: KID, alg: 'ES256', use: 'sig' }] });
const ENV = { JWKS_LOCAL: JWKS, JWT_EMISOR: EMISOR };

const b64 = (x) => Buffer.from(typeof x === 'string' ? x : JSON.stringify(x)).toString('base64url');
async function token(datos = {}, cab = {}) {
  const ahora = Math.floor(Date.now() / 1000);
  const h = b64({ alg: 'ES256', typ: 'JWT', kid: KID, ...cab });
  const p = b64({ iss: EMISOR, aud: 'authenticated', role: 'authenticated', sub: SUB, email: 'a@b.mx', exp: ahora + 600, ...datos });
  const firma = await subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, par.privateKey, new TextEncoder().encode(h + '.' + p));
  return `${h}.${p}.${Buffer.from(firma).toString('base64url')}`;
}
const pedir = (tk) => new Request('https://api.local/api/yo', { headers: tk ? { Authorization: 'Bearer ' + tk } : {} });
async function motivo(promesa) {
  try { await promesa; return 'aceptado'; } catch (e) { assert.ok(e instanceof SinSesion, e.message); return e.message; }
}

test('sesión: acepta un token válido y rechaza los alterados', async () => {
  assert.deepEqual(await usuarioDe(pedir(await token()), ENV), { id: SUB, correo: 'a@b.mx' });
  assert.equal(await motivo(usuarioDe(pedir(null), ENV)), 'sin_token');
  assert.equal(await motivo(usuarioDe(pedir(await token({ iss: 'https://otro.supabase.co/auth/v1' })), ENV)), 'emisor_incorrecto');
  assert.equal(await motivo(usuarioDe(pedir(await token({ aud: 'anon' })), ENV)), 'rol_incorrecto');
  assert.equal(await motivo(usuarioDe(pedir(await token({ role: 'service_role' })), ENV)), 'rol_incorrecto');
  assert.equal(await motivo(usuarioDe(pedir(await token({ exp: Math.floor(Date.now() / 1000) - 120 })), ENV)), 'token_caducado');
  assert.equal(await motivo(usuarioDe(pedir(await token({ is_anonymous: true })), ENV)), 'usuario_anonimo');
  assert.equal(await motivo(usuarioDe(pedir(await token({}, { alg: 'HS256' })), ENV)), 'algoritmo_no_admitido');
  // alg «none» sin firma: el formato ni siquiera pasa
  const [h, p] = (await token()).split('.');
  assert.equal(await motivo(usuarioDe(pedir(b64({ alg: 'none', kid: KID }) + '.' + p + '.'), ENV)), 'sin_token');
  // la carga cambiada después de firmar
  const otro = b64({ ...JSON.parse(Buffer.from(p, 'base64url')), sub: 'ffffffff-ffff-4fff-8fff-ffffffffffff' });
  assert.equal(await motivo(usuarioDe(pedir(h + '.' + otro + '.' + (await token()).split('.')[2]), ENV)), 'firma_invalida');
});

const PROD_BIEN = {
  ENTORNO: 'produccion', SUPABASE_URL: 'https://x.supabase.co', TURNSTILE_SECRET: '0x4AAAAAAAbcdefghijklmnopqrstuvwxyz',
  LAB_CLAVE: 'k'.repeat(32), LAB_URL: 'https://lab.modal.run', ORIGENES: 'https://nodosmap.com',
  TURNSTILE_HOSTS: 'nodosmap.com', LIMITE_IP: {}, LIMITE_IP_LAB: {}, LIMITE_USUARIO: {}, FILA: {},
};

test('configuración: en producción falla cerrado con valores de desarrollo', async () => {
  assert.deepEqual(problemasDeConfig({ ENTORNO: 'local', JWKS_LOCAL: '{}' }), []);
  assert.deepEqual(problemasDeConfig(PROD_BIEN), []);
  const mal = problemasDeConfig({
    ENTORNO: 'produccion', JWKS_LOCAL: '{}', SUPABASE_URL: 'https://x.supabase.co',
    TURNSTILE_SECRET: '1x0000000000000000000000000000000AA', LAB_CLAVE: 'corta', LAB_URL: 'http://127.0.0.1:8770',
    ORIGENES: 'https://nodosmap.com,http://127.0.0.1:8765',
  });
  assert.deepEqual(mal.sort(), ['FILA', 'JWKS_LOCAL', 'LAB_CLAVE', 'LAB_URL', 'LIMITE_IP', 'ORIGENES', 'TURNSTILE_HOSTS', 'TURNSTILE_SECRET']);
  const r = await worker.fetch(new Request('https://api.local/api/salud'), { ...PROD_BIEN, JWKS_LOCAL: '{}' }, {});
  assert.equal(r.status, 503);
  assert.equal((await r.json()).error, 'servicio_no_disponible');
});

const limitador = (ok) => ({ llamadas: [], async limit(o) { this.llamadas.push(o.key); return { success: ok }; } });

test('límite por IP: antes de la sesión, y el del análisis solo en lo costoso', async () => {
  const cab = { 'CF-Connecting-IP': '203.0.113.7' };
  let env = { ...ENV, LIMITE_IP: limitador(false), LIMITE_IP_LAB: limitador(true) };
  let r = await worker.fetch(new Request('https://api.local/api/salud', { headers: cab }), env, {});
  assert.equal(r.status, 429);
  assert.equal((await r.json()).error, 'demasiadas_peticiones');
  assert.deepEqual(env.LIMITE_IP.llamadas, ['203.0.113.7']);

  env = { ...ENV, LIMITE_IP: limitador(true), LIMITE_IP_LAB: limitador(false) };
  r = await worker.fetch(new Request('https://api.local/api/yo', { headers: cab }), env, {});
  assert.equal(r.status, 401, 'lo barato no usa el límite del análisis');
  assert.equal(env.LIMITE_IP_LAB.llamadas.length, 0);
  r = await worker.fetch(new Request('https://api.local/api/lab/analisis', { method: 'POST', headers: cab, body: '{}' }), env, {});
  assert.equal(r.status, 429, 'el análisis se frena antes de pedir sesión');
});

test('límite por IP: IPv6 cuenta por su /64', () => {
  assert.equal(claveIp('203.0.113.7'), '203.0.113.7');
  assert.equal(claveIp(null), 'sin-ip');
  const k = claveIp('2001:db8:abcd:12:1111:2222:3333:4444');
  assert.equal(k, '2001:db8:abcd:12::/64');
  assert.equal(claveIp('2001:0db8:abcd:0012:ffff::1'), k, 'otra dirección del mismo /64, con ceros a la izquierda');
  assert.equal(claveIp('2001:db8:abcd:12::'), k);
  assert.notEqual(claveIp('2001:db8:abcd:13::1'), k);
  assert.equal(claveIp('2001:db8::1'), '2001:db8:0:0::/64');
});

test('entrada del análisis: tipos y topes del servicio, sin campos ajenos', () => {
  const buena = { title: 'Una tesis', problematiza: 'p', keywords: ['a'], objectives: ['Analizar x'], program: 'Derecho', degree: 'Maestría',
    study_period: { applies: true, start_year: 1990, end_year: 2020, label: '1990-2020' } };
  assert.deepEqual(validarEntrada({ ...buena, extra: 'fuera', __proto__: { admin: 1 } }), buena);
  assert.deepEqual(validarEntrada({ title: 'abc' }), { title: 'abc', keywords: [], objectives: [] });
  const campos = (e) => { try { validarEntrada(e); return []; } catch (x) { assert.equal(x.status, 400); return x.extra.campos.sort(); } };
  assert.deepEqual(campos({ title: 'ab' }), ['title']);
  assert.deepEqual(campos({ title: 12345 }), ['title']);
  assert.deepEqual(campos({}), ['title']);
  assert.deepEqual(campos({ title: 'abc', objectives: 'Analizar algo' }), ['objectives']);
  assert.deepEqual(campos({ title: 'abc', objectives: Array(9).fill('Analizar') }), ['objectives']);
  assert.deepEqual(campos({ title: 'abc', objectives: [null] }), ['objectives']);
  assert.deepEqual(campos({ title: 'abc', keywords: { a: 1 } }), ['keywords']);
  assert.deepEqual(campos({ title: 'abc', problematiza: 'x'.repeat(2001) }), ['problematiza']);
  assert.deepEqual(campos({ title: 'abc', study_period: { applies: 'sí' } }), ['study_period']);
  assert.deepEqual(campos({ title: 'abc', study_period: { start_year: 1.5 } }), ['study_period']);
  assert.deepEqual(campos({ title: 'abc', study_period: [] }), ['study_period']);
});

test('Turnstile: exige acción y dominio, además de success', () => {
  const env = { TURNSTILE_HOSTS: 'nodosmap.com,www.nodosmap.com' };
  const v = { success: true, action: 'analisis', hostname: 'nodosmap.com' };
  assert.equal(turnstileValido(v, env, 'analisis'), true);
  assert.equal(turnstileValido({ ...v, success: false }, env, 'analisis'), false);
  assert.equal(turnstileValido({ ...v, action: 'login' }, env, 'analisis'), false);
  assert.equal(turnstileValido({ ...v, hostname: 'otro-sitio.com' }, env, 'analisis'), false);
  assert.equal(turnstileValido({ success: true, action: 'x', hostname: 'example.com' }, {}, null), true, 'en local, las claves de prueba');
  assert.equal(turnstileValido(null, env, 'analisis'), false);
});

test('cuerpo: corta un envío por partes que pasa el tope, sin leerlo entero', async () => {
  let leidos = 0;
  const cuerpo = new ReadableStream({
    pull(c) { leidos++; if (leidos > 100) { c.close(); return; } c.enqueue(new Uint8Array(1024).fill(32)); },
  });
  const req = new Request('https://api.local/x', { method: 'POST', body: cuerpo, duplex: 'half' });
  await assert.rejects(leerJson(req, 4 * 1024), (e) => e.status === 413);
  assert.ok(leidos < 10, `leyó ${leidos} partes`);
  const bytes = new Uint8Array([0x7b, 0xff, 0x7d]); // «{\xff}»: UTF-8 inválido
  await assert.rejects(leerJson(new Request('https://api.local/x', { method: 'POST', body: bytes }), 1024), (e) => e.status === 400);
  assert.deepEqual(await leerJson(new Request('https://api.local/x', { method: 'POST', body: '{"a":"ñ"}' }), 1024), { a: 'ñ' });
});

test('respuestas: sin caché, sin incrustar y sin ejecutar', () => {
  const r = responder({ ok: true }, 200, {});
  assert.equal(r.headers.get('Cache-Control'), 'no-store');
  assert.equal(r.headers.get('X-Content-Type-Options'), 'nosniff');
  assert.match(r.headers.get('Content-Security-Policy'), /default-src 'none'/);
  assert.equal(r.headers.get('Referrer-Policy'), 'no-referrer');
});
