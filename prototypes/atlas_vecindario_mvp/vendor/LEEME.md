# Librerías de terceros

Se sirven desde el propio sitio, con versión exacta, en lugar de un CDN (v4.28). Así la política de
seguridad (CSP) solo permite scripts de `'self'` y el sitio no depende de un servicio externo.

| Archivo | Paquete | Licencia | Origen |
|---|---|---|---|
| `d3-7.9.0.min.js` | d3 7.9.0 | ISC | https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js |
| `regl-2.1.1.min.js` | regl 2.1.1 | MIT | https://cdn.jsdelivr.net/npm/regl@2.1.1/dist/regl.min.js |
| `regl-scatterplot-1.16.0.min.js` | regl-scatterplot 1.16.0 | MIT | https://cdn.jsdelivr.net/npm/regl-scatterplot@1.16.0/dist/regl-scatterplot.min.js |
| `pub-sub-es-3.0.0.js` | pub-sub-es 3.0.0 | MIT | https://cdn.jsdelivr.net/npm/pub-sub-es@3.0.0/dist/index.js |
| `supabase-js-2.117.2.js` | @supabase/supabase-js 2.117.2 | MIT | https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/dist/umd/supabase.js |

supabase-js coincide con el SRI publicado (`sha384-Rj26LVGv…`). Para actualizar una librería, se
descarga la versión exacta, se cambia el nombre del archivo y la referencia en las páginas.
