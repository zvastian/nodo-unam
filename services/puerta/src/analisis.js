// Análisis completo del Laboratorio por SSE (ADR-0015, paso 3): cada sección se envía en cuanto
// está lista, como la plantilla la pinta.
//
// Eventos, en orden de llegada:
//   lexico     Bloom por léxico (inmediato, sin IA)
//   datos      contexto del servicio de datos (ubicación, saturación, asesores, vecinas)
//   nota | bloom | preguntas    las 3 llamadas de IA, en paralelo, según terminan
//   ia_agotada el cupo de IA del día se acabó: el análisis queda solo con datos
//   error      { seccion, error } si una sección falla; las demás siguen
//   fin        { cuota_restante, ia: { nota: { proveedor, intentos, costo }, … } }
//
// La cuota del usuario se toma al empezar y se devuelve si el servicio de datos falla antes de
// mandar nada. Si falla la IA, la cuota no se devuelve: los datos ya se entregaron.

import { clasificarObjetivo, clasificarObjetivos } from '../../../prototypes/atlas_vecindario_mvp/compartido/bloom.js';
import { ErrorApi, TOPE_ENTRADA, devolverCuota, entero, hoy, leerJson, pedirContexto, responder, tomarCuota, validarEntrada, verificarTurnstile } from './comun.js';
import { fila } from './fila.js';
import { ESQUEMAS } from './ia/esquemas.js';
import { contarInyeccion, limpiarEntrada } from './ia/limpieza.js';
import { entradaUsuario, promptBloom, promptNota, promptPreguntas, senalesCorpus } from './ia/prompts.js';
import { IAAgotada, IAInvalida, pedirIA, tomarCupoIA } from './ia/proveedores.js';
import { CABECERAS_API } from './seguridad.js';

// --- Revisiones que el esquema no puede expresar ---

// v2 (evaluación del 26-sep-2026): ya no se exige orden ascendente, porque forzaba órdenes
// artificiales («Evaluar» con F1 después de «Analizar» los errores). Se exige un verbo por objetivo y
// no agregar Crear si el estudiante no propone crear nada (salvo doctorado, que lo exige).
function revisarBloom(lexico) {
  const proponeCrear = lexico.objetivos.some((o) => o.nivel === 5) || lexico.esperado === 5;
  return (d) => {
    const e = [];
    if (d.objectives.length !== lexico.objetivos.length) e.push(`objectives debe tener ${lexico.objetivos.length} elementos, uno por objetivo`);
    const niveles = d.revised.map((r, i) => {
      const c = clasificarObjetivo(r.text);
      if (c.nivel === null) e.push(`revised[${i}] debe empezar con un verbo en infinitivo de la lista (empieza con «${c.verbo}»)`);
      else if (c.nivel === 0) e.push(`revised[${i}] no puede ser de Recordar: un objetivo de tesis empieza en Comprender o más arriba`);
      if (c.banderas.includes('varios_verbos')) e.push(`revised[${i}] tiene dos verbos: deja uno solo`);
      return c.nivel;
    });
    if (niveles.includes(5) && !niveles.includes(4)) e.push('revised incluye Crear sin un objetivo de Evaluar');
    if (niveles.includes(5) && !proponeCrear) e.push('revised incluye Crear, pero el estudiante no propone crear nada: quítalo');
    return e;
  };
}

function revisarPreguntas(d) {
  const e = [];
  const tipos = d.items.map((q) => q.type);
  if (new Set(tipos).size !== tipos.length) e.push('cada pregunta debe ser de un tipo distinto');
  d.items.forEach((q, i) => { if (!q.question.includes('?')) e.push(`items[${i}].question debe ser una pregunta entre ¿?`); });
  return e;
}

// Arreglos menores, antes de validar, que no ameritan reintento. Defensivos: si falta la estructura,
// la validación lo reporta. (Evaluación del 26-sep-2026: con applies = false el modelo omitía start,
// end y units en vez de ponerlos en null, y eso causaba casi todos los reintentos de la nota.)
function prepararNota(d) {
  const t = d?.scope?.temporal, g = d?.scope?.geographic;
  if (t && t.applies === false) { t.start = null; t.end = null; }
  if (g && g.applies === false) g.units = [];
  return d;
}
const NO_OBJETIVO = ['metodo', 'tramite', 'otro_idioma'];
function prepararBloom(d, lexico) {
  if (Array.isArray(d?.objectives)) d.objectives.forEach((o, i) => {
    const lx = lexico.objetivos[i];
    if (o && lx && (lx.nivel !== null || lx.banderas.some((b) => NO_OBJETIVO.includes(b)))) o.level = null;
  });
  if (Array.isArray(d?.revised)) d.revised.forEach((r) => {
    if (r && typeof r.text === 'string') r.text = r.text.charAt(0).toUpperCase() + r.text.slice(1);
  });
  return d;
}

/**
 * Las 3 llamadas de IA sobre un contexto ya calculado. La usan el análisis en vivo (SSE) y la fila
 * (src/fila.js), para que los dos den exactamente lo mismo. `aviso(evento, datos)` recibe cada
 * sección al terminar. Devuelve { ia: {nota, preguntas, bloom} | null, costos }.
 */
export async function correrIA(env, dia, entrada, datos, lexico, aviso = async () => {}) {
  const costos = {}, ia = {};
  if (!(await tomarCupoIA(env, dia))) { await aviso('ia_agotada', { motivo: 'tope_del_sitio' }); return { ia: null, costos }; }
  const eu = entradaUsuario(entrada), sen = senalesCorpus(datos);
  const tareas = [
    ['nota', promptNota(eu, sen), () => [], prepararNota],
    ['preguntas', promptPreguntas(eu, sen), revisarPreguntas, (d) => d],
  ];
  if (lexico.objetivos.length) tareas.push(['bloom', promptBloom(eu, lexico), revisarBloom(lexico), (d) => prepararBloom(d, lexico)]);

  let agotada = false;
  await Promise.all(tareas.map(async ([nombre, mensajes, revisar, preparar]) => {
    try {
      const r = await pedirIA(env, dia, nombre, mensajes, ESQUEMAS[nombre], revisar, preparar);
      costos[nombre] = { proveedor: r.proveedor, intentos: r.intentos, costo: r.costo };
      ia[nombre] = r.datos;
      await aviso(nombre, r.datos);
    } catch (e) {
      if (e instanceof IAAgotada) { agotada = true; return; }
      const error = e instanceof IAInvalida ? 'salida_invalida' : 'ia_fallo';
      if (!(e instanceof IAInvalida)) console.error(JSON.stringify({ evento: 'ia_error', tarea: nombre, mensaje: String(e.message).slice(0, 200) }));
      await aviso('error', { seccion: nombre, error });
    }
  }));
  if (agotada) await aviso('ia_agotada', { motivo: 'proveedores_agotados' });
  return { ia: Object.keys(ia).length ? ia : null, costos };
}

/**
 * Deja el análisis en la fila (src/fila.js): una fila de D1 con estado «fila», que Mi espacio
 * muestra como «En la fila», y su turno en el Durable Object. Ocupa uno de los 2 análisis
 * guardados: con los 2 llenos no entra y la cuota se devuelve.
 */
async function formarEnFila(env, u, entrada, dia, restante, h) {
  const id = crypto.randomUUID();
  const limite = entero(env.MAX_ANALISIS_GUARDADOS, 2);
  const r = await env.DB.prepare(
    `INSERT INTO analisis (id, usuario, titulo, entrada, resultado, estado)
     SELECT ?1, ?2, ?3, ?4, 'null', 'fila' WHERE (SELECT count(*) FROM analisis WHERE usuario = ?2) < ?5`,
  ).bind(id, u.id, String(entrada.title).slice(0, 400), JSON.stringify(entrada), limite).run();
  if (!r.meta.changes) {
    await devolverCuota(env, u.id, dia);
    throw new ErrorApi(409, 'limite_de_guardados', { limite });
  }
  const { posicion } = await fila(env, '/formar', { id, usuario: u.id, dia });
  return responder({ en_fila: true, id, posicion, cuota_restante: restante }, 202, h);
}

export async function analisisSSE(request, env, ctx, u, h) {
  // Limpia antes de todo: el léxico, el servicio de datos y los 3 prompts reciben el mismo texto.
  const entrada = limpiarEntrada(validarEntrada(await leerJson(request, TOPE_ENTRADA)));
  await verificarTurnstile(request, env);
  const sospechas = contarInyeccion(entrada);
  if (sospechas) console.log(JSON.stringify({ evento: 'posible_inyeccion', patrones: sospechas }));
  const dia = hoy();
  const restante = await tomarCuota(env, u.id, dia);

  // Un lugar en el servicio de datos (FILA_SIMULTANEOS a la vez); si no hay, a la fila.
  const { ok, lugar } = await fila(env, '/lugar');
  if (!ok) return formarEnFila(env, u, entrada, dia, restante, h);
  const soltar = () => fila(env, '/soltar', { lugar }).catch(() => {});

  // Si el servicio de datos falla, pedirContexto devuelve la cuota y lanza un error normal (no SSE).
  let datosTexto;
  try { datosTexto = await pedirContexto(env, entrada, u.id, dia); } catch (e) { await soltar(); throw e; }

  const { readable, writable } = new TransformStream();
  const w = writable.getWriter();
  const enc = new TextEncoder();
  const enviar = (evento, datos) => w.write(enc.encode(`event: ${evento}\ndata: ${typeof datos === 'string' ? datos : JSON.stringify(datos)}\n\n`)).catch(() => {});

  const trabajo = (async () => {
    let costos = {};
    try {
      await soltar(); // el servicio de datos ya respondió: la IA no ocupa su lugar
      const lexico = clasificarObjetivos(entrada.objectives || [], entrada.degree || '');
      await enviar('lexico', lexico);
      await enviar('datos', datosTexto);
      costos = (await correrIA(env, dia, entrada, JSON.parse(datosTexto), lexico, enviar)).costos;
    } catch (e) {
      console.error(JSON.stringify({ evento: 'analisis_error', nombre: e.name, mensaje: String(e.message).slice(0, 200) }));
      await enviar('error', { seccion: 'analisis', error: 'interno' });
    } finally {
      await enviar('fin', { cuota_restante: restante, ia: costos });
      await w.close().catch(() => {});
    }
  })();
  ctx.waitUntil(trabajo);

  return new Response(readable, {
    status: 200,
    headers: { ...CABECERAS_API, ...h, 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store', 'X-Cuota-Restante': String(restante) },
  });
}
