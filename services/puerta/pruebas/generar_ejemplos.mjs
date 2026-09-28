// Genera los análisis de ejemplo de la presentación del Laboratorio: corre cada entrada de
// prototypes/atlas_vecindario_mvp/lab/ejemplos/<id>/entrada.json contra el Worker local (datos del
// servicio real + IA real) y guarda lo que devuelve en datos.json e ia.json junto a la entrada.
//   node pruebas/generar_ejemplos.mjs [id…]      (con `wrangler dev` y el servicio de datos levantados)
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';

const URL_PUERTA = process.env.PUERTA_URL || 'http://127.0.0.1:8787';
const BASE = new URL('../../../prototypes/atlas_vecindario_mvp/lab/ejemplos/', import.meta.url);
const { emisor, privada } = JSON.parse(readFileSync(new URL('claves.local.json', import.meta.url)));
const ids = process.argv.slice(2).length ? process.argv.slice(2) : readdirSync(BASE, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name);

const b64 = (x) => Buffer.from(JSON.stringify(x)).toString('base64url');
async function token() {
  const ahora = Math.floor(Date.now() / 1000);
  const c = b64({ alg: 'ES256', kid: privada.kid }), p = b64({ iss: emisor, aud: 'authenticated', role: 'authenticated', sub: crypto.randomUUID(), exp: ahora + 600 });
  const clave = await crypto.subtle.importKey('jwk', privada, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const firma = Buffer.from(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, clave, new TextEncoder().encode(c + '.' + p))).toString('base64url');
  return `${c}.${p}.${firma}`;
}

for (const id of ids) {
  const entrada = JSON.parse(readFileSync(new URL(`${id}/entrada.json`, BASE), 'utf8'));
  const t0 = Date.now();
  const r = await fetch(URL_PUERTA + '/api/lab/analisis', {
    method: 'POST',
    headers: { Authorization: `Bearer ${await token()}`, 'Content-Type': 'application/json', 'X-Turnstile': 'XXXX.DUMMY.TOKEN.XXXX' },
    body: JSON.stringify(entrada),
  });
  if (!r.headers.get('content-type')?.startsWith('text/event-stream')) { console.log(id, 'HTTP', r.status, await r.text()); continue; }
  const eventos = {}, dec = new TextDecoder();
  let buf = '';
  for await (const trozo of r.body) {
    buf += dec.decode(trozo, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const bloque = buf.slice(0, i); buf = buf.slice(i + 2);
      const evento = /^event: (.*)$/m.exec(bloque)?.[1];
      const datos = bloque.split('\n').filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n');
      eventos[evento] = JSON.parse(datos);
    }
  }
  const { datos, lexico, fin, error, ia_agotada, ...ia } = eventos;
  if (datos) writeFileSync(new URL(`${id}/datos.json`, BASE), JSON.stringify(datos));
  // si la IA se agota a medias (límite por minuto del proveedor), se conservan las secciones de la corrida anterior
  let previa = {}; try { previa = JSON.parse(readFileSync(new URL(`${id}/ia.json`, BASE), 'utf8')); } catch { /* primera corrida */ }
  writeFileSync(new URL(`${id}/ia.json`, BASE), JSON.stringify({ ...previa, _nota: `Salida real de la IA (Worker local, ${new Date().toISOString().slice(0, 10)}).`, ...ia }, null, 1));
  console.log(id, `${((Date.now() - t0) / 1000).toFixed(1)} s`, 'eventos:', Object.keys(eventos).join(', '), error ? 'ERROR ' + JSON.stringify(error) : '', ia_agotada ? 'IA AGOTADA ' + JSON.stringify(ia_agotada) : '');
}
