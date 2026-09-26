# RFC-0002: Arquitectura de producción gratuita para NodOS (atlas + Laboratorio)

- **Estado**: En discusión (abierto 2026-09-25). Es una propuesta, no una decisión. Cuando se resuelva, cada pieza se registra como ADR; en particular, un ADR nuevo reemplazará a ADR-0001, que sigue «Propuesto».
- **Autor de la propuesta**: investigación de la sesión 2026-09-25, con las capas gratuitas verificadas en la documentación oficial ese día (fuentes al final).

## Contexto

NodOS tiene dos partes con necesidades muy distintas:

1. **El atlas**: 100 % estático.
   - `index.html` y `data/` suman 186 MB en 3,230 archivos; el mayor pesa 24.4 MB.
   - Todo lo que muestra está precalculado (ADR-0014).
   - No necesita servidor.
2. **El Laboratorio**: recibe un texto libre (título, Problematiza, objetivos) y necesita cómputo por petición.
   - **Embeber** la consulta con el mismo `intfloat/multilingual-e5-large` del corpus. Otro modelo pone la consulta en otro espacio vectorial y rompe la búsqueda.
   - **Buscar** las 100 vecinas entre 609,154 vectores de 1024 dimensiones.
   - **Calcular el contexto**, que hoy hace `pipeline/lab_contexto.py`: votos de campo, tema y subtema, saturación, asesores y parecidas.
   - **Hacer 3 llamadas a un LLM**: nota, Bloom y preguntas.
   - **Limitar el uso** a 2 análisis por día y 2 guardados.

**Restricción del usuario:** costo cero.

**Hallazgo de la investigación:** en 2026 las capas gratuitas cambiaron varias veces, a veces sin aviso.
- Hugging Face exige plan PRO para crear Spaces con Docker o Gradio.
- Oracle redujo a la mitad su ARM gratuito: 2 OCPU y 12 GB desde agosto.
- Cerebras eliminó su capa gratuita.
- Groq sacó los modelos Llama de su capa gratuita el 16 de agosto.

**Consecuencia de diseño:** la arquitectura debe poder mudarse de proveedor cambiando configuración, no reescribiendo código.

## Propuesta

```
Navegador
 ├── Sitio estático: atlas + interfaz del Lab ─────────── Cloudflare Pages
 │      └── (a futuro) datos grandes ──────────────────── Cloudflare R2
 └── /api/* ─── Cloudflare Worker «puerta» ─────────────── Workers (gratis)
                  ├── Turnstile (anti-bots), CORS, tope de tamaño
                  ├── sesión: verifica JWT ─────────────── Supabase Auth
                  ├── cuota, análisis y tesis guardadas ── D1
                  ├── Parte de datos ──► Servicio del Lab ─ Google Cloud Run
                  │                        e5-large ONNX int8 + índice FAISS SQ8
                  │                        + metadatos (desde Cloud Storage)
                  └── Parte de IA ────► LLM ─────────────── Groq (gpt-oss / qwen)
                                                           respaldo: Workers AI
```

### 1. Sitio estático: Cloudflare Pages

- **Ancho de banda:** ilimitado y gratis. Importa porque cada visita descarga varios MB de datos.
- **Límites:** 20,000 archivos por sitio (hoy son 3,230) y 25 MiB por archivo (el mayor pesa 24.4 MB, justo debajo), con 500 compilaciones al mes.
- **Cabeceras:** el archivo `_headers` (hasta 100 reglas) permite CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy` y `Permissions-Policy`.
- **R2 solo cuando haga falta:** 10 GB gratis y sin costo de egreso. Hace falta si algún archivo pasa de 25 MiB o si se publica el vecindario completo. Así se resuelve ADR-0001.
- **Descartados:**
  - GitHub Pages: no admite cabeceras propias y tiene límites de 1 GB por sitio y unos 100 GB al mes.
  - Netlify y Vercel: 100 GB al mes, y Vercel Hobby es solo para uso no comercial.

### 2. Puerta de la API: Cloudflare Worker

- **Límites del plan gratuito:** 100,000 peticiones al día y 10 ms de CPU por petición. Esperar respuestas de otros servicios no cuenta como CPU.
- **Única API pública.** Se encarga de:
  - CORS con orígenes explícitos;
  - tope de tamaño de entrada;
  - verificar **Turnstile** (gratis);
  - llevar la cuota por dispositivo o IP (hash) en **D1**: gratis con 5 GB, 5 millones de lecturas y 100,000 escrituras al día;
  - ocultar la URL del servicio de cómputo, que así no puede usarse directamente para gastar su cuota.
- **Orquesta la parte de IA:** llama al LLM y transmite al navegador por SSE. El léxico de Bloom en JavaScript se comparte entre el formulario y el Worker.

### 3. Servicio del Lab, parte de datos: Google Cloud Run

- **Qué es:** FastAPI en un contenedor Docker estándar que corre sin cambios en Cloud Run, Modal, Oracle o cualquier VPS.
  - Carga `multilingual-e5-large` exportado a **ONNX int8** (~0.6 GB) y el índice **FAISS SQ8** de 609,154 × 1024 (~0.6 GB, en vez de 2.5 GB en float32).
  - Carga también los metadatos que usa `lab_contexto.py`.
  - Todo baja al arrancar de **Cloud Storage**, que da 5 GB gratis en regiones de EE. UU.
- **Capa siempre gratuita:** 2 millones de peticiones, 180,000 vCPU-segundos y 360,000 GiB-segundos al mes, y 1 GB de salida.
  - Con 2 vCPU y 4 GiB son unas **25 horas de cómputo activo al mes**.
  - Si el análisis de datos dura unos 2 s (estimado; medirlo), alcanza para decenas de miles de análisis al mes.
  - Escala a cero: sin tráfico no consume cuota.
- **Imagen ligera:** el código va en Artifact Registry (0.5 GB gratis) y los pesos del modelo en Cloud Storage.
- **Requiere cuenta de facturación con tarjeta.** Para no pagar por sorpresa:
  - `max-instances` en 1 o 2;
  - alerta de presupuesto en 1 USD.
- **Arranque en frío** de ~10 a 30 s, estimado por cargar ~1.2 GB. Se mitiga con *startup CPU boost*. La interfaz ya anima la espera: la mascota «ubicando tu tesis entre 609,154».
- **Riesgo de la cuantización:** un modelo int8 contra un corpus embebido en float32 puede cambiar a las vecinas. **Prueba de aceptación:** coincidencia de al menos 95 % en el top-100 frente a float32, con el conjunto de evaluación.

### 4. Parte de IA: Groq, con Workers AI de respaldo

- **Groq** (sin tarjeta):
  - Límites por modelo: gpt-oss-120b, gpt-oss-20b y qwen3.8-27b tienen cada uno 30 peticiones por minuto, 1,000 al día y **200,000 tokens al día**.
  - Repartir las 3 llamadas entre modelos distintos da unos **50 a 60 análisis completos al día** (estimado con 3 a 4 mil tokens por llamada).
  - **No entrena con los datos** por contrato. Tiene **Zero Data Retention**, que hay que activar en la consola para los textos de tesis.
- **Respaldo:** Cloudflare Workers AI, con 10,000 neuronas al día y gpt-oss-120b disponible. Su precio de lista es de 0.35 USD por millón de tokens de entrada y 0.75 USD por millón de salida, así que si hiciera falta pagar sería del orden de medio centavo de dólar por análisis.
- **Una sola interfaz:** Groq, Workers AI y OpenRouter hablan la API compatible con OpenAI. Cambiar de proveedor es cambiar la URL, la clave y el modelo.
- **Descartados:**
  - Gemini gratis: usa los datos para entrenar y revisión humana. Inaceptable para tesis de usuarios.
  - Cerebras: ya no tiene capa gratuita.
  - Los modelos gratuitos de OpenRouter: su privacidad depende del proveedor que toque.
- **Cuando se agote el cupo:** el Lab entrega la parte de datos y marca la de IA como «cupo del día agotado».
- **Reemplazos de Cerebras evaluados (25-sep-2026):** ninguno es a la vez gratuito, apto para producción y respetuoso de los datos.
  - Mistral Experiment: unos mil millones de tokens al mes, pero según varias fuentes exige aceptar que entrenen con los datos. Su documentación oficial no lo aclara; confirmarlo en la consola.
  - NVIDIA API Catalog: sus términos lo limitan a pruebas, no producción.
  - Cohere: prueba sin uso comercial.
  - OpenRouter: sus modelos gratis permiten 50 peticiones al día, o 1,000 tras una compra única de 10 USD, pero la política de datos depende del proveedor.
  - GitHub Models y SambaNova: cerrados.
  - **Capacidad gratuita realista:** Groq (unos 60 análisis al día) más Workers AI (unos 20 más), **unos 80 análisis diarios**, del orden de 2,400 al mes. Al pasar de eso, cada análisis cuesta del orden de medio centavo de dólar.

### 5. Cuentas de usuario desde la primera versión

**Decisión del usuario (2026-09-25):** las cuentas son una función central. Guardan MI TESIS, los análisis y las tesis del atlas, y los sincronizan entre dispositivos. Un borrador anterior de este RFC proponía empezar sin cuentas, por privacidad y simplicidad; se descartó.

- **Identidad: Supabase Auth**, solo para identidad (plan gratuito: 50,000 usuarios activos al mes).
  - Resuelve lo delicado del inicio de sesión: OAuth, sesiones, renovación de tokens, enlaces mágicos y protección contra fuerza bruta.
  - **Métodos:** Google, más enlace mágico por correo para quien no quiera usar Google. Sin contraseñas.
  - **Correo propio:** el de Supabase tiene un tope muy bajo de envíos; se usa Resend (3,000 correos al mes y 100 al día gratis).
  - **Pausa del proyecto:** el plan gratuito lo pausa tras 7 días sin actividad en la base. Los inicios de sesión y las renovaciones cuentan como actividad; como seguro, un *cron* diario del Worker (gratis) hace una consulta ligera.
- **Datos: D1**, que da 5 GB frente a los 500 MB de Postgres en Supabase.
  - Tablas: `analisis` (máximo 2 por usuario), `tesis_guardadas` y `cuota_diaria`, todas con el id de usuario de Supabase.
  - El Worker verifica el JWT de Supabase con sus claves públicas (JWKS; verificación ES256 con WebCrypto, que gasta menos de 1 ms de CPU) y solo lee o escribe filas de ese usuario.
- **Cuota:**
  - por cuenta: 2 análisis nuevos al día y 2 guardados;
  - Turnstile, para frenar cuentas en masa hechas por bots.
- **Sin sesión** se puede explorar el atlas completo; el Laboratorio pide iniciar sesión.

**Lo que las cuentas agregan y hay que atender:**
- **El servidor guarda correo y textos de tesis.** Obliga a:
  - un aviso de privacidad completo, con derechos ARCO;
  - un botón «borrar mi cuenta y mis datos» que borre de verdad en Supabase y D1;
  - retención definida;
  - ningún texto de tesis en los logs.
- **Superficie de ataque nueva:** cada consulta a D1 filtra por el usuario del token, nunca por un id que mande el cliente. Hay que probar el acceso cruzado (IDOR).

**Alternativa, todo en Cloudflare:** Better Auth en el Worker con D1.
- Ventajas: un solo proveedor y sin riesgo de pausa.
- En contra: más código propio de seguridad. Además, con 10 ms de CPU por petición en el plan gratuito, las contraseñas quedan fuera (su hash no cabe) y solo sirve OAuth.

### 6. Operación

- **CI/CD con GitHub Actions**, gratis y sin límite de minutos porque el repo es público:
  - pruebas del pipeline, incluida la de privacidad de títulos;
  - pruebas de extremo a extremo con Chrome headless (`tools/cdp.mjs`);
  - despliegue a Pages con `wrangler`;
  - despliegue a Cloud Run con *Workload Identity Federation*, sin claves JSON.
  - Gratis también: CodeQL, Dependabot y escaneo de secretos.
- **Observabilidad:**
  - Cloudflare Web Analytics, sin cookies ni banner;
  - Sentry, plan Developer gratuito;
  - UptimeRobot, gratis;
  - alertas de presupuesto de Google Cloud;
  - el panel de uso de Groq.
- **Dominio:**
  - el subdominio `*.pages.dev` es gratis;
  - el paquete de estudiante de GitHub da un dominio gratis por un año;
  - un `.com` en Cloudflare Registrar cuesta ~10 USD al año, y es el único gasto que se recomienda.
- **Correo:** Cloudflare Email Routing (gratis) reenvía `contacto@` a una cuenta de Gmail solo del proyecto, no a la personal; se responde con «Enviar como». Requiere dominio propio o de eu.org. Detalle en `development.md`, «Correo de contacto del proyecto (2026-09-25)».
- **Secretos:**
  - las claves de Groq van como secretos del Worker y de Cloud Run (Secret Manager: 6 versiones gratis);
  - nunca en el repo, que es público.

### 7. Servidores y Docker

**No hay ningún servidor propio que rentar ni mantener.** Nadie administra un sistema operativo, parches, firewall, certificados ni respaldos de una máquina. Para un proyecto de una persona, ese mantenimiento es el mayor riesgo de seguridad.

**Tres clases de cómputo:**

| Pieza | Qué es | Quién administra la máquina |
|---|---|---|
| Sitio (Pages) | Archivos estáticos en la CDN | Cloudflare |
| Puerta de la API (Worker) | Código que corre por petición, sin servidor | Cloudflare |
| Servicio del Lab (Cloud Run) | **Nuestro contenedor Docker**, que Google arranca cuando llega una petición y apaga sin tráfico | Google |

**El contenedor del Lab** (un `Dockerfile`, la misma imagen en local y en producción):
- `python:3.12-slim`, FastAPI con uvicorn, `onnxruntime`, `faiss-cpu` y el código portado de `lab_contexto.py`;
- al arrancar descarga de Cloud Storage el modelo e5-large en ONNX int8 y el índice FAISS SQ8, así que la imagen queda chica;
- corre como usuario sin privilegios, con endpoint de salud y configuración por variables de entorno;
- se muda sin cambios a AWS Lambda, Modal o un VPS.

**Desarrollo local** con Docker Compose (ADR-0002):
- el contenedor del Lab;
- `wrangler dev` para el Worker, Pages y D1 locales;
- opcionalmente, Supabase local con su CLI, que también usa Docker.

**Cuándo convendría un servidor propio:** si el tráfico rebasa la capa gratuita de Cloud Run o los arranques en frío molestan. Un VPS de unos 5 USD al mes correría el mismo contenedor.

### 8. Presupuesto de IA con tope duro

- **Sin gastar:** Groq más Workers AI, unos 80 análisis al día.
- **Si hace falta pagar, con tope** (5 USD al mes rinden unos 1,000 a 1,700 análisis más, a 0.3-0.5 centavos cada uno):
  - **OpenRouter prepagado** con ZDR obligatorio: no se puede gastar más que el saldo cargado y no hace cargos automáticos.
  - **Groq de pago:** su tope mensual bloquea la API al llegar, con 10 a 15 minutos de retraso en la medición.
- **Tope propio, que es la defensa real:**
  - el Worker cuenta los análisis del día de todo el sitio en D1 y corta al llegar al límite;
  - la cuota por usuario (2 al día) se suma a ese tope global.
- El dominio (10.44 USD **al año**) y la IA con tope (hasta 5 USD **al mes**) no se excluyen. Se decide por separado.

### 9. Si no se compra dominio

| Opción | Ejemplo | A favor | En contra |
|---|---|---|---|
| Subdominio de Cloudflare Pages | `nodostesis.pages.dev` | Inmediato, gratis, HTTPS. La API va en el mismo origen (`/api/*`, Pages Functions): sin CORS y con cookies simples | Mudar después rompe enlaces y obliga a reconfigurar OAuth. Sin correo `contacto@` propio |
| eu.org | `nodos.eu.org` | Dominio real y gratuito, mantenido por voluntarios desde 1996. Admite DNS de Cloudflare y correo | La aprobación manual puede tardar semanas |
| is-a.dev, js.org | `nodos.is-a.dev` | Gratis, por pull request | Pensados para sitios personales o proyectos de JavaScript; puede no cumplir sus reglas |
| Paquete de estudiante de GitHub | `.me` u otros | Gratis el primer año | Después se renueva a precio normal |

## Alternativas consideradas para el cómputo del Lab

| Opción | Gratis | A favor | En contra |
|---|---|---|---|
| **Google Cloud Run** (propuesta) | Siempre, con tarjeta | Administrado, escala a cero, capa estable desde hace años, contenedor estándar | Arranque en frío; exige tarjeta |
| Modal | 30 USD al mes en créditos (Starter) | Python nativo, *snapshots* de memoria que acortan el arranque | Créditos, no capa gratuita: puede cambiar. Verificar si pide tarjeta |
| AWS Lambda | Siempre: 1 M de peticiones y 400,000 GB-s al mes; con tarjeta | Da algo más de cómputo que Cloud Run (~100,000 s al mes con 4 GB); contenedores de hasta 10 GB | Cada instancia atiende **una** petición a la vez: con análisis simultáneos, cada uno arranca en frío y recarga ~1.2 GB. Almacenamiento gratis solo con créditos que caducan, así que el modelo va dentro de la imagen (ECR ~0.10 USD por GB al mes). Desde julio de 2025 las cuentas nuevas empiezan en un plan de créditos que caduca a los 6 meses; hay que pasar al plan de pago para conservar la capa permanente. Queda como **plan B** con el mismo contenedor |
| Oracle Always Free (ARM) | Siempre, con tarjeta | Siempre encendido, 12 GB de RAM, sin arranque en frío | Recortado a la mitad en 2026 sin anuncio. Reclama instancias ociosas (CPU, red y memoria bajo 20 % en 7 días; mantener el índice en RAM lo evita). Servidor a mantener y parchar |
| Hugging Face ZeroGPU | Sin tarjeta | Gratis de verdad | Solo Gradio, 3.5 a 5 minutos de GPU al día y colas. Sirve de demo o respaldo |
| Hugging Face Space con Docker | **Ya no** | — | Exige PRO desde 2026 |
| Cloudflare Vectorize | **No** para este tamaño | Integrado con Workers | Almacena gratis 5 M de dimensiones y el índice necesita 624 M. Además no ofrece e5-large |
| Qdrant Cloud Free | Sí (1 GB de RAM) | Base vectorial administrada | Suspende tras una semana sin uso; no cabe holgado; su inferencia gratis no incluye e5-large |
| Créditos del paquete de estudiante | Azure 100 USD, DigitalOcean 200 USD por un año | Sirven de colchón | Temporales; no son base de una arquitectura |

## Riesgos y mitigaciones

- **Una capa gratuita cambia** (ya pasó cuatro veces en 2026):
  - contenedor estándar y API compatible con OpenAI;
  - los proveedores van en la configuración;
  - un ADR registra el plan B de cada pieza.
- **Abuso o gasto inesperado:**
  - Turnstile y la cuota en el Worker;
  - `max-instances` en Cloud Run;
  - alertas de presupuesto;
  - con las claves solo en el servidor, el navegador nunca habla directo con el LLM.
- **Privacidad:**
  - el texto de la tesis pasa por Cloudflare, Google, Groq y Supabase; se declaran como encargados en el aviso de privacidad;
  - ZDR activado en Groq;
  - ningún cuerpo de petición en los logs;
  - los análisis guardados se borran con la cuenta.
- **Arranque en frío:** la espera se comunica en la interfaz. Si molesta, un ping programado en horario diurno mantiene la instancia caliente.

## Decisiones pendientes de este RFC

- [x] Cloud Run aceptado aunque pida tarjeta (usuario, 25-sep-2026), con `max-instances` bajo y alerta de presupuesto. Plan B: AWS Lambda con el mismo contenedor.
- [x] Cuentas desde la primera versión, con Supabase Auth: Google y enlace mágico por correo (usuario, 25-sep-2026).
- [ ] Dominio: el usuario lo reconsidera frente a pagar IA con tope (25-sep-2026). Ver secciones 8 y 9.
  - Cloudflare Registrar vende el `.com` a 10.44 USD al año sin margen; sube a 11.15 USD el 1-nov-2026 y conviene comprar antes.
  - `.com.mx` cuesta unos 14 EUR el primer año y 26 EUR al renovar; `.mx`, 40 y 45 EUR (DonDominio).
  - Ya ocupados: nodos.com, .org, .app, .dev y .xyz.
  - Libres según RDAP el 25-sep-2026: nodostesis.com, nodosatlas.com y atlasnodos.com.
  - Evitar «unam» en el dominio: parecería sitio oficial (`CLAUDE.md`).
- [ ] Medir antes de aceptar:
  - tiempo de arranque en frío y latencia de la parte de datos en Cloud Run;
  - coincidencia del top-100 entre int8 y float32;
  - tokens reales por llamada con los prompts nuevos.

## Fuentes (consultadas 2026-09-25)

- Hugging Face, [Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview) y [ZeroGPU](https://huggingface.co/docs/hub/en/spaces-zerogpu)
- Cloudflare, [límites de Pages](https://developers.cloudflare.com/pages/platform/limits/), [precios de Workers](https://developers.cloudflare.com/workers/platform/pricing/), [precios de D1](https://developers.cloudflare.com/d1/platform/pricing/), [precios de Vectorize](https://developers.cloudflare.com/vectorize/platform/pricing/) y [gpt-oss-120b en Workers AI](https://developers.cloudflare.com/workers-ai/models/gpt-oss-120b/)
- Google Cloud, [capa gratuita](https://docs.cloud.google.com/free/docs/free-cloud-features) y [precios de Cloud Run](https://cloud.google.com/run/pricing)
- Groq, [límites de tasa](https://console.groq.com/docs/rate-limits) y [tus datos en GroqCloud](https://console.groq.com/docs/your-data)
- Cerebras, [límites de tasa](https://inference-docs.cerebras.ai/support/rate-limits)
- Oracle, [recursos Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) e [InfoQ sobre el recorte de 2026](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
- Modal, [precios](https://modal.com/pricing)
- Qdrant, [precios](https://qdrant.tech/pricing/)
- Supabase, [precios](https://supabase.com/pricing)
- Gemini API, [guía de la capa gratuita](https://www.aifreeapi.com/en/posts/google-gemini-api-free-tier) (uso de datos para entrenar)
- AWS, [capa gratuita con créditos, 2025](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/) y [explicación de la capa de 2026](https://spot.rackspace.com/blog/aws-free-tier)
- OpenRouter, [comparativa de APIs de LLM gratuitas, 2026](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)
- Mistral, [La Plateforme: plan Experiment y datos](https://pricepertoken.com/endpoints/mistral/free) (fuente secundaria)
- NVIDIA, [términos de la API de prueba](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf)
- Groq, [topes de gasto](https://console.groq.com/docs/spend-limits); OpenRouter, [límites de crédito](https://openrouter.ai/docs/api_reference/limits) y [ZDR](https://openrouter.ai/docs/guides/features/zdr)
- Cloudflare Registrar, [precios](https://tld-list.com/registrars/cloudflare); DonDominio, [.mx](https://www.dondominio.com/en/products/domains/mx/)
- GitHub, [paquete de estudiante](https://education.github.com/pack)
