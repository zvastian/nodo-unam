# Arquitectura de NodOS

Documento de arquitectura del proyecto NodOS, un mapa semántico navegable de las tesis de la
UNAM. Describe los componentes del sistema, cómo se relacionan y las razones de las decisiones
principales. Los detalles de cada decisión están en los ADR (`adr/`) y en los RFC (`rfc/`). La
historia de cómo se llegó a cada una está en `development.md`.

Estado de referencia: septiembre de 2026. Atlas v4.22 y servicio de datos del Laboratorio,
paso 1 de ADR-0015.

---

## 1. Propósito y alcance

NodOS representa 609,154 tesis de la UNAM como un espacio continuo, en el que la cercanía
equivale a parecido temático. El producto tiene dos partes:

- **Atlas (Explorar).** Mapa interactivo del corpus completo, organizado en tres niveles:
  campo, tema y subtema. Tiene fichas de tesis, de agrupaciones y de asesores, búsqueda y un
  modo de análisis por tema.
- **Laboratorio.** Recibe la descripción de una tesis en proceso (título, problematización,
  palabras clave) y devuelve su contexto en el corpus: dónde cae en el mapa, cuántas tesis
  parecidas hay, qué asesores han dirigido trabajos cercanos y cuáles son las 100 tesis más
  parecidas. Después se añade una lectura generada por un modelo de lenguaje.

Este documento cubre la arquitectura de ambas partes, del dato crudo al navegador.

## 2. Requisitos que guían la arquitectura

Las decisiones de las secciones siguientes responden a estos requisitos, en orden de peso:

1. **Costo de operación cero.** Es un proyecto independiente y sin financiamiento. Cada
   componente de producción tiene que caber en una capa gratuita y poder mudarse de proveedor
   cambiando solo configuración (ADR-0015).
2. **Privacidad.** Los nombres de los autores (estudiantes) no se muestran ni se publican; los
   de los asesores sí. El texto que un usuario escribe en el Laboratorio no queda en los logs.
3. **El corpus cambia poco.** Se actualiza, a lo sumo, una vez al año. Por eso conviene
   calcular todo lo posible de antemano y servirlo como archivos estáticos.
4. **Consistencia del espacio semántico.** Todo lo que se compara con el corpus (una consulta
   del Laboratorio, un premio Nobel) tiene que representarse con el mismo modelo y el mismo
   preprocesamiento con que se representó el corpus.
5. **Un solo desarrollador.** Sin paso de build en el frontend, pocas piezas desplegables y
   ningún servidor propio que mantener.

## 3. Vista general

El sistema se divide en dos planos. El **plano offline** produce artefactos a partir de los
datos. El **plano en línea** los sirve y atiende las peticiones.

```
                PLANO OFFLINE (local y Kaggle)                     PLANO EN LÍNEA
 ┌───────────────────────────────────────────────────┐
 │ TESIUNAM (Aleph, Koha/MARC)                        │
 │   └─► adquisición y limpieza ─► corpus canónico    │
 │         └─► embeddings e5-large (1024 d)           │
 │               ├─► UMAP ─► HDBSCAN ─► Ward ─► jerarquía, c-TF-IDF
 │               ├─► PaCMAP ─► coordenadas 2D          │
 │               └─► FAISS ─► vecindarios top-100      │
 │                                                    │
 │   generar_atlas_*.py ──────────────────────────────┼──► datos estáticos ──► Atlas (navegador)
 │   services/lab/construir.py ───────────────────────┼──► modelo ONNX, índice ──► Servicio del Lab
 └───────────────────────────────────────────────────┘                          (contenedor)
```

Lo que el atlas muestra está calculado de antemano. El único cómputo por petición es el del
Laboratorio, porque su entrada es un texto que no existe en el corpus (ADR-0014).

## 4. Capa de datos

### 4.1 Adquisición

El corpus viene del catálogo público TESIUNAM. La extracción principal se hizo sobre las
fichas de detalle del sistema Aleph. En nueve años, esa extracción había perdido una parte
importante de los registros. Esos años se recuperaron desde la vista MARC del sistema Koha
(`tesiunam_marc_downloader.py`, `normalizar_marc_recovered.py`).

La integración **reemplaza años completos** en lugar de añadir los registros faltantes. Así se
evita tener que deduplicar sin un identificador común entre los dos sistemas.

### 4.2 Corpus canónico y linaje

- **Maestro interno.** `data/clean/base7_kaggle_clean.parquet` (609,156 registros, 1873 a 2026)
  es la única fuente de verdad (ADR-0004). Todo artefacto posterior se deriva de él. Contiene
  nombres de autores, así que no se versiona ni se publica.
- **Export público.** `data/public/data_unam.parquet` lo genera `generar_data_unam.py` con un
  mapeo explícito columna por columna (ADR-0011). Una columna nueva del maestro no llega al
  export por accidente: hay que declararla. El export no tiene autores ni campos internos de
  linaje.

Las correcciones de entidades (plantel, programa, grado, asesores) siguen una política común
(ADR-0005 a 0010):

- solo se fusiona lo verificado;
- hay que distinguir el campo técnico del de presentación;
- cada cambio queda en un CSV de auditoría, con un respaldo del archivo anterior.

Los asesores se unifican con `unificar_asesores.py`, que reúne en un solo identificador las
variantes de escritura de una misma persona.

### 4.3 Privacidad en los datos

El título del catálogo suele incluir la mención de responsabilidad («tesis que para obtener el
título de …, presenta NOMBRE»). `titulo_sin_autor.py` corta el título en esa mención y omite lo
que aún parezca un nombre. Ningún artefacto publicado se genera sin pasar por ese corte. Antes
de versionar datos regenerados, `limpiar_autores_atlas.py` hace una limpieza final.

## 5. Pipeline semántico

El pipeline es un conjunto de scripts de Python en `pipeline/`, sin orquestador. Cada script
lee y escribe parquet o NumPy y lo configuran variables de entorno. Esto corresponde a una
madurez de MLOps de nivel 0 a 1, elegida a propósito: el corpus casi no cambia y una
orquestación formal costaría más de lo que aportaría.

### 5.1 Representación

- **Modelo.** Cada tesis se representa con `intfloat/multilingual-e5-large` (1024 dimensiones,
  normalizado a norma 1), aplicado al texto `"query: " + título normalizado`
  (`generar_embeddings_full_e5.py`). Esto corrió en Kaggle con GPU.
- **Solo el título.** El texto embebido no incluye programa, área ni plantel. Si los incluyera,
  el espacio se ordenaría por categoría administrativa, que ya existe como filtro explícito.
  Eso borraría las cercanías entre disciplinas, que son justo el hallazgo que el mapa busca
  mostrar.

### 5.2 Agrupamiento

El agrupamiento sigue el esquema de BERTopic (ADR-0013):

1. **Reducción con UMAP** a 5 dimensiones, con métrica coseno y `min_dist = 0`. HDBSCAN agrupa
   por densidad local, que UMAP conserva y PCA no.
2. **HDBSCAN** con selección `leaf` y `min_cluster_size = 150` (`clustering_hdbscan.py`). Da
   513 subtemas, de 150 a 2,475 tesis cada uno.
3. **Tesis sin subtema.** El 67.2 % de las tesis no queda en ningún subtema porque no está en
   una zona densa del espacio. No se fuerza su asignación. El mapa las muestra como dispersión
   entre las zonas agrupadas, y esa dispersión es información: dice qué tan concentrada o
   difusa está la producción de tesis en cada zona.

### 5.3 Jerarquía

`construir_jerarquia_macro_meso.py` aplica un agrupamiento jerárquico de Ward sobre los
centroides de los 513 subtemas, en el espacio original de 1024 dimensiones:

- El árbol se corta por **distancia de fusión** (0.40), no por número de grupos. Así, el número
  de campos lo decide la coherencia temática y no un parámetro fijado de antemano.
- Resultado: **130 campos** (nivel macro), **432 temas** (meso) y **513 subtemas** (micro).
- Los nombres visibles de los campos vienen de una curaduría manual
  (`pipeline/curaduria/macro_nombres.v1.json`). Cada nombre lleva una **huella**: la primera
  palabra clave del campo. Si la jerarquía se recalcula y la huella ya no coincide, el frontend
  usa el nombre automático en lugar de mostrar uno equivocado.

### 5.4 Etiquetado

`generar_topicos_ctfidf.py` nombra automáticamente cada grupo con c-TF-IDF. Cada grupo se trata
como un solo documento, formado por sus títulos. Los términos que distinguen a un grupo son los
frecuentes en él y raros en el resto. Se excluyen las palabras vacías del español y el
vocabulario académico genérico («tesis», «estudio», «análisis»…).

### 5.5 Proyección 2D

`generar_layout_pacmap.py` proyecta el corpus a dos dimensiones con PaCMAP. Se prefirió a UMAP
para esta tarea porque, además de los vecinos cercanos, modela pares a distancia intermedia.
Con eso conserva mejor la posición relativa entre campos lejanos, que es lo que el usuario lee
en un mapa. La proyección 2D solo sirve para dibujar: el agrupamiento se hace aparte, sobre
UMAP de 5 dimensiones.

### 5.6 Vecindarios

`generar_vecindario_knn.py` calcula las 100 tesis más cercanas de cada una de las 609,154.
Usa FAISS `IndexFlatIP`, una búsqueda exacta por producto interno, que con vectores
normalizados es la similitud coseno. FAISS se usa aquí como herramienta de build y nunca como
servicio (ADR-0014). La tabla completa ocupa del orden de cientos de MB. El atlas publica por
ahora una muestra de 2,500 tesis con 50 vecinas cada una.

### 5.7 Entornos de ejecución

- **Kaggle, con GPU.** Los pasos que operan sobre la matriz de 609,154 × 1024 (embeddings,
  UMAP, HDBSCAN): no caben con holgura en los 16 GB de la máquina local.
- **Local.** Los pasos sobre texto y metadatos (c-TF-IDF, jerarquía, generación de artefactos).

Los scripts largos guardan los resultados intermedios en disco apenas terminan las etapas
caras, para poder reanudar sin repetirlas.

## 6. Frontend

### 6.1 Atlas: organización

El atlas es un solo archivo, `prototypes/atlas_vecindario_mvp/index.html`, con HTML, CSS y
JavaScript. No tiene paso de build ni framework. La decisión cambia modularidad por dos
ventajas: el sitio se despliega copiando archivos y cualquier cambio se prueba recargando la
página.

Dentro del archivo, el código se divide en secciones con encabezados. Las principales son:

- carga;
- cámara;
- niveles de revelado;
- capa de nombres;
- fichas;
- modo taller;
- asesores;
- buscador;
- introducción;
- página de método.

Un objeto `state` concentra el estado de la aplicación. `window.__debugAtlas` lo expone para
las pruebas automatizadas.

Las bibliotecas se cargan al vuelo desde jsDelivr:

- `regl` y `regl-scatterplot`, para dibujar los puntos con WebGL;
- `d3`, para contornos de densidad, escalas y la simulación de fuerzas de la red de asesores;
- `pub-sub-es`, dependencia de `regl-scatterplot`.

### 6.2 Atlas: capas de dibujo

El mapa superpone capas con responsabilidades separadas:

| Capa | Tecnología | Contenido |
|---|---|---|
| Puntos | WebGL (`regl-scatterplot`) | Las 609,154 tesis, coloreadas por área o por agrupación |
| Animación | Canvas 2D (`#flow`) | Enlaces y deriva en el modo aislado de un subtema |
| Marcas | Canvas 2D (`#marks`) | Tesis elegidas, dibujadas encima del mapa |
| Nombres y nodos | SVG (`#overlay`) | Rótulos de campos, temas y subtemas, nodos y retícula |
| Minimapa y localizadores | Canvas 2D | Vista general y ubicación de la selección en las fichas |

WebGL se reserva para lo que tiene volumen, que son los puntos. Los nombres van en SVG, donde
el texto se dibuja nítido y se puede seleccionar.

### 6.3 Atlas: formatos de datos y carga

Los datos del atlas (`data/`, unos 160 MB en 3,231 archivos) se sirven como archivos
estáticos. Siguen dos principios.

**1. Datos masivos en binario columnar.** Todo lo que tiene un valor por tesis viaja como
arreglos tipados concatenados en un `.bin`. Lo acompaña un `.json` pequeño que declara el tipo,
el desplazamiento y el conteo de cada campo. El navegador crea vistas
`new Float32Array(buffer, offset, count)` sin copiar ni interpretar texto. Todos los binarios
siguen el mismo orden de filas, que es el índice de la tesis en el mapa, así que se cruzan sin
tablas de unión.

- `atlas_chaos_mode.v1.bin`: coordenadas, campo y área.
- `tesis_meta.v1.bin`: nivel, programa y plantel.
- `tesis_anio.v1.bin`: año.
- `tesis_catalogo.v1.bin`: número de registro en TESIUNAM.
- `asesores_por_tesis.v1.bin`: relación entre tesis y asesores, en formato CSR (desplazamientos
  e identificadores).

**2. Carga progresiva.** Al abrir solo se descarga lo necesario para dibujar el mapa. Lo demás
se pide al usarse y se guarda en memoria:

| Qué | Cuándo se pide | Partición |
|---|---|---|
| Grafo de campos, puntos, nombres curados | Al abrir | Único |
| Temas y subtemas de un campo | Al acercarse a ese campo | Un archivo por campo (`meso_by_macro/`, `micro_by_macro/`) |
| Títulos para el texto flotante (tooltip) | Al pasar el cursor | Rejilla espacial de 64 × 64 teselas (`titulos_teselas/`) |
| Tesis de un subtema | Al abrir ese subtema | Un archivo por subtema (`tesis_por_micro/`) |
| Índice de búsqueda | Al escribir | Fragmentos por prefijo (`busqueda/titulos/`) |
| Metadatos, asesores y catálogo | Con la primera ficha | Archivos únicos |

Los nombres de archivo llevan versión (`.v1`). Con eso, una regeneración del pipeline puede
publicarse junto a la anterior y el cambio se hace en un solo paso.

### 6.4 Sistema visual

Todo color de interfaz sale de variables CSS (tokens: `--paper`, `--ink`…). El modo día es el
predeterminado y el modo noche redefine los mismos tokens. En el mapa, el color solo codifica
datos (área, agrupación, nivel), no decora. La tipografía es únicamente Libre Franklin. Las
reglas de diseño y los 25 anti-patrones vetados están en `PRODUCT.md`.

El navegador guarda en `localStorage` solo preferencias de quien mira (modo noche, minimapa,
introducción vista). La aplicación funciona igual si ese almacenamiento no está disponible.

### 6.5 Laboratorio: interfaz

La interfaz del Laboratorio (`laboratorio.html`) es hoy la plantilla del análisis ya
terminado. Pide la parte de datos al servicio del Laboratorio: `127.0.0.1:8770` en local, o
la URL que indique el parámetro `?api=`. Si el servicio no responde, pinta un resultado de
ejemplo y lo avisa en la consola. Todo texto que viene del usuario o del modelo se escapa antes
de insertarse en la página (`esc()`). Faltan el formulario de entrada, los estados de error y
la integración con el atlas.

## 7. Backend: servicio de datos del Laboratorio

### 7.1 Responsabilidad y contrato

`services/lab/` es un servicio FastAPI **sin estado y sin IA**. Recibe el texto de una tesis y
devuelve su contexto en el corpus, con el mismo formato que el script offline
`pipeline/lab_contexto.py` del que está portado.

- `GET /salud`: disponibilidad y tiempo de arranque.
- `POST /v1/contexto`: recibe título (3 a 400 caracteres), problematización (hasta 2,000),
  palabras clave (hasta 12) y datos académicos opcionales. Devuelve la ubicación, la
  saturación, las tesis cercanas, los asesores, las 100 vecinas y los tiempos por etapa.
  Pydantic valida la entrada y rechaza la inválida con 422.

El servicio no conoce usuarios, sesiones ni cuotas: de eso se encarga la puerta que lo precede
(§8). Tampoco escribe el texto recibido en los logs, solo tiempos y tamaños.

### 7.2 Diseño interno

Cada petición pasa por tres etapas:

1. **Embedding** (`embeber.py`). e5-large exportado a ONNX y ejecutado con ONNX Runtime, sin
   PyTorch. Reproduce el preprocesamiento del corpus: el prefijo `query:`, la misma
   normalización del texto, truncado a 512 tokens, promedio con máscara y norma 1.
2. **Búsqueda.** Índice FAISS IVF-SQ8 con 4,096 listas y cuantización escalar de 8 bits. Cada
   búsqueda recorre 768 listas (`nprobe`).
3. **Contexto** (`contexto.py`):
   - las 50 vecinas más cercanas votan la ubicación, con peso igual al cuadrado de su
     similitud;
   - la saturación se mide con umbrales de similitud;
   - los asesores y la distribución por décadas se leen de estadísticas precalculadas.

Los artefactos se cargan una sola vez al arrancar y quedan en memoria, en el objeto `Datos` y
en la sesión de ONNX. Después, cada petición es de solo lectura.

### 7.3 Separación entre build y ejecución

`construir.py` genera los artefactos del servicio (unos 3 GB, fuera de git):

- el modelo ONNX;
- el índice;
- `meta.parquet`, alineado con el índice y sin autores;
- `precalculo.json`.

Corre con el entorno de Python del pipeline, que incluye PyTorch y transformers. El servicio
tiene un entorno propio y mínimo: FastAPI, ONNX Runtime, FAISS, tokenizers y pandas. La imagen
queda pequeña y sin dependencias de entrenamiento.

### 7.4 Calidad del resultado

La configuración se eligió con una prueba de aceptación (`evaluar.py`). Compara el top-100 del
servicio con una referencia: el modelo original en float32 con búsqueda exacta. Usa ocho tesis
de campos distintos y exige al menos 95 % de coincidencia en promedio y en cada caso.

| Configuración | Coincidencia del top-100 (promedio / peor caso) | Tiempo |
|---|---|---|
| ONNX float32, búsqueda exacta | 100 % / 100 % | 260 ms |
| ONNX int8 dinámico, búsqueda exacta | 84.1 % / 72 % | 130 ms |
| **ONNX float32 + IVF-SQ8, nprobe 768 (en uso)** | **99.1 % / 98 %** | ~300 a 400 ms por petición |

La cuantización del modelo se descartó aunque reducía memoria y latencia. Mueve la consulta
fuera del espacio en que se embebió el corpus, lo que viola el requisito 4 (§2).

### 7.5 Contenerización

El `Dockerfile` parte de `python:3.12-slim`, instala solo las dependencias de ejecución y copia
el código. El proceso corre con un usuario sin privilegios. Los artefactos **no van en la
imagen**:

- en desarrollo se montan en `/artefactos`, en solo lectura;
- en producción se descargarán desde almacenamiento de objetos al arrancar.

La imagen mide unos 200 MB comprimida y se puede reconstruir sin mover los 3 GB de datos. El
puerto sale de la variable `PORT`, como espera Cloud Run.

Medido en un contenedor local, con el motor de Docker 29.8:

- respuestas idénticas a las del servicio fuera del contenedor;
- mediana de unos 300 ms por petición;
- unos 3 GiB de memoria residente.

## 8. Arquitectura de producción

Decidida en ADR-0015; en construcción. El paso 1, el servicio de datos, está completo en local.

```
Navegador
 ├── Sitio estático (atlas + interfaz del Lab) ──── Cloudflare Pages
 └── /api/* ── Worker «puerta» ──────────────────── Cloudflare Workers
                ├── Turnstile, CORS explícito, tope de tamaño
                ├── sesión: JWT verificado con JWKS ── Supabase Auth
                ├── cuotas, análisis y tesis guardadas ── Cloudflare D1
                ├── datos ──► servicio del Lab ──────── Google Cloud Run (8 GiB)
                └── IA ────► gpt-oss-120b ──────────── Groq + Workers AI
```

- **Sitio estático.** Atlas e interfaz del Laboratorio en Cloudflare Pages. Los datos caben
  dentro de sus límites por número y tamaño de archivos. R2 queda como opción para un archivo
  que pase de 25 MiB.
- **Worker puerta.** Es el único punto de entrada a lo dinámico:
  - verifica la sesión (JWT de Supabase, validado contra su JWKS);
  - aplica el desafío anti-bots (Turnstile), CORS con orígenes explícitos y un tope al tamaño
    de la entrada;
  - lleva las cuotas en D1;
  - llama al servicio de datos y a los proveedores de IA.

  Ningún servicio interno queda expuesto directamente al navegador.
- **Identidad y datos de usuario.** Supabase se usa solo para la identidad (Google y enlace
  mágico). Los datos del usuario (análisis y tesis guardadas) viven en D1, junto a la puerta.
- **Servicio de datos.** El contenedor de §7 en Cloud Run, con instancia de 8 GiB, un número
  máximo de instancias bajo y una alerta de presupuesto. AWS Lambda con el mismo contenedor es
  el plan B.
- **IA.** El mismo modelo (`gpt-oss-120b`), con los mismos prompts y esquemas de salida, en dos
  proveedores. La puerta usa Groq primero y pasa a Workers AI cuando Groq agota su cupo o
  responde 429. Así, un análisis no cambia según el proveedor que contestó. Si ambos se agotan,
  se entrega la parte de datos y se indica que la de IA no está disponible ese día.
- **Portabilidad.** Cada pieza depende de una interfaz estándar: HTTP, JWT o un contenedor
  OCI. Mudarla es cambiar configuración. Esto responde a que varias capas gratuitas cambiaron
  sin aviso durante 2026.

Orden de construcción: (1) servicio de datos; (2) puerta, autenticación y D1; (3) IA con
respuesta por streaming (SSE); (4) despliegue con integración continua.

## 9. Seguridad y privacidad

- **Datos personales.** Los autores quedan fuera de todo artefacto publicado (§4.3). El export
  público se construye por lista blanca de columnas.
- **Separación de responsabilidades.** La autenticación, las cuotas y la protección contra
  abuso se concentran en la puerta. Los servicios internos confían en ella y no manejan
  identidad.
- **Entradas.** Se validan por esquema y tamaño en la puerta y otra vez en el servicio. El
  texto del usuario viaja al modelo de lenguaje como dato delimitado. La salida del modelo se
  valida contra un esquema y se escapa al pintarse.
- **Registros.** Ningún componente escribe en los logs el texto de una tesis del usuario.
- **Secretos.** Se leen de variables de entorno o del gestor de secretos de cada plataforma.
  Ninguno se versiona.
- **Pendiente para producción:**
  - cabeceras del sitio (CSP, HSTS y afines);
  - versiones exactas con SRI para las bibliotecas de CDN;
  - aviso de privacidad y borrado real de cuentas;
  - pruebas de acceso cruzado entre usuarios.

## 10. Verificación y gestión del cambio

- **Interfaz.** `tools/cdp.mjs` controla Chrome sin ventana (headless) con el protocolo
  DevTools: ejecuta pasos declarados en JSON, toma capturas en escritorio y móvil y vuelca la
  consola. Con él se verifica cada versión del atlas.
- **Backend.** `evaluar.py` es la prueba de aceptación de calidad semántica (§7.4). Las pruebas
  de contrato (422, CORS, paridad dentro y fuera del contenedor) se corren contra el servicio en
  ejecución.
- **Versiones.** El atlas sigue versionado semántico (se muestra en el pie). Cada versión queda
  registrada en `development.md` con qué cambió, por qué y cómo se verificó.
- **Decisiones.** Las decisiones de arquitectura se registran como ADR, que no se editan
  después de aceptarse: un ADR nuevo reemplaza al anterior y lo cita. Las propuestas que
  requieren investigación pasan primero por un RFC.
- **Pendiente:** integración continua con una prueba de privacidad (que falle si un título
  publicado menciona a un autor) y pruebas de extremo a extremo automáticas.

## 11. Limitaciones conocidas

- Solo un tercio del corpus tiene subtema (§5.2). La ubicación que calcula el Laboratorio
  todavía vota solo con las tesis agrupadas.
- El atlas publica una muestra de los vecindarios, no la tabla completa (§5.6).
- El frontend en un solo archivo, sin módulos, facilita el despliegue pero dificulta la
  cobertura de pruebas unitarias.
- El arranque en frío del servicio del Laboratorio en Cloud Run dependerá de descargar unos
  3 GB de artefactos. Falta medirlo.
- Los umbrales de similitud del Laboratorio son orientativos hasta calibrarlos con un conjunto
  de evaluación más amplio.

## Apéndice: mapa del repositorio

| Ruta | Contenido |
|---|---|
| `prototypes/atlas_vecindario_mvp/` | Atlas (`index.html`), sus datos (`data/`) y la interfaz del Laboratorio (`laboratorio.html`, con sus ejemplos en `lab/`) |
| `services/lab/` | Servicio de datos del Laboratorio, su `Dockerfile`, la construcción de artefactos y la prueba de aceptación |
| `pipeline/` | Adquisición, limpieza, pipeline semántico y generación de artefactos |
| `tools/` | Herramienta de verificación visual (`cdp.mjs`) |
| `adr/`, `rfc/` | Decisiones de arquitectura y propuestas |
| `marca/` | Logo y favicon de NodOS |
| `PRODUCT.md` | Usuarios, propósito y reglas de diseño |
| `development.md` | Bitácora del proyecto y hoja de ruta |
| `app/` | Código de la versión anterior del producto, conservado como referencia |
