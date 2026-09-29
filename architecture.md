# Arquitectura de NodOS

Documento de arquitectura del proyecto NodOS, un mapa semántico navegable de las tesis de la
UNAM. Describe los componentes del sistema, cómo se relacionan y las razones de las decisiones
principales. Los detalles de cada decisión están en los ADR (`adr/`) y en los RFC (`rfc/`). La
historia de cómo se llegó a cada una está en `development.md`.

Estado de referencia: 29 de septiembre de 2026, v4.38.0. El mapa está publicado como copia de
prueba (sin dominio); el Laboratorio funciona de punta a punta en local, con su API blindada y su
fila, y le falta el despliegue (staging). La tabla de §8.1 dice qué está publicado, qué corre
solo en local y qué falta.

---

## 1. Propósito y alcance

NodOS representa 609,154 tesis de la UNAM como un espacio continuo, en el que la cercanía
equivale a parecido temático. El producto tiene dos partes:

- **Atlas (Explorar).** Mapa interactivo del corpus completo, organizado en tres niveles:
  campo, tema y subtema. Tiene fichas de tesis, de agrupaciones y de asesores, búsqueda y un
  modo de análisis por tema.
- **Laboratorio.** Recibe la descripción de una tesis en proceso (título, problematización,
  objetivos, palabras clave, programa y grado) y devuelve su contexto en el corpus: dónde cae en
  el mapa, cuántas tesis parecidas hay, qué asesores han dirigido trabajos cercanos y cuáles son
  las 100 tesis más parecidas. Encima van tres lecturas de un modelo de lenguaje: una nota del
  planteamiento, la revisión de los objetivos con la taxonomía de Bloom y preguntas de
  investigación. Pide cuenta; cada cuenta hace 2 análisis al día y guarda hasta 2.
- **Mi espacio.** Lo que cada usuario guarda: sus análisis, tesis, asesores y lugares del mapa
  (campos, temas y subtemas).

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
 │   generar_atlas_*.py ──────────────────────────────┼──► datos estáticos ──► sitio (navegador)
 │   services/lab/construir.py ───────────────────────┼──► modelo ONNX, índice ──► servicio de datos
 │   generar_data_unam.py ────────────────────────────┼──► dataset público (Kaggle, CC BY 4.0)
 └───────────────────────────────────────────────────┘
```

Lo que el mapa muestra está calculado de antemano. El único cómputo por petición es el del
Laboratorio, porque su entrada es un texto que no existe en el corpus (ADR-0014). Entre el
navegador y ese cómputo hay una sola puerta, el Worker `puerta` (§8), que pone la sesión, los
topes, la fila y las llamadas a la IA.

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
  linaje. Está publicado en Kaggle (`sebastiandiazprado/nodos-map`, CC BY 4.0, con un cuaderno
  de ejemplo).

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

### 6.1 Páginas y piezas compartidas

El sitio son seis páginas HTML, cada una en un solo archivo con su HTML, CSS y JavaScript, sin
paso de build ni framework. La decisión cambia modularidad por dos ventajas: el sitio se
despliega copiando archivos y cualquier cambio se prueba recargando la página. Comparten una
navegación (Mapa, Laboratorio, Acerca de; Ajustes, Entrar y Mi espacio) y un pie.

| Página | Qué es |
|---|---|
| `index.html` | El mapa |
| `laboratorio.html` | El Laboratorio: formulario, análisis y ejemplos (`lab/`) |
| `espacio.html` | Mi espacio: lo guardado de cada cuenta, y borrar la cuenta |
| `acerca.html` | Cómo se hizo el mapa y el Laboratorio (antes, la página de método) |
| `privacidad.html`, `contacto.html` | Aviso de privacidad y contacto |

Lo que usan varias páginas vive en `compartido/`, como scripts clásicos que dejan un objeto
global:

- `sesion.js` (`window.NodOS`): la sesión con Supabase Auth, la pantalla de acceso, la barra
  (Entrar, la inicial con su menú, Mi espacio), las llamadas a la API con el token, lo guardado
  (incluido `guardarTesisLote`, que guarda en bloques de 100) y las confirmaciones antes de
  borrar;
- `ajustes.js` y `ajustes.css`: el panel de Ajustes, con los modos día y noche;
- `bloom.js`: el léxico de la taxonomía de Bloom. Es un módulo ES que usan **el formulario y el
  Worker** (§8.3), así que el nivel de un objetivo se calcula igual en los dos lados;
- `apoyo.js`: el enlace de «Apoya este proyecto» (Stripe), en un solo lugar;
- `cuenta.css`: estilos de la pantalla de acceso y de Mi espacio.

Las bibliotecas de terceros se sirven desde el propio sitio, con versión exacta, en `vendor/`:

- `regl` y `regl-scatterplot`, para dibujar los puntos con WebGL;
- `d3`, para contornos de densidad, escalas y la red de asesores;
- `pub-sub-es`, dependencia de `regl-scatterplot`;
- `supabase-js`, con SRI.

Así la CSP puede limitar los scripts al propio origen (§9).

### 6.2 Mapa: organización

Dentro de `index.html`, el código se divide en secciones con encabezados. Las principales son:

- carga;
- cámara;
- niveles de revelado;
- capa de nombres;
- fichas;
- modo taller;
- asesores;
- buscador;
- lo guardado junto al buscador.

La introducción animada se quitó en la v4.35. Un objeto `state` concentra el estado de la
aplicación, y `window.__debugAtlas` lo expone para las pruebas automatizadas.

`?tesis=`, `?lugar=` y `?asesor=` abren el mapa directo en una tesis, un campo, tema o subtema,
o un asesor. Solo buscan valores que ya existen en los datos.

### 6.3 Mapa: capas de dibujo

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

### 6.4 Mapa: formatos de datos y carga

Los datos del mapa (`data/`, unos 160 MB en unos 3,200 archivos) se sirven como archivos
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

### 6.5 Sistema visual

Todo color de interfaz sale de variables CSS (tokens: `--paper`, `--ink`…). El modo día es el
predeterminado y el modo noche redefine los mismos tokens en todas las páginas. En el mapa, el
color solo codifica datos (área, agrupación, nivel), no decora. La tipografía es únicamente
Libre Franklin. Las reglas de diseño y los 25 anti-patrones vetados están en `PRODUCT.md`.

El navegador guarda en `localStorage` solo lo de quien mira: el modo noche, el minimapa, el
borrador del Laboratorio y la sesión de Supabase. Lo guardado de cada cuenta vive en el servidor
(D1), no en el navegador. Las páginas funcionan igual si ese almacenamiento no está disponible.

### 6.6 Laboratorio: interfaz

`laboratorio.html` tiene cuatro estados: la portada con cuatro análisis de ejemplo, el
formulario, el análisis que se despliega y los avisos.

- **Formulario.** Título, problematización, objetivos con el léxico de Bloom en vivo, palabras
  clave, programa, grado y periodo, con validación debajo de cada campo. El borrador se guarda
  en el navegador.
- **Sin cuenta**, la invitación a entrar ocupa el lugar del botón. Al volver de entrar, el
  análisis arranca solo.
- **Envío.** Primero pide un token a Turnstile (§9). Es invisible, salvo que Cloudflare pida
  una prueba; entonces aparece junto al botón. Después hace `POST /api/lab/analisis` y lee la
  respuesta por SSE: cada sección se pinta al llegar (léxico, datos, nota, Bloom, preguntas).
- **Guardado.** Al terminar, el análisis se guarda solo en Mi espacio (hasta 2).
- **Avisos.** Usan un mismo componente, con ilustración e invitación a apoyar el proyecto:
  - el análisis entró a la fila y aparecerá en Mi espacio;
  - ya hiciste tus 2 análisis de hoy;
  - ya tienes 2 análisis guardados;
  - se llegó al límite del día o del mes;
  - el servicio no respondió.
- **Escape.** Todo texto que viene del usuario, del catálogo o del modelo se escapa antes de
  insertarse (`esc()`, que también escapa comillas porque se usa dentro de atributos).
- **Parámetros de desarrollo.** `?api=`, `?sesion=local` y `?puerta=` solo se leen en local.
  Publicados, un enlace con ellos podría mandar el borrador o el token a otro sitio.

## 7. Backend: servicio de datos del Laboratorio

### 7.1 Responsabilidad y contrato

`services/lab/` es un servicio FastAPI **sin estado y sin IA**. Recibe el texto de una tesis y
devuelve su contexto en el corpus, con el mismo formato que el script offline
`pipeline/lab_contexto.py` del que está portado.

- `GET /salud`: disponibilidad y tiempo de arranque.
- `POST /v1/contexto`: recibe título (3 a 400 caracteres), problematización (hasta 2,000),
  palabras clave (hasta 12), objetivos (hasta 8) y datos académicos opcionales. Devuelve la ubicación, la
  saturación, las tesis cercanas, los asesores, las 100 vecinas y los tiempos por etapa.
  Pydantic valida la entrada y rechaza la inválida con 422.

El servicio no conoce usuarios, sesiones, cuotas ni la fila: de eso se encarga la puerta que lo
precede (§8). Tampoco escribe el texto recibido en los logs, solo tiempos y tamaños.

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
- en Modal, desde un volumen (§7.6).

El `Dockerfile` queda como plan B, por si el servicio se muda a Cloud Run o a otro proveedor de
contenedores.

La imagen mide unos 200 MB comprimida y se puede reconstruir sin mover los 3 GB de datos. El
puerto sale de la variable `PORT`, como espera Cloud Run.

Medido en un contenedor local, con el motor de Docker 29.8:

- respuestas idénticas a las del servicio fuera del contenedor;
- mediana de unos 300 ms por petición;
- unos 3 GiB de memoria residente.

### 7.6 Despliegue en Modal

El plan de ADR-0015 era Cloud Run, pero Google rechazó la cuenta de facturación (26-sep).
El servicio corre en **Modal** (`modal_app.py`) con la misma app de FastAPI, sin cambios:

- **Recursos:** 2 núcleos y 4 GiB, **un solo contenedor** (`max_containers = 1`), que atiende
  hasta 4 peticiones a la vez y se apaga tras 1 minuto sin uso.
- **Arranque en frío:** de 12 a 16 s, aceptados por el usuario; con el servicio despierto, un
  análisis completo tarda unos 3 s.
- **Artefactos:** viven en un volumen de Modal (`nodos-lab-artefactos`), montado en
  `/artefactos`; la imagen lleva solo el código.
- **Acceso** (29-sep):
  - Modal exige un **token de proxy** (`Modal-Key` y `Modal-Secret`) y rechaza en su borde lo
    que no lo trae, **sin despertar el contenedor**;
  - la app exige además la clave compartida `X-Lab-Clave`;
  - con `LAB_EXIGIR_CLAVE=1`, que Modal pone, la app no arranca sin una clave de 32 o más
    caracteres.
- **Costo:** 30 USD de crédito al mes con tarjeta registrada (29-sep), unos 6,000 análisis. El
  Worker los topa con `TOPE_MES` = 6000; al llegar, el Laboratorio se pausa hasta el día 1 y
  no cobra de más.

Pendiente: registrar el cambio a Modal como enmienda a ADR-0015, y volver a desplegar con el
token de proxy.

## 8. Arquitectura de producción

Decidida en ADR-0015, con dos cambios de proveedor en la práctica: el sitio va en Workers con
archivos estáticos y no en Pages (§8.2), y el servicio de datos va en Modal y no en Cloud Run
(§7.6).

```
Navegador
 ├── Sitio estático (6 páginas + data/) ──────── Cloudflare Workers, archivos estáticos («nodosmap»)
 ├── Inicio de sesión (PKCE) ─────────────────── Supabase Auth: Google, GitHub y enlace por correo
 └── /api/* ── Worker «puerta» ───────────────── Cloudflare Workers
                ├── límites por IP y por usuario ── Rate Limiting de Workers
                ├── sesión: JWT (ES256) ─────────── JWKS de Supabase
                ├── Turnstile (acción y dominio) ── Cloudflare Turnstile
                ├── cuotas, análisis y guardados ── Cloudflare D1
                ├── fila (2 a la vez) ───────────── Durable Object «Fila» (SQLite)
                ├── datos ─► servicio del Lab ───── Modal (token de proxy + X-Lab-Clave)
                └── IA ───► gpt-oss-120b ────────── Groq (retención cero) → Workers AI de respaldo
```

Ningún servicio interno queda expuesto al navegador: la URL del servicio de datos y las claves
de los proveedores viven solo en el Worker.

### 8.1 Estado de cada pieza (29-sep-2026)

| Pieza | Estado |
|---|---|
| Sitio estático | **Publicado como copia de prueba** en `nodosmap.sebastian-diaz-prado.workers.dev` (v4.36.9). Cuenta de Cloudflare `98c2acfa…`, dueña del dominio. `nodosmap.com` está comprado y sin conectar |
| Dominio y cuenta | `nodosmap.com` en Cloudflare Registrar, vence el 28-sep-2027. **Los cuatro contactos del registro** (titular, administrador, técnico y facturación) **están en el correo personal (gmail)**, no en el institucional, y la cuenta de gmail es Superadministradora de la cuenta `98c2acfa…` (revisado el 29-sep-2026). El nombre de la cuenta sigue diciendo «comunidad.unam.mx», pero solo es el nombre. `wrangler` opera con el inicio de sesión de gmail |
| Worker `puerta` | **Solo en local** (`wrangler dev`). Falta staging: D1 remoto con migraciones, entorno de producción y secretos |
| D1 | Local, con las migraciones 0001 a 0004 |
| Fila (Durable Object) | Local, probada (§8.4) |
| Supabase Auth | Configurado: Google (app en modo prueba), GitHub y correo. Faltan las URL de producción |
| Turnstile | Widget «NodOS» (Managed) creado; clave de sitio en `laboratorio.html`. La secreta va con staging |
| Servicio de datos | **Desplegado en Modal** (prueba). Falta volver a desplegar con el token de proxy |
| IA | Groq y Workers AI funcionando desde el Worker local |
| Apoyos | Enlace de Stripe **en modo de prueba** |
| Dataset público | **Publicado** en Kaggle |

La decisión del usuario (28-sep) es no publicar a medias: el mapa y el Laboratorio salen juntos
en `nodosmap.com` cuando todo esté listo. El orden restante está en la «Lista de lanzamiento»
de `development.md`: staging, estrés y CI, calidad, contenido y legal, producción y difusión.

### 8.2 Sitio estático

`tools/construir_sitio.py` arma `dist/` con las seis páginas, `compartido/`, `vendor/`, `lab/`,
`data/` y `_headers`, y se publica con
`npx wrangler deploy --assets dist --name nodosmap` desde la raíz del repo. Queda en Workers con
archivos estáticos, no en Pages: wrangler 4.141 manda Pages a ese flujo. Los límites son los
mismos (20,000 archivos y 25 MiB por archivo), y hoy caben con margen.

- `_headers` pone las cabeceras de seguridad comunes (HSTS, `nosniff`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, COOP) y **una CSP por página**. Workers Static
  Assets no respeta `! Content-Security-Policy`, así que una CSP general se sumaba a la del
  mapa, y la estricta bloqueaba regl.
- Las URL `.html` redirigen (307) a la ruta sin extensión, conservando la consulta.

### 8.3 Worker `puerta`

`services/puerta/` es el único punto de entrada a lo dinámico, en JavaScript sin build. Cada
petición pasa, en orden, por:

1. **La configuración.** Con `ENTORNO = "produccion"`, si hay algo de desarrollo (un JWKS local,
   la clave de prueba de Turnstile, una clave corta con el servicio, URLs sin https, o faltan
   los límites o la fila), responde 503 a todo y registra qué variable falla.
2. **CORS** con orígenes explícitos. Sin cookies: la sesión va en `Authorization: Bearer`, así
   que no hay CSRF que cuidar.
3. **Límite por IP**, antes de la sesión: 120 peticiones por minuto a toda la API y 10 al
   análisis. IPv6 cuenta por su /64.
4. **Sesión.**
   - El JWT de Supabase se verifica con WebCrypto contra su JWKS, en caché 10 minutos.
   - Solo acepta ES256 o RS256, y exige emisor, audiencia, rol `authenticated` y vigencia.
   - Rechaza a los usuarios anónimos.
   - Después aplica el límite de **30 escrituras por minuto por usuario**, que cuida las
     100,000 filas escritas al día de D1.
5. **La entrada.** Tope de tamaño (el cuerpo se lee por partes y se corta al pasarlo) y
   revisión de la forma, con los mismos topes que el servicio de datos.
6. **Limpieza contra inyección de prompt**, antes del léxico, del servicio y de la IA.
7. **Turnstile**, que en producción exige la acción `analisis` y uno de los dominios propios.
8. **Cuotas**, con UPSERT atómicos en D1: el tope del mes (`TOPE_MES`), el del sitio por día y
   el del usuario (2 al día). Si algo falla antes de entregar datos, la cuota se devuelve.
9. **La fila** (§8.4) y, al final, el servicio de datos y la IA.

**Rutas:**

| Ruta | Qué hace |
|---|---|
| `POST /api/lab/analisis` | Análisis completo por SSE; sin lugar, 202 y a la fila |
| `POST /api/lab/contexto` | Solo datos |
| `GET /api/yo` | Cuotas y conteos de la cuenta |
| `/api/analisis` | Guardar, listar, abrir y borrar análisis |
| `/api/tesis` | Tesis guardadas, también por lotes de 100 |
| `/api/asesores`, `/api/lugares` | Asesores y lugares del mapa guardados |
| `DELETE /api/cuenta` | Borra los datos de D1 y, con la clave de servicio, la identidad en Supabase |

Lo que se muestra de cada guardado pasa por una lista blanca de campos y tipos, con tope de 2 KB.
Toda consulta a D1 filtra por el `sub` del token, nunca por un id que mande el cliente.

**IA** (`src/ia/`):

- **Tres llamadas en paralelo**, cada una con su esquema de salida y un reintento con los
  errores como retroalimentación:
  - la nota del planteamiento;
  - Bloom, con el nivel que da el léxico compartido;
  - las preguntas.
- **Proveedores:** primero Groq (`gpt-oss-120b`, con retención de datos desactivada) y, si se
  agota o falla, Workers AI con el mismo modelo.
- **Topes diarios:** análisis con IA (`TOPE_IA_DIA`), tokens de Groq y neuronas de Workers AI.
  Si se acaban, el análisis se entrega solo con datos.

**D1** (`migrations/`): `analisis` (con `estado`: `listo` o `fila`), `tesis_guardadas`,
`asesores_guardados`, `lugares_guardados`, `cuota_diaria` y `cuota_sitio` (tipos `datos`, `mes`,
`ia`, `groq_tokens` y `workers_ai_neuronas`). Un cron diario borra las cuotas viejas (las del mes,
a los 3 meses) y mantiene despierto el proyecto de Supabase.

### 8.4 Fila del Laboratorio

Modal corre un solo contenedor de 2 núcleos, así que el servicio de datos atiende
`FILA_SIMULTANEOS` (2) análisis a la vez. La fila es un **Durable Object**, uno para todo el sitio
(`src/fila.js`), con almacenamiento SQLite (plan gratuito).

- **Con lugar**, el análisis corre en vivo por SSE. El lugar se suelta en cuanto responde el
  servicio de datos, porque la IA no lo ocupa. Si nadie lo suelta, vence a los 4 minutos.
- **Sin lugar**, el Worker responde 202 y guarda el análisis en D1 con estado `fila`, que Mi
  espacio muestra como «En la fila».
  - El Durable Object lo corre en segundo plano (alarma), con el mismo código que el análisis en
    vivo (`correrIA`), y lo guarda como un análisis normal.
  - Quien llega mientras hay fila espera su turno, aunque se libere un lugar.
- **Ocupa uno de los 2 guardados** desde que entra. Con los 2 llenos no entra, y la cuota se
  devuelve.
- **Si se borra antes de su turno**, sale de la fila y la cuota vuelve. Si el servicio falla en
  segundo plano, el análisis se borra y la cuota vuelve.
- **No tiene largo máximo:** el freno es el tope diario del sitio. Al llegar al tope del mes, el
  Laboratorio se pausa hasta el día 1.
- **Recuperación:** un objeto que se reinicia a mitad de un análisis lo devuelve al frente en la
  siguiente alarma. Cada alarma dura a lo más 12 minutos y se reprograma.

### 8.5 Portabilidad

Cada pieza depende de una interfaz estándar: HTTP, JWT o un contenedor OCI. Mudarla es cambiar
configuración, y ya pasó dos veces (Pages → Workers y Cloud Run → Modal). Esto responde a que
varias capas gratuitas cambiaron sin aviso durante 2026.

## 9. Seguridad y privacidad

Revisada en dos pasadas el 29-sep-2026 (v4.37.0 y v4.37.1, en `development.md`), con ataques
simulados y el flujo normal probado de punta a punta.

- **Datos personales.**
  - Los autores quedan fuera de todo artefacto publicado (§4.3), y el export público se
    construye por lista blanca de columnas.
  - Los asesores sí se muestran.
  - El texto de una tesis nunca llega a los logs de ningún componente, solo conteos y tiempos.
- **Sesión.** Tokens firmados y verificados contra el JWKS; sin cookies ni CSRF. Los parámetros
  de desarrollo que cambian a dónde se manda el token o el borrador (`?puerta=`, `?api=`,
  `?sesion=local`) solo se leen en local.
- **Abuso y costo.**
  - Límites por IP y por usuario, Turnstile con acción y dominio, y cuotas por usuario, sitio
    y mes.
  - El servicio de datos está detrás de un token de proxy que Modal revisa sin despertar el
    contenedor.
  - La configuración de producción falla cerrada.
- **Entradas.**
  - Se validan por esquema y tamaño en la puerta y otra vez en el servicio.
  - El texto del usuario viaja al modelo como dato delimitado, después de normalizarlo y quitar
    caracteres invisibles y delimitadores.
  - La salida del modelo se valida contra un esquema.
- **Salidas.** Todo texto del catálogo, del usuario o del modelo se escapa al pintarse, también
  dentro de atributos. Una prueba con **el catálogo envenenado** (cada texto con una carga XSS)
  no ejecutó ninguna en el mapa ni en el Laboratorio.
- **Cabeceras.**
  - El sitio lleva CSP por página, HSTS y afines (§8.2).
  - La API lleva `default-src 'none'`, `no-referrer` y `nosniff`.
  - Las bibliotecas van con versión exacta y desde el propio origen; supabase-js, con SRI.
- **Aislamiento entre cuentas.** Toda consulta filtra por el usuario del token; hay pruebas de
  acceso cruzado.
- **Secretos.** Viven en el gestor de secretos de cada plataforma o en `.dev.vars` en local;
  ninguno se versiona.
- **Riesgos abiertos:**
  - **Cuentas creadas en masa** podrían agotar el tope diario del sitio.
  - **La sesión vive en `localStorage`** y la CSP admite `'unsafe-inline'`, porque las páginas
    llevan su código en línea. La defensa de fondo es sacar los scripts a archivos y usar hashes.
  - **Un token vale hasta su caducidad** (1 hora), aun después de salir.
  - **Las claves viejas de los scripts de `app/`** siguen sin rotar.

## 10. Verificación y gestión del cambio

- **CI** (`.github/workflows/pruebas.yml`, en cada push):
  - **privacidad**: ningún título publicado trae mención de autor;
  - **humo**: cada página carga en Chrome sin errores en la consola (`tools/prueba_humo.mjs`);
  - **léxico e inyección**: los casos límite de Bloom y de la limpieza contra inyección;
  - **seguridad**: sesión, límites, forma de la entrada, configuración de producción y
    Turnstile, sin necesidad de levantar el Worker.
- **Pruebas del Worker contra `wrangler dev`**, fuera del CI porque necesitan el servicio de
  datos:
  - `puerta.test.mjs`: 11 pruebas, incluidas las de acceso cruzado y los lotes;
  - `fila.test.mjs`: 4 pruebas, con una configuración de un lugar y sin IA.
- **Interfaz.** `tools/cdp.mjs` controla Chrome sin ventana (headless) con el protocolo
  DevTools: ejecuta pasos declarados en JSON, toma capturas en escritorio y móvil y vuelca la
  consola.
- **Backend.**
  - `evaluar.py` es la prueba de aceptación de calidad semántica (§7.4).
  - `evaluacion/evaluar_ia.mjs` corre 11 casos de IA con chequeos automáticos: fuga de
    inyección, citas inventadas, periodo e idioma.
- **Versiones.** El sitio sigue versionado semántico (se muestra en el pie del mapa). Cada
  versión queda registrada en `development.md` con qué cambió, por qué y cómo se verificó.
- **Decisiones.** Las decisiones de arquitectura se registran como ADR, que no se editan
  después de aceptarse: un ADR nuevo reemplaza al anterior y lo cita. Las propuestas que
  requieren investigación pasan primero por un RFC.
- **Pendiente:**
  - las pruebas del Worker en el CI (con staging);
  - pruebas de estrés con 50 análisis simultáneos;
  - Dependabot.

## 11. Limitaciones conocidas

- Solo un tercio del corpus tiene subtema (§5.2). La ubicación que calcula el Laboratorio
  todavía vota solo con las tesis agrupadas.
- El mapa publica una muestra de los vecindarios, no la tabla completa (§5.6).
- Las páginas en un solo archivo, sin módulos, facilitan el despliegue pero dificultan la
  cobertura de pruebas unitarias y obligan a `'unsafe-inline'` en la CSP.
- **Capacidad del Laboratorio.**
  - Un contenedor de 2 núcleos da 2 análisis a la vez.
  - El límite por minuto de Groq en la capa gratuita alcanza para cerca de 1 análisis con IA
    por minuto; los demás esperan o pasan a Workers AI, que tarda unos 25 s.
  - Con una fila larga, la espera puede ser de horas.
- Si el servicio de datos falla con un análisis de la fila, este desaparece de Mi espacio sin
  aviso (la cuota se devuelve).
- Los umbrales de similitud del Laboratorio son orientativos hasta calibrarlos con un conjunto
  de evaluación más amplio.

## Apéndice: mapa del repositorio

| Ruta | Contenido |
|---|---|
| `prototypes/atlas_vecindario_mvp/` | El sitio: las seis páginas, `compartido/`, `vendor/`, los datos (`data/`), los ejemplos del Laboratorio (`lab/`) y `_headers` |
| `services/puerta/` | Worker de la API: sesión, límites, cuotas, fila (`src/fila.js`), IA (`src/ia/`), migraciones de D1 y pruebas |
| `services/lab/` | Servicio de datos del Laboratorio: app de FastAPI, `modal_app.py`, `Dockerfile`, la construcción de artefactos y la prueba de aceptación |
| `pipeline/` | Adquisición, limpieza, pipeline semántico y generación de artefactos |
| `tools/` | `construir_sitio.py` (arma `dist/`), `prueba_humo.mjs` y `cdp.mjs` |
| `.github/workflows/` | CI: privacidad, humo, léxico, inyección y seguridad |
| `adr/`, `rfc/` | Decisiones de arquitectura y propuestas |
| `marca/` | Logo y favicon de NodOS |
| `PRODUCT.md` | Usuarios, propósito y reglas de diseño |
| `development.md` | Bitácora del proyecto, hoja de ruta y lista de lanzamiento |
| `app/` | Código de la versión anterior del producto, conservado como referencia |
