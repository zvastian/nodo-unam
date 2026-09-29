// Limpieza del texto que llega al modelo (development.md, frente 6, «Inyección de prompt»).
// Corre en el Worker antes de cada llamada a la IA: es la que protege. La del formulario es comodidad.
//
//   - normaliza con NFKC (así «＜» de ancho completo pasa a «<» antes de neutralizarlo);
//   - quita caracteres de control, de formato (ancho cero, bidi, guion suave) y privados;
//   - cambia < y > por ‹ y ›, para que el texto no pueda abrir ni cerrar etiquetas como
//     <entrada_usuario> y salirse del bloque de datos del prompt («x < 5» queda «x ‹ 5»);
//   - colapsa espacios y repeticiones («!!!!!!!!», «ja ja ja ja ja…»), sin tocar cifras («1000000»).
// Los patrones típicos de inyección solo se cuentan: el texto nunca va a los logs.

const INVISIBLES = /[\p{Cc}\p{Cf}\p{Co}\p{Cs}]/gu;   // incluye U+200B–200F, U+202A–202E, U+2066–2069
const REPETIDO = /(\D{1,40}?)\1{4,}/gsu;            // lo mismo 5 o más veces seguidas

export function limpiarTexto(s) {
  let t = String(s ?? '').normalize('NFKC').replace(/[\t\r]/g, ' ');
  t = t.replace(INVISIBLES, (c) => (c === '\n' ? c : ''));   // los saltos de línea se conservan
  t = t.replace(/</g, '‹').replace(/>/g, '›');
  t = t.replace(REPETIDO, '$1$1$1');
  return t.replace(/[  ]{2,}/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

/** La entrada del análisis con cada texto limpio. La forma no cambia: el servicio de datos la valida. */
export function limpiarEntrada(e) {
  if (!e || typeof e !== 'object') return e;
  const o = { ...e };
  for (const k of ['title', 'problematiza', 'program', 'degree']) if (typeof o[k] === 'string') o[k] = limpiarTexto(o[k]);
  for (const k of ['objectives', 'keywords']) {
    if (Array.isArray(o[k])) o[k] = o[k].map((x) => (typeof x === 'string' ? limpiarTexto(x) : x));
  }
  return o;
}

const PATRONES = [
  /\b(ignora|olvida|omite|descarta)\w*\s+(\w+\s+){0,3}(instrucci|indicaci|reglas|anterior)/iu,
  /\b(ignore|disregard|forget)\s+(\w+\s+){0,3}(instructions|rules|previous|above)/iu,
  /\b(system|developer)\s*(prompt|message|mensaje)/iu,
  /\bprompt\s+(del\s+)?sistema\b/iu,
  /^\s*(system|assistant|user|sistema|asistente)\s*:/imu,
  /\b(act[úu]a|comp[óo]rtate|responde)\s+como\b/iu,
  /\b(you are now|from now on|a partir de ahora eres)\b/iu,
  /‹\/?\s*(entrada_usuario|system|instructions?|instrucciones)/iu,
];

/** Cuántos patrones típicos de inyección aparecen en la entrada ya limpia (para el registro). */
export function contarInyeccion(e) {
  const textos = [e?.title, e?.problematiza, e?.program, ...(e?.objectives || []), ...(e?.keywords || [])]
    .filter((x) => typeof x === 'string');
  // Unidos con salto de línea, para detectar instrucciones repartidas entre campos.
  const todo = textos.join('\n');
  return PATRONES.reduce((n, re) => n + (re.test(todo) ? 1 : 0), 0);
}
