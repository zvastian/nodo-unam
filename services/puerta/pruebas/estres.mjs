// Prueba de estrés de la fila (paso 4 de la lista de lanzamiento): N estudiantes, cada uno con su
// cuenta y su IP, piden un análisis al mismo tiempo. Contra `wrangler dev` con pruebas/wrangler.ci.jsonc
// y el servicio simulado (sin IA: no gasta Groq ni Modal). Comprueba que:
//   - nadie recibe un 5xx ni un 429: cada uno corre en vivo (200) o entra a la fila (202);
//   - los de la fila terminan todos «listo», con las 100 vecinas;
//   - cada cuenta gastó exactamente 1 análisis de su cuota;
//   - el servicio de datos nunca atendió más de FILA_SIMULTANEOS a la vez.
//   node pruebas/estres.mjs [N=50]
import { readFileSync } from 'node:fs';

const N = +(process.argv[2] || 50);
const PUERTA = process.env.PUERTA_URL || 'http://127.0.0.1:8787';
const SERVICIO = process.env.SERVICIO_URL || 'http://127.0.0.1:8770';
const SIMULTANEOS = +(process.env.FILA_SIMULTANEOS || 2);
const { emisor, privada } = JSON.parse(readFileSync(new URL('claves.local.json', import.meta.url)));
const ENTRADA = JSON.parse(readFileSync(new URL('../../../prototypes/atlas_vecindario_mvp/lab/entrada_ejemplo.json', import.meta.url)));
const b64 = (x) => Buffer.from(JSON.stringify(x)).toString('base64url');
const clave = await crypto.subtle.importKey('jwk', privada, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
const pct = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : 0; };

async function token() {
  const ahora = Math.floor(Date.now() / 1000);
  const c = b64({ alg: 'ES256', typ: 'JWT', kid: privada.kid });
  const p = b64({ iss: emisor, aud: 'authenticated', role: 'authenticated', sub: crypto.randomUUID(), iat: ahora, exp: ahora + 3600 });
  const f = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, clave, new TextEncoder().encode(c + '.' + p));
  return `${c}.${p}.${Buffer.from(f).toString('base64url')}`;
}
const api = async (ruta, tk, ip) => (await fetch(PUERTA + ruta, { headers: { Authorization: 'Bearer ' + tk, 'CF-Connecting-IP': ip } })).json();

const antes = await (await fetch(SERVICIO + '/salud')).json();
const estudiantes = await Promise.all(Array.from({ length: N }, async (_, i) => ({ tk: await token(), ip: `198.18.${i >> 8}.${i & 255}` })));
console.log(`${N} análisis a la vez contra ${PUERTA} (servicio: ${SIMULTANEOS} a la vez)…`);

const t0 = Date.now();
const res = await Promise.all(estudiantes.map(async (e) => {
  const r = await fetch(PUERTA + '/api/lab/analisis', {
    method: 'POST', body: JSON.stringify(ENTRADA),
    headers: { Authorization: 'Bearer ' + e.tk, 'Content-Type': 'application/json', 'X-Turnstile': 'x', 'CF-Connecting-IP': e.ip },
  });
  const texto = await r.text();
  const out = { ...e, status: r.status, ms: Date.now() - t0 };
  if (r.status === 200) out.eventos = [...texto.matchAll(/^event: (.*)$/gm)].map((m) => m[1]);
  else { try { out.cuerpo = JSON.parse(texto); } catch { out.cuerpo = texto.slice(0, 120); } }
  return out;
}));

const vivos = res.filter((r) => r.status === 200), fila = res.filter((r) => r.status === 202), malos = res.filter((r) => r.status !== 200 && r.status !== 202);
console.log(`en vivo (200): ${vivos.length}   a la fila (202): ${fila.length}   otros: ${malos.length}`);
malos.forEach((m) => console.log('  ', m.status, JSON.stringify(m.cuerpo)));
const vivosCompletos = vivos.filter((v) => v.eventos.includes('datos') && v.eventos.includes('fin')).length;
console.log(`en vivo con datos y fin: ${vivosCompletos}/${vivos.length}; espera en vivo p50 ${pct(vivos.map((v) => v.ms), 0.5)} ms, p95 ${pct(vivos.map((v) => v.ms), 0.95)} ms`);

// la fila se vacía sola: cada uno de la fila termina «listo»
const pendientes = new Set(fila.map((f) => f.cuerpo.id));
const listos = {};
for (const fin = Date.now() + 10 * 60 * 1000; pendientes.size && Date.now() < fin; await espera(1000)) {
  await Promise.all(fila.filter((f) => pendientes.has(f.cuerpo.id)).map(async (f) => {
    const a = (await api('/api/analisis', f.tk, f.ip)).analisis.find((x) => x.id === f.cuerpo.id);
    if (!a) { pendientes.delete(f.cuerpo.id); listos[f.cuerpo.id] = 'desaparecio'; }
    else if (a.estado === 'listo') { pendientes.delete(f.cuerpo.id); listos[f.cuerpo.id] = Date.now() - t0; }
  }));
}
const tiempos = Object.values(listos).filter((x) => typeof x === 'number');
console.log(`fila: ${tiempos.length}/${fila.length} listos, ${Object.values(listos).filter((x) => x === 'desaparecio').length} desaparecidos, ${pendientes.size} sin terminar; la fila se vació en ${Math.max(0, ...tiempos)} ms`);
let completos = 0;
for (const f of fila.slice(0, 5)) {
  const uno = await api('/api/analisis/' + f.cuerpo.id, f.tk, f.ip);
  if (uno.resultado && uno.resultado.datos && uno.resultado.datos.vecinas && uno.resultado.datos.vecinas.length === 100) completos++;
}
console.log(`muestra de la fila con las 100 vecinas: ${completos}/${Math.min(5, fila.length)}`);

const usados = await Promise.all(estudiantes.map(async (e) => (await api('/api/yo', e.tk, e.ip)).analisis_hoy.usados));
const cuotaBien = usados.filter((u) => u === 1).length;
console.log(`cuentas con exactamente 1 análisis gastado: ${cuotaBien}/${N}`);

const despues = await (await fetch(SERVICIO + '/salud')).json();
console.log(`servicio: ${despues.atendidas - antes.atendidas} peticiones; máximo simultáneo ${despues.max_simultaneas} (tope ${SIMULTANEOS})`);

const ok = malos.length === 0 && vivosCompletos === vivos.length && tiempos.length === fila.length && cuotaBien === N
  && despues.max_simultaneas <= SIMULTANEOS && despues.atendidas - antes.atendidas === N;
console.log(ok ? 'RESULTADO: bien' : 'RESULTADO: FALLA');
process.exit(ok ? 0 : 1);
