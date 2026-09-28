// Corre un análisis completo contra el Worker (SSE) y muestra cada evento al llegar, con su tiempo.
//   node pruebas/analisis_sse.mjs [entrada.json] [--completo]
// Sin --completo, de los datos solo imprime el tamaño; las secciones de IA salen completas para
// poder revisarlas. Usa un usuario nuevo en cada corrida (token firmado con las claves locales).
import { readFileSync } from 'node:fs';

const URL_PUERTA = process.env.PUERTA_URL || 'http://127.0.0.1:8787';
const args = process.argv.slice(2);
const archivo = args.find((a) => !a.startsWith('--')) || new URL('../../../prototypes/atlas_vecindario_mvp/lab/entrada_ejemplo.json', import.meta.url);
const entrada = JSON.parse(readFileSync(archivo, 'utf8'));
const { emisor, privada } = JSON.parse(readFileSync(new URL('claves.local.json', import.meta.url)));

const b64 = (x) => Buffer.from(JSON.stringify(x)).toString('base64url');
const ahora = Math.floor(Date.now() / 1000);
const c = b64({ alg: 'ES256', kid: privada.kid }), p = b64({ iss: emisor, aud: 'authenticated', role: 'authenticated', sub: crypto.randomUUID(), exp: ahora + 600 });
const clave = await crypto.subtle.importKey('jwk', privada, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
const firma = Buffer.from(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, clave, new TextEncoder().encode(c + '.' + p))).toString('base64url');

const t0 = Date.now();
const r = await fetch(URL_PUERTA + '/api/lab/analisis', {
  method: 'POST',
  headers: { Authorization: `Bearer ${c}.${p}.${firma}`, 'Content-Type': 'application/json', 'X-Turnstile': 'XXXX.DUMMY.TOKEN.XXXX' },
  body: JSON.stringify(entrada),
});
console.log(`HTTP ${r.status} ${r.headers.get('content-type')} (${((Date.now() - t0) / 1000).toFixed(1)} s)`);
if (!r.headers.get('content-type')?.startsWith('text/event-stream')) { console.log(await r.text()); process.exit(1); }

const dec = new TextDecoder();
let buf = '';
for await (const trozo of r.body) {
  buf += dec.decode(trozo, { stream: true });
  let i;
  while ((i = buf.indexOf('\n\n')) >= 0) {
    const bloque = buf.slice(0, i); buf = buf.slice(i + 2);
    const evento = /^event: (.*)$/m.exec(bloque)?.[1];
    const datos = bloque.split('\n').filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n');
    const t = ((Date.now() - t0) / 1000).toFixed(1);
    if (evento === 'datos' && !args.includes('--completo')) console.log(`\n[${t} s] datos: ${datos.length} caracteres`);
    else console.log(`\n[${t} s] ${evento}:\n${JSON.stringify(JSON.parse(datos), null, 1)}`);
  }
}
