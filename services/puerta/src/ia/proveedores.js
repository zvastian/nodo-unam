// Reparto de la IA entre Groq y Workers AI (ADR-0015): el mismo gpt-oss-120b en los dos.
// Primero Groq; si falla o se gastó su presupuesto diario, Workers AI; si los dos están agotados, la
// parte de IA se marca «cupo del día agotado» y el análisis entrega solo datos.
//
// Los 429 de Groq no son todos iguales (evaluación del 26-sep-2026): el plan gratuito de gpt-oss-120b
// tiene 8,000 tokens POR MINUTO y un análisis gasta ~5,200, así que dos análisis seguidos chocan.
//   - límite por minuto y espera corta (≤ ESPERA_MAX_GROQ_S): se espera y se reintenta en Groq,
//     que aun así es más rápido que Workers AI (15 a 28 s);
//   - límite por minuto con espera larga: esa llamada va a Workers AI, sin marcar el día;
//   - límite por día: Groq se marca agotado hasta mañana.
//
// Contadores diarios en `cuota_sitio`: 'groq_tokens', 'workers_ai_neuronas' y 'ia' (análisis con IA).
// Los de los proveedores van por día UTC, porque Cloudflare reinicia las neuronas gratis a las 00:00 UTC;
// el tope 'ia' va por día de la Ciudad de México, como las cuotas de usuario.
// Privacidad: los logs llevan proveedor, tarea, tokens y errores de esquema, nunca el texto.

import { paraProveedor, validar } from './esquemas.js';

export class IAAgotada extends Error { constructor() { super('ia_agotada'); this.name = 'IAAgotada'; } }
export class IAInvalida extends Error { constructor(errores) { super('ia_invalida'); this.name = 'IAInvalida'; this.errores = errores; } }
class Limite429 extends Error {
  constructor(porDia, espera) { super('groq_429'); this.porDia = porDia; this.espera = espera; }
}
const ESPERA_MAX_GROQ_S = 20;
// Esperas ante un 429 por minuto: la de Groq o, si es menor, 2, 5 y 10 s. Esperar solo lo que pide
// retry-after (a veces 1 s) volvía a chocar, porque la ventana de tokens por minuto sigue llena.
const ESPERAS_GROQ_S = [2, 5, 10];
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
// Solo la ruta de cada error de esquema, sin los valores (pueden venir del texto del usuario).
const sinValores = (errores) => errores.map((e) => e.replace(/«[^»]*»/g, '«…»').slice(0, 120));

const entero = (v, def) => (Number.isFinite(+v) && v !== '' && v !== undefined ? +v : def);

async function contador(env, dia, tipo) {
  const r = await env.DB.prepare('SELECT n FROM cuota_sitio WHERE dia = ?1 AND tipo = ?2').bind(dia, tipo).first();
  return r ? r.n : 0;
}
async function sumar(env, dia, tipo, n) {
  await env.DB.prepare(
    'INSERT INTO cuota_sitio (dia, tipo, n) VALUES (?1, ?2, ?3) ON CONFLICT (dia, tipo) DO UPDATE SET n = n + ?3',
  ).bind(dia, tipo, Math.ceil(n)).run();
}

/** Toma un lugar del tope diario de análisis con IA. false si ya se llegó. */
export async function tomarCupoIA(env, dia) {
  const r = await env.DB.prepare(
    `INSERT INTO cuota_sitio (dia, tipo, n) VALUES (?1, 'ia', 1)
     ON CONFLICT (dia, tipo) DO UPDATE SET n = n + 1 WHERE n < ?2 RETURNING n`,
  ).bind(dia, entero(env.TOPE_IA_DIA, 55)).first();
  return !!r;
}

async function groq(env, mensajes, esquema, nombre) {
  const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + env.GROQ_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: env.IA_MODELO_GROQ || 'openai/gpt-oss-120b',
      messages: mensajes,
      temperature: 0.4,
      reasoning_effort: 'low',
      max_completion_tokens: 4000,
      response_format: { type: 'json_schema', json_schema: { name: nombre, schema: paraProveedor(esquema), strict: false } },
    }),
    signal: AbortSignal.timeout(60000),
  });
  const d = await r.json().catch(() => ({}));
  if (r.status === 429) {
    const msg = String(d.error?.message || '');
    const espera = parseFloat(r.headers.get('retry-after')) || parseFloat(/try again in ([\d.]+)s/i.exec(msg)?.[1]) || NaN;
    throw new Limite429(/per day|\((TPD|RPD)\)/i.test(msg), espera);
  }
  if (!r.ok) throw new Error('groq ' + r.status + ' ' + (d.error?.code || ''));
  return { texto: d.choices?.[0]?.message?.content || '', costo: d.usage?.total_tokens || 0, fin: d.choices?.[0]?.finish_reason };
}

async function workersAI(env, mensajes, esquema, dia, tope) {
  const ultimo = mensajes.at(-1);
  const conEsquema = [...mensajes.slice(0, -1), { ...ultimo, content: ultimo.content + '\n\nEsquema JSON de la respuesta:\n' + JSON.stringify(paraProveedor(esquema)) }];
  let d;
  try {
    d = await env.AI.run(env.IA_MODELO_WORKERS || '@cf/openai/gpt-oss-120b', {
      messages: conEsquema,
      reasoning: { effort: 'low' },
      // 2,500 y no 4,000: las salidas válidas no pasan de ~2,400 caracteres, así que un bucle de
      // espacios falla antes y gasta la mitad de neuronas.
      max_tokens: 2500,
      temperature: 0.4,
      // Sin response_format: la documentación de Cloudflare no lo admite para este modelo y, con él,
      // 3 de 15 llamadas de la evaluación entraron en un bucle de espacios hasta llenar max_tokens
      // (finish_reason «length», 4,000 caracteres). El esquema va en el prompt y el Worker valida.
    });
  } catch (e) {
    // 4006: se acabaron las neuronas gratis del día en Cloudflare. Es cupo agotado, no un fallo.
    if (/4006|daily free allocation/i.test(String(e.message))) {
      await sumar(env, dia, 'workers_ai_neuronas', tope);
      console.log(JSON.stringify({ evento: 'ia_workers_ai_4006' }));
      throw new IAAgotada();
    }
    throw e;
  }
  return { texto: d.choices?.[0]?.message?.content || d.response || '', costo: d.usage?.neurons || 0, tokens: d.usage?.total_tokens || 0, fin: d.choices?.[0]?.finish_reason };
}

function extraerJson(texto) {
  const t = String(texto).trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  return JSON.parse(t);
}

/**
 * Pide a la IA un JSON que cumpla `esquema` (y `revisar(datos)`, que devuelve errores adicionales).
 * `preparar(datos)` corrige omisiones inofensivas antes de validar (p. ej., campos nulos omitidos).
 * Un reintento controlado si la salida no cumple, con los errores como retroalimentación.
 * Devuelve { datos, proveedor, intentos, costo } (costo: tokens en Groq, neuronas en Workers AI).
 */
export async function pedirIA(env, _diaMexico, tarea, mensajes, esquema, revisar = () => [], preparar = (d) => d) {
  const dia = new Date().toISOString().slice(0, 10);   // día UTC, el de los proveedores
  const topeGroq = entero(env.GROQ_TOKENS_DIA, 180000);
  const topeWai = entero(env.WORKERS_AI_NEURONAS_DIA, 9000);
  let conversacion = mensajes, ultimo = [], costoTotal = 0;
  for (let intento = 0; intento < 2; intento++) {
    let respuesta, proveedor;
    if (env.GROQ_API_KEY && (await contador(env, dia, 'groq_tokens')) < topeGroq) {
      for (let espera = 0; espera <= ESPERAS_GROQ_S.length && !respuesta; espera++) {
        try {
          respuesta = await groq(env, conversacion, esquema, tarea);
          proveedor = 'groq';
          await sumar(env, dia, 'groq_tokens', respuesta.costo);
        } catch (e) {
          if (e instanceof Limite429 && e.porDia) {
            await sumar(env, dia, 'groq_tokens', topeGroq);   // agotado hasta mañana
            console.log(JSON.stringify({ evento: 'ia_groq_429_dia', tarea }));
            break;
          }
          const pausa = Math.max(e.espera || 0, ESPERAS_GROQ_S[espera] ?? Infinity);
          if (e instanceof Limite429 && espera < ESPERAS_GROQ_S.length && pausa <= ESPERA_MAX_GROQ_S) {
            console.log(JSON.stringify({ evento: 'ia_groq_429_minuto', tarea, espera_s: pausa }));
            await dormir(pausa * 1000);
            continue;
          }
          // Espera larga, 429 tras las 3 esperas o error de Groq (5xx, red): esta llamada va a Workers AI.
          console.log(JSON.stringify({ evento: 'ia_groq_a_respaldo', tarea, motivo: e instanceof Limite429 ? '429' : String(e.message).slice(0, 80) }));
          break;
        }
      }
    }
    if (!respuesta) {
      if (!env.AI || (await contador(env, dia, 'workers_ai_neuronas')) >= topeWai) throw new IAAgotada();
      respuesta = await workersAI(env, conversacion, esquema, dia, topeWai);
      proveedor = 'workers_ai';
      await sumar(env, dia, 'workers_ai_neuronas', respuesta.costo);
    }

    let datos;
    try { datos = preparar(extraerJson(respuesta.texto)); } catch { datos = undefined; }
    if (datos === undefined) ultimo = ['la respuesta no es JSON válido'];
    else {
      ultimo = validar(esquema, datos);
      if (!ultimo.length) ultimo = revisar(datos);   // las revisiones suponen la estructura ya validada
    }
    console.log(JSON.stringify({ evento: 'ia', tarea, proveedor, intento, costo: respuesta.costo, fin: respuesta.fin, largo: String(respuesta.texto).length, errores: sinValores(ultimo) }));
    costoTotal += respuesta.costo;
    if (!ultimo.length) return { datos, proveedor, intentos: intento + 1, costo: Math.round(costoTotal) };

    conversacion = [...mensajes,
      { role: 'assistant', content: String(respuesta.texto).slice(0, 8000) },
      { role: 'user', content: 'Tu respuesta no cumple lo pedido:\n- ' + ultimo.slice(0, 12).join('\n- ') + '\nDevuelve el JSON completo corregido, sin texto adicional.' },
    ];
  }
  throw new IAInvalida(ultimo);
}
