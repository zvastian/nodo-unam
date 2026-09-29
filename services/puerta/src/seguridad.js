// Defensas del Worker que no son la sesión (revisión de seguridad del 29-sep-2026):
// límite por IP, revisión de la configuración de producción y cabeceras de las respuestas.

import { ErrorApi } from './comun.js';

// Claves secretas de prueba de Turnstile: aprueban o reprueban siempre, sin mirar el token.
// https://developers.cloudflare.com/turnstile/troubleshooting/testing/
const TURNSTILE_PRUEBA = /^[123]x0+AA$/;

export const esProduccion = (env) => env.ENTORNO === 'produccion';

/**
 * En producción, una configuración de desarrollo abre la puerta sin que nadie lo note: un JWKS
 * local acepta tokens firmados por cualquiera, la clave de prueba de Turnstile aprueba a todos y un
 * servicio de datos sin clave lo llama cualquiera. Falla cerrado: sin esto en orden, no responde.
 * Devuelve la lista de problemas (vacía si todo está bien); no incluye valores, solo nombres.
 */
export function problemasDeConfig(env) {
  if (!esProduccion(env)) return [];
  const p = [];
  if (env.JWKS_LOCAL) p.push('JWKS_LOCAL');
  if (!/^https:\/\//.test(env.SUPABASE_URL || '')) p.push('SUPABASE_URL');
  if (!env.TURNSTILE_SECRET || TURNSTILE_PRUEBA.test(env.TURNSTILE_SECRET)) p.push('TURNSTILE_SECRET');
  if (!env.LAB_CLAVE || env.LAB_CLAVE.length < 32) p.push('LAB_CLAVE');
  if (!/^https:\/\//.test(env.LAB_URL || '')) p.push('LAB_URL');
  if ((env.ORIGENES || '').split(',').some((o) => o.trim() && !/^https:\/\//.test(o.trim()))) p.push('ORIGENES');
  if (!env.TURNSTILE_HOSTS) p.push('TURNSTILE_HOSTS');
  if (!env.LIMITE_IP || !env.LIMITE_IP_LAB || !env.LIMITE_USUARIO) p.push('LIMITE_IP');
  if (!env.FILA) p.push('FILA'); // sin la fila, cualquier cantidad de análisis iría directo a Modal
  return p;
}

/**
 * Límite por IP con el binding de Rate Limiting de Workers (por ubicación de Cloudflare, no global:
 * frena ráfagas, no es una cuota). Dos límites: uno general para toda la API y otro, más estrecho,
 * para lo costoso (el análisis). La IP no se guarda en ningún lado.
 * Sin el binding (pruebas unitarias) no limita; en producción, problemasDeConfig lo exige.
 */
export async function limitarPorIp(request, env, costoso) {
  const ip = claveIp(request.headers.get('CF-Connecting-IP'));
  const limitadores = costoso ? [env.LIMITE_IP, env.LIMITE_IP_LAB] : [env.LIMITE_IP];
  for (const l of limitadores) {
    if (!l) continue;
    const { success } = await l.limit({ key: ip });
    if (!success) throw new ErrorApi(429, 'demasiadas_peticiones', { reintentar_en_s: 60 });
  }
}

/**
 * IPv4 tal cual; IPv6 por su /64. Una conexión doméstica recibe un /64 entero (18 trillones de
 * direcciones): contar por dirección exacta no frenaría a nadie.
 */
export function claveIp(ip) {
  if (!ip) return 'sin-ip';
  if (!ip.includes(':')) return ip;
  // expande «::» para tomar los 4 primeros grupos
  const [a, b = ''] = ip.toLowerCase().split('::');
  const izq = a ? a.split(':') : [], der = b ? b.split(':') : [];
  const grupos = ip.includes('::') ? [...izq, ...Array(8 - izq.length - der.length).fill('0'), ...der] : izq;
  return grupos.slice(0, 4).map((g) => g.replace(/^0+(?=.)/, '')).join(':') + '::/64';
}

/**
 * Escrituras por usuario (guardar y borrar): D1 gratuito admite 100,000 filas escritas al día en
 * todo el sitio, y las cuotas del análisis también escriben. Sin este tope, una cuenta con muchas
 * IP podría agotarlas y dejar el Laboratorio sin servicio para todos.
 */
export async function limitarEscrituras(env, usuario) {
  if (!env.LIMITE_USUARIO) return;
  const { success } = await env.LIMITE_USUARIO.limit({ key: usuario });
  if (!success) throw new ErrorApi(429, 'demasiadas_peticiones', { reintentar_en_s: 60 });
}

/**
 * Revisa la respuesta de siteverify: además de success, que el token se haya emitido para la
 * acción del análisis y en uno de nuestros dominios. Sin esto, un token resuelto en otro sitio que
 * use la misma clave de sitio, o para otra acción, pasaría.
 */
export function turnstileValido(v, env, accion) {
  if (!v || v.success !== true) return false;
  if (accion && v.action !== accion) return false;
  const hosts = (env.TURNSTILE_HOSTS || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (hosts.length && !hosts.includes(v.hostname)) return false;
  return true;
}

/** Cabeceras de toda respuesta de la API: nada se incrusta, nada se ejecuta, nada se filtra. */
export const CABECERAS_API = {
  'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'",
  'Referrer-Policy': 'no-referrer',
  'X-Content-Type-Options': 'nosniff',
  'Cross-Origin-Resource-Policy': 'same-site',
};
