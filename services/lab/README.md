# Servicio de datos del Laboratorio

Paso 1 de [ADR-0015](../../adr/0015-arquitectura-produccion-gratuita.md). Recibe lo que escribe el
usuario (título, Problematiza, palabras clave…) y devuelve el contexto de datos del análisis, sin IA:
ubicación en el mapa (campo, tema, subtema), saturación, tesis cercanas, asesores y las 100 tesis
más parecidas. La salida tiene el mismo formato que `pipeline/lab_contexto.py`, así que la plantilla
del Laboratorio la lee tal cual.

En producción solo lo llama el [Worker puerta](../puerta/README.md), con la clave compartida `LAB_CLAVE`;
el Worker verifica sesión, Turnstile y cuota. Este servicio
no ve cuentas ni guarda nada, y no escribe textos de tesis en los logs.

## Cómo funciona

1. **Embedding.** La consulta (`query: ` + título, Problematiza y palabras clave normalizados) se
   embebe con `multilingual-e5-large` exportado a ONNX en **float32**, con ONNX Runtime y sin torch.
2. **Búsqueda.** Índice FAISS IVF-SQ8 (4,096 listas, 8 bits) sobre los 609,154 vectores del corpus.
   Recorre 768 listas por búsqueda.
3. **Contexto.** Voto de ubicación, saturación y asesores sobre metadatos y estadísticas
   precalculadas (`meta.parquet`, `precalculo.json`).

## Prueba de aceptación (`evaluar.py`)

Compara contra la referencia: SentenceTransformer en float32 con búsqueda exacta. Usa 8 tesis
inventadas de campos distintos (`casos_evaluacion.json`). El criterio es al menos 95 % del top-100
en común, en promedio y en cada caso.

| Configuración | Top-100 en común (prom. / mín.) | Tiempo |
|---|---|---|
| ONNX float32, búsqueda exacta | 100 / 100 | 260 ms |
| int8 dinámico, búsqueda exacta (**rechazado**) | 84.1 / 72 | 130 ms |
| **Servicio: ONNX float32 + IVF-SQ8, nprobe 768** | **99.1 / 98** | ~400 ms por petición |

Otras variantes medidas y descartadas:
- int8 por canal: 87 %.
- int8 solo en las multiplicaciones: 86 %.
- 8 bits solo en los pesos: 98.6 %, pero tarda 1.1 s.
- SQ8 plano: 99.5 %, pero tarda 750 ms.

## Correr en local

```sh
# 1. Artefactos (una vez; ~3 GB en services/lab/artefactos/, fuera de git). Necesita data/ local.
python services/lab/construir.py todo

# 2. Servicio (entorno propio, sin torch)
cd services/lab
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
LAB_ORIGENES="http://127.0.0.1:8765" .venv/Scripts/python -m uvicorn app.main:app --port 8770

# 3. Prueba de aceptación (con el Python del pipeline)
python services/lab/evaluar.py
```

El Laboratorio (`prototypes/atlas_vecindario_mvp/bocetos/lab/analisis.html`) lo llama en
`http://127.0.0.1:8770`, o en `?api=URL`. Si no responde, usa `datos_ejemplo.json`.

### Con Docker

```sh
docker build -t nodos-lab:local services/lab
docker run --rm -p 8770:8080 -e LAB_ORIGENES="http://127.0.0.1:8765"   -v "$PWD/services/lab/artefactos:/artefactos:ro" nodos-lab:local
```

Da la misma salida que el servicio en Windows, a unos 300 ms por petición y con 3 GiB de memoria.
Con los artefactos montados desde Windows arranca en unos 36 s, porque la lectura a través de WSL
es lenta.

### En Modal (prueba del 26-sep-2026)

Alternativa a Cloud Run: Google rechazó la tarjeta (`OR_BACR2_59`). `modal_app.py` sirve la misma
app sin cambios; los artefactos viven en el volumen `nodos-lab-artefactos` y la clave compartida en
el secreto `nodos-lab`.

```sh
# En Git Bash: MSYS_NO_PATHCONV=1, o las rutas del volumen se convierten en C:/Program Files/Git/...
modal volume put nodos-lab-artefactos meta.parquet /meta.parquet     # uno por archivo, sin model_int8
modal deploy services/lab/modal_app.py
python services/lab/medir_remoto.py https://<workspace>--nodos-lab-servicio.modal.run --frio
```

Medido con `medir_remoto.py` (2 núcleos, 4 GiB, un solo contenedor):

| | Resultado |
|---|---|
| Arranque en frío | 12 a 16 s hasta la primera respuesta (11.4 s cargando modelo e índice del volumen) |
| Análisis despierto | Mediana de 721 ms de ida y vuelta: 299 ms de embedding, 37 ms de contexto y unos 385 ms de red |
| Resultado | Las mismas 100 vecinas y la misma ubicación que el script offline en el caso de ejemplo; solo cambian similitudes en la cuarta cifra decimal, por el SQ8 |
| Sin la clave | 401 |
| Gasto | 0.01 USD por 4 arranques y unos 20 análisis |

Costo estimado: cada minuto despierto cuesta unos 0.2 centavos de dólar. Con 2 minutos despierto tras la última
petición, un análisis aislado cuesta unos 0.5 centavos: el dólar gratis sin tarjeta da unos 200 y
los 30 USD con tarjeta unos 6,000 al mes.

## API

- `GET /salud`: `{"ok": true, "arranque_s": 5.0}`.
- `POST /v1/contexto`: recibe `title` (3 a 400 caracteres), `problematiza` (hasta 2,000),
  `keywords` (hasta 12), `objectives`, `program`, `degree` y `study_period`. Devuelve el contexto y
  `tiempos_ms`. Con una entrada inválida responde 422.

## Variables de entorno

| Variable | Por defecto | Qué es |
|---|---|---|
| `LAB_ARTEFACTOS` | `services/lab/artefactos` | Carpeta de los artefactos |
| `LAB_MODELO` | `model_fp32.onnx` | Modelo dentro de `modelo/` |
| `LAB_NPROBE` | `768` | Listas del índice IVF que se recorren por búsqueda |
| `LAB_HILOS` | `0` (automático) | Hilos de ONNX Runtime |
| `LAB_ORIGENES` | vacío | Orígenes CORS; solo en local, porque en producción llama el Worker |
| `LAB_CLAVE` | vacío | Clave compartida con el [Worker puerta](../puerta/README.md). Si está puesta, `/v1/*` exige la cabecera `X-Lab-Clave` y responde 401 antes de validar el cuerpo. En producción es obligatoria |

## Recursos (medidos en local, Windows)

- Arranque: 5 s con los artefactos en disco. En Cloud Run se suma la descarga de unos 3 GB.
- Memoria: unos 3 GB en uso, así que en Cloud Run se usa la instancia de **8 GiB**, porque 4 GiB
  queda justo.

## Pendiente

- Descarga de artefactos desde Cloud Storage al arrancar, y medir el arranque en frío en Cloud Run
  (paso 4).
- Hoy solo un tercio de las tesis tiene subtema asignado: el script original solo conoce las de los
  temas finos del atlas. Conviene votar campo y tema con las 609,154 (`macroCode` del atlas).
- Calibrar los umbrales `SIM_CERCANA` y `SIM_LEJANA` con el conjunto de evaluación.
