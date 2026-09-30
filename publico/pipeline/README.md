# Pipeline de datos

Scripts que llevan el dataset público de tesis a los archivos que carga el mapa (`sitio/data/`).
Se ejecutan desde la raíz del repositorio, en el orden de esta página. Cada script documenta en su
encabezado sus entradas, sus salidas y las variables de entorno que acepta.

Los datos ya generados se descargan con `python tools/descargar_datos.py`. Esta guía solo hace
falta para reconstruirlos o para cambiar el método.

## Requisitos

- Python 3.12 y las dependencias de `pipeline/requirements.txt`.
- Una GPU para los pasos 1 y 5 (embeddings y vecinas exactas). La corrida original usó las GPU
  de Kaggle; en CPU es posible, pero mucho más lenta.
- Varios GB libres en disco (solo los embeddings ocupan 2.5 GB). Los intermedios se guardan en `data/` y `atlas_data/`, que git ignora.

## Reproducibilidad

El método se reproduce completo, pero los números no salen idénticos a los publicados, por tres
razones:

1. **El texto de entrada.** La corrida original embebió el título normalizado a partir de la cadena
   bibliográfica completa del catálogo. El dataset público solo trae `titulo_legible`, sin la
   mención de autor, y `preparar_dataset.py` normaliza esa columna.
2. **La curaduría manual.** La jerarquía de campos y temas se corrigió a mano en varias rondas
   (`aplicar_correccion_manual_macro.py`), algunas tesis se reubicaron en el mapa
   (`corregir_layout_manual.py`) y los nombres de los 130 campos se redactaron a mano
   (`curaduria/macro_nombres.v1.json`). Esas correcciones usan los identificadores de grupo de la
   corrida original: sobre una corrida nueva hay que revisarlas antes de aplicarlas. Cada archivo de
   curaduría guarda la primera palabra clave de cada grupo para detectar si los identificadores ya no
   corresponden.
3. **Los algoritmos estocásticos.** UMAP, HDBSCAN y PaCMAP usan semillas fijas, pero sus resultados
   pueden variar entre versiones de las bibliotecas y entre plataformas.

## Orden de ejecución

### 0. Dataset

Descarga el dataset de [Kaggle](https://www.kaggle.com/datasets/sebastiandiazprado/nodos-map)
(licencia CC BY 4.0) y prepáralo:

```sh
python pipeline/preparar_dataset.py ruta/al/dataset.parquet   # → data/public/data_unam.parquet
```

`generar_data_unam.py` es el script que produjo ese dataset a partir de la base interna, que incluye
los nombres de autor. Se publica para documentar qué columnas se excluyen; no hace falta
ejecutarlo.

### 1. Embeddings

```sh
SOURCE_PATH=data/public/data_unam.parquet OUTPUT_DIR=data/embeddings \
  python pipeline/generar_embeddings_full_e5.py
```

Embebe solo el título con `intfloat/multilingual-e5-large` (1024 dimensiones, normalizados). El
encabezado del script explica por qué el programa y el área no se mezclan en el texto.

### 2. Grupos, mapa y palabras clave

```sh
python pipeline/clustering_hdbscan.py          # UMAP a 5 dimensiones + HDBSCAN → data/clustering/clusters_hdbscan.parquet
python pipeline/generar_layout_pacmap.py       # PaCMAP 2D → data/clustering/layout_pacmap2d.parquet
python pipeline/generar_topicos_ctfidf.py      # palabras clave c-TF-IDF de cada subtema
```

### 3. Jerarquía de campo, tema y subtema

```sh
python pipeline/construir_jerarquia_macro_meso.py   # Ward sobre los centroides: corte por distancia (D_MACRO, D_MESO)
python pipeline/aplicar_correccion_manual_macro.py  # correcciones manuales (ver «Reproducibilidad»)
python pipeline/corregir_layout_manual.py           # reubicaciones manuales en el mapa
```

Después, las palabras clave de cada nivel y sus matrices c-TF-IDF, con el mismo script del paso 2
aplicado a tablas `thesis_id, cluster_id` en las que `cluster_id` es el campo (`macro_id`) o el
tema (`meso_id`) de `data/clustering/tesis_macro_meso.parquet`:

```sh
CLUSTERS_PATH=<tabla por campo> OUTPUT_PATH=data/clustering/macro_topics_ctfidf.parquet \
  python pipeline/generar_topicos_ctfidf.py
CLUSTERS_PATH=<tabla por tema> OUTPUT_PATH=data/clustering/meso_topics_ctfidf.parquet \
  MATRIZ_PATH=data/clustering/meso_ctfidf_matrix.npz IDS_PATH=data/clustering/meso_ctfidf_ids.npy \
  python pipeline/generar_topicos_ctfidf.py
MATRIZ_PATH=data/clustering/micro_ctfidf_matrix.npz IDS_PATH=data/clustering/micro_ctfidf_ids.npy \
  python pipeline/generar_topicos_ctfidf.py
```

### 4. Archivos del mapa

```sh
python pipeline/generar_atlas_modo_caos.py        # posiciones y grupo de cada tesis → atlas_data/atlas_chaos_mode.v1.*
python pipeline/generar_atlas_macro_graph.py      # los 130 campos → atlas_data/atlas_macro_graph.v1.json
python pipeline/generar_atlas_subgraphs.py        # temas y subtemas de cada campo → atlas_data/{meso,micro}_by_macro/
python pipeline/generar_atlas_titulos_teselas.py  # títulos por tesela del mapa → sitio/data/titulos_teselas/
python pipeline/mover_teselas_corregidas.py       # aplica las reubicaciones del paso 3 a las teselas
python pipeline/generar_atlas_tesis_meta.py       # nivel, programa y plantel → sitio/data/tesis_meta.v1.*
python pipeline/generar_atlas_acentos.py          # diccionario de acentos para nombres y títulos → sitio/data/escritura.v1.json
```

Copia a `sitio/data/` lo que quedó en `atlas_data/` (`atlas_chaos_mode.v1.bin` y `.json`,
`atlas_macro_graph.v1.json`, `meso_by_macro/` y `micro_by_macro/`), y
`pipeline/curaduria/macro_nombres.v1.json` como `sitio/data/macro_nombres.v1.json`.

### 5. Vecinas, asesores y búsqueda

```sh
OUTPUT_DIR=data/vecindario python pipeline/generar_vecindario_knn.py  # las 100 más parecidas a cada tesis (FAISS exacto)
python pipeline/generar_atlas_tesis_por_micro.py  # tesis de cada subtema, con sus vecinas → sitio/data/tesis_por_micro/
python services/lab/construir.py todo             # modelo ONNX e índice FAISS del servicio del Laboratorio
python pipeline/generar_vecinas_tesis.py          # vecinas de cada tesis para la ficha del mapa → sitio/data/vecinas/
python pipeline/unificar_asesores.py              # une las variantes de nombre de cada asesor
python pipeline/generar_atlas_busqueda.py         # índices de búsqueda, asesores y años → sitio/data/busqueda/ y otros
python pipeline/generar_atlas_catalogo.py         # número de registro de TESIUNAM de cada tesis → sitio/data/tesis_catalogo.v1.bin
python pipeline/generar_acerca.py                 # datos de las ilustraciones de «Acerca de»
```

`unificar_asesores.py` y `generar_atlas_catalogo.py` leen columnas de la base interna que el
dataset público no trae: las variantes crudas de los nombres de asesor y el número de registro del
catálogo. Se publican para documentar el método. Sin esas columnas, la búsqueda por asesor y el
enlace a la ficha de TESIUNAM quedan con los archivos ya publicados.

### 6. Verificación de privacidad

```sh
python pipeline/limpiar_autores_atlas.py             # corta la mención de autor en todos los títulos publicados
python pipeline/limpiar_autores_atlas.py --verificar # falla si queda alguna; la corre el CI
```

Ningún archivo de `sitio/data/` debe contener nombres de autor. Los de asesor sí se publican.

## Otros archivos

- `titulo_sin_autor.py`: reglas para cortar la mención de responsabilidad de un título del catálogo
  («… / tesis que para obtener el título de …, presenta …»). La usan los pasos 4 a 6.
- `lab_contexto.py`: versión de referencia, fuera de línea, del contexto de datos que calcula el
  servicio del Laboratorio (ubicación, saturación, asesores y tesis parecidas).
