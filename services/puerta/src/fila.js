// La fila del Laboratorio (paso 2 de la lista de lanzamiento, 29-sep-2026). Un Durable Object, uno
// solo para todo el sitio (plan gratuito, con almacenamiento SQLite), que hace tres cosas:
//
// 1. Reparte lugares en el servicio de datos: FILA_SIMULTANEOS a la vez (2), porque Modal corre un
//    solo contenedor de 2 núcleos. Un lugar vale mientras el servicio de datos trabaja; la IA ya no
//    lo ocupa. Si el Worker que lo pidió muere sin soltarlo, vence solo a los 4 minutos.
// 2. Guarda el turno de los análisis que llegaron sin lugar. El texto no vive aquí: está en la fila
//    de D1 del análisis (estado «fila»), la misma que Mi espacio muestra como «En la fila».
// 3. Los corre en segundo plano (alarma) con el mismo código del análisis en vivo y guarda el
//    resultado en D1 como un análisis normal. Si el usuario lo borró antes de su turno, o si el
//    servicio de datos falla, se devuelve su cuota.
//
// Sin largo máximo (decisión del usuario, 29-sep): el único freno es el tope diario del sitio.
// Quien llega mientras hay fila espera su turno aunque se libere un lugar: primero los de la fila.

import { correrIA } from './analisis.js';
import { clasificarObjetivos } from '../../../prototypes/atlas_vecindario_mvp/compartido/bloom.js';
import { devolverCuota, entero, hoy, pedirContexto } from './comun.js';

const LUGAR_VIVO_MS = 4 * 60 * 1000;         // lugar de un análisis en vivo, si nadie lo suelta
const LUGAR_FILA_MS = 10 * 60 * 1000;        // lugar de un análisis de la fila
const TURNO_ALARMA_MS = 12 * 60 * 1000;      // una alarma dura a lo más 15 min: se reprograma antes

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
    } else if (ruta === '/estado') {
      r = { en_fila: s.cola.length, lugares_ocupados: Object.keys(s.lugares).length, en_curso: Object.keys(s.enCurso).length };
    } else return new Response('no', { status: 404 });
    await this.guardar();
    if (s.cola.length) await this.programar();
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
    await soltar(); // la IA no ocupa el servicio de datos

    try {
      const datos = JSON.parse(datosTexto);
      const lexico = clasificarObjetivos(entrada.objectives || [], entrada.degree || '');
      const { ia } = await correrIA(env, hoy(), entrada, datos, lexico);
      // El mismo formato que guarda el Laboratorio: { datos, ia }. Si lo borró mientras corría, no
      // hay fila que actualizar y el resultado se descarta.
      await env.DB.prepare(
        `UPDATE analisis SET resultado = ?3, estado = 'listo', creado = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
         WHERE id = ?1 AND usuario = ?2 AND estado = 'fila'`,
      ).bind(t.id, t.usuario, JSON.stringify({ datos, ia })).run();
    } catch (e) {
      await quitar();
      await devolverCuota(env, t.usuario, t.dia);
      throw e;
    }
  }
}
