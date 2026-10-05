// Worker «puerta» de NodOS (ADR-0015, pasos 2 y 3): la única API pública del Laboratorio.
// El análisis completo, con IA y por SSE, está en analisis.js.
//
// Hace, en este orden: CORS con orígenes explícitos, sesión (JWT de Supabase), tope de tamaño,
// Turnstile, cuota (por usuario y del sitio, en D1) y, al final, llama al servicio de datos, cuya
// URL no se expone. También guarda análisis y tesis de cada usuario.
//
// Privacidad: ni el texto de la tesis ni el cuerpo de ninguna petición van a los logs.
// Seguridad: toda consulta a D1 filtra por el id del token, nunca por uno que mande el cliente.

import { analisisSSE } from './analisis.js';
import { fila } from './fila.js';
import { limpiarEntrada } from './ia/limpieza.js';
import { ErrorApi, TOPE_ENTRADA, entero, hoy, leerJson, pedirContexto, responder, tomarCuota, validarEntrada, verificarTurnstile } from './comun.js';
import { limitarEscrituras, limitarPorIp, problemasDeConfig } from './seguridad.js';
import { SinSesion, usuarioDe } from './sesion.js';

const TOPE_GUARDADO = 512 * 1024;     // bytes de un análisis guardado (el contexto pesa ~55 KB)
const RE_TESIS = /^[A-Za-z0-9_-]{1,40}$/;
const RE_UUID = /^[0-9a-f-]{36}$/;
const RE_ASESOR = /^[a-z0-9 .'-]{2,160}$/;   // nombre normalizado: minúsculas, sin acentos
const RE_LUGAR = /^(macro|meso|micro):[A-Za-z0-9_.-]{1,80}$/; // campo, tema o subtema del mapa
const TOPE_DATOS = 2 * 1024;                  // bytes de los datos de una tesis o un asesor guardado
// Lo que se muestra de lo guardado: lista blanca de campos y tipos; lo demás se descarta.
const CAMPOS_TESIS = { titulo: 's', anio: 'n', programa: 's', nivel: 's', plantel: 's', area: 'n', catalogo: 'n' };
const CAMPOS_ASESOR = { nombre: 's', programa: 's', plantel: 's', total: 'n', ultimo: 'n', area: 'n' };
// color: solo hexadecimal, porque las páginas lo ponen dentro de un style
const CAMPOS_LUGAR = { nombre: 's', nivel: 's', campo: 's', tesis: 'n', color: 'c' };
const RE_COLOR = /^#[0-9a-f]{3,8}$/i;
function limpiarDatos(d, campos) {
  const o = {};
  if (!d || typeof d !== 'object') return o;
  for (const [k, tipo] of Object.entries(campos)) {
    const v = d[k];
    if (tipo === 'n' && v !== null && v !== '' && Number.isFinite(+v)) o[k] = Math.round(+v);
    else if (tipo === 's' && typeof v === 'string' && v.trim()) o[k] = v.trim().slice(0, 300);
    else if (tipo === 'c' && typeof v === 'string' && RE_COLOR.test(v.trim())) o[k] = v.trim();
  }
  return o;
}
async function datosOpcionales(request, campos) {
  if (!(request.headers.get('Content-Type') || '').includes('json')) return null;
  const o = limpiarDatos(await leerJson(request, TOPE_DATOS), campos);
  return Object.keys(o).length ? JSON.stringify(o) : null;
}
const conDatos = (filas, clave) => filas.map((f) => ({ [clave]: f[clave], datos: f.datos ? JSON.parse(f.datos) : null, creado: f.creado }));

function cors(request, env) {
  const origen = request.headers.get('Origin');
  const permitidos = (env.ORIGENES || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (!origen || !permitidos.includes(origen)) return {};
  return {
    'Access-Control-Allow-Origin': origen,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Turnstile',
    'Access-Control-Expose-Headers': 'X-Cuota-Restante',
    'Access-Control-Max-Age': '600',
    Vary: 'Origin',
  };
}

// --- Rutas ---

async function yo(env, u) {
  const dia = hoy();
  const [c, a, t, s, l] = await env.DB.batch([
    env.DB.prepare('SELECT n FROM cuota_diaria WHERE usuario = ?1 AND dia = ?2').bind(u.id, dia),
    env.DB.prepare('SELECT count(*) AS n FROM analisis WHERE usuario = ?1').bind(u.id),
    env.DB.prepare('SELECT count(*) AS n FROM tesis_guardadas WHERE usuario = ?1').bind(u.id),
    env.DB.prepare('SELECT count(*) AS n FROM asesores_guardados WHERE usuario = ?1').bind(u.id),
    env.DB.prepare('SELECT count(*) AS n FROM lugares_guardados WHERE usuario = ?1').bind(u.id),
  ]);
  const limite = entero(env.CUOTA_USUARIO_DIA, 2);
  return {
    correo: u.correo,
    analisis_hoy: { usados: c.results[0]?.n || 0, limite },
    analisis_guardados: { usados: a.results[0].n, limite: entero(env.MAX_ANALISIS_GUARDADOS, 2) },
    tesis_guardadas: t.results[0].n,
    asesores_guardados: s.results[0].n,
    lugares_guardados: l.results[0].n,
  };
}

async function contexto(request, env, u, h) {
  const entrada = limpiarEntrada(validarEntrada(await leerJson(request, TOPE_ENTRADA)));
  await verificarTurnstile(request, env);
  // Solo datos, sin fila: si el servicio está ocupado se dice, sin gastar cuota.
  const { ok, lugar } = await fila(env, '/lugar');
  if (!ok) throw new ErrorApi(503, 'servicio_ocupado');
  try {
    const dia = hoy();
    const restante = await tomarCuota(env, u.id, dia);
    const texto = await pedirContexto(env, entrada, u.id, dia);
    return responder(texto, 200, { ...h, 'X-Cuota-Restante': String(restante) });
  } finally {
    await fila(env, '/soltar', { lugar }).catch(() => {});
  }
}

async function guardarAnalisis(request, env, u) {
  const { entrada, resultado } = await leerJson(request, TOPE_GUARDADO);
  if (!entrada || typeof entrada !== 'object' || !resultado || typeof resultado !== 'object') throw new ErrorApi(400, 'faltan_entrada_o_resultado');
  const titulo = String(entrada.title || '').slice(0, 400);
  if (!titulo) throw new ErrorApi(400, 'falta_titulo');
  const id = crypto.randomUUID();
  const limite = entero(env.MAX_ANALISIS_GUARDADOS, 2);
  // El conteo y la inserción van en una sola sentencia: dos peticiones simultáneas no rebasan el límite.
  const r = await env.DB.prepare(
    `INSERT INTO analisis (id, usuario, titulo, entrada, resultado)
     SELECT ?1, ?2, ?3, ?4, ?5 WHERE (SELECT count(*) FROM analisis WHERE usuario = ?2) < ?6`,
  ).bind(id, u.id, titulo, JSON.stringify(entrada), JSON.stringify(resultado), limite).run();
  if (!r.meta.changes) throw new ErrorApi(409, 'limite_de_guardados', { limite });
  return { id };
}

async function guardarTesis(env, u, tesis, datos = null) {
  const limite = entero(env.MAX_TESIS_GUARDADAS, 500);
  const r = await env.DB.prepare(
    `INSERT INTO tesis_guardadas (usuario, tesis, datos) SELECT ?1, ?2, ?4
     WHERE (SELECT count(*) FROM tesis_guardadas WHERE usuario = ?1) < ?3
     ON CONFLICT (usuario, tesis) DO UPDATE SET datos = excluded.datos
     WHERE excluded.datos IS NOT NULL AND excluded.datos IS NOT tesis_guardadas.datos`,
  ).bind(u.id, tesis, limite, datos).run();
  if (!r.meta.changes) {
    const ya = await env.DB.prepare('SELECT 1 FROM tesis_guardadas WHERE usuario = ?1 AND tesis = ?2').bind(u.id, tesis).first();
    if (!ya) throw new ErrorApi(409, 'limite_de_tesis', { limite });
  }
}

// «Guardar las N»: hasta LOTE_TESIS por petición, en un solo batch de D1 (antes eran N peticiones,
// que chocaban con el límite por IP). Cada fila lleva la misma condición de límite que una sola,
// y el batch corre en orden dentro de una transacción: dos lotes simultáneos no rebasan el límite.
// Devuelve cuáles quedaron guardadas; si faltan, es que se llegó al límite.
const LOTE_TESIS = 100;
const TOPE_LOTE = LOTE_TESIS * (TOPE_DATOS + 256);
async function guardarTesisLote(request, env, u) {
  const { tesis } = await leerJson(request, TOPE_LOTE);
  if (!Array.isArray(tesis) || !tesis.length || tesis.length > LOTE_TESIS) throw new ErrorApi(400, 'lote_invalido', { maximo: LOTE_TESIS });
  const filas = new Map();
  for (const t of tesis) {
    if (!t || typeof t.id !== 'string' || !RE_TESIS.test(t.id)) throw new ErrorApi(400, 'id_de_tesis_invalido');
    const o = limpiarDatos(t.datos, CAMPOS_TESIS);
    const datos = Object.keys(o).length ? JSON.stringify(o) : null;
    if (datos && datos.length > TOPE_DATOS) throw new ErrorApi(413, 'entrada_demasiado_grande');
    filas.set(t.id, datos);
  }
  const limite = entero(env.MAX_TESIS_GUARDADAS, 500);
  const ids = [...filas.keys()];
  // Solo filas nuevas (DO NOTHING): repetir un lote no vuelve a escribir las que ya estaban.
  await env.DB.batch(ids.map((id) => env.DB.prepare(
    `INSERT INTO tesis_guardadas (usuario, tesis, datos) SELECT ?1, ?2, ?4
     WHERE (SELECT count(*) FROM tesis_guardadas WHERE usuario = ?1) < ?3
     ON CONFLICT (usuario, tesis) DO NOTHING`,
  ).bind(u.id, id, limite, filas.get(id))));
  // Un solo parámetro con la lista: D1 admite a lo más 100 por sentencia.
  const r = await env.DB.prepare('SELECT tesis FROM tesis_guardadas WHERE usuario = ?1 AND tesis IN (SELECT value FROM json_each(?2))')
    .bind(u.id, JSON.stringify(ids)).all();
  const guardadas = r.results.map((f) => f.tesis);
  return guardadas.length < ids.length ? { guardadas, error: 'limite_de_tesis', limite } : { guardadas };
}

async function guardarAsesor(env, u, asesor, datos) {
  const limite = entero(env.MAX_ASESORES_GUARDADOS, 200);
  const r = await env.DB.prepare(
    `INSERT INTO asesores_guardados (usuario, asesor, datos) SELECT ?1, ?2, ?4
     WHERE (SELECT count(*) FROM asesores_guardados WHERE usuario = ?1) < ?3
     ON CONFLICT (usuario, asesor) DO UPDATE SET datos = excluded.datos
     WHERE excluded.datos IS NOT NULL AND excluded.datos IS NOT asesores_guardados.datos`,
  ).bind(u.id, asesor, limite, datos).run();
  if (!r.meta.changes) {
    const ya = await env.DB.prepare('SELECT 1 FROM asesores_guardados WHERE usuario = ?1 AND asesor = ?2').bind(u.id, asesor).first();
    if (!ya) throw new ErrorApi(409, 'limite_de_asesores', { limite });
  }
}

async function guardarLugar(env, u, lugar, datos) {
  const limite = entero(env.MAX_LUGARES_GUARDADOS, 200);
  const r = await env.DB.prepare(
    `INSERT INTO lugares_guardados (usuario, lugar, datos) SELECT ?1, ?2, ?4
     WHERE (SELECT count(*) FROM lugares_guardados WHERE usuario = ?1) < ?3
     ON CONFLICT (usuario, lugar) DO UPDATE SET datos = excluded.datos
     WHERE excluded.datos IS NOT NULL AND excluded.datos IS NOT lugares_guardados.datos`,
  ).bind(u.id, lugar, limite, datos).run();
  if (!r.meta.changes) {
    const ya = await env.DB.prepare('SELECT 1 FROM lugares_guardados WHERE usuario = ?1 AND lugar = ?2').bind(u.id, lugar).first();
    if (!ya) throw new ErrorApi(409, 'limite_de_lugares', { limite });
  }
}

async function borrarCuenta(env, u) {
  // Primero los datos propios (lo sensible); luego la identidad en Supabase.
  await env.DB.batch(['analisis', 'tesis_guardadas', 'asesores_guardados', 'lugares_guardados', 'cuota_diaria'].map((t) =>
    env.DB.prepare(`DELETE FROM ${t} WHERE usuario = ?1`).bind(u.id)));
  if (env.SUPABASE_SERVICE_KEY && env.SUPABASE_URL) {
    const r = await fetch(env.SUPABASE_URL.replace(/\/$/, '') + '/auth/v1/admin/users/' + u.id, {
      method: 'DELETE',
      headers: { apikey: env.SUPABASE_SERVICE_KEY, Authorization: 'Bearer ' + env.SUPABASE_SERVICE_KEY },
    });
    if (!r.ok && r.status !== 404) throw new ErrorApi(502, 'no_se_borro_la_identidad');
  }
}

async function rutear(request, env, ctx, h) {
  const url = new URL(request.url);
  const p = url.pathname.replace(/\/+$/, '');
  const m = request.method;

  // Antes que la sesión: un token falso también gasta verificación y, con un kid nuevo, el JWKS.
  const costoso = m === 'POST' && (p === '/api/lab/analisis' || p === '/api/lab/contexto');
  await limitarPorIp(request, env, costoso);

  if (p === '/api/salud' && m === 'GET') return responder({ ok: true }, 200, h);

  const u = await usuarioDe(request, env);
  // guardar y borrar (el análisis ya lleva cuota diaria)
  if ((m === 'PUT' || m === 'DELETE' || m === 'POST') && !costoso) await limitarEscrituras(env, u.id);
  const ok = (v) => responder(v, 200, h);
  const vacio = () => responder(null, 204, h);
  let x;

  if (p === '/api/yo' && m === 'GET') return ok(await yo(env, u));
  if (p === '/api/lab/contexto' && m === 'POST') return contexto(request, env, u, h);
  if (p === '/api/lab/analisis' && m === 'POST') return analisisSSE(request, env, ctx, u, h);

  if (p === '/api/analisis' && m === 'GET') {
    // estado: «listo» o «fila» (esperando su turno; Mi espacio lo muestra como «En la fila»)
    // ia_pendiente: 1 si le falta la lectura con IA (se hará cuando haya cupo)
    const r = await env.DB.prepare('SELECT id, titulo, creado, estado, ia_pendiente FROM analisis WHERE usuario = ?1 ORDER BY creado DESC').bind(u.id).all();
    return ok({ analisis: r.results });
  }
  if (p === '/api/analisis' && m === 'POST') return responder(await guardarAnalisis(request, env, u), 201, h);
  if ((x = /^\/api\/analisis\/([^/]+)$/.exec(p))) {
    const id = x[1].toLowerCase();
    if (!RE_UUID.test(id)) throw new ErrorApi(404, 'no_encontrado');
    if (m === 'GET') {
      const a = await env.DB.prepare('SELECT id, titulo, entrada, resultado, creado, estado, ia_pendiente FROM analisis WHERE id = ?1 AND usuario = ?2').bind(id, u.id).first();
      if (!a) throw new ErrorApi(404, 'no_encontrado');
      return ok({ ...a, entrada: JSON.parse(a.entrada), resultado: JSON.parse(a.resultado) });
    }
    if (m === 'DELETE') {
      const r = await env.DB.prepare('DELETE FROM analisis WHERE id = ?1 AND usuario = ?2').bind(id, u.id).run();
      if (!r.meta.changes) throw new ErrorApi(404, 'no_encontrado');
      return vacio();
    }
  }

  if (p === '/api/tesis' && m === 'GET') {
    const r = await env.DB.prepare('SELECT tesis, datos, creado FROM tesis_guardadas WHERE usuario = ?1 ORDER BY creado DESC').bind(u.id).all();
    return ok({ tesis: conDatos(r.results, 'tesis') });
  }
  if (p === '/api/tesis' && m === 'PUT') return ok(await guardarTesisLote(request, env, u));
  if ((x = /^\/api\/tesis\/([^/]+)$/.exec(p))) {
    if (!RE_TESIS.test(x[1])) throw new ErrorApi(400, 'id_de_tesis_invalido');
    if (m === 'PUT') { await guardarTesis(env, u, x[1], await datosOpcionales(request, CAMPOS_TESIS)); return vacio(); }
    if (m === 'DELETE') {
      await env.DB.prepare('DELETE FROM tesis_guardadas WHERE usuario = ?1 AND tesis = ?2').bind(u.id, x[1]).run();
      return vacio();
    }
  }

  if (p === '/api/asesores' && m === 'GET') {
    const r = await env.DB.prepare('SELECT asesor, datos, creado FROM asesores_guardados WHERE usuario = ?1 ORDER BY creado DESC').bind(u.id).all();
    return ok({ asesores: conDatos(r.results, 'asesor') });
  }
  if ((x = /^\/api\/asesores\/([^/]+)$/.exec(p))) {
    let clave;
    try { clave = decodeURIComponent(x[1]); } catch { throw new ErrorApi(400, 'asesor_invalido'); }
    if (!RE_ASESOR.test(clave)) throw new ErrorApi(400, 'asesor_invalido');
    if (m === 'PUT') { await guardarAsesor(env, u, clave, await datosOpcionales(request, CAMPOS_ASESOR)); return vacio(); }
    if (m === 'DELETE') {
      await env.DB.prepare('DELETE FROM asesores_guardados WHERE usuario = ?1 AND asesor = ?2').bind(u.id, clave).run();
      return vacio();
    }
  }

  if (p === '/api/lugares' && m === 'GET') {
    const r = await env.DB.prepare('SELECT lugar, datos, creado FROM lugares_guardados WHERE usuario = ?1 ORDER BY creado DESC').bind(u.id).all();
    return ok({ lugares: conDatos(r.results, 'lugar') });
  }
  if ((x = /^\/api\/lugares\/([^/]+)$/.exec(p))) {
    let clave;
    try { clave = decodeURIComponent(x[1]); } catch { throw new ErrorApi(400, 'lugar_invalido'); }
    if (!RE_LUGAR.test(clave)) throw new ErrorApi(400, 'lugar_invalido');
    if (m === 'PUT') { await guardarLugar(env, u, clave, await datosOpcionales(request, CAMPOS_LUGAR)); return vacio(); }
    if (m === 'DELETE') {
      await env.DB.prepare('DELETE FROM lugares_guardados WHERE usuario = ?1 AND lugar = ?2').bind(u.id, clave).run();
      return vacio();
    }
  }

  if (p === '/api/cuenta' && m === 'DELETE') { await borrarCuenta(env, u); return vacio(); }

  throw new ErrorApi(404, 'no_encontrado');
}

export { Fila } from './fila.js';

export default {
  async fetch(request, env, ctx) {
    const h = cors(request, env);
    // Falla cerrado: en producción, una configuración de desarrollo no atiende a nadie.
    const mal = problemasDeConfig(env);
    if (mal.length) {
      console.error(JSON.stringify({ evento: 'configuracion_insegura', variables: mal }));
      return responder({ error: 'servicio_no_disponible' }, 503, h);
    }
    if (request.method === 'OPTIONS') return responder(null, h['Access-Control-Allow-Origin'] ? 204 : 403, h);
    try {
      return await rutear(request, env, ctx, h);
    } catch (e) {
      if (e instanceof ErrorApi) return responder({ error: e.message, ...e.extra }, e.status, h);
      if (e instanceof SinSesion) return responder({ error: 'sin_sesion', motivo: e.message }, 401, { ...h, 'WWW-Authenticate': 'Bearer' });
      // Solo el nombre y el mensaje de errores propios; nunca el cuerpo de la petición.
      console.error(JSON.stringify({ evento: 'error_interno', nombre: e.name, mensaje: String(e.message).slice(0, 200) }));
      return responder({ error: 'interno' }, 500, h);
    }
  },

  // Diario: borra cuotas de hace más de 7 días y mantiene despierto el proyecto de Supabase,
  // que el plan gratuito pausa tras 7 días sin actividad.
  async scheduled(evento, env, ctx) {
    const limite = new Date(Date.now() - 7 * 86400 * 1000).toISOString().slice(0, 10);
    // El contador del mes («2026-09») se queda 3 meses: su «dia» es más corto y, comparado como
    // texto, caería en el primer borrado.
    const d = new Date(); d.setUTCMonth(d.getUTCMonth() - 3);
    ctx.waitUntil(env.DB.batch([
      env.DB.prepare('DELETE FROM cuota_diaria WHERE dia < ?1').bind(limite),
      env.DB.prepare(`DELETE FROM cuota_sitio WHERE dia < ?1 AND tipo != 'mes'`).bind(limite),
      env.DB.prepare(`DELETE FROM cuota_sitio WHERE tipo = 'mes' AND dia < ?1`).bind(d.toISOString().slice(0, 7)),
    ]));
    // Red de seguridad del carril de IA (1.0.4): si su alarma se perdiera, los análisis con la IA
    // pendiente esperarían a que alguien más analizara. El cron (09:17 UTC, después del reinicio de
    // las 06:05) lo despierta; si está en pausa, solo reprograma la alarma.
    ctx.waitUntil(fila(env, '/ia').catch(() => {}));
    if (env.SUPABASE_URL && env.SUPABASE_ANON_KEY) {
      ctx.waitUntil(fetch(env.SUPABASE_URL.replace(/\/$/, '') + '/auth/v1/health', { headers: { apikey: env.SUPABASE_ANON_KEY } }));
    }
  },
};
