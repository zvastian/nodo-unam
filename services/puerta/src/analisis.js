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
import { TOPE_ENTRADA, hoy, leerJson, pedirContexto, tomarCuota, verificarTurnstile } from './comun.js';
import { ESQUEMAS } from './ia/esquemas.js';
import { entradaUsuario, promptBloom, promptNota, promptPreguntas, senalesCorpus } from './ia/prompts.js';
import { IAAgotada, IAInvalida, pedirIA, tomarCupoIA } from './ia/proveedores.js';

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

export async function analisisSSE(request, env, ctx, u, h) {
  const entrada = await leerJson(request, TOPE_ENTRADA);
  await verificarTurnstile(request, env);
  const dia = hoy();
  const restante = await tomarCuota(env, u.id, dia);
  // Si el servicio de datos falla, pedirContexto devuelve la cuota y lanza un error normal (no SSE).
  const datosTexto = await pedirContexto(env, entrada, u.id, dia);

  const { readable, writable } = new TransformStream();
  const w = writable.getWriter();
  const enc = new TextEncoder();
  const enviar = (evento, datos) => w.write(enc.encode(`event: ${evento}\ndata: ${typeof datos === 'string' ? datos : JSON.stringify(datos)}\n\n`)).catch(() => {});

  const trabajo = (async () => {
    const ia = {};
    try {
      const lexico = clasificarObjetivos(entrada.objectives || [], entrada.degree || '');
      await enviar('lexico', lexico);
      await enviar('datos', datosTexto);

      if (!(await tomarCupoIA(env, dia))) { await enviar('ia_agotada', { motivo: 'tope_del_sitio' }); return; }
      const datos = JSON.parse(datosTexto);
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
          ia[nombre] = { proveedor: r.proveedor, intentos: r.intentos, costo: r.costo };
          await enviar(nombre, r.datos);
        } catch (e) {
          if (e instanceof IAAgotada) { agotada = true; return; }
          const error = e instanceof IAInvalida ? 'salida_invalida' : 'ia_fallo';
          if (!(e instanceof IAInvalida)) console.error(JSON.stringify({ evento: 'ia_error', tarea: nombre, mensaje: String(e.message).slice(0, 200) }));
          await enviar('error', { seccion: nombre, error });
        }
      }));
      if (agotada) await enviar('ia_agotada', { motivo: 'proveedores_agotados' });
    } catch (e) {
      console.error(JSON.stringify({ evento: 'analisis_error', nombre: e.name, mensaje: String(e.message).slice(0, 200) }));
      await enviar('error', { seccion: 'analisis', error: 'interno' });
    } finally {
      await enviar('fin', { cuota_restante: restante, ia });
      await w.close().catch(() => {});
    }
  })();
  ctx.waitUntil(trabajo);

  return new Response(readable, {
    status: 200,
    headers: { ...h, 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Cuota-Restante': String(restante) },
  });
}
