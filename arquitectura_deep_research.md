# NodOS: insumo para dos investigaciones profundas

## Cómo usar este archivo

Sirve para **dos investigaciones distintas**, cada una en un chat nuevo de Claude con Research
activado. Una investigación profunda rinde más con una pregunta enfocada que con todas a la vez.

1. Completa la **parte C** (tu perfil, 2 minutos).
2. Chat 1: pega el archivo completo y escribe **«Ejecuta la investigación A1»** (arquitectura).
3. Chat 2: pega el archivo completo y escribe **«Ejecuta la investigación A2»** (aprendizaje).

Contenido:

- **Parte A.** Las instrucciones: A0 (reglas para las dos), A1 y A2.
- **Parte B.** Cómo está construido NodOS hoy, leído del código (versión 1.0.7, 5 de octubre de
  2026).
- **Parte C.** Quién pregunta y para qué.

---

# PARTE A. Instrucciones de investigación

## A0. Reglas para las dos investigaciones

**Aprovecha lo que una investigación profunda hace mejor que una respuesta normal:**

- **Fuentes actuales.** Prioriza documentación y publicaciones de 2025 y 2026. Las capas gratuitas,
  los límites de los proveedores y las prácticas con modelos de lenguaje cambian cada pocos meses:
  pon la fecha de cada dato que pueda caducar.
- **Fuentes primarias.** Documentación oficial, normas, artículos y libros reconocidos, blogs de
  ingeniería de las empresas que operan esos sistemas. Evita resúmenes de terceros cuando exista
  la fuente original.
- **Comparar, no listar.** Para cada decisión, al menos tres alternativas reales en una tabla de
  compromisos (costo, complejidad, riesgo, encaje con las restricciones de la parte B, §2).
- **Casos reales.** Busca proyectos comparables (mapas semánticos de corpus académicos, sitios
  estáticos con funciones de borde, aplicaciones de un solo desarrollador en capas gratuitas,
  productos con LLM en producción) y *postmortems* públicos. Di qué decidieron y qué aprendieron.
- **Desacuerdos.** Si las fuentes se contradicen, muéstralo y di cuál te parece más sólida y por qué.
- **Confianza.** Marca cada afirmación importante como alta, media o baja confianza.

**Reglas de contenido:**

- **No inventes nada de NodOS.** Todo lo que digas del proyecto debe salir de la parte B. Lo que no
  esté, márcalo como «supuesto» o «recomendación», nunca como hecho.
- **Cita las fuentes** de cada estándar, patrón, práctica o dato externo, con enlace.
- **Respeta las restricciones** de la parte B, §2, en toda recomendación: costo de operación cero,
  un solo desarrollador, sin compilación en el frontend.
- **Español formal y claro.** Los términos técnicos en inglés van en cursiva la primera vez, con su
  traducción, y se explican con un ejemplo de NodOS.
- **Diagramas en Mermaid que compilen.** En las etiquetas evita «;» y «:» sueltos, que rompen el
  análisis de Mermaid.
- Un solo documento con resumen ejecutivo de una página, índice y secciones numeradas.

---

## A1. Investigación de arquitectura

### Rol

Arquitecto de software sénior con experiencia en documentación formal de arquitectura (ISO/IEC/IEEE
42010, modelo C4, plantilla arc42, vistas 4+1), en aplicaciones *serverless* y de borde (*edge*),
en sistemas con modelos de lenguaje y en privacidad de datos en México.

### Objetivo

El **documento formal de arquitectura de NodOS**, presentable para un proyecto profesional o
académico: que una persona técnica que nunca vio el proyecto entienda cómo funciona, por qué está
hecho así y dónde están sus riesgos.

### Entregables

1. **Clasificación de la arquitectura.** Qué estilos y patrones aplica, con definición y fuente,
   dónde se ven en NodOS y qué tan fiel es la aplicación. Candidatos: sitio estático con funciones
   de borde (JAMstack), *Backend for Frontend* o *API gateway* (el Worker «puerta»), lotes offline
   más servicio en línea (*batch* + *online serving*), *serverless*, fila con *Durable Objects*,
   *Server-Sent Events*, flujo de trabajo con LLM (paralelización, evaluador-optimizador).
2. **Diagramas** con la notación C4: contexto (nivel 1), contenedores (nivel 2), componentes del
   Worker «puerta» (nivel 3); despliegue (qué corre en qué proveedor); secuencia de los flujos de la
   parte B, §7 (sesión, análisis en vivo, análisis en la fila, carril de IA con reintentos); flujo de
   datos con **fronteras de confianza** (*trust boundaries*); y la máquina de estados del análisis
   guardado (§7.6).
3. **Atributos de calidad** con la clasificación de ISO/IEC 25010: cómo los atiende hoy la
   arquitectura, con evidencia de la parte B, y escenarios de calidad concretos.
4. **Seguridad:** amenazas STRIDE sobre el flujo de datos, contraste con OWASP ASVS y con el OWASP
   Top 10 para aplicaciones con LLM, y riesgos ordenados por severidad.
5. **Privacidad:** contraste con la Ley Federal de Protección de Datos Personales en Posesión de los
   Particulares (México) y su reglamento, incluida la función que viene (avisos por correo).
6. **La función siguiente, avisos por correo** (parte B, §11): comparación actual de proveedores de
   envío con capa gratuita (límites y fecha), SPF, DKIM y DMARC, baja de un clic (RFC 8058 y
   `List-Unsubscribe`), dónde vive el consentimiento y cómo encaja sin romper las restricciones.
7. **Panorama de capas gratuitas 2026** para cada pieza de NodOS (sitio, cómputo de borde, base de
   datos, contenedor con 4 GiB, inferencia de LLM, identidad, correo): proveedor actual, dos
   alternativas, límites con fecha y el costo de mudarse. NodOS ya cambió de proveedor dos veces por
   cambios en capas gratuitas.
8. **Proyectos comparables:** cómo resolvieron arquitecturas parecidas otros mapas semánticos de
   publicaciones o corpus académicos, y qué conviene adoptar.
9. **Registro de decisiones:** las de la parte B, §10, en formato ADR (contexto, decisión,
   consecuencias), y cuáles conviene revisar.
10. **Brechas y hoja de ruta:** qué le falta para considerarse madura (observabilidad, pruebas,
    recuperación ante desastres, gestión de secretos…), ordenado por impacto y costo.

---

## A2. Investigación de aprendizaje: ser mejor desarrollador con NodOS como laboratorio

### Rol

Mentor de ingeniería de software sénior que diseña planes de aprendizaje a partir del trabajo real
de la persona, no de temarios genéricos.

### Objetivo

Que quien construyó NodOS (parte C) se vuelva mejor desarrollador **usando su propio proyecto como
material de estudio**: entender a fondo lo que ya construyó, cerrar las brechas que el proyecto deja
ver y adquirir los hábitos de un ingeniero sénior.

### Entregables

1. **Mapa de competencias.** A partir de la parte B, qué competencias ya demuestra el proyecto y
   cuáles faltan, contrastadas con marcos reconocidos (por ejemplo, SWEBOK v4, roadmap.sh, las
   escalas de carrera públicas de empresas de software). Una tabla: competencia, evidencia en
   NodOS, nivel estimado, brecha.
2. **Los conceptos que el proyecto ya usa, explicados con el proyecto.** Para cada uno: qué es, la
   fuente canónica, dónde aparece en NodOS y un error típico. Al menos: atomicidad y condiciones de
   carrera (la reserva de cupo de la 1.0.4), idempotencia y reintentos con espera (la 1.0.6), filas
   y contrapresión (*backpressure*), caché e invalidación, consistencia, autenticación con JWT y
   PKCE, CSP, arranque en frío, formatos columnares, *embeddings* y búsqueda vectorial, salidas
   estructuradas de LLM, flujo de trabajo frente a agente.
3. **Estado del arte 2025-2026 en lo que NodOS necesita ahora:**
   - **Evaluación de LLM con humanos en el ciclo:** conjuntos de evaluación, rúbricas, LLM como
     juez y su calibración contra etiquetas humanas, optimización de prompts (por ejemplo DSPy u
     otras), y cómo hacerlo con un presupuesto de tokens casi nulo.
   - **Flujos de trabajo y agentes:** cuándo conviene un grafo (LangGraph u otros) y cuándo un
     script; agentes de programación (como Claude Code) en el desarrollo diario: cómo especificar,
     verificar y no perder el entendimiento del propio código.
   - **Pruebas y observabilidad** en *serverless* con capas gratuitas.
   - **Ingeniería de datos** a escala de un desarrollador: linaje, reproducibilidad, versionado de
     datos y de modelos.
4. **Hábitos de un ingeniero sénior**, con fuente y un ejercicio en NodOS para cada uno:
   documentos de diseño, ADR, *postmortems* sin culpa (ejemplo para practicar: los análisis que
   quedaban parciales para siempre, parte B §7.6), revisión de código, SLO y presupuestos de error,
   medir antes de cambiar, versionado y bitácora.
5. **Plan de 12 semanas.** Cada semana: un concepto, una lectura primaria (capítulo concreto) y un
   ejercicio sobre el código real de NodOS con un resultado verificable (una prueba, un ADR, una
   métrica, un diagrama). Ajusta el ritmo a las horas de la parte C.
6. **Biblioteca curada.** Libros, cursos y documentación, priorizando lo gratuito, con nivel,
   tiempo estimado y para qué sirve en NodOS. Investiga y valida cuáles son hoy las referencias más
   recomendadas en diseño de sistemas, arquitectura, SRE, seguridad web y LLM en producción.
7. **NodOS como caso de portafolio:** cómo presentarlo (estructura de un estudio de caso técnico,
   qué métricas y decisiones destacar) para un empleo, un posgrado o una beca.

---

# PARTE B. Contexto: la arquitectura de NodOS (versión 1.0.7)

## 1. Qué es

NodOS es un **mapa semántico navegable de las tesis de la UNAM** (más de 600 mil registros del
catálogo público TESIUNAM, de 1873 a 2026). Es un proyecto independiente y no oficial, de un solo
desarrollador, en producción en `nodosmap.com` desde el 29 de septiembre de 2026.

Tiene tres partes visibles:

- **Mapa.** Todas las tesis como puntos en un plano 2D, donde la cercanía equivale a parecido
  temático. Se organizan en tres niveles: 130 campos, 432 temas y 513 subtemas. Tiene fichas de
  tesis, de agrupaciones y de asesores, buscador y un modo de análisis por tema. No pide cuenta.
- **Laboratorio.** El estudiante describe su tesis en curso (título, problematización, objetivos,
  palabras clave, programa, grado y periodo). Recibe dónde cae en el mapa, qué tan saturado está su
  tema, qué asesores dirigieron trabajos cercanos y las 100 tesis más parecidas. Encima, un modelo
  de lenguaje produce tres lecturas: una nota del planteamiento, la revisión de los objetivos con
  la taxonomía de Bloom y preguntas de investigación. Pide cuenta; cada cuenta hace 2 análisis al
  día y guarda hasta 2.
- **Mi espacio.** Lo que cada cuenta guarda: análisis, tesis, asesores y lugares del mapa. Desde
  ahí se borra la cuenta.

Además hay páginas de método («Acerca de»), aviso de privacidad, términos de uso y contacto.

**Usuarios:** estudiantes y egresados que buscan tema, asesor o antecedentes; asesores y
coordinadores de posgrado. Escala observada en la primera semana: unos 340 análisis guardados de
unas 260 cuentas; un pico de 182 análisis en un día.

## 2. Restricciones y requisitos que guían la arquitectura

En orden de peso:

1. **Costo de operación cero.** Sin financiamiento. Cada componente de producción cabe en una capa
   gratuita y debe poder cambiar de proveedor modificando solo configuración. La única tarjeta
   registrada (en el proveedor del servicio de datos) tiene un límite de uso igual a su crédito
   mensual gratuito.
2. **Privacidad.** Los nombres de los autores (estudiantes) nunca se muestran ni se publican; los
   de los asesores sí. El texto que un usuario escribe en el Laboratorio no llega a ningún log.
3. **El corpus cambia poco** (a lo sumo una vez al año): conviene calcular todo de antemano y
   servirlo como archivos estáticos.
4. **Consistencia del espacio semántico.** Todo lo que se compara con el corpus se representa con
   el mismo modelo y el mismo preprocesamiento con que se representó el corpus.
5. **Un solo desarrollador.** Sin paso de compilación en el frontend, pocas piezas desplegables y
   ningún servidor propio que mantener.

## 3. Actores y sistemas externos

| Actor o sistema | Relación con NodOS |
|---|---|
| Visitante anónimo | Usa el mapa y lee las páginas; no necesita cuenta |
| Estudiante con cuenta | Usa el Laboratorio y Mi espacio |
| Desarrollador (dueño) | Opera el pipeline offline, despliega y revisa |
| TESIUNAM (catálogo de la UNAM) | Origen de los datos; se extrajo una vez, offline |
| Supabase Auth | Proveedor de identidad: Google, GitHub y enlace mágico por correo |
| Cloudflare | Aloja el sitio, la API, la base de datos, la fila, el antiabuso, las estadísticas y la IA de respaldo; registrador del dominio |
| Modal | Ejecuta el servicio de datos del Laboratorio (contenedor) |
| Groq | Proveedor principal del modelo de lenguaje (`gpt-oss-120b`), con retención de datos desactivada |
| Stripe | Enlace de pago para aportaciones voluntarias (sale del sitio) |
| Kaggle y GitHub | Distribución pública del dataset (CC BY 4.0) y del código |

## 4. Contenedores (piezas desplegables)

| Pieza | Tecnología | Dónde corre | Responsabilidad |
|---|---|---|---|
| **Sitio estático** | 7 páginas HTML, cada una en un solo archivo (HTML, CSS y JS), sin framework ni compilación; WebGL (`regl-scatterplot`), Canvas 2D, SVG y `d3` | Cloudflare Workers con archivos estáticos | Mapa, Laboratorio (interfaz), Mi espacio, páginas legales; unos 160 MB de datos precalculados |
| **Worker «puerta»** | JavaScript sin compilación, Cloudflare Workers | Borde de Cloudflare, en `nodosmap.com/api/*` (mismo origen que el sitio) | Único punto de entrada a lo dinámico: sesión, límites, cuotas, fila, llamadas al servicio de datos y a la IA, guardados |
| **Base de datos D1** | SQLite gestionado (Cloudflare D1) | Cloudflare | Análisis guardados, lo guardado en Mi espacio, contadores de cuotas |
| **Durable Object «Fila»** | Objeto durable con almacenamiento SQLite | Cloudflare | Una instancia para todo el sitio: turnos del servicio de datos y el carril de IA (alarmas) |
| **Servicio de datos del Laboratorio** | Python, FastAPI, ONNX Runtime, FAISS | Modal: un contenedor de 2 núcleos y 4 GiB, se apaga tras 1 min sin uso | Sin estado y sin IA: convierte el texto en un vector y devuelve su contexto en el corpus |
| **Modelo de lenguaje** | `gpt-oss-120b` | Groq; de respaldo, Workers AI (Cloudflare) | Las tres lecturas del Laboratorio |
| **Identidad** | Supabase Auth (OAuth y enlace mágico, flujo PKCE) | Supabase | Cuentas y tokens JWT |
| **Pipeline offline** | Scripts de Python, sin orquestador | Máquina local y Kaggle con GPU | Produce los datos del mapa y los artefactos del servicio de datos |

Ningún servicio interno queda expuesto al navegador: la URL del servicio de datos y las claves de
los proveedores viven solo en el Worker.

## 5. Plano offline: del catálogo a los artefactos

1. **Adquisición.** Extracción del catálogo TESIUNAM (sistema Aleph); nueve años con pérdidas se
   recuperaron desde la vista MARC del sistema Koha, reemplazando años completos para no
   deduplicar sin identificador común.
2. **Corpus canónico.** Un único archivo maestro (parquet) es la fuente de verdad; contiene
   autores, así que nunca se publica. Un export público se genera por lista blanca de columnas.
   Las correcciones de entidades (plantel, programa, grado, asesores) dejan un CSV de auditoría.
3. **Privacidad.** Un paso corta del título la mención de autoría («… presenta NOMBRE») antes de
   generar cualquier artefacto publicado.
4. **Representación.** `intfloat/multilingual-e5-large` (1024 dimensiones, norma 1) sobre el
   título normalizado. Solo el título: incluir programa o plantel ordenaría el espacio por
   categoría administrativa y borraría las cercanías entre disciplinas.
5. **Agrupamiento** (esquema BERTopic): UMAP a 5 dimensiones, HDBSCAN (513 subtemas), jerarquía de
   Ward sobre los centroides cortada por distancia (130 campos, 432 temas), nombres con c-TF-IDF y
   curaduría manual de los nombres de los campos. El 67 % de las tesis no cae en ningún subtema y
   no se fuerza su asignación.
6. **Proyección 2D** con PaCMAP, solo para dibujar.
7. **Vecindarios**: las 100 tesis más cercanas de cada una, con FAISS exacto, como herramienta de
   compilación (nunca como servicio).
8. **Artefactos**: binarios columnares para el mapa; para el servicio de datos, el modelo en ONNX,
   un índice FAISS IVF-SQ8 y metadatos (unos 3 GB, en un volumen de Modal).

## 6. Frontend

- **Sin compilación.** Cada página es un archivo autocontenido. Lo compartido vive en
  `compartido/` como scripts clásicos con un objeto global: sesión (Supabase y llamadas a la API),
  ajustes (modos día y noche), el léxico de Bloom (un módulo ES que usan **la página y el Worker**,
  para calcular igual el nivel de un objetivo), el enlace de apoyo y estilos.
- **Bibliotecas de terceros** servidas desde el propio sitio, con versión exacta (y SRI en
  `supabase-js`), para que la CSP limite los scripts al propio origen.
- **Mapa por capas:** puntos en WebGL; animaciones y marcas en Canvas 2D; nombres, nodos y retícula
  en SVG; minimapa en Canvas.
- **Datos del mapa en binario columnar:** arreglos tipados concatenados en un `.bin`, más un `.json`
  pequeño con tipo, desplazamiento y conteo. Todos siguen el mismo orden de filas, así que se
  cruzan sin uniones. **Carga progresiva:** al abrir, solo lo necesario para dibujar (unos 26 MB);
  temas, títulos (en teselas de 64 × 64), tesis por subtema e índice de búsqueda (por prefijo) se
  piden al usarse. Los nombres de archivo llevan versión.
- **Laboratorio:** formulario con validación y léxico de Bloom en vivo; el envío pide un token de
  Turnstile y abre una respuesta por *Server-Sent Events*: cada sección se pinta al llegar. Todo
  texto del usuario, del catálogo o del modelo se escapa al insertarse.
- **Almacenamiento en el navegador** (`localStorage`): solo preferencias, el borrador del
  formulario y la sesión. Lo guardado de cada cuenta vive en D1.
- **Sistema visual:** todo color sale de variables CSS; una sola tipografía; modo día
  predeterminado y modo noche.

## 7. Flujos clave

### 7.1 Abrir el mapa

El navegador descarga la página, los binarios y los nombres; dibuja; y pide lo demás según la
interacción. No hay servidor de aplicación en este flujo: solo archivos estáticos con caché.

### 7.2 Inicio de sesión

Supabase Auth con flujo PKCE (Google, GitHub o enlace por correo). El token JWT (ES256) se guarda en
el navegador y viaja en `Authorization: Bearer`. Sin cookies, así que no hay CSRF. El Worker
verifica cada token con WebCrypto contra el JWKS de Supabase (en caché 10 minutos), exige emisor,
audiencia, rol `authenticated` y vigencia, y rechaza usuarios anónimos.

### 7.3 Cadena de una petición en el Worker

Cada petición a `/api/*` pasa, en orden, por:

1. **Configuración segura:** en producción, si detecta algo de desarrollo (claves de prueba, URLs
   sin https, faltan límites), responde 503 a todo (falla cerrado).
2. **CORS** con orígenes explícitos.
3. **Límite por IP:** 120 peticiones por minuto a la API y 10 al análisis (IPv6 por su /64).
4. **Sesión** (§7.2) y límite de 30 escrituras por minuto por usuario.
5. **Entrada:** tope de tamaño (lectura por partes), validación de forma y **limpieza contra
   inyección de instrucciones** (*prompt injection*): normaliza, quita caracteres invisibles y
   delimitadores, y registra (sin el texto) los patrones sospechosos.
6. **Turnstile** con acción y dominio.
7. **Cuotas** con UPSERT atómicos en D1: del mes (ligada al crédito del servicio de datos), del
   sitio por día y del usuario (2 al día). Si algo falla antes de entregar datos, la cuota vuelve.

### 7.4 Análisis en vivo

1. El Worker pide a la Fila un lugar en el servicio de datos (2 a la vez, por los 2 núcleos).
2. Con lugar: llama al servicio de datos (Modal, con token de proxy y una clave compartida);
   suelta el lugar en cuanto responde.
3. Calcula el léxico de Bloom (sin IA) y lo manda por SSE junto con los datos.
4. Toma un lugar del **tope diario de análisis con IA** (55, la capacidad gratuita medida).
5. Lanza **tres llamadas al modelo en paralelo** (nota, preguntas y Bloom si hay objetivos). Cada
   una: reserva cupo del proveedor, llama, valida la salida contra un esquema JSON y reglas
   propias; si no cumple, **un reintento con los errores como retroalimentación**.
6. Guarda el análisis en D1 (si la cuenta tiene menos de 2) y manda `fin`.

### 7.5 Análisis en la fila

Sin lugar libre, el Worker responde 202 y guarda el análisis con estado `fila`. El Durable Object
lo corre en segundo plano con una alarma: pide los datos, los guarda y deja la IA pendiente para el
carril. Si el usuario lo borra antes de su turno, sale de la fila y la cuota vuelve. Un objeto que
se reinicia a mitad de un análisis lo devuelve al frente de la fila.

### 7.6 Carril de IA, reintentos y ciclo de vida del análisis

El carril, dentro del mismo Durable Object, completa **de uno en uno y espaciados (45 s)** los
análisis con la IA pendiente, del más antiguo al más nuevo, y solo las secciones que faltan.

- **Falta por cupo:** queda pendiente sin contar intento; si el cupo del día se acabó, el carril se
  pausa hasta la medianoche de la Ciudad de México.
- **Falta por fallo** (salida inválida tras el reintento, o error del proveedor): cuenta un
  intento, espera 6 horas y vuelve; tras 2 reintentos queda parcial, con el motivo guardado (solo
  la ruta del error, sin texto del usuario).
- Un cron diario despierta el carril por si su alarma se perdiera.

Estados de un análisis guardado: `en fila` → `pendiente` → `completo`; `pendiente` ↔ `reintento`
(espera de 6 h) → `parcial` (terminal, tras el tercer fallo). Un análisis en vivo entra directo a
`completo`, `pendiente` o `reintento`.

### 7.7 Borrar la cuenta

Borra los datos de D1 y, con la clave de servicio de Supabase (solo en el Worker), la identidad.

## 8. Subsistema de IA

- **Proveedores:** Groq primero; si su cupo se agota, si su límite por minuto exige una espera
  larga o si falla, Workers AI con el mismo modelo.
- **Topes diarios estrictos, para no salir nunca de las capas gratuitas:** análisis con IA (55),
  tokens de Groq (180,000) y neuronas de Workers AI (9,000 de 10,000 gratuitas). Desde la 1.0.4,
  cada llamada **reserva su peor caso** con una sola sentencia atómica en D1 antes de llamar (si no
  cabe, no se llama) y al final ajusta al costo real. Así, llamadas simultáneas no pueden rebasar
  el tope.
- **Validación:** esquema JSON por sección y reglas que el esquema no expresa (un verbo de una
  lista cerrada por objetivo revisado, tipos de pregunta distintos, etc.). El esquema que recibe el
  proveedor va sin topes de longitud; el Worker los aplica al validar.
- **Privacidad:** los logs llevan proveedor, tarea, tokens y rutas de error, nunca el texto. El
  texto del usuario viaja al modelo como dato delimitado.
- **Formalmente** es un flujo de trabajo con forma de grafo (paralelización y
  evaluador-optimizador con un evaluador determinista), no un agente: el modelo nunca decide el
  siguiente paso.

## 9. Datos persistentes

**D1** (migraciones 0001 a 0007):

| Tabla | Contenido |
|---|---|
| `analisis` | id, usuario (el `sub` del JWT), título, entrada (JSON), resultado (JSON: datos, IA y motivos de fallo), creado, `estado` (`listo` o `fila`), `ia_pendiente`, `ia_intentos`, `ia_siguiente`, `avisar` (0 no; 1 estuvo pendiente; 2 estimado), `avisado` |
| `tesis_guardadas`, `asesores_guardados`, `lugares_guardados` | Lo guardado en Mi espacio |
| `cuota_diaria` | Análisis por usuario y día |
| `cuota_sitio` | Contadores del sitio por día y tipo: datos, mes, ia, tokens de Groq, neuronas de Workers AI |

Toda consulta filtra por el usuario del token, nunca por un id que mande el cliente. Un cron
diario borra contadores viejos y mantiene activo el proyecto de Supabase (la capa gratuita lo pausa
tras 7 días sin actividad). El correo de cada usuario **no** está en D1: vive solo en Supabase.

**Durable Object «Fila»:** cola de turnos, lugares ocupados, análisis en curso y pausa del carril.

**Servicio de datos:** artefactos de solo lectura en un volumen; el servicio no guarda nada.

## 10. Decisiones de arquitectura registradas

- **ADR-0001 y ADR-0003 (reemplazadas):** almacenamiento de objetos y vecindario híbrido
  (precálculo más cálculo a demanda).
- **ADR-0002 (no implementada):** entorno de desarrollo con Docker Compose y proxy inverso.
- **ADR-0004:** el archivo maestro es la única fuente de verdad del corpus.
- **ADR-0005 a ADR-0010:** política de corrección de entidades (plantel, programa, grado,
  asesores): solo se fusiona lo verificado, con auditoría.
- **ADR-0011:** export público por lista blanca de columnas, sin autores.
- **ADR-0012:** redefinición de producto (exploración y Laboratorio).
- **ADR-0013:** agrupamiento al estilo BERTopic en lugar de FAISS más Leiden manual.
- **ADR-0014:** vecindario semántico 100 % precalculado; FAISS solo en compilación.
- **ADR-0015:** arquitectura de producción gratuita. En la práctica cambió de proveedor dos veces
  con solo configuración: el sitio pasó de Pages a Workers con archivos estáticos y el servicio de
  datos de Cloud Run a Modal (Google rechazó la cuenta de facturación). El servicio conserva un
  `Dockerfile` como plan B.

## 11. Operación, calidad y estado

- **CI** en cada push (GitHub Actions): privacidad (ningún título publicado con mención de autor),
  humo (cada página carga en Chrome sin errores de consola), léxico e inyección, y el Worker contra
  `wrangler dev` con un servicio de datos simulado (pruebas de acceso cruzado entre cuentas,
  estrés de 50 usuarios simultáneos y la fila).
- **Despliegue:** comandos de `wrangler` para el sitio, el Worker y las migraciones de D1; `modal
  deploy` para el servicio de datos. Versionado semántico visible en el pie del mapa; cada versión
  se registra con qué cambió, por qué y cómo se verificó.
- **Observabilidad:** logs del Worker (3 días en la capa gratuita), estadísticas de visitas sin
  cookies, analíticas de uso de la IA por API de Cloudflare, panel de Modal. No hay alertas
  automáticas.
- **Calidad del servicio de datos:** prueba de aceptación que exige 95 % de coincidencia del
  top-100 contra la búsqueda exacta (en uso: 99.1 % en promedio).
- **Seguridad:** CSP por página, HSTS y cabeceras afines; la API con `default-src 'none'`. Riesgos
  abiertos conocidos: cuentas creadas en masa, la sesión en `localStorage` con `'unsafe-inline'` en
  la CSP (por el código en línea de las páginas), tokens válidos hasta su caducidad (1 hora).
- **Capacidad:** 2 análisis simultáneos en el servicio de datos (arranque en frío de 12 a 16 s);
  ~1 análisis con IA por minuto en la capa gratuita de Groq; 55 análisis con IA al día; en la
  primera semana hubo un rezago de unos 200 análisis esperando su lectura con IA.
- **Siguiente función (en diseño): avisos por correo.** Cuando el carril completa un análisis que
  esperó, avisar al usuario por correo. Ya existe el registro (`avisar`, `avisado`); falta elegir
  proveedor de envío con capa gratuita, autenticar el dominio, la baja de un clic y la preferencia
  de cada usuario, y actualizar el aviso de privacidad (hoy declara solo las finalidades
  necesarias del servicio y a Supabase, Cloudflare, Groq, Modal y Stripe como encargados).

## 12. Glosario

- **Worker:** función de Cloudflare que corre en el borde de la red, cerca del usuario.
- **Durable Object:** objeto con estado y almacenamiento propio, único en todo el sistema, que
  coordina accesos concurrentes; aquí, la fila.
- **D1:** base de datos SQLite gestionada por Cloudflare.
- **SSE (Server-Sent Events):** respuesta HTTP que el servidor va escribiendo por partes; el
  navegador las recibe a medida que llegan.
- **JWT / JWKS:** token firmado que prueba la sesión / conjunto de claves públicas con que se
  verifica.
- **PKCE:** variante segura del flujo OAuth para aplicaciones en el navegador.
- **Turnstile:** verificación de Cloudflare contra accesos automatizados.
- **Embedding:** vector que representa el significado de un texto.
- **FAISS:** biblioteca de búsqueda de vectores parecidos.
- **Carril de IA:** proceso en segundo plano que completa, a su ritmo, las lecturas con IA
  pendientes.
- **Taxonomía de Bloom:** clasificación de objetivos de aprendizaje por nivel cognitivo
  (Recordar, Comprender, Aplicar, Analizar, Evaluar, Crear).

---

# PARTE C. Quién pregunta y para qué

**Lo que se sabe por el proyecto:**

- Desarrollador independiente; construyó y opera NodOS solo, en producción desde el 29 de
  septiembre de 2026, con un asistente de programación (Claude Code) como apoyo diario.
- Aprende infraestructura e IA en la práctica: conceptos como Docker, contenedores, Workers, grafos
  y agentes los está aprendiendo mientras los usa. Prefiere explicaciones sencillas con ejemplos de
  su propio proyecto antes que la jerga.
- Trabaja con disciplina de registro: bitácora por versión (qué cambió, por qué, cómo se verificó),
  ADR, CI y revisión visual. Cuida la privacidad y el costo cero.
- Quiere mantener a un humano en el ciclo: ver los datos crudos, no solo interpretaciones.

**Completa antes de pegar** (borra lo que no aplique):

- Formación y experiencia previa en programación: …
- Horas por semana para estudiar: …
- Objetivo profesional (empleo, posgrado, emprender, investigación): …
- Lenguajes y herramientas que ya dominas: …
- Lo que más te cuesta hoy: …
