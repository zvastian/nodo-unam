# NODO UNAM — Contexto del Proyecto

> Documento de referencia permanente. Guarda aquí el estado y las decisiones de arquitectura del proyecto para no perder contexto entre sesiones.

## Propósito del Proyecto

NODO UNAM es una plataforma de exploración, análisis y visualización del acervo de tesis de la UNAM. El objetivo es convertir un corpus académico muy grande, originalmente tabular y bibliográfico, en una interfaz navegable que permita ver patrones históricos, institucionales, disciplinares y semánticos.

La plataforma tiene dos grandes líneas:

- **Taller / visualización cuantitativa**: explora rankings, burbujas, heatmaps y series temporales usando datos curados y agregados.
- **Atlas semántico / exploración conceptual**: representa tesis como un espacio de relaciones semánticas: macroclusters, mesoclusters, microclusters, tesis representativas y vecindarios de tesis similares.

La idea final es que el usuario no solo busque tesis, sino que pueda "navegar" la producción académica de la UNAM como un mapa de temas, áreas, programas, épocas y relaciones intelectuales.

## Stack General

### Frontend
- HTML, CSS y JavaScript vanilla.
- Visualización de grafos con `sigma.js` y `graphology`.
- Visualización de gráficas cuantitativas con `ECharts`.
- Interfaz estática desplegable en Cloudflare Pages.
- Carga de datos: JSON curados pequeños para Taller; JSON jerárquicos lazy-loaded para Atlas; eventualmente archivos grandes desde Cloudflare R2.

### Backend de desarrollo
- Python, FastAPI, Uvicorn.
- DuckDB para consultar Parquet localmente.
- Pandas / PyArrow para transformación de datos.
- PostgreSQL + pgvector para búsqueda semántica o consultas vectoriales en la arquitectura original.
- Endpoints REST tipo:
  - `/api/workshop/tools/bubbles`
  - `/api/workshop/tools/ranking`
  - `/api/workshop/tools/heatmap`
  - `/api/workshop/tools/heatmap-matrix`
  - `/api/workshop/tools/series`
  - `/api/explore/neighborhood/{thesis_id}`
  - `/api/lab/run-full`

### IA / Semántica
- Embeddings con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (dimensión 384).
- Procesamiento acelerado en GPU vía Google Colab para tesis nuevas.
- Búsqueda vectorial con FAISS.
- Clustering de grafos con `igraph` y `leidenalg`.
- Vecindarios semánticos por tesis: top 50 similares.
- LLM / IA generativa: **no está activa en el deploy estático**. El Laboratorio o análisis asistido queda pensado para backend separado (posiblemente HF Spaces, Worker o API propia). En frontend aparece arquitectura para `/api/lab/run-full`, pero en deploy público inicial debe quedar desactivado o "próximamente".

## Datos Base

- Dataset principal actual: **`base7_kaggle_clean.parquet`** (en `data/clean/`).
- ~609,156 tesis.
- Identificador estable principal: `thesis_id`.
- Fuentes: `base6` (corpus histórico principal) + `marc_recovered` (tesis recuperadas nuevas).
- Columnas importantes: `thesis_id`, `Año`, `titulo_limpio`, `titulo_normalizado`, `autor_ui`, `asesor_ui`, `programa`, `area`, `nivel_estandar`, `plantel_estandarizado`, `texto_completo_url`, campos MARC/Aleph/bibliográficos.
- **Punto crítico**: se abandonó `stable_id` como identificador porque generaba duplicados entre `base6` y `marc_recovered`. El identificador correcto para unir embeddings y registros es `thesis_id`.

## Embeddings

- Base histórica: `base7_embeddings_base6.parquet` — 562,211 filas — modelo `paraphrase-multilingual-MiniLM-L12-v2`.
- Tesis recuperadas: `base7_marc_recovered_embeddings.parquet` — 46,944 filas — generadas en Google Colab con GPU (una tesis quedó sin embedding por falta real de título/datos útiles).
- Embeddings completos: `base7_embeddings_full.parquet` — 609,155 filas — dimensión 384 — sin duplicados por `thesis_id`.
- Matrices exportadas (en `app/semantic_full/`):
  - `base7_semantic_embeddings.float32.npy`
  - `base7_semantic_embeddings_norm.float32.npy`
  - `base7_semantic_ids.npy`
  - `base7_semantic_metadata.parquet`
- Esto permite separar: metadata legible en Parquet, vectores densos en `.npy`, IDs en arreglo compacto.

## Búsqueda Semántica

- Índice FAISS sobre los embeddings normalizados.
- Proceso: cargar matriz (609155, 384) → construir índice FAISS → buscar vecinos top-k por tesis → exportar edges semánticos → filtrar candidatos por ranking mutuo, score mínimo, top-k.
- Resultado: `base7_semantic_edges_mutual_rank15_score075.parquet` — ~1,637,549 edges no dirigidos, 519,037 nodos conectados, score mínimo 0.75.
- Este grafo es la base del atlas semántico.

## Clustering

- Leiden sobre el grafo semántico.
- Primer resultado: resolución 1.0 → 9,515 clusters (demasiados para visualización directa).
- Jerarquía editorial diseñada:
  - **Macroclusters**: vista de alto nivel, ~43 nodos macro visibles (Área 1: 12, Área 2: 15, Área 3: 10, Área 4: 6).
  - **Mesoclusters**: nivel intermedio. Para Área 4 se permitió usar microclusters como mesoclusters por poca masa temática. Para áreas con mucha producción (especialmente Área 2), se controla visualmente el exceso.
  - **Microclusters**: nivel fino, filtrado con política editorial — mínimo visible 5 tesis, máximo 30 nodos por macro, fallback si un macro queda vacío.
  - **Tesis representativas**: por microcluster, máximo 25, mínimo ideal 5 (puede haber menos tras deduplicación). Selección por cercanía al centroide + diversificación por título.
  - **Vecindario de tesis**: tesis central + top 50 similares + edges semánticos + controles de agrupación por año/programa/plantel/nivel/área.

## Archivos del Atlas Beta

Estructura de `atlas_preview_data/` (vive en el repo de GitHub, generado a partir de `app/semantic_full/`):

```
atlas_preview_data/
  atlas_manifest.v1.json
  atlas_display_policy.v1.json
  atlas_balanced_macro_graph.json
  meso_by_macro/{macro_id}.json          # lazy load
  micro_by_macro/{macro_id}.json         # lazy load
  theses_by_micro/{micro_id}.json        # lazy load
  neighborhood_by_thesis/{thesis_id}.json # lazy load pesado
```

Contrato de carga (definido en `atlas_manifest.v1.json`):
- `macro`: eager
- `meso_by_macro`, `micro_by_macro`, `theses_by_micro`, `neighborhood_by_thesis`: lazy

Esto permite que el frontend sea estático pero inteligente: no necesita backend para navegar capas ya precomputadas. El atlas no muestra "todo" directamente — muestra una selección curada (política en `atlas_display_policy.v1.json`) para que sea navegable.

## Frontend del Atlas

Archivo: `atlas_macro_preview.html` (en `app/`). Usa `graphology@0.25.4` y `sigma@2.4.0`.

Funciones: carga del macro graph, render Sigma, click en macro, carga lazy de meso/micro/tesis/vecindario, modo universo, modo análisis, agrupación de vecinos, controles de cámara, ocultamiento de tesis/labels según zoom.

Visual: nodos macro grandes, mesoclusters secundarios, tesis como estrellas pequeñas, edges semánticos, panel inferior desplegable, fondo oscuro tipo mapa/constelación.

## Taller Cuantitativo

Configuración de modo dual:

```js
window.NODO_CONFIG = {
  mode: "api" | "static",
  apiBase: "",
  dataBaseUrl: "./data",
  labEnabled: false,
  semanticEnabled: false
}
```

- `mode: "api"` (desarrollo): los módulos consultan FastAPI.
- `mode: "static"` (deploy): los módulos cargan JSON locales o desde R2.

Funciones adaptadas: `loadBubbleData()`, `loadRankingData()`, `loadHeatmapData()`, `loadSeriesData()`.

Archivos estáticos curados en `data/workshop/`: bubbles (advisor/program/plantel/level), ranking (program/advisor/area/level/plantel), heatmap temporal (advisor/program/area/level/plantel/degree), heatmap matrix (program×level/area×level/program×area), series (level/area/program/plantel/advisor).

## Backend API de Desarrollo

- Archivo conceptual: `scripts/workshop_api.py`.
- Endpoints: `/api/workshop/health`, `/api/workshop/facets`, `/api/workshop/exact` (POST), `/api/workshop/analyze` (POST), `/api/workshop/tools/{bubbles,ranking,heatmap,heatmap-matrix,series}`.
- Servicio `workshop_service.py`: usa DuckDB, Parquet, agregaciones SQL, filtros por año/área/nivel/dimensión.
- Hubo un bug de concurrencia cuando varias llamadas pegaban al mismo servicio/DuckDB simultáneamente. Solución conceptual: serializar llamadas críticas con lock, o evitar dependencia concurrente en deploy usando JSON estático.

## DuckDB / SQL

- **Desarrollo/generación**: leer Parquet grandes, agregar por dimensión, crear resúmenes, exportar JSON/Parquet pequeños.
- **Deploy futuro posible**: DuckDB WASM en navegador — no activar todavía (aumenta complejidad de carga, obliga a manejar memoria en cliente, requiere diseñar bien qué consultas van al navegador).
- Conclusión: Taller actual puede funcionar con JSON pequeños. El parquet/SQL completo queda para backend o futura capa avanzada. Asesores o búsquedas muy flexibles podrían requerir DuckDB WASM después.

## Deploy Público

Estrategia híbrida:

**Cloudflare Pages** (proyecto `nodo-unam`, URL `https://nodo-unam.pages.dev/`):
- Frontend estático: `index.html`, `workshop.js`, `workshop.css`, `app.js`, vendor JS liviano, favicon, JSON pequeños del Taller, quizá macro graph inicial del atlas.
- Framework preset: None. Build output directory ideal: `deploy/static` (no `/`, porque puede incluir archivos grandes).
- **Límite duro**: Pages solo soporta archivos hasta 25 MiB. Ya se dio el error `explore/thesis_atlas_index.json is 36.2 MiB` → hubo que excluirlo y moverlo a R2.

**Cloudflare R2** (bucket `nodo-unam-data`):
- Sirve archivos grandes o numerosos: atlas semántico, vecindarios por tesis, JSON pesados, posiblemente Parquet/Numpy derivados.
- URLs públicas vistas:
  - `https://pub-276e5a3e9b954e50af88ec2358be2f9a.r2.dev/explore/thesis_atlas_index.json`
  - `https://pub-276e5a3e9b954e50af88ec2358be2f9a.r2.dev/nobel/nobel_atlas_es_ui.v1.json`
- Decisión posterior: pausar el atlas viejo (basado en muestra de 50k) y reconstruir sobre la base completa `base7`.
- Recomendaciones: versionar archivos, cache fuerte, no cargar atlas al inicio, cargar solo al entrar a Explorar/Atlas, usar manifest para rutas, bloquear indexación innecesaria con `robots.txt`, activar protecciones básicas de Cloudflare.

### No se debe subir a Pages
Archivos >25 MB, atlas completo monolítico, matrices `.npy` gigantes, parquets grandes, índices FAISS enormes, data cruda completa.

### Sí se puede subir a Pages
Frontend, CSS/JS, JSON pequeños de Taller, manifest, display policy, macro graph liviano, favicon/assets livianos.

### Sí conviene subir a R2
`neighborhood_by_thesis/`, atlas pesado reconstruido, archivos grandes versionados (`thesis_atlas_index.v1.json`, `nobel_atlas_es_ui.v1.json`, futuros bundles semánticos).

## Modo Static vs API

```js
// Deploy público
window.NODO_CONFIG = {
  mode: "static",
  apiBase: "",
  dataBaseUrl: "./data",
  labEnabled: false,
  semanticEnabled: false
}
```

- Static: `fetch("./data/workshop/ranking_program.json")`
- API: `fetch("/api/workshop/tools/ranking?dimension=program...")`

Esto permite desarrollo local con backend, deploy público sin backend, y futura reactivación de backend semántico sin reescribir la UI.

## Laboratorio / IA

Actualmente desactivado en deploy público inicial (`labEnabled: false`, `semanticEnabled: false`). Razones: requiere backend, puede requerir claves/API, puede disparar costos, necesita seguridad/rate limiting/control de abuso.

Arquitectura futura: Cloudflare Worker como proxy ligero, Hugging Face Space para inferencia/búsqueda semántica, backend FastAPI separado para pgvector/FAISS, endpoints autenticados o rate-limited.

## Nobel

Sección Nobel con archivo `nobel_atlas_es_ui.json`. **Cuidado**: había copias dispersas en `static/nobel/`, `deploy/static/nobel/`, `nobel/static/`, `nobel/outputs/`, `outputs/nobel/` — causaron 404 por rutas inconsistentes (ej. buscar `/static/nobel/nobel_atlas_es_ui.json`). Para deploy: si pesa poco va en Pages, si crece se mueve a R2, y la ruta debe quedar consistente.

## Seguridad y Costos

**Riesgos**: bots descargando JSON pesados, costos por operaciones en R2, abuso de endpoints IA, scraping masivo de vecindarios, carga inicial lenta si se cargan demasiados datos.

**Medidas**:
- Lazy loading estricto.
- Cache fuerte: `Cache-Control: public, max-age=86400` (o más para archivos versionados).
- Nombres versionados (`atlas_manifest.v1.json`, `neighborhood_index.v1.json`).
- `robots.txt` para evitar indexación de JSON (`Disallow: /atlas_preview_data/`, `Disallow: /explore/thesis_atlas_index`).
- Cloudflare WAF / bot protection.
- No exponer endpoints de IA sin rate limit.
- Separar archivos pesados en R2.
- No cargar vecindarios al inicio.

## Estructura Recomendada para Deploy

```
deploy/
  static/
    index.html
    app.js
    workshop.js
    workshop.css
    favicon.png / favicon.ico
    vendor/echarts.min.js
    data/workshop/*.json
    atlas/
      atlas_manifest.v1.json
      atlas_display_policy.v1.json
      atlas_balanced_macro_graph.json
  r2/
    atlas_preview_data/{meso_by_macro,micro_by_macro,theses_by_micro,neighborhood_by_thesis}/
    explore/thesis_atlas_index.v1.json
    nobel/nobel_atlas_es_ui.v1.json
```

Producción sugerida:
- **Pages**: `/index.html`, `/workshop.js`, `/workshop.css`, `/data/workshop/*.json`, `/atlas/atlas_manifest.v1.json`, `/atlas/atlas_balanced_macro_graph.json`.
- **R2**: `/atlas/{meso_by_macro,micro_by_macro,theses_by_micro,neighborhood_by_thesis}/*.json`.

## Flujo de Usuario — Atlas

1. Usuario abre el atlas → Pages carga HTML/JS/CSS/macro graph.
2. Se renderizan macroclusters con Sigma.
3. Click en macrocluster → carga `meso_by_macro/{macro_id}.json`.
4. Entra a micro/meso → carga `theses_by_micro/{micro_id}.json`.
5. Selecciona tesis → carga `neighborhood_by_thesis/{thesis_id}.json` → modo análisis con top 50 similares.

## Flujo de Usuario — Taller

1. Usuario entra a Taller (por default puede iniciar en Burbujas).
2. Cada módulo carga JSON estático (bubbles/ranking/heatmap/series).
3. No necesita backend en producción. Si se activa modo API en desarrollo, usa FastAPI.

## Qué Falta para Deploy Completo

- [ ] Consolidar carpeta `deploy/static`.
- [ ] Copiar frontend final ahí.
- [ ] Asegurar `window.NODO_CONFIG.mode = "static"`.
- [ ] Asegurar rutas relativas correctas.
- [ ] Mantener Laboratorio desactivado.
- [ ] Subir JSON ligeros a Pages.
- [ ] Subir JSON pesados a R2.
- [ ] Cambiar `dataBaseUrl` / `atlasBaseUrl` para apuntar a R2 cuando corresponda.
- [ ] Agregar `robots.txt`.
- [ ] Agregar `_headers` para cache.
- [ ] Probar en `nodo-unam.pages.dev`.
- [ ] Validar consola: sin `/api/` en modo static, sin 404, sin carga inicial de archivos pesados.
- [ ] Versionar datos (v1, v2, etc.).
- [ ] Automatizar scripts de exportación.
- [ ] Documentar contrato de datos.

## Resumen Ejecutivo Técnico

NODO UNAM combina un pipeline de datos académico en Python con visualizaciones web estáticas y un atlas semántico precomputado. La base completa de más de 609 mil tesis se limpia en Parquet, se consulta con DuckDB, se transforma con Pandas/PyArrow y se enriquece con embeddings multilingües. Sobre esos embeddings se construyen vecinos semánticos con FAISS, edges filtrados por similitud mutua y clusters con Leiden/igraph.

Para producción, la plataforma se divide en dos capas: un frontend estático en Cloudflare Pages y datos pesados en Cloudflare R2. El Taller funciona con JSON pequeños preagregados. El Atlas funciona con JSON jerárquicos lazy-loaded: macro al inicio, meso/micro bajo demanda, tesis representativas bajo demanda y vecindarios semánticos solo cuando el usuario abre una tesis específica.

El backend FastAPI, pgvector y llamadas IA quedan como capa de desarrollo o fase posterior, no como dependencia del primer deploy público.

---

## Estado del Repositorio (registro de orden — 2026-09-19)

- **Repo de GitHub activo**: [`zvastian/MI-TESIS-UNAM`](https://github.com/zvastian/MI-TESIS-UNAM) (público). Contiene la app real desplegable: `scripts/`, `static/`, `atlas_preview_data/`, `deploy/`, `nobel/`, `data/thesis_lookup.parquet` (vía Git LFS). Sin GitHub Pages activo — el deploy objetivo es Cloudflare Pages, aún no conectado.
- **Repos obsoletos a revisar para archivar/borrar**:
  - `ssebastian-diazz/MI-TESIS-UNAM` (privado) — prototipo temprano (14-abr a 6-may), superado.
  - `ssebastian-diazz/tesis-extractor-api` (público) — 5 archivos JS sueltos, casi vacío.
- **Carpeta local `C:\Users\sebas\Desktop\UNAM Tesis`**: no estaba conectada a ningún remoto de git. Se reorganizó en:
  - `app/` — código de la aplicación (AI Pipeline, atlas HTML, semantic_full, nodo-unam/, Nodos/) — homólogo de lo que vive en el repo de GitHub.
  - `pipeline/` — ~65 scripts de limpieza/homogeneización/auditoría del dataset + `outputs/` + `recovery/`.
  - `data/clean/` — `base7_kaggle_clean.parquet` (dataset final) + diccionario de columnas.
  - `data/embeddings/` — embeddings base6/marc/full.
  - `data/raw/` — manifests, scraping de bibliografía (JS), sqlite, jsonl crudos.
  - `data/archive/` — versiones intermedias/superadas de `base`, `base6`, `t*`, `Old/`.
  - `notebooks/` — todos los `.ipynb`.
  - `prototypes/` — mockups HTML (`a - prototypes/`, `assets/`, prototipo*.html, etc.).
  - `docs/` — documentos personales y de referencia (credencial, constancia, PDFs, logos).
  - `_scratch/` — instaladores (.exe/.msi), `node_modules/`, `.venv/`, zips, y un script ajeno al proyecto (`AJENO_patch_overall_risk_from_radar.py`, parece de otro proyecto de análisis de riesgo país) — pendiente de revisión/borrado.
- **Borrado**: `bibliography_run_fresh/bibliography_raw.jsonl` (~3.1 GB, confirmado innecesario por el usuario).
- **Pendiente**: decidir cuál(es) parquet de `data/archive/` se pueden borrar definitivamente (deduplicación de versiones `base6_homogeneizada_stream_v1..v4_1`, `t*.parquet`, etc.) — deliberadamente pospuesto.
- **Pendiente**: conectar la carpeta local (`app/`) como remote del repo `zvastian/MI-TESIS-UNAM`, o decidir si se sigue trabajando solo por subida manual.
