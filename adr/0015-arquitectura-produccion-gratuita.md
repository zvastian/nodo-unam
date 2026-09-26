# ADR-0015: Arquitectura de producción gratuita (atlas + Laboratorio)

- **Estado**: Aceptado (2026-09-26). **Reemplaza a [ADR-0001](0001-arquitectura-datos-produccion.md)**, que seguía «Propuesto» y queda como archivo histórico. Cierra [RFC-0002](../rfc/0002-arquitectura-produccion-gratuita.md), donde están la investigación, las cifras de las capas gratuitas y sus fuentes.

## Contexto

El atlas es estático; el Laboratorio necesita cómputo por petición: embeber el texto del usuario con el mismo `multilingual-e5-large` del corpus, buscar las 100 vecinas entre 609,154 vectores, calcular el contexto y hacer 3 llamadas a un LLM. Restricción del usuario: costo cero. En 2026 cuatro capas gratuitas cambiaron sin aviso, así que cada pieza debe poder mudarse cambiando configuración.

## Decisión

Se adopta la propuesta de RFC-0002, con dos cambios del usuario (2026-09-26):

```
Navegador
 ├── Sitio estático (atlas + interfaz del Lab) ──── Cloudflare Pages (R2 solo si un archivo pasa de 25 MiB)
 └── /api/* ── Worker «puerta» ──────────────────── Cloudflare Workers
                ├── Turnstile, CORS explícito, tope de tamaño
                ├── sesión: JWT verificado con JWKS ── Supabase Auth (Google + enlace mágico)
                ├── cuotas, análisis y tesis guardadas ── D1
                ├── datos ──► servicio del Lab ──────── Google Cloud Run
                │               FastAPI + e5-large ONNX int8 + FAISS SQ8
                └── IA ────► gpt-oss-120b ──────────── Groq + Workers AI (reparto)
```

1. **Groq y Workers AI se reparten la IA; Workers AI deja de ser solo respaldo.**
   - Ambos corren **el mismo modelo, `gpt-oss-120b`**, con los mismos prompts y los mismos esquemas de salida validados. Un análisis no cambia según qué proveedor contestó.
   - El Worker enruta cada llamada: primero Groq; si responde 429 o se agotó su presupuesto diario de tokens, la llamada va a Workers AI.
   - D1 lleva un contador diario por proveedor y un tope global del sitio.
   - Capacidad estimada: unos 80 análisis completos al día (unos 60 en Groq y unos 20 en Workers AI). La parte de Workers AI se cuenta en «neuronas» y se mide con los prompts reales antes de fijar el número.
   - Si ambos se agotan, el análisis entrega la parte de datos y marca la de IA como «cupo del día agotado».
2. **Todo el Laboratorio requiere sesión**, también la parte de datos. Sin sesión se explora el atlas completo; el Laboratorio y guardar tesis piden cuenta (el botón «Guardar» de v4.21 abre la invitación a crearla).

El resto, como en RFC-0002: Cloud Run con `max-instances` bajo y alerta de presupuesto en 1 USD; plan B en AWS Lambda con el mismo contenedor; Supabase solo para identidad y D1 para los datos; ZDR activado en Groq; ningún texto de tesis en los logs; borrar la cuenta borra los datos.

## Orden de construcción

1. **Servicio de datos del Lab, en local:** `services/lab/` con FastAPI y Dockerfile; exportación de e5-large a ONNX int8 e índice FAISS SQ8; `lab_contexto.py` portado sobre un paquete compacto de metadatos; conjunto de evaluación de 6 a 8 tesis de campos distintos; prueba de aceptación de int8. La plantilla del Lab se conecta a esta API en vez de `datos_ejemplo.json`.
2. Worker puerta, Supabase Auth y D1 (sesión, cuotas, guardados), con `wrangler dev` en local.
3. Parte de IA: prompts nuevos, reparto Groq + Workers AI, SSE.
4. Despliegue: Pages, Worker y Cloud Run con CI en GitHub Actions.

## Consecuencias

- (+) Costo cero hasta unos 80 análisis al día; al pasar de ahí, del orden de medio centavo de dólar por análisis, con tope propio en D1.
- (+) Ningún servidor propio que parchar; cada pieza se muda cambiando configuración.
- (+) Un solo modelo en los dos proveedores de IA: salidas comparables y un solo conjunto de pruebas.
- (−) Exigir sesión también para la parte de datos retrasa el lanzamiento hasta tener cuentas listas (paso 2), y suma fricción a la primera visita.
- (−) Arranque en frío de Cloud Run por la descarga de ~1.2 GB; se mide en el paso 1.
- (−) Las cuentas obligan a aviso de privacidad con derechos ARCO, borrado real y pruebas de acceso cruzado (IDOR).

## Enmienda: el modelo va en float32 (medición, 2026-09-26)

La prueba de aceptación (`services/lab/evaluar.py`) **rechazó el int8 dinámico**: 84.1 % del top-100 en promedio y 72 % en el peor caso, frente al 95 % pedido. Ninguna cuantización pasó con buena latencia. El servicio queda así:
- modelo **ONNX en float32** (2.2 GB), que da el 100 % del top-100;
- índice **FAISS IVF-SQ8** en vez del SQ8 plano, recorriendo 768 de sus 4,096 listas.

Resultado: 99.1 % del top-100 en promedio y 98 % en el peor caso, en unos 400 ms por petición.
- **Memoria:** unos 3 GB en uso, así que Cloud Run usa la instancia de **8 GiB**, no la de 4.
- **Capa gratuita:** sigue cubriendo decenas de miles de análisis al mes, porque se cobra solo mientras se atiende la petición.
- **Arranque en frío:** la descarga sube a unos 3 GB.

El detalle de todas las variantes está en `services/lab/README.md`.

## Por medir antes de producción

- ~~Coincidencia del top-100: al menos 95 %.~~ Medido: 99.1 % (ver la enmienda).
- Arranque en frío y latencia de la parte de datos en Cloud Run.
- Tokens reales por llamada y neuronas de Workers AI por análisis.
