---
target: NODO UNAM app (deploy/static/index.html)
total_score: 18
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-09-19T21-00-22Z
slug: app-mi-tesis-unam-github-deploy-static-index-html
---
Method: dual-agent (Assessment A: revision de diseno, Assessment B: detector + evidencia de navegador)

## Design Health Score

| # | Heuristica | Score | Hallazgo clave |
|---|---|---|---|
| 1 | Visibilidad del estado del sistema | 2 | Laboratorio simula progreso creible antes de fallar siempre; charts de Ranking/Heatmap sin indicador de carga |
| 2 | Correspondencia con el mundo real | 3 | Identidad academica mexicana fuerte, pero copy metaforico sin explicacion para publico general |
| 3 | Control y libertad del usuario | 2 | Sin undo/reset en Explorar; sin cancelar en Laboratorio |
| 4 | Consistencia y estandares | 2 | Tres sistemas de color no relacionados entre pestanas; uso sistematico de Montserrat/Inter sin variacion |
| 5 | Prevencion de errores | 2 | Formulario largo de Laboratorio no avisa ausencia de backend |
| 6 | Reconocimiento antes que recuerdo | 1 | Leyenda de mezcla disciplinar deshabilitada por CSS; sin leyenda de color en Heatmap/Burbujas; jerarquia de encabezados rota |
| 7 | Flexibilidad y eficiencia de uso | 2 | Sin vistas guardadas/compartibles; GUARDAR deshabilitado en los 4 modulos |
| 8 | Diseno estetico y minimalista | 2 | Bugs reales de overflow confirmados por overlay: formas de Inicio se recortan; padding insuficiente, interlineado apretado |
| 9 | Ayuda para reconocer/diagnosticar errores | 1 | renderError() inyecta mensaje crudo de fetch/red sin traduccion ni siguiente paso |
| 10 | Ayuda y documentacion | 1 | Ninguna pestana tiene ayuda/about/FAQ; sin onboarding en el Atlas |
| **Total** | | **18/40** | **Poor** |

## Veredicto de especificidad de diseno
Inicio y Explorar autorados para UNAM (mural Biblioteca Central, triada Bauhaus/muralismo, taxonomia Area 1-4). Taller se siente como plantilla BI generica. Detector: 60 hallazgos en 4 HTML (modo degradado, subestimado), dominados por Montserrat/Inter repetido (tratar como un hallazgo sistemico). Overlay en vivo sumo 11 tipos de defecto no visibles por lectura de codigo (clipped-overflow-container x3, texto mayusculas sostenidas ~15 elementos, padding insuficiente, interlineado/tracking fuera de rango, linea ~93 caracteres, salto de encabezado h2-h4, grid-background, transicion de width). codex-grid-background posible falso positivo (app de dataviz).

## Impresion general
Techo alto (Inicio/Explorar), piso bajo (Laboratorio, teclado, responsive). Mayor oportunidad: cerrar brecha entre promesa visual de las primeras dos pestanas y ejecucion generica/rota del resto, especialmente Laboratorio (engana activamente, no solo esta inactivo).

## Lo que funciona
- Inicio: mural ilustrado + formas animadas, primera impresion memorable.
- Panel de detalle de Explorar: estadisticas densas y organizadas al seleccionar territorio.
- Estructura modular de Taller (rail Burbujas/Ranking/Heatmap/Series), patron de IA solido aunque piel visual generica.

## Problemas prioritarios

[P0] Inicio no orienta a nadie. Solo <img alt="Inicio"> + formas decorativas; sin titular, cifra de corpus, ni CTA. Formas ademas se recortan/sangran fuera del viewport (div.tab-shell/div.bauhaus-bg clipan hijo posicionado, confirmado por overlay). Fix: mision de una linea + cifra del corpus + CTA + alt descriptivo. Comando: /impeccable onboard

[P0] Explorar/Solar view inusable bajo ~500px. .app { grid-template-columns: 1fr 380px } sin override responsive en todo el archivo; overflow:hidden en body elimina escape por scroll. Panel lateral fijo de 380px consume casi toda la pantalla en movil. Fix: media query que colapse .app a una columna, panel como bottom-sheet. Comando: /impeccable adapt

[P1] Laboratorio invita, luego falla con error crudo sin avisar inactividad. Boton de pestana sin badge/estado deshabilitado; animateLoading() simula progreso creible antes de que postJSON falle siempre (sin backend); renderError() muestra err.message tal cual. Peor momento emocional del producto. Fix: badge "Proximamente" o mensaje amable en vez de error crudo. Comando: /impeccable clarify

[P1] Ranking (Taller) pierde etiquetas de categoria en varias filas. Confirmado con zoom: barras con valores 8009/7014/5496/5167 sin nombre de programa, filas adyacentes si. Rompe tarea central del modulo para ~1/4 de las filas. Fix: revisar logica de truncado/colision de etiquetas. Comando: /impeccable harden

[P2] Sistemas de color inconsistentes y sin leyenda entre pestanas. Leyenda de mezcla disciplinar de Explorar forzada a display:none aunque el markup existe; Burbujas sin leyenda; Heatmap sin escala de color. Fix: reactivar leyenda de mezcla; agregar clave de escala a cada grafica con color semantico. Comando: /impeccable clarify

## Red flags por persona

Jordan (primerizo, publico general): Inicio sin pistas de que es la herramienta; Explorar aterriza en cluster ya seleccionado sin leyenda de color; Laboratorio invita con el copy mas calido del producto y termina en error crudo tras invertir tiempo.

Alex (avanzado, comparando produccion por facultad): Ranking pierde ~4 de 16 nombres de programa visibles; Heatmap sin leyenda de intensidad; colores de burbuja nunca se conectan con "Area 1-4" de Explorar; GUARDAR deshabilitado en los 4 modulos.

Sam (teclado/lector de pantalla): sin anillo de foco visible fuera de campos de Laboratorio; Inicio completo es una imagen con alt="Inicio"; grafo Sigma.js y graficas SVG sin alternativa textual/tabular para 609k tesis.

## Observaciones menores
- Texto en mayusculas sostenidas en ~15 elementos (hasta 130 caracteres), detectado solo por overlay en vivo.
- Salto de jerarquia de encabezados (h2 a h4 sin h3).
- Explorar auto-selecciona cluster generico de terminos top en vez de invitacion neutral.
- Serie temporal cae a cero abruptamente cerca de 1986 sin anotacion.
- En Nobel, etiqueta del cluster superior tapada por barra de filtros a altura de viewport por defecto.
- index.html contiene un Taller alternativo completo no usado en vivo (reemplazado por workshop.js) - riesgo de mantenimiento.
- transition: width en body.workshop-curated-tools, mas costoso que animar transform.
- Evidencia movil no verificada en vivo (resize de viewport no funciono en este entorno); hallazgo de Explorar en movil es derivado de codigo.

## Preguntas para reflexionar
- Si Laboratorio tiene el copy mas invitante del producto, por que es la unica experiencia garantizada a terminar en error crudo?
- La leyenda de mezcla de color en Explorar esta oculta con display:none pero su markup sigue intacto - fue deliberado, y que la reemplazo?
- Tres pestanas inventan cada una su propio sistema de color para "area/disciplina academica" - vale la pena un token de diseno compartido antes del lanzamiento?
