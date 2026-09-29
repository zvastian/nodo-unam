# Worker puerta

Pasos 2 y 3 de [ADR-0015](../../adr/0015-arquitectura-produccion-gratuita.md). Es la única API pública del
Laboratorio: un Cloudflare Worker que verifica la sesión, frena bots, lleva las cuotas y guarda los
análisis y las tesis de cada usuario en D1. Al final llama al [servicio de datos](../lab/README.md),
cuya URL nunca llega al navegador.

JavaScript sin build, como el resto del proyecto; `wrangler` solo empaqueta y corre en local.

## Qué revisa, en orden

0. **Configuración** (`src/seguridad.js`). Con `ENTORNO = "produccion"`, si hay `JWKS_LOCAL`, la
   clave de prueba de Turnstile, una `LAB_CLAVE` de menos de 32 caracteres, algo sin https, falta
   `TURNSTILE_HOSTS` o falta un límite por IP, responde 503 a todo y registra qué variable falla.
1. **CORS** con orígenes explícitos (`ORIGENES`). Sin credenciales de navegador: la sesión va en
   `Authorization: Bearer`, así que no hay CSRF que cuidar.
2. **Límite por IP**, antes de la sesión (binding de Rate Limiting): 120 peticiones por minuto a
   toda la API y 10 por minuto al análisis. Es por ubicación de Cloudflare: frena ráfagas, no es
   una cuota. IPv6 cuenta por su /64. La IP no se guarda. Después de la sesión, **30 escrituras
   por minuto por usuario** (guardar y borrar), para cuidar las 100,000 filas escritas al día de D1.
3. **Sesión.** JWT de Supabase Auth verificado con WebCrypto contra su JWKS, que se guarda 10 minutos
   en caché:
   - solo acepta ES256 o RS256;
   - emisor, audiencia y rol tienen que ser `authenticated`, con 30 s de holgura en `exp` y `nbf`;
   - un usuario anónimo de Supabase (`is_anonymous`) no cuenta como sesión;
   - un `kid` desconocido vuelve a pedir el JWKS, a lo más una vez por minuto;
   - la clave `anon` de Supabase no sirve como sesión.
4. **Tope de tamaño:** 16 KB la entrada del análisis y 512 KB un análisis guardado. El cuerpo se lee
   por partes y se corta al pasar el tope. La **forma** de la entrada (tipos y topes de cada campo,
   los mismos del servicio) se revisa aquí: `400 entrada_invalida` con `campos`, sin gastar cuota.
5. **Turnstile** en la cabecera `X-Turnstile`, en `POST /api/lab/analisis` y `/api/lab/contexto`.
   En producción exige además la acción `analisis` y un dominio de `TURNSTILE_HOSTS`.
6. **Cuota.** Dos UPSERT atómicos: primero el tope del sitio (`TOPE_SITIO_DIA`), luego el del
   usuario (`CUOTA_USUARIO_DIA`).
   - Si el servicio falla o responde 422, la cuota se devuelve.
   - El día es el de la Ciudad de México.
7. **Servicio de datos**, con la clave compartida en `X-Lab-Clave` y 90 s de espera, que cubren el
   arranque en frío. En Modal lleva además el token de proxy (`Modal-Key` y `Modal-Secret`), que
   Modal revisa en su borde, sin despertar el contenedor.
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
| `PUT /api/tesis` | «Guardar las N»: `{tesis: [{id, datos}]}`, hasta 100. Solo inserta las nuevas. Responde `{guardadas}` y, si se llegó al límite, `error: "limite_de_tesis"` |
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

## Pruebas con el servicio simulado y estrés

`pruebas/servicio_simulado.mjs` responde como el servicio de datos: misma forma, exige `X-Lab-Clave`
y tiene un retraso configurable. Usa el contexto de ejemplo del Laboratorio y no necesita el
modelo ni los 3 GB de artefactos. Además cuenta cuántas peticiones atendió a la vez. Con él y
`pruebas/wrangler.ci.jsonc` (sin IA y sin cuenta de Cloudflare), el Worker completo se prueba sin
gastar nada:

- `puerta.test.mjs`: 11 pruebas;
- `estres.mjs [N]`: N estudiantes con su cuenta y su IP piden un análisis a la vez. Falla si
  alguno recibe un 5xx o un 429, si uno de la fila no termina «listo», si una cuenta no gastó
  exactamente 1, o si el servicio atendió más de `FILA_SIMULTANEOS` a la vez;
- `fila.test.mjs`: 4 pruebas, con `wrangler.fila.jsonc`.

`pruebas/ci.sh` corre todo en el CI (job `worker` de `.github/workflows/pruebas.yml`), en Linux.
En Windows, los mismos pasos a mano: `cp .dev.vars pruebas/.dev.vars`, el servicio simulado con la
`LAB_CLAVE` de `.dev.vars`, y `wrangler dev -c pruebas/wrangler.ci.jsonc`.

## Fila (`src/fila.js`)

Un Durable Object, uno solo para todo el sitio (plan gratuito, SQLite). Modal corre un contenedor de 2 núcleos, así que el servicio de datos atiende `FILA_SIMULTANEOS` (2) análisis a la vez.

- **Con lugar:** el análisis corre en vivo por SSE, como siempre. El lugar se suelta en cuanto el servicio de datos responde (la IA no lo ocupa); si el Worker muere sin soltarlo, vence a los 4 minutos.
- **Sin lugar:** `202 {en_fila, id, posicion}`. El análisis se guarda en D1 con `estado = 'fila'` (Mi espacio lo muestra «En la fila») y el Durable Object lo corre en segundo plano (alarma) con el mismo código (`correrIA`), y lo guarda como un análisis normal. Quien llega mientras hay fila espera su turno aunque se libere un lugar.
- **Carril de IA (v4.38.3).** Los de la fila guardan sus datos en cuanto el servicio responde y quedan con `ia_pendiente = 1`.
  - La IA la hace un carril aparte del Durable Object, **de uno en uno y espaciado** (`IA_INTERVALO_S`, 45 s): Groq gratuito da ~8,000 tokens por minuto y un análisis gasta ~5,200. Antes, 50 en fila soltaban 50 llamadas a Groq en el mismo minuto, casi todas caían a Workers AI y agotaban el día.
  - El mismo carril completa los análisis en vivo que se quedaron sin IA por falta de cupo.
  - Si el cupo del día se acabó, se pausa hasta las 06:05 UTC (medianoche de la Ciudad de México).
  - Cede en cuanto alguien entra a la fila de datos.
  - Solo completa lo que el Worker guardó: el análisis en vivo ahora lo guarda el Worker (antes, la página con `POST /api/analisis`), y `POST /api/analisis` nunca marca `ia_pendiente`. Si no, cualquiera obtendría IA gratis sobre un texto inventado.
  - Si una sección falla por otra causa (salida inválida tras el reintento), se deja de intentar.
  - `pruebas/wrangler.ia.jsonc` sirve para probarlo a mano con IA real.
- **Ocupa uno de los 2 guardados desde que entra:** con los 2 llenos, `409 limite_de_guardados` y la cuota se devuelve.
- **Borrarlo antes de su turno** lo saca de la fila y devuelve la cuota; si el servicio de datos falla en segundo plano, se borra y la cuota vuelve.
- **Sin largo máximo** (decisión del usuario): el freno es el tope diario del sitio.
- **Tope del mes (`TOPE_MES`)**, ligado al crédito de Modal: al llegar, `429 mes_agotado` con `vuelve` (el día 1 del mes siguiente) y el Laboratorio se pausa. 6,000 con los 30 USD de crédito de Modal (tarjeta registrada el 29-sep).
- `POST /api/lab/contexto` (solo datos) no entra a la fila: sin lugar, `503 servicio_ocupado`, sin gastar cuota.
- Un objeto que se reinicia a mitad de un análisis lo devuelve al frente de la fila en la siguiente alarma. Cada alarma dura a lo más 12 minutos y se reprograma.

**Pruebas:** `pruebas/fila.test.mjs` (4) corre contra `pruebas/wrangler.fila.jsonc`: un lugar, sin IA (no gasta Groq) y un proxy lento en `:8771` que hace que el análisis que bloquea ocupe su lugar unos segundos seguros. Hace falta una copia de `.dev.vars` en `pruebas/` (ignorada por git; bórrala al terminar), porque `--env-file` choca con el de node:

```sh
cp .dev.vars pruebas/.dev.vars
npx wrangler dev -c pruebas/wrangler.fila.jsonc --persist-to .wrangler/state --port 8787 --ip 127.0.0.1
node --test pruebas/fila.test.mjs
```

Antes de levantar otro `wrangler dev`, detén el anterior **completo** (el proceso `wrangler`, no solo `workerd`): si solo se mata `workerd`, `wrangler` lo vuelve a levantar con su configuración, sigue atendiendo el puerto y los dos comparten el almacenamiento del Durable Object, que se traba. Así pasó al escribir estas pruebas.

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
npm run prueba:seguridad   # 8 pruebas de sesión, límites, entrada, configuración y Turnstile (sin Worker)
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
| `FILA_SIMULTANEOS` | var | Análisis a la vez en el servicio de datos (2); el resto va a la fila |
| `IA_INTERVALO_S` | var | Segundos entre lecturas del carril de IA (45 por defecto: el ritmo de Groq gratuito) |
| `TOPE_MES` | var | Análisis al mes en todo el sitio; al llegar, el Laboratorio se pausa hasta el día 1. 6,000: los 30 USD de crédito de Modal con tarjeta |
| `FILA` | binding | Durable Object de la fila (`src/fila.js`); obligatorio en producción |
| `TOPE_IA_DIA` | var | Análisis con IA al día en todo el sitio: 55, la capacidad gratuita medida en la evaluación |
| `GROQ_TOKENS_DIA`, `WORKERS_AI_NEURONAS_DIA` | var | Presupuesto diario de cada proveedor (180,000 y 9,000) |
| `IA_MODELO_GROQ`, `IA_MODELO_WORKERS` | var | Opcionales; por defecto, `gpt-oss-120b` en los dos |
| `ENTORNO` | var | `local` o `produccion`; en producción activa la revisión de configuración |
| `TURNSTILE_HOSTS` | var | Dominios donde se resuelve el widget (`nodosmap.com,www.nodosmap.com`); obligatorio en producción |
| `MODAL_KEY`, `MODAL_SECRET` | secreto | Token de proxy de Modal para el servicio de datos |
| `LIMITE_IP`, `LIMITE_IP_LAB`, `LIMITE_USUARIO` | binding | Límites por IP y de escrituras por usuario (`ratelimits` en `wrangler.jsonc`); cada entorno los declara |

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
- Interfaz: inicio de sesión, estados sin sesión y cuota agotada, y «mis análisis». Es trabajo de
  diseño, y la estrategia visual se acuerda antes de codificar.
