# El Laboratorio como grafo

Formalización del flujo de un análisis del Laboratorio, leída del código de `services/puerta/src/`
(versión 1.0.5, 2026-10-04). Tres niveles: el análisis completo, la llamada a la IA por dentro y el
ciclo de vida del registro en D1. Los diagramas son Mermaid: se ven en GitHub, o en VS Code con la
extensión «Markdown Preview Mermaid Support».

Notación: rectángulo = paso (nodo); rombo = decisión (arista condicional); círculo = bifurcación o
unión en paralelo; doble borde = salida (estado terminal).

## 1. Un análisis, de la petición a la respuesta (`analisis.js`)

```mermaid
flowchart TD
  A[POST /api/analisis] --> B[validar y limpiar entrada]
  B --> C[Turnstile]
  C --> D[detector de inyección: solo registra]
  D --> E{cuota del usuario, del sitio y del mes}
  E -- agotada --> X1[[429: aviso de cuota, cupo o mes]]
  E -- ok --> F{¿lugar libre en el servicio de datos?}
  F -- no --> Q[formar en la fila: D1 estado=fila + turno en el Durable Object]
  Q --> R1[[202: en la fila]]
  F -- sí --> G[pedir contexto a Modal]
  G -- falla --> X2[[error; se devuelve la cuota]]
  G -- ok --> H[soltar el lugar]
  H --> I[léxico de Bloom, sin IA]
  I --> J{¿cupo de IA del día? tope 55}
  J -- no --> P
  J -- sí --> K((bifurcación))
  K --> N1[IA: nota]
  K --> N2[IA: preguntas]
  K --> N3[IA: bloom, si hay objetivos]
  N1 --> M((unión))
  N2 --> M
  N3 --> M
  M --> P{¿cupo agotado y faltan secciones?}
  P -- sí --> S1[guardar con ia_pendiente=1]
  S1 --> T[despertar el carril de IA]
  P -- no --> S2[guardar con ia_pendiente=0]
```

Cada nodo que termina manda su evento por SSE (`lexico`, `datos`, `nota`, `preguntas`, `bloom`,
`ia_agotada`, `error`, `fin`): la página pinta cada sección en cuanto llega.

## 2. Una llamada a la IA por dentro (`ia/proveedores.js`, `pedirIA`)

Aquí están los ciclos: la espera ante el límite por minuto y el reintento con retroalimentación.

```mermaid
flowchart TD
  S[intento i] --> R1{reservar tokens de Groq}
  R1 -- cabe --> G[llamar a Groq]
  G -- ok --> V
  G -- "429 por minuto, espera ≤ 20 s" --> W[dormir 2, 5 o 10 s] --> R1
  G -- 429 por día --> MD[marcar Groq agotado] --> R2
  G -- "otro error, o 429 sin esperas restantes" --> R2
  R1 -- no cabe --> R2{reservar neuronas de Workers AI}
  R2 -- no cabe --> AG[[IAAgotada]]
  R2 -- cabe --> WA[llamar a Workers AI] --> V
  V{preparar, validar esquema y revisar}
  V -- válido --> OK[[datos de la sección]]
  V -- "inválido, i = 0" --> FB[errores como retroalimentación] --> S
  V -- "inválido, i = 1" --> INV[[IAInvalida]]
```

## 3. Ciclo de vida del análisis guardado (D1 + Durable Object `Fila`)

```mermaid
stateDiagram-v2
  [*] --> EnFila: sin lugar libre
  [*] --> Completo: en vivo, las 3 secciones
  [*] --> Pendiente: en vivo, cupo agotado
  [*] --> Reintento: en vivo, una sección inválida o con error
  [*] --> NoGuardado: ya tenía 2 guardados
  EnFila --> Pendiente: su turno, Modal responde
  EnFila --> [*]: Modal falla o el usuario lo borra
  Pendiente --> Pendiente: cupo agotado, pausa hasta las 06h05 UTC
  Pendiente --> Completo: el carril completa lo que falta
  Pendiente --> Reintento: salida inválida o error, intentos ≤ 2
  Reintento --> Pendiente: pasan 6 horas
  Pendiente --> Parcial: tercer fallo
  note right of Parcial: terminal a propósito, con el motivo guardado en resultado.fallos
  NoGuardado --> [*]: si faltaba IA, nunca llega
```

Hasta la 1.0.5, `Parcial` era un **sumidero** al que se llegaba con el primer fallo: solo la falta de
cupo dejaba pendiente un análisis (`r.agotada`). Al 4-oct-2026 había 15 parciales y 18 sin IA y sin
pendiente (de 342 desde el 1-oct). Desde la 1.0.6 (`planIA` en `analisis.js`), un fallo que no es por
cupo cuenta un intento, espera `IA_REINTENTO_HORAS` (6) y vuelve a la fila del carril; tras
`IA_REINTENTOS` (2) reintentos queda en `Parcial`, ya con el motivo guardado. En la base, `Reintento`
es `ia_pendiente = 1` con `ia_siguiente` en el futuro.

## Correspondencia con LangGraph

| LangGraph | NodOS |
|---|---|
| `StateGraph` y su estado | `entrada`, `lexico`, `datos`, `ia`, `costos` (variables de `analisisSSE`/`correrIA`) |
| nodo | cada función: `limpiarEntrada`, `pedirContexto`, `clasificarObjetivos`, `pedirIA`… |
| `add_conditional_edges` | los `if`: cuota, lugar, cupo de IA, proveedor, validez |
| `Send` (bifurcación en paralelo) | `Promise.all` de las 3 tareas (`analisis.js:99`) |
| ciclo con condición de salida | reintento con retroalimentación (`intento < 2`) y espera ante 429 |
| `checkpointer` (persistencia y reanudación) | D1 (`estado`, `ia_pendiente`) y el almacenamiento del Durable Object (cola, lugares, en curso, pausa) |
| `interrupt` (pausa para un humano) | no hay |
| nodo agente (el LLM elige la arista) | no hay: todas las aristas las decide el código |
