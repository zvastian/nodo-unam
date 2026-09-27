// Piezas comunes del Worker puerta: errores, respuestas, topes, Turnstile, cuotas y la llamada al
// servicio de datos. Ni el texto de la tesis ni el cuerpo de ninguna petición van a los logs.

export const TOPE_ENTRADA = 16 * 1024;     // bytes de la entrada del análisis
const ESPERA_LAB_MS = 90 * 1000;           // incluye el arranque en frío del servicio

export class ErrorApi extends Error {
  constructor(status, codigo, extra) { super(codigo); this.status = status; this.extra = extra; }
}

// Día en la Ciudad de México (UTC-6 todo el año desde 2022).
export const hoy = () => new Date(Date.now() - 6 * 3600 * 1000).toISOString().slice(0, 10);
export const entero = (v, def) => (Number.isFinite(+v) && v !== '' && v !== undefined ? +v : def);

export function responder(cuerpo, status, extra) {
  const h = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...extra };
  if (cuerpo === null) return new Response(null, { status, headers: h });
  h['Content-Type'] = 'application/json; charset=utf-8';
  return new Response(typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo), { status, headers: h });
}

/** Lee el cuerpo como JSON sin pasar de `tope` bytes. Nunca registra el contenido. */
export async function leerJson(request, tope) {
  const declarado = +request.headers.get('Content-Length');
  if (declarado > tope) throw new ErrorApi(413, 'entrada_demasiado_grande');
  const texto = await request.text();
  if (new TextEncoder().encode(texto).length > tope) throw new ErrorApi(413, 'entrada_demasiado_grande');
  try {
    const v = JSON.parse(texto);
    if (!v || typeof v !== 'object' || Array.isArray(v)) throw 0;
    return v;
  } catch { throw new ErrorApi(400, 'json_invalido'); }
}

export async function verificarTurnstile(request, env) {
  const token = request.headers.get('X-Turnstile');
  if (!token || token.length > 2048) throw new ErrorApi(403, 'turnstile_requerido');
  if (!env.TURNSTILE_SECRET) throw new Error('falta TURNSTILE_SECRET');
  const f = new FormData();
  f.append('secret', env.TURNSTILE_SECRET);
  f.append('response', token);
  const ip = request.headers.get('CF-Connecting-IP');
  if (ip) f.append('remoteip', ip);
  const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: f });
  const v = await r.json().catch(() => ({}));
  if (!v.success) throw new ErrorApi(403, 'turnstile_invalido');
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
  try {
    r = await fetch(env.LAB_URL.replace(/\/$/, '') + '/v1/contexto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Lab-Clave': env.LAB_CLAVE || '' },
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
