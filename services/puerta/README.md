# Worker puerta

Pasos 2 y 3 de [ADR-0015](../../adr/0015-arquitectura-produccion-gratuita.md). Es la única API pública del
Laboratorio: un Cloudflare Worker que verifica la sesión, frena bots, lleva las cuotas y guarda los
análisis y las tesis de cada usuario en D1. Al final llama al [servicio de datos](../lab/README.md),
cuya URL nunca llega al navegador.

JavaScript sin build, como el resto del proyecto; `wrangler` solo empaqueta y corre en local.

## Qué revisa, en orden

1. **CORS** con orígenes explícitos (`ORIGENES`). Sin credenciales de navegador: la sesión va en
   `Authorization: Bearer`, así que no hay CSRF que cuidar.
2. **Sesión.** JWT de Supabase Auth verificado con WebCrypto contra su JWKS, que se guarda 10 minutos
   en caché:
   - solo acepta ES256 o RS256;
   - emisor, audiencia y rol tienen que ser `authenticated`, con 30 s de holgura en `exp` y `nbf`;
   - un `kid` desconocido vuelve a pedir el JWKS, a lo más una vez por minuto;
   - la clave `anon` de Supabase no sirve como sesión.
3. **Tope de tamaño:** 16 KB la entrada del análisis y 512 KB un análisis guardado.
4. **Turnstile** en la cabecera `X-Turnstile`, solo en `POST /api/lab/contexto`, que es lo costoso.
5. **Cuota.** Dos UPSERT atómicos: primero el tope del sitio (`TOPE_SITIO_DIA`), luego el del
   usuario (`CUOTA_USUARIO_DIA`).
   - Si el servicio falla o responde 422, la cuota se devuelve.
   - El día es el de la Ciudad de México.
6. **Servicio de datos**, con la clave compartida en `X-Lab-Clave` y 90 s de espera, que cubren el
   arranque en frío.
   - Un 422 del servicio llega al cliente solo con los nombres de los campos inválidos. El detalle
     de FastAPI repite el texto enviado.

Toda consulta a D1 filtra por el `sub` del token, nunca por un id que mande el cliente. Los logs
nunca llevan el cuerpo de una petición.

## API

Todas, salvo `salud`, piden `Authorization: Bearer <jwt de Supabase>`. Los errores llegan como
`{"error": "<código>"}`.

| Ruta | Qué hace |
|---|---|
| `GET /api/salud` | `{"ok": true}` |
| `GET /api/yo` | Correo, análisis de hoy, análisis guardados y número de tesis guardadas |
| `POST /api/lab/analisis` | **Análisis completo por SSE** (con `X-Turnstile`): datos y las 3 llamadas de IA. Ver abajo |
| `POST /api/lab/contexto` | Solo el contexto de datos, en JSON (con `X-Turnstile`). Cabecera `X-Cuota-Restante` |
| `GET /api/analisis` | Análisis guardados: `id`, `titulo` y `creado` |
| `POST /api/analisis` | Guarda `{entrada, resultado}`. Con 2 guardados responde 409 `limite_de_guardados` |
| `GET` y `DELETE /api/analisis/:id` | Uno de los análisis propios; si es ajeno, 404 |
| `GET /api/tesis` | Tesis del atlas guardadas |
| `PUT` y `DELETE /api/tesis/:id` | Guarda o quita una tesis. Es idempotente y admite hasta `MAX_TESIS_GUARDADAS` |
| `DELETE /api/cuenta` | Borra los datos del usuario en D1 y, con `SUPABASE_SERVICE_KEY`, su identidad en Supabase |

Códigos: 401 `sin_sesion` (con `motivo`), 403 `turnstile_*`, 413, 422 `entrada_invalida` (con
`campos`), 429 `cuota_diaria_agotada` o `cupo_del_sitio_agotado`, 503 `servicio_no_disponible`.

## Análisis con IA (paso 3)

`POST /api/lab/analisis` responde `text/event-stream`. Los eventos llegan en este orden:
- `lexico`: el Bloom por léxico de `compartido/bloom.js`;
- `datos`: el contexto del servicio de datos;
- `nota`, `bloom` y `preguntas`, según termina cada uno, porque van en paralelo;
- `ia_agotada` (`{motivo}`) y `error` (`{seccion, error}`), si ocurren;
- `fin` (`{cuota_restante, ia}`): proveedor, intentos y costo de cada sección.

Si el servicio de datos falla, la respuesta es un error HTTP normal y la cuota se devuelve. Si falla la IA, la cuota no se devuelve: los datos ya llegaron.

- **Proveedores** (`src/ia/proveedores.js`). El mismo `gpt-oss-120b`, con esfuerzo de razonamiento bajo:
  - primero Groq. Ante un 429 por minuto espera 2, 5 y 10 s. Solo un límite diario lo marca agotado. Si Groq falla por otra causa, esa llamada va al respaldo;
  - después Workers AI, hasta `WORKERS_AI_NEURONAS_DIA`:
    - sin `response_format`, que con ese modelo provocaba bucles de espacios;
    - `max_tokens` de 2,500;
    - si Cloudflare responde `4006`, el cupo cuenta como agotado;
  - si los dos están agotados, `ia_agotada`;
  - los contadores de los proveedores van por día UTC, que es cuando Cloudflare reinicia las neuronas.
- **Contadores** en `cuota_sitio`: `groq_tokens`, `workers_ai_neuronas` e `ia`. Este último es el tope de análisis con IA al día (`TOPE_IA_DIA`).
- **Prompts** (`src/ia/prompts.js`):
  - el texto del usuario va como dato en `<entrada_usuario>`;
  - el modelo recibe señales del corpus (campos, saturación, cobertura de palabras clave y tesis más parecidas);
  - Bloom recibe el nivel del léxico y no lo cambia.
- **Validación** (`src/ia/esquemas.js`, `src/analisis.js`):
  - esquema propio para cada sección;
  - en Bloom, además, que los objetivos revisados empiecen con un verbo del léxico, suban de nivel, no incluyan Recordar y no pongan Crear sin Evaluar;
  - en preguntas, tipos distintos entre sí;
  - un reintento con los errores como retroalimentación.

Medido el 26-sep-2026 con el caso México-China:

| | Groq | Workers AI |
|---|---|---|
| Tiempo de las 3 llamadas | ~2 s (mediana) | ~25 s (mediana) |
| Costo por análisis (mediana, 11 casos) | ~6,000 tokens | ~340 neuronas |
| Capacidad diaria con los topes | ~30 análisis (180,000 tokens) | ~26 análisis (9,000 neuronas) |
| Límite por minuto (plan gratuito) | 8,000 tokens: ~1 análisis por minuto | — |

`node pruebas/analisis_sse.mjs [entrada.json]` corre un análisis completo y muestra cada evento con su tiempo.

### Evaluación (`evaluacion/`)

- `casos_ia.json`: 11 casos.
  - 8 de campos distintos, con objetivos que cubren los casos límite del léxico.
  - 3 adversos: inyección de prompt, entrada mínima y objetivos que no son objetivos.
- `evaluar_ia.mjs --etiqueta X [--casos a,b] [--pausa 45]`: corre los casos contra el Worker, aplica chequeos automáticos y guarda la corrida en `resultados_ia.json`. Los chequeos:
  - secciones completas y reintentos;
  - periodo coherente con la entrada;
  - años fuera del periodo;
  - fuga de inyección;
  - citas inventadas;
  - idioma.
- `resultados_ia.json`: todas las corridas, más la revisión cualitativa (`revision`), con puntuaciones de la v1 a la v2, hallazgos y pendientes.

Cada corrida completa gasta unos 65,000 tokens de Groq, un tercio del día: para comprobar un cambio basta con 2 o 3 casos.

**Cron diario (9:17 UTC):**
- borra las cuotas de hace más de 7 días;
- toca `auth/v1/health` de Supabase para que el plan gratuito no pause el proyecto. Falta confirmar
  que eso cuenta como actividad (ver «Pendiente»).

## D1

`migrations/0001_inicial.sql` tiene cuatro tablas: `analisis`, `tesis_guardadas`, `cuota_diaria` y
`cuota_sitio`. En `cuota_sitio`, el tipo `datos` es el único que se usa hoy; en el paso 3 se suman
`groq` y `workers_ai`.

## Correr en local

Hace falta el servicio de datos en `:8770` (ver su README).

```sh
cd services/puerta
npm install
npm run claves    # claves ES256 de prueba en lugar de Supabase, y .dev.vars
npm run migrar    # D1 local, en .wrangler/
npm run dev       # http://127.0.0.1:8787
npm run prueba    # 8 pruebas de integración contra el Worker y el servicio
npm run prueba:bloom   # 12 pruebas del léxico de Bloom (sin Worker)
```

- `npm run claves` escribe `.dev.vars` con:
  - el JWKS local (`JWKS_LOCAL`) y su emisor;
  - la clave compartida con el servicio;
  - la clave secreta de prueba de Turnstile, que siempre aprueba.
- Para que el servicio exija la clave, se arranca con `LAB_CLAVE=<la de .dev.vars>`. Sin ella
  acepta cualquier llamada, y así el boceto del Lab puede llamarlo directo en local.

## Variables

| Variable | Tipo | Qué es |
|---|---|---|
| `ORIGENES` | var | Orígenes CORS, separados por coma. En producción, con la API en el mismo origen, solo hace falta para las previsualizaciones |
| `LAB_URL` | var | URL del servicio de datos (Cloud Run) |
| `SUPABASE_URL` | var | `https://<proyecto>.supabase.co`; de ahí salen el JWKS y el emisor |
| `JWT_EMISOR` | var | Solo si el emisor no es `SUPABASE_URL/auth/v1` |
| `CUOTA_USUARIO_DIA`, `TOPE_SITIO_DIA` | var | 2 y 500 |
| `MAX_ANALISIS_GUARDADOS`, `MAX_TESIS_GUARDADAS` | var | 2 y 500 |
| `TURNSTILE_SECRET` | secreto | Clave secreta de Turnstile |
| `LAB_CLAVE` | secreto | Clave compartida con el servicio de datos |
| `SUPABASE_SERVICE_KEY` | secreto | Opcional. Solo para borrar la identidad al borrar la cuenta |
| `SUPABASE_ANON_KEY` | var | Opcional. Para el cron que evita la pausa |
| `JWKS_LOCAL` | solo local | JWKS en JSON, en lugar de pedirlo a Supabase |
| `GROQ_API_KEY` | secreto | Clave de Groq, con Zero Data Retention activado en su consola |
| `TOPE_IA_DIA` | var | Análisis con IA al día en todo el sitio: 55, la capacidad gratuita medida en la evaluación |
| `GROQ_TOKENS_DIA`, `WORKERS_AI_NEURONAS_DIA` | var | Presupuesto diario de cada proveedor (180,000 y 9,000) |
| `IA_MODELO_GROQ`, `IA_MODELO_WORKERS` | var | Opcionales; por defecto, `gpt-oss-120b` en los dos |

## Pendiente

- Revisión humana de las salidas de derecho, historia_arte y medicina en `evaluacion/resultados_ia.json`.
- Bajar los tokens por análisis (hoy ~6,000 en Groq) para ganar capacidad gratuita.

- **Crear el proyecto de Supabase.** Lo hace el usuario:
  - Google y enlace mágico como métodos;
  - claves de firma asimétricas (ES256), para que el JWKS publique la clave pública;
  - SMTP de Resend;
  - poner `SUPABASE_URL`. Después, probar con un token real.
- Confirmar que tocar `auth/v1/health` evita la pausa del plan gratuito, o cambiarlo por una consulta
  a la base.
- Crear la base D1 remota (`wrangler d1 create nodos`) y poner su `database_id`. Va con el despliegue
  (paso 4).
- Límite de tasa por IP (binding de Rate Limiting de Workers) para las rutas sin Turnstile.
- Interfaz: inicio de sesión, estados sin sesión y cuota agotada, y «mis análisis». Es trabajo de
  diseño, y la estrategia visual se acuerda antes de codificar.
