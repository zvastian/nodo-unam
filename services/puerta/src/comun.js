// Piezas comunes del Worker puerta: errores, respuestas, topes, Turnstile, cuotas y la llamada al
// servicio de datos. Ni el texto de la tesis ni el cuerpo de ninguna petición van a los logs.

import { CABECERAS_API, turnstileValido } from './seguridad.js';

export const TOPE_ENTRADA = 16 * 1024;     // bytes de la entrada del análisis
const ESPERA_LAB_MS = 90 * 1000;           // incluye el arranque en frío del servicio
const ESPERA_TURNSTILE_MS = 10 * 1000;

export class ErrorApi extends Error {
  constructor(status, codigo, extra) { super(codigo); this.status = status; this.extra = extra; }
}

// Día en la Ciudad de México (UTC-6 todo el año desde 2022).
export const hoy = () => new Date(Date.now() - 6 * 3600 * 1000).toISOString().slice(0, 10);
export const entero = (v, def) => (Number.isFinite(+v) && v !== '' && v !== undefined ? +v : def);

export function responder(cuerpo, status, extra) {
  const h = { 'Cache-Control': 'no-store', ...CABECERAS_API, ...extra };
  if (cuerpo === null) return new Response(null, { status, headers: h });
  h['Content-Type'] = 'application/json; charset=utf-8';
  return new Response(typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo), { status, headers: h });
}

/**
 * Lee el cuerpo como JSON sin pasar de `tope` bytes. Nunca registra el contenido.
 * Lee por partes y corta en cuanto pasa el tope: un cuerpo sin Content-Length (chunked) no llega
 * entero a memoria antes de medirse.
 */
export async function leerJson(request, tope) {
  const declarado = +request.headers.get('Content-Length');
  if (declarado > tope) throw new ErrorApi(413, 'entrada_demasiado_grande');
  const partes = [];
  let total = 0;
  if (request.body) {
    const lector = request.body.getReader();
    for (;;) {
      const { done, value } = await lector.read();
      if (done) break;
      total += value.byteLength;
      if (total > tope) { lector.cancel().catch(() => {}); throw new ErrorApi(413, 'entrada_demasiado_grande'); }
      partes.push(value);
    }
  }
  const bytes = new Uint8Array(total);
  let i = 0;
  for (const p of partes) { bytes.set(p, i); i += p.byteLength; }
  let texto;
  try { texto = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { throw new ErrorApi(400, 'json_invalido'); }
  try {
    const v = JSON.parse(texto);
    if (!v || typeof v !== 'object' || Array.isArray(v)) throw 0;
    return v;
  } catch { throw new ErrorApi(400, 'json_invalido'); }
}

/**
 * Forma de la entrada del análisis, con los mismos topes que el servicio de datos (services/lab,
 * clase Entrada). Se revisa aquí, antes del léxico, de Turnstile y de la cuota: una entrada con
 * tipos cambiados (objetivos como texto) tiraba el Worker con un 500, y una con 5,000 objetivos
 * recorría el léxico antes de que el servicio la rechazara. Devuelve solo los campos conocidos.
 */
export function validarEntrada(e) {
  const mal = [];
  const texto = (k, min, max, obligatorio) => {
    const v = e[k];
    if (v === undefined || v === null) { if (obligatorio) mal.push(k); return obligatorio ? '' : undefined; }
    if (typeof v !== 'string' || v.length < min || v.length > max) { mal.push(k); return ''; }
    return v;
  };
  const lista = (k, maxItems, maxLargo) => {
    const v = e[k];
    if (v === undefined || v === null) return [];
    if (!Array.isArray(v) || v.length > maxItems || v.some((x) => typeof x !== 'string' || x.length > maxLargo)) { mal.push(k); return []; }
    return v;
  };
  const o = {
    title: texto('title', 3, 400, true),
    problematiza: texto('problematiza', 0, 2000),
    keywords: lista('keywords', 12, 200),
    objectives: lista('objectives', 8, 1000),
    program: texto('program', 0, 160),
    degree: texto('degree', 0, 40),
  };
  const p = e.study_period;
  if (p !== undefined && p !== null) {
    const anio = (x) => x === null || x === undefined || (Number.isInteger(x) && x >= 0 && x <= 3000);
    if (typeof p !== 'object' || Array.isArray(p) || (p.applies !== undefined && typeof p.applies !== 'boolean')
      || !anio(p.start_year) || !anio(p.end_year) || (p.label !== undefined && (typeof p.label !== 'string' || p.label.length > 40))) mal.push('study_period');
    else o.study_period = { applies: !!p.applies, start_year: p.start_year ?? null, end_year: p.end_year ?? null, label: p.label || '' };
  }
  if (mal.length) throw new ErrorApi(400, 'entrada_invalida', { campos: mal });
  for (const k of Object.keys(o)) if (o[k] === undefined) delete o[k];
  return o;
}

// El widget del Laboratorio se renderiza con esta acción; un token de otra acción no sirve aquí.
export const ACCION_TURNSTILE = 'analisis';

export async function verificarTurnstile(request, env) {
  const token = request.headers.get('X-Turnstile');
  if (!token || token.length > 2048) throw new ErrorApi(403, 'turnstile_requerido');
  if (!env.TURNSTILE_SECRET) throw new Error('falta TURNSTILE_SECRET');
  const f = new FormData();
  f.append('secret', env.TURNSTILE_SECRET);
  f.append('response', token);
  const ip = request.headers.get('CF-Connecting-IP');
  if (ip) f.append('remoteip', ip);
  let v = {};
  try {
    const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: f, signal: AbortSignal.timeout(ESPERA_TURNSTILE_MS) });
    v = await r.json().catch(() => ({}));
  } catch (e) {
    console.log(JSON.stringify({ evento: 'turnstile_inalcanzable', nombre: e.name }));
    throw new ErrorApi(503, 'servicio_no_disponible');
  }
  // Las claves de prueba responden con action y hostname fijos: la acción solo se exige en producción.
  const accion = env.ENTORNO === 'produccion' ? ACCION_TURNSTILE : null;
  if (!turnstileValido(v, env, accion)) throw new ErrorApi(403, 'turnstile_invalido');
}

// --- Cuotas: un solo UPSERT atómico que solo suma si no se llegó al límite. ---

export async function tomarCuota(env, usuario, dia) {
  const tope = entero(env.TOPE_SITIO_DIA, 500);
  const limite = entero(env.CUOTA_USUARIO_DIA, 2);
  const sitio = await env.DB.prepare(
    `INSERT INTO cuota_sitio (dia, tipo, n) VALUES (?1, 'datos', 1)
     ON CONFLICT (dia, tipo) DO UPDATE SET n = n + 1 WHERE n < ?2 RETURNING n`,
  ).bind(dia, tope).first();
  if (!sitio) throw new ErrorApi(429, 'cupo_del_sitio_agotado');
  const propia = await env.DB.prepare(
    `INSERT INTO cuota_diaria (usuario, dia, n) VALUES (?1, ?2, 1)
     ON CONFLICT (usuario, dia) DO UPDATE SET n = n + 1 WHERE n < ?3 RETURNING n`,
  ).bind(usuario, dia, limite).first();
  if (!propia) {
    await devolverCuota(env, null, dia);
    throw new ErrorApi(429, 'cuota_diaria_agotada', { limite });
  }
  return limite - propia.n;
}

export async function devolverCuota(env, usuario, dia) {
  const q = [env.DB.prepare(`UPDATE cuota_sitio SET n = n - 1 WHERE dia = ?1 AND tipo = 'datos' AND n > 0`).bind(dia)];
  if (usuario) q.push(env.DB.prepare('UPDATE cuota_diaria SET n = n - 1 WHERE usuario = ?1 AND dia = ?2 AND n > 0').bind(usuario, dia));
  await env.DB.batch(q);
}

/**
 * Llama al servicio de datos. Si falla, devuelve la cuota y lanza ErrorApi.
 * Un 422 llega solo con los nombres de los campos: el detalle de FastAPI repite el texto enviado.
 */
export async function pedirContexto(env, entrada, usuario, dia) {
  let r;
  const cab = { 'Content-Type': 'application/json', 'X-Lab-Clave': env.LAB_CLAVE || '' };
  // Token de proxy de Modal: Modal rechaza en su borde, sin despertar el contenedor, lo que no lo trae.
  if (env.MODAL_KEY && env.MODAL_SECRET) { cab['Modal-Key'] = env.MODAL_KEY; cab['Modal-Secret'] = env.MODAL_SECRET; }
  try {
    r = await fetch(env.LAB_URL.replace(/\/$/, '') + '/v1/contexto', {
      method: 'POST',
      headers: cab,
      body: JSON.stringify(entrada),
      signal: AbortSignal.timeout(ESPERA_LAB_MS),
    });
  } catch (e) {
    await devolverCuota(env, usuario, dia);
    console.log(JSON.stringify({ evento: 'lab_inalcanzable', nombre: e.name, mensaje: String(e.message).slice(0, 200) }));
    throw new ErrorApi(503, 'servicio_no_disponible');
  }
  if (!r.ok) {
    await devolverCuota(env, usuario, dia);
    if (r.status === 422) {
      const d = await r.json().catch(() => ({}));
      const campos = [...new Set((d.detail || []).map((x) => (x.loc || []).filter((p) => p !== 'body').join('.')))];
      throw new ErrorApi(422, 'entrada_invalida', { campos });
    }
    console.log(JSON.stringify({ evento: 'lab_error', status: r.status }));
    throw new ErrorApi(502, 'servicio_fallo');
  }
  return r.text();
}
