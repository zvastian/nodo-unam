// Léxico de Bloom de NodOS: clasifica objetivos de tesis sin IA, en vivo y de forma determinista.
// Lo comparten el formulario del Laboratorio (navegador, <script type="module">) y el Worker puerta,
// que pasa este resultado al prompt de Bloom. Módulo ES sin dependencias.
//
// Reglas (development.md, «Casos límite del análisis Bloom»):
//   - un nivel por verbo; los verbos ambiguos llevan un rango y el modelo elige por contexto;
//   - rige el verbo rector (el primero que aparece al inicio del objetivo), lematizado;
//   - el léxico propone y el modelo decide; la interfaz marca lo que clasificó la IA.

export const NIVELES = ['Recordar', 'Comprender', 'Aplicar', 'Analizar', 'Evaluar', 'Crear'];

// Verbo en infinitivo, sin acentos -> nivel (0 a 5).
const NIVEL = {};
const porNivel = [
  'recordar reconocer enumerar listar nombrar definir memorizar localizar recuperar citar',
  'comprender explicar interpretar resumir clasificar categorizar contextualizar caracterizar describir ' +
    'ejemplificar inferir parafrasear ilustrar exponer',
  'aplicar utilizar usar implementar emplear calcular resolver modelar ejecutar simular operacionalizar ' +
    'estimar cuantificar',
  'analizar comparar contrastar examinar diferenciar distinguir relacionar correlacionar desglosar ' +
    'descomponer atribuir deconstruir',
  'evaluar valorar juzgar justificar argumentar criticar verificar validar comprobar ponderar calificar ' +
    'dictaminar defender priorizar recomendar',
  'crear proponer disenar formular sugerir construir elaborar desarrollar planear planificar generar ' +
    'producir idear inventar componer reformular plantear innovar',
];
porNivel.forEach((lista, n) => lista.split(/\s+/).forEach((v) => { NIVEL[v] = n; }));

/** Verbos con nivel fijo, por nivel (sin acentos: «disenar»). Los usa el prompt de objetivos revisados. */
export const VERBOS_POR_NIVEL = porNivel.map((l) => l.split(/\s+/));

// Ambiguos: el léxico da una banda y el modelo elige por contexto.
const RANGO = {
  identificar: [0, 3],   // localizar algo o distinguir sus rasgos
  determinar: [2, 4],    // medir o decidir
  medir: [2, 4],         // aplicar un instrumento o valorar un efecto
  demostrar: [2, 4],     // mostrar un procedimiento o probar una tesis
  diagnosticar: [3, 4],
  explorar: [1, 3],
  establecer: [1, 4],
};

// No observables: no se puede evaluar si se cumplieron.
const VAGOS = new Set(('conocer entender saber profundizar abordar estudiar investigar indagar tratar ver ' +
  'aprender reflexionar familiarizar acercar aproximar').split(' '));

// Sustantivo al inicio del objetivo -> verbo sugerido («Análisis de…» -> analizar).
const NOMINAL = {
  analisis: 'analizar', estudio: 'estudiar', evaluacion: 'evaluar', diseno: 'disenar', propuesta: 'proponer',
  comparacion: 'comparar', identificacion: 'identificar', descripcion: 'describir', caracterizacion: 'caracterizar',
  elaboracion: 'elaborar', desarrollo: 'desarrollar', implementacion: 'implementar', determinacion: 'determinar',
  explicacion: 'explicar', interpretacion: 'interpretar', aplicacion: 'aplicar', construccion: 'construir',
  creacion: 'crear', formulacion: 'formular', medicion: 'medir', valoracion: 'valorar', revision: 'revisar',
  clasificacion: 'clasificar', verificacion: 'verificar', validacion: 'validar', estimacion: 'estimar',
  exploracion: 'explorar', diagnostico: 'diagnosticar', modelado: 'modelar', calculo: 'calcular',
  examen: 'examinar', planeacion: 'planear', planificacion: 'planificar', sistematizacion: 'sistematizar',
};

// Verbos «ligeros» que toman el sentido de su complemento: «realizar un análisis», «llevar a cabo encuestas».
const LIGEROS = new Set(['realizar', 'hacer', 'efectuar', 'llevar']);
// Instrumentos y actividades de método (no son objetivos).
const METODO_OBJ = /^(una?s?\s+|el\s+|la\s+|los\s+|las\s+)?(entrevistas?|encuestas?|cuestionarios?|grupos?\s+focal(es)?|trabajo\s+de\s+campo|observacion(es)?|muestreos?|experimentos?|revision\s+(bibliografica|documental|de\s+(la\s+)?literatura)|bibliografia|literatura|estado\s+del\s+arte|fuentes|documentos|archivos?|datos)\b/;
const METODO_VERBOS = new Set(['entrevistar', 'encuestar', 'recopilar', 'recolectar', 'recabar', 'capturar', 'levantar', 'revisar', 'consultar', 'aplicar']);
// «Aplicar» y «revisar» solo son de método con un instrumento de complemento.
const METODO_SOLO_CON_OBJETO = new Set(['aplicar', 'revisar', 'consultar', 'levantar', 'capturar']);

const TRAMITE = /\b((hacer|terminar|concluir|presentar|escribir|redactar|entregar)\s+(mi|la|una)\s+tesis|titular(me|se|nos)|obtener\s+(el|mi)\s+(titulo|grado)|acreditar|cumplir\s+(con\s+)?(el|los)\s+requisitos?)\b/;

const INGLES = new Set('to the of and for in on with by from analyze analyse evaluate identify describe design develop compare assess determine explore examine understand propose'.split(' '));
const ESPANOL = new Set('de la el los las en y para por con del al que se un una'.split(' '));

// Palabras que se saltan antes del verbo rector.
const PREAMBULO = new Set(['se', 'para', 'que', 'el', 'la', 'objetivo', 'general', 'especifico', 'es', 'busca', 'pretende', 'intenta', 'quiere', 'buscamos', 'pretendo', 'busco', 'mi', 'nuestro', 'primero', 'finalmente', 'ademas', 'tambien', 'y']);

const ENCLITICOS = /(selos|selas|sela|selo|los|las|lo|la|les|le|se|nos)$/;
const FUTURO = /(emos|eis|an|as|a|e)$/;          // analizare, analizaran… (tras quitar acentos)
const CONDICIONAL = /(iamos|iais|ian|ias|ia)$/;

export function normalizar(t) {
  return String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function esVerbo(v) { return NIVEL[v] !== undefined || RANGO[v] !== undefined || VAGOS.has(v) || METODO_VERBOS.has(v) || LIGEROS.has(v); }

/** Infinitivo de una forma verbal si pertenece al léxico (analizaré, analizando, analizarlo…). */
export function lematizar(palabra) {
  const w = normalizar(palabra);
  if (esVerbo(w)) return w;
  const cand = new Set();
  // Enclíticos: analizarlo, desarrollarse
  const sinClitico = w.replace(ENCLITICOS, '');
  if (/(ar|er|ir)$/.test(sinClitico)) cand.add(sinClitico);
  // Futuro y condicional: analizare, analizaria
  for (const re of [FUTURO, CONDICIONAL]) {
    const base = w.replace(re, '');
    if (base !== w && /(ar|er|ir)$/.test(base)) cand.add(base);
  }
  // Gerundio y participio: analizando, analizado, construyendo
  if (/ando$/.test(w)) cand.add(w.replace(/ando$/, 'ar'));
  if (/(iendo|yendo)$/.test(w)) { const r = w.replace(/(iendo|yendo)$/, ''); cand.add(r + 'er'); cand.add(r + 'ir'); }
  if (/ad[oa]s?$/.test(w)) cand.add(w.replace(/ad[oa]s?$/, 'ar'));
  if (/id[oa]s?$/.test(w)) { const r = w.replace(/id[oa]s?$/, ''); cand.add(r + 'er'); cand.add(r + 'ir'); }
  for (const c of cand) if (esVerbo(c)) return c;
  // Presente y subjuntivo (analiza, analizan, analice): solo con raíces largas, para no confundir.
  for (const v of [...Object.keys(NIVEL), ...Object.keys(RANGO), ...VAGOS]) {
    const raiz = v.slice(0, -2);
    if (raiz.length >= 5 && w.startsWith(raiz) && w.length - raiz.length <= 4 && /^(o|a|as|an|amos|e|es|en|emos|imos|a)$/.test(w.slice(raiz.length))) return v;
  }
  return null;
}

function palabras(t) { return normalizar(t).split(/[^a-zñ]+/).filter(Boolean); }

/**
 * Clasifica un objetivo.
 * Devuelve { texto, verbo, lema, nivel, rango, banderas, sugerencias }:
 *   nivel: 0 a 5, o null si el léxico no decide (ambiguo, vago, fuera del léxico…);
 *   rango: [min, max] para los ambiguos;
 *   banderas: fuera_lexico, ambiguo, vago, varios_verbos, sin_verbo, metodo, tramite, otro_idioma, vacio.
 */
export function clasificarObjetivo(texto) {
  const r = { texto: String(texto || '').trim(), verbo: '', lema: null, nivel: null, rango: null, banderas: [], sugerencias: [] };
  const norm = normalizar(r.texto).replace(/^\s*(\d+[.)-]?|[a-z][.)])\s+/, '');
  const t = palabras(norm);
  if (!t.length) { r.banderas.push('vacio'); return r; }

  const ing = t.filter((w) => INGLES.has(w)).length, esp = t.filter((w) => ESPANOL.has(w)).length;
  if (t[0] === 'to' || (ing >= 2 && ing > esp)) { r.banderas.push('otro_idioma'); return r; }
  if (TRAMITE.test(norm)) { r.banderas.push('tramite'); return r; }

  // Verbo rector: el primero reconocible entre las primeras palabras, después del preámbulo.
  let i = 0;
  while (i < t.length && PREAMBULO.has(t[i]) && !lematizar(t[i])) i++;
  // Sin verbo: «Análisis de…». Va antes de lematizar: «desarrollo» o «estudio» también son verbos
  // conjugados, pero al inicio de un objetivo casi siempre son sustantivos.
  if (NOMINAL[t[i]]) {
    const l = NOMINAL[t[i]];
    r.banderas.push('sin_verbo');
    r.verbo = t[i];
    r.lema = l;
    r.sugerencias.push(l);
    if (NIVEL[l] !== undefined) r.nivel = NIVEL[l];
    if (RANGO[l]) { r.rango = RANGO[l]; r.banderas.push('ambiguo'); }
    if (VAGOS.has(l)) r.banderas.push('vago');
    return r;
  }

  let lema = null, pos = -1;
  for (let k = i; k < Math.min(i + 3, t.length); k++) {
    const l = lematizar(t[k]);
    if (l) { lema = l; pos = k; break; }
    if (k === i && /(ar|er|ir)$/.test(t[k]) && t[k].length > 4) { pos = k; break; } // infinitivo fuera del léxico
  }
  if (pos === -1) { r.verbo = t[i] || ''; r.banderas.push('fuera_lexico'); return r; }

  r.verbo = t[pos];
  if (lema === null) { r.banderas.push('fuera_lexico'); return r; }

  // Verbo ligero + complemento: «realizar entrevistas» (método) o «realizar un análisis» (analizar).
  const resto = t.slice(pos + 1).join(' ');
  if (LIGEROS.has(lema) || (lema === 'llevar' && /^a cabo/.test(resto))) {
    const comp = resto.replace(/^a cabo\s+/, '');
    if (METODO_OBJ.test(comp)) { r.lema = lema; r.banderas.push('metodo'); return r; }
    const n = comp.split(' ').find((w) => !/^(un|una|unos|unas|el|la|los|las)$/.test(w));
    if (n && NOMINAL[n]) { lema = NOMINAL[n]; }
  }
  if (METODO_VERBOS.has(lema) && (!METODO_SOLO_CON_OBJETO.has(lema) || METODO_OBJ.test(resto))) {
    r.lema = lema; r.banderas.push('metodo'); return r;
  }

  r.lema = lema;
  if (NIVEL[lema] !== undefined) r.nivel = NIVEL[lema];
  else if (RANGO[lema]) { r.rango = RANGO[lema]; r.banderas.push('ambiguo'); }
  else if (VAGOS.has(lema)) { r.banderas.push('vago'); r.sugerencias.push('describir', 'analizar', 'comparar', 'evaluar'); }
  else r.banderas.push('fuera_lexico');

  // Varios verbos: «identificar y analizar…» (rige el primero; se sugiere partir el objetivo).
  const sig = t.slice(pos + 1, pos + 4);
  const conj = sig.findIndex((w) => w === 'y' || w === 'e');
  if (conj >= 0 && sig[conj + 1] && lematizar(sig[conj + 1]) && !METODO_VERBOS.has(lematizar(sig[conj + 1]))) {
    r.banderas.push('varios_verbos');
  }
  return r;
}

// Nivel máximo que se espera ver por grado (provisional; calibrar con el conjunto de evaluación).
export const ESPERADO_POR_GRADO = { licenciatura: 3, especialidad: 3, maestria: 4, doctorado: 5 };

/**
 * Clasifica la lista completa y añade banderas de estructura:
 *   un_objetivo, demasiados, mismo_nivel, retroceso (por objetivo), salto (niveles faltantes entre
 *   el menor y el mayor), crear_sin_evaluar, bajo_para_grado.
 */
export function clasificarObjetivos(objetivos, grado = '') {
  const items = (objetivos || []).map(clasificarObjetivo).filter((o) => !o.banderas.includes('vacio'));
  const estructura = [];
  if (items.length === 1) estructura.push('un_objetivo');
  if (items.length > 6) estructura.push('demasiados');
  const niveles = items.map((o) => o.nivel).filter((n) => n !== null);
  let previo = null;
  for (const o of items) {
    if (o.nivel === null) continue;
    if (previo !== null && o.nivel < previo) o.banderas.push('retroceso');
    previo = o.nivel;
  }
  const faltan = [];
  if (niveles.length >= 2) {
    const u = [...new Set(niveles)].sort((a, b) => a - b);
    if (u.length === 1) estructura.push('mismo_nivel');
    for (let n = u[0] + 1; n < u[u.length - 1]; n++) if (!u.includes(n)) faltan.push(n);
    if (faltan.length) estructura.push('salto');
    if (u.includes(5) && !u.includes(4)) estructura.push('crear_sin_evaluar');
  }
  const esperado = ESPERADO_POR_GRADO[normalizar(grado)];
  const maximo = niveles.length ? Math.max(...niveles) : null;
  if (esperado !== undefined && maximo !== null && maximo < esperado) estructura.push('bajo_para_grado');
  return { objetivos: items, estructura, niveles_faltantes: faltan, maximo, esperado: esperado ?? null };
}
