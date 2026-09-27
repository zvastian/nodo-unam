// Sesión: verifica el JWT de Supabase Auth con sus claves públicas (JWKS) y WebCrypto.
// Solo acepta ES256 y RS256, tokens de rol «authenticated», con emisor y audiencia correctos
// y sin caducar. Nada de esto confía en datos del cliente que no estén firmados.

const ALGS = {
  ES256: { importar: { name: 'ECDSA', namedCurve: 'P-256' }, verificar: { name: 'ECDSA', hash: 'SHA-256' } },
  RS256: { importar: { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, verificar: { name: 'RSASSA-PKCS1-v1_5' } },
};
const HOLGURA_S = 30;           // diferencia de reloj tolerada en exp y nbf
const JWKS_VIGENCIA_MS = 10 * 60 * 1000;
const JWKS_REINTENTO_MS = 60 * 1000;  // un kid desconocido vuelve a pedir el JWKS, a lo más cada minuto

let cache = { claves: new Map(), hasta: 0, pedido: 0 };

export class SinSesion extends Error {
  constructor(motivo) { super(motivo); this.name = 'SinSesion'; }
}

function b64url(s) {
  const b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}
const json = (bytes) => JSON.parse(new TextDecoder().decode(bytes));

function emisor(env) {
  return env.JWT_EMISOR || (env.SUPABASE_URL ? env.SUPABASE_URL.replace(/\/$/, '') + '/auth/v1' : '');
}

async function cargarJwks(env, forzar) {
  const ahora = Date.now();
  if (!forzar && ahora < cache.hasta) return;
  if (forzar && ahora - cache.pedido < JWKS_REINTENTO_MS) return;
  cache.pedido = ahora;
  let jwks;
  if (env.JWKS_LOCAL) {
    jwks = JSON.parse(env.JWKS_LOCAL);
  } else {
    if (!env.SUPABASE_URL) throw new Error('falta SUPABASE_URL');
    const r = await fetch(emisor(env) + '/.well-known/jwks.json', { cf: { cacheTtl: 600 } });
    if (!r.ok) throw new Error('JWKS respondió ' + r.status);
    jwks = await r.json();
  }
  const claves = new Map();
  for (const jwk of jwks.keys || []) {
    const alg = ALGS[jwk.alg];
    if (!alg || !jwk.kid || (jwk.use && jwk.use !== 'sig')) continue;
    claves.set(jwk.kid, { alg: jwk.alg, clave: await crypto.subtle.importKey('jwk', jwk, alg.importar, false, ['verify']) });
  }
  cache = { claves, hasta: ahora + JWKS_VIGENCIA_MS, pedido: ahora };
}

/** Devuelve { id, correo } del usuario del token Bearer, o lanza SinSesion. */
export async function usuarioDe(request, env) {
  const m = /^Bearer\s+([\w-]+)\.([\w-]+)\.([\w-]+)$/.exec(request.headers.get('Authorization') || '');
  if (!m) throw new SinSesion('sin_token');
  let cab, datos;
  try { cab = json(b64url(m[1])); datos = json(b64url(m[2])); } catch { throw new SinSesion('token_malformado'); }
  if (!ALGS[cab.alg] || !cab.kid) throw new SinSesion('algoritmo_no_admitido');

  await cargarJwks(env, false);
  if (!cache.claves.has(cab.kid)) await cargarJwks(env, true);  // rotación de claves
  const k = cache.claves.get(cab.kid);
  if (!k || k.alg !== cab.alg) throw new SinSesion('clave_desconocida');

  const firmado = new TextEncoder().encode(m[1] + '.' + m[2]);
  const valido = await crypto.subtle.verify(ALGS[cab.alg].verificar, k.clave, b64url(m[3]), firmado);
  if (!valido) throw new SinSesion('firma_invalida');

  const ahora = Math.floor(Date.now() / 1000);
  if (typeof datos.exp !== 'number' || datos.exp + HOLGURA_S < ahora) throw new SinSesion('token_caducado');
  if (typeof datos.nbf === 'number' && datos.nbf - HOLGURA_S > ahora) throw new SinSesion('token_aun_no_valido');
  if (datos.iss !== emisor(env)) throw new SinSesion('emisor_incorrecto');
  const aud = Array.isArray(datos.aud) ? datos.aud : [datos.aud];
  if (!aud.includes('authenticated') || datos.role !== 'authenticated') throw new SinSesion('rol_incorrecto');
  if (typeof datos.sub !== 'string' || !/^[0-9a-f-]{36}$/i.test(datos.sub)) throw new SinSesion('sin_usuario');

  return { id: datos.sub.toLowerCase(), correo: datos.email || '' };
}
