// La fila del Laboratorio (paso 2 de la lista de lanzamiento, 29-sep-2026). Un Durable Object, uno
// solo para todo el sitio (plan gratuito, con almacenamiento SQLite), que hace tres cosas:
//
// 1. Reparte lugares en el servicio de datos: FILA_SIMULTANEOS a la vez (2), porque Modal corre un
//    solo contenedor de 2 núcleos. Un lugar vale mientras el servicio de datos trabaja; la IA ya no
//    lo ocupa. Si el Worker que lo pidió muere sin soltarlo, vence solo a los 4 minutos.
// 2. Guarda el turno de los análisis que llegaron sin lugar. El texto no vive aquí: está en la fila
//    de D1 del análisis (estado «fila»), la misma que Mi espacio muestra como «En la fila».
// 3. Les pide los datos en segundo plano (alarma) y los guarda en D1 como un análisis normal, con la
//    IA pendiente para el carril de IA (abajo). Si el usuario lo borró antes de su turno, o si el
//    servicio de datos falla, se devuelve su cuota.
//
// Sin largo máximo (decisión del usuario, 29-sep): el único freno es el tope diario del sitio.
// Quien llega mientras hay fila espera su turno aunque se libere un lugar: primero los de la fila.
//
// Carril de IA (29-sep): los análisis de la fila guardan sus datos en cuanto el servicio responde y
// quedan con la IA pendiente (`ia_pendiente`). La hace un carril aparte, de uno en uno y espaciado
// (IA_INTERVALO_S): Groq gratuito da ~8,000 tokens por minuto y un análisis gasta ~5,200. Antes, 50 en
// fila soltaban 50 llamadas a Groq en el mismo minuto; casi todas caían a Workers AI y agotaban el día.
// El mismo carril completa los análisis en vivo que se quedaron sin IA por falta de cupo; si el cupo
// del día se acabó, se pausa hasta que se reinicia (06:05 UTC: medianoche de la Ciudad de México).

import { correrIA } from './analisis.js';
import { clasificarObjetivos } from '../../../prototypes/atlas_vecindario_mvp/compartido/bloom.js';
import { devolverCuota, entero, hoy, pedirContexto } from './comun.js';

const LUGAR_VIVO_MS = 4 * 60 * 1000;         // lugar de un análisis en vivo, si nadie lo suelta
const LUGAR_FILA_MS = 10 * 60 * 1000;        // lugar de un análisis de la fila
const TURNO_ALARMA_MS = 12 * 60 * 1000;      // una alarma dura a lo más 15 min: se reprograma antes

// El cupo de IA se reinicia a las 00:00 UTC (proveedores) y a las 06:00 UTC (tope del sitio, día de
// la Ciudad de México): el carril pausado vuelve a las 06:05 UTC.
function siguienteReinicio(ahora = Date.now()) {
  const d = new Date(ahora);
  const hoy605 = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 6, 5);
  return ahora < hoy605 ? hoy605 : hoy605 + 86400 * 1000;
}
const TAREAS_IA = (lexico) => ['nota', 'preguntas'].concat(lexico.objetivos.length ? ['bloom'] : []);

/**
 * Completa la IA de un análisis guardado con `ia_pendiente`: solo las secciones que faltan. Si
 * vuelve a faltar algo por cupo, sigue pendiente (y se devuelve agotada); si falta por otra causa
 * (salida inválida tras el reintento), se deja de intentar, para no gastar cupo en un bucle.
 */
async function completarIA(env, f) {
  const entrada = JSON.parse(f.entrada), res = JSON.parse(f.resultado) || {};
  const lexico = clasificarObjetivos(entrada.objectives || [], entrada.degree || '');
  const solo = TAREAS_IA(lexico).filter((k) => !(res.ia && res.ia[k]));
  const fijar = (resultado, pendiente) => env.DB.prepare(
    `UPDATE analisis SET resultado = ?3, ia_pendiente = ?4 WHERE id = ?1 AND usuario = ?2 AND ia_pendiente = 1`,
  ).bind(f.id, f.usuario, JSON.stringify(resultado), pendiente ? 1 : 0).run();
  if (!solo.length || !res.datos) { await fijar(res, false); return { agotada: false }; }
  const r = await correrIA(env, hoy(), entrada, res.datos, lexico, undefined, solo);
  const ia = { ...(res.ia || {}), ...(r.ia || {}) };
  const sigue = r.agotada && r.faltan.length > 0;
  await fijar({ ...res, ia: Object.keys(ia).length ? ia : null }, sigue);
  console.log(JSON.stringify({ evento: 'ia_completada', secciones: solo.length - r.faltan.length, faltan: r.faltan.length, agotada: sigue }));
  return { agotada: sigue };
}

/** Habla con la fila. Sin el binding (pruebas unitarias) siempre hay lugar y no hay fila. */
export async function fila(env, ruta, cuerpo) {
  if (!env.FILA) return { ok: true, lugar: null, posicion: 0 };
  const obj = env.FILA.get(env.FILA.idFromName('laboratorio'));
  const r = await obj.fetch('https://fila' + ruta, { method: 'POST', body: JSON.stringify(cuerpo || {}) });
  if (!r.ok) throw new Error('la fila respondió ' + r.status);
  return r.json();
}

export class Fila {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.s = null;           // { cola: [{id, usuario, dia}], lugares: {lugar: vence}, enCurso: {id: tarea} }
    this.despertar = null;   // la alarma espera aquí a que se libere un lugar
  }

  async cargar() {
    if (!this.s) this.s = (await this.state.storage.get('s')) || { cola: [], lugares: {}, enCurso: {} };
    const ahora = Date.now();
    for (const [k, vence] of Object.entries(this.s.lugares)) if (vence < ahora) delete this.s.lugares[k];
    return this.s;
  }
  guardar() { return this.state.storage.put('s', this.s); }
  libres() { return entero(this.env.FILA_SIMULTANEOS, 2) - Object.keys(this.s.lugares).length; }
  async programar(en = 0) {
    const cuando = Date.now() + en, actual = await this.state.storage.getAlarm();
    if (actual === null || actual > cuando) await this.state.storage.setAlarm(cuando);
  }

  async fetch(request) {
    const ruta = new URL(request.url).pathname;
    const c = await request.json().catch(() => ({}));
    const s = await this.cargar();
    let r;
    if (ruta === '/lugar') {
      if (!s.cola.length && this.libres() > 0) {
        const lugar = crypto.randomUUID();
        s.lugares[lugar] = Date.now() + LUGAR_VIVO_MS;
        r = { ok: true, lugar };
      } else r = { ok: false };
    } else if (ruta === '/soltar') {
      if (c.lugar) delete s.lugares[c.lugar];
      r = { ok: true };
    } else if (ruta === '/formar') {
      if (typeof c.id !== 'string' || typeof c.usuario !== 'string' || typeof c.dia !== 'string') return new Response('mal', { status: 400 });
      s.cola.push({ id: c.id, usuario: c.usuario, dia: c.dia });
      r = { posicion: s.cola.length };
    } else if (ruta === '/ia') {
      // un análisis en vivo quedó con la IA pendiente: que el carril lo tome (si no está en pausa)
      r = { ok: true };
    } else if (ruta === '/estado') {
      r = { en_fila: s.cola.length, lugares_ocupados: Object.keys(s.lugares).length, en_curso: Object.keys(s.enCurso).length, ia_pausa_hasta: s.iaPausaHasta || null };
    } else return new Response('no', { status: 404 });
    await this.guardar();
    if (s.cola.length) await this.programar();
    else if (ruta === '/ia') await this.programar(Math.max(0, (s.iaPausaHasta || 0) - Date.now()));
    if (this.despertar) this.despertar();
    return Response.json(r);
  }

  async alarm() {
    const inicio = Date.now(), s = await this.cargar(), activos = new Set();
    // Las alarmas no se enciman: lo que quedó «en curso» de antes es de un objeto que se reinició
    // a mitad de un análisis. Vuelve al frente de la fila.
    const huerfanas = Object.values(s.enCurso);
    if (huerfanas.length) { s.cola.unshift(...huerfanas); s.enCurso = {}; await this.guardar(); }

    for (;;) {
      await this.cargar();
      while (this.libres() > 0 && s.cola.length && Date.now() - inicio < TURNO_ALARMA_MS) {
        const t = s.cola.shift(), lugar = crypto.randomUUID();
        s.lugares[lugar] = Date.now() + LUGAR_FILA_MS;
        s.enCurso[t.id] = t;
        await this.guardar();
        const soltar = async () => {
          if (!(lugar in s.lugares)) return;
          delete s.lugares[lugar]; await this.guardar();
          if (this.despertar) this.despertar();
        };
        const p = this.correr(t, soltar)
          .catch((e) => console.error(JSON.stringify({ evento: 'fila_error', nombre: e.name, mensaje: String(e.message).slice(0, 200) })))
          .finally(async () => { await soltar(); delete s.enCurso[t.id]; await this.guardar(); activos.delete(p); });
        activos.add(p);
      }
      if (!activos.size) break;
      await new Promise((listo) => { this.despertar = listo; Promise.race(activos).then(listo); });
      this.despertar = null;
    }

    if (s.cola.length) {
      // Sin lugar (los ocupan análisis en vivo) o se acabó el turno de esta alarma. Soltar un lugar
      // ya programa la alarma; esto es el respaldo si un lugar vence sin que nadie lo suelte.
      const vencen = Object.values(s.lugares);
      await this.programar(Date.now() - inicio >= TURNO_ALARMA_MS || !vencen.length ? 0 : Math.max(1000, Math.min(...vencen) - Date.now()));
      return;
    }
    // La fila de datos está vacía: turno del carril de IA.
    const proxima = await this.carrilIA(inicio);
    if (proxima !== null) await this.programar(Math.max(0, proxima - Date.now()));
  }

  /**
   * Completa las lecturas de IA pendientes, de una en una y espaciadas. Devuelve cuándo volver
   * (ms desde la época) o null si no queda nada. Cede en cuanto llega alguien a la fila de datos.
   */
  async carrilIA(inicio) {
    const s = this.s, env = this.env;
    if (s.iaPausaHasta && Date.now() < s.iaPausaHasta) return s.iaPausaHasta;
    const intervalo = entero(env.IA_INTERVALO_S, 45) * 1000;
    for (;;) {
      if (s.cola.length) return Date.now();                         // primero los datos de quien espera
      if (Date.now() - inicio > TURNO_ALARMA_MS) return Date.now() + 1000;
      const f = await env.DB.prepare(
        `SELECT id, usuario, entrada, resultado FROM analisis WHERE ia_pendiente = 1 AND estado = 'listo' ORDER BY creado LIMIT 1`,
      ).first();
      if (!f) return null;
      const falta = (s.iaUltima || 0) + intervalo - Date.now();
      if (falta > 0) {
        // Espera interrumpible: si alguien entra a la fila, /formar la despierta.
        await new Promise((listo) => { this.despertar = listo; setTimeout(listo, falta); });
        this.despertar = null;
        continue;
      }
      s.iaUltima = Date.now(); await this.guardar();
      let r;
      try { r = await completarIA(env, f); } catch (e) {
        console.error(JSON.stringify({ evento: 'ia_completar_error', nombre: e.name, mensaje: String(e.message).slice(0, 200) }));
        return Date.now() + intervalo;                              // se reintenta en la siguiente vuelta
      }
      if (r.agotada) {
        s.iaPausaHasta = siguienteReinicio(); await this.guardar();
        console.log(JSON.stringify({ evento: 'ia_carril_en_pausa', hasta: new Date(s.iaPausaHasta).toISOString() }));
        return s.iaPausaHasta;
      }
    }
  }

  /** Un análisis de la fila, de principio a fin. Nunca registra el texto. */
  async correr(t, soltar) {
    const env = this.env;
    const quitar = () => env.DB.prepare(`DELETE FROM analisis WHERE id = ?1 AND usuario = ?2 AND estado = 'fila'`).bind(t.id, t.usuario).run();
    const f = await env.DB.prepare(`SELECT entrada FROM analisis WHERE id = ?1 AND usuario = ?2 AND estado = 'fila'`).bind(t.id, t.usuario).first();
    if (!f) { await devolverCuota(env, t.usuario, t.dia); return; } // lo borró antes de su turno

    const entrada = JSON.parse(f.entrada);
    let datosTexto;
    try {
      datosTexto = await pedirContexto(env, entrada, t.usuario, t.dia); // si falla, ya devolvió la cuota
    } catch (e) {
      await quitar();
      console.log(JSON.stringify({ evento: 'fila_sin_datos', error: e.message }));
      return;
    }
    await soltar();

    try {
      // Los datos se guardan ya, con la IA pendiente: la hace el carril de IA, a su ritmo. El mismo
      // formato que guarda el análisis en vivo: { datos, ia }. Si lo borró mientras corría, no hay
      // fila que actualizar y el resultado se descarta.
      const datos = JSON.parse(datosTexto);
      await env.DB.prepare(
        `UPDATE analisis SET resultado = ?3, estado = 'listo', ia_pendiente = 1, creado = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
         WHERE id = ?1 AND usuario = ?2 AND estado = 'fila'`,
      ).bind(t.id, t.usuario, JSON.stringify({ datos, ia: null })).run();
    } catch (e) {
      await quitar();
      await devolverCuota(env, t.usuario, t.dia);
      throw e;
    }
  }
}
