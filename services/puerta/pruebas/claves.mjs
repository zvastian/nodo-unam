// Prepara el entorno local del Worker: un par de claves ES256 de prueba (el papel de Supabase),
// la clave compartida con el servicio de datos y la clave de prueba de Turnstile que siempre
// aprueba. Escribe .dev.vars y pruebas/claves.local.json; ninguno se versiona.
import { writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
const { subtle } = globalThis.crypto;

const par = await subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
const kid = 'local-' + randomBytes(4).toString('hex');
const publica = { ...(await subtle.exportKey('jwk', par.publicKey)), kid, alg: 'ES256', use: 'sig' };
const privada = { ...(await subtle.exportKey('jwk', par.privateKey)), kid, alg: 'ES256' };
const emisor = 'http://supabase.local/auth/v1';
const labClave = randomBytes(24).toString('base64url');

const dir = new URL('..', import.meta.url);
writeFileSync(new URL('pruebas/claves.local.json', dir), JSON.stringify({ emisor, privada, labClave }, null, 1));
writeFileSync(new URL('.dev.vars', dir), [
  `JWKS_LOCAL=${JSON.stringify({ keys: [publica] })}`,
  `JWT_EMISOR=${emisor}`,
  // Claves de prueba públicas de Turnstile: 1x… siempre aprueba.
  'TURNSTILE_SECRET=1x0000000000000000000000000000000AA',
  `LAB_CLAVE=${labClave}`,
  '',
].join('\n'));
console.log('Listo: .dev.vars y pruebas/claves.local.json (kid ' + kid + ').');
console.log('Arranca el servicio de datos con LAB_CLAVE=' + labClave);
