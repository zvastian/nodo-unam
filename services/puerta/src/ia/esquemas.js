// Esquemas de salida de las 3 llamadas de IA (nota, Bloom, preguntas), en el formato que pinta la
// plantilla del Laboratorio (laboratorio.html, v3). Toda salida se valida aquí antes de
// llegar al navegador: Workers AI no garantiza el esquema y Groq solo lo aplica si el modelo lo admite.

const texto = (max) => ({ type: 'string', maxLength: max });
const lista = (items, min, max) => ({ type: 'array', items, minItems: min, maxItems: max });
const objeto = (properties) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });

export const TIPOS_PREGUNTA = ['Comparativa', 'Histórica', 'Causal', 'Evaluativa', 'Prospectiva', 'Exploratoria'];

export const ESQUEMAS = {
  // «Comprendí tu tesis así»: objetos de estudio, periodo, espacio y enfoque. Sin intro ni problema central.
  nota: objeto({
    main_objects: lista(texto(80), 1, 6),
    interpretive_angle: texto(120),
    scope: objeto({
      temporal: objeto({ applies: { type: 'boolean' }, text: texto(280), start: { type: ['integer', 'null'] }, end: { type: ['integer', 'null'] } }),
      geographic: objeto({ applies: { type: 'boolean' }, text: texto(280), units: lista(texto(60), 0, 6) }),
    }),
  }),
  // El nivel de cada objetivo lo pone el léxico; `level` solo para los que el léxico dejó sin nivel.
  bloom: objeto({
    main_risk: texto(260),
    objectives: lista(objeto({
      original: texto(600),
      level: { type: ['integer', 'null'], minimum: 0, maximum: 5 },
      diagnosis: texto(260),
      improvement: texto(260),
    }), 1, 8),
    revised: lista(objeto({ text: texto(320) }), 2, 5),
    final_note: texto(260),
  }),
  preguntas: objeto({
    items: lista(objeto({
      type: { type: 'string', enum: TIPOS_PREGUNTA },
      question: texto(320),
      methodological_angle: texto(240),
    }), 3, 5),
  }),
};

/** Versión para el proveedor: sin topes de longitud ni de cantidad, que no todos los modos estrictos admiten. */
export function paraProveedor(esquema) {
  if (Array.isArray(esquema)) return esquema.map(paraProveedor);
  if (!esquema || typeof esquema !== 'object') return esquema;
  const out = {};
  for (const [k, v] of Object.entries(esquema)) {
    if (['maxLength', 'minItems', 'maxItems', 'minimum', 'maximum'].includes(k)) continue;
    out[k] = paraProveedor(v);
  }
  return out;
}

function tipoDe(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  if (Number.isInteger(v)) return 'integer';
  return typeof v;
}

/** Valida `valor` contra el subconjunto de JSON Schema que usan estos esquemas. Devuelve errores. */
export function validar(esquema, valor, ruta = '$') {
  const errores = [];
  const tipos = [].concat(esquema.type || []);
  const t = tipoDe(valor);
  if (tipos.length && !tipos.includes(t) && !(t === 'integer' && tipos.includes('number'))) {
    return [`${ruta}: se esperaba ${tipos.join(' o ')} y llegó ${t}`];
  }
  if (esquema.enum && !esquema.enum.includes(valor)) errores.push(`${ruta}: «${valor}» no está en ${esquema.enum.join(', ')}`);
  if (t === 'string') {
    if (!valor.trim()) errores.push(`${ruta}: vacío`);
    if (esquema.maxLength && valor.length > esquema.maxLength) errores.push(`${ruta}: más de ${esquema.maxLength} caracteres`);
  }
  if (t === 'integer') {
    if (esquema.minimum !== undefined && valor < esquema.minimum) errores.push(`${ruta}: menor que ${esquema.minimum}`);
    if (esquema.maximum !== undefined && valor > esquema.maximum) errores.push(`${ruta}: mayor que ${esquema.maximum}`);
  }
  if (t === 'array') {
    if (esquema.minItems !== undefined && valor.length < esquema.minItems) errores.push(`${ruta}: menos de ${esquema.minItems} elementos`);
    if (esquema.maxItems !== undefined && valor.length > esquema.maxItems) errores.push(`${ruta}: más de ${esquema.maxItems} elementos`);
    if (esquema.items) valor.forEach((v, i) => errores.push(...validar(esquema.items, v, `${ruta}[${i}]`)));
  }
  if (t === 'object') {
    for (const k of esquema.required || []) if (!(k in valor)) errores.push(`${ruta}.${k}: falta`);
    for (const [k, v] of Object.entries(valor)) {
      if (esquema.properties?.[k]) errores.push(...validar(esquema.properties[k], v, `${ruta}.${k}`));
      else if (esquema.additionalProperties === false) errores.push(`${ruta}.${k}: campo no permitido`);
    }
  }
  return errores;
}
