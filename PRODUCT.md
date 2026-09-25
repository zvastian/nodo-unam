# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Estudiantes (licenciatura y posgrado) e investigadores que exploran qué se ha investigado en la UNAM: para elegir o delimitar un tema de tesis, encontrar antecedentes, asesores y trabajos parecidos, o entender cómo se distribuye la producción académica. Sesiones de exploración largas, en laptop. Secundario: la pieza también se presenta (defensa de tesis, portafolio).

## Product Purpose

NODO UNAM / Atlas de tesis UNAM convierte el catálogo de 609,154 tesis de la UNAM en un mapa semántico navegable: cada tesis se ubica junto a las que tratan temas parecidos (embeddings e5-large, HDBSCAN + Ward, PaCMAP). Éxito: que un estudiante encuentre en minutos su tema, sus antecedentes y quién los asesoró, y que un investigador confíe en lo que ve.

**Nomenclatura (v4.7, 2026-09-24).** Los tres niveles del agrupamiento se llaman **campo** (macro, 130), **tema** (meso, ~440) y **subtema** (micro, 513). Sustituyen a «territorio», «subtema» y «tema fino», que el usuario consideró poco precisos. Se evitan «área», porque es el área administrativa, «especialidad», porque es un nivel de estudios, y «disciplina», porque los grupos se forman por contenido y no son oficiales. En el código y los datos siguen `macro`, `meso` y `micro`.

## Positioning

Los catálogos de tesis (TESIUNAM) se consultan por búsqueda de palabras y listas. Este atlas organiza el corpus completo por *contenido*, no por área administrativa, y hace visible lo que una lista oculta: vecindarios temáticos, territorios, temas finos, asesores y la relación entre ellos. Referencia de seriedad declarada por el usuario: Gapminder (herramienta de datos seria, clara, para estudiantes).

## Operating Context

- Prototipo web estático servido localmente (`prototypes/atlas_vecindario_mvp/`), regl-scatterplot (WebGL) + d3; datos precalculados (`atlas_data/`), sin backend.
- Flujos: explorar el mapa (campo → tema → subtema), buscar (Ctrl+K), aislar un subtema (conexiones), ficha de tesis, ficha de asesor o búsqueda, ficha de cluster y taller (tesis, perfil, asesores). Se retiraron en v4.14 las rutas guiadas, el modal de vecindario, el modo «Analizar» y la leyenda.
- Datos derivados del catálogo público TESIUNAM; títulos sin mención de autor; asesor sí se muestra.

## Capabilities and Constraints

- Proyecto propio, **no oficial**: puede citar a la UNAM y su catálogo, pero no usa escudo, logotipos ni la identidad institucional (azul Pantone 294 / oro 130), ni debe parecer sitio oficial.
- Fondo claro obligatorio (decisión del usuario, 22-09: "fondo oscuro hoy parece AI slop"). Actualizado el 2026-09-24: el claro sigue siendo el predeterminado y el único para paneles y fichas; toda la interfaz tiene un modo noche opcional (Ajustes, v4.18; en v4.17 era solo el mapa), homenaje a las ventanas de ónix de la Biblioteca Central que se iluminan al anochecer.
- Las posiciones del mapa no tienen unidad física; los nombres de temas finos y subtemas son keywords c-TF-IDF sin acentos; los 130 nombres de territorio son un borrador curado pendiente de revisión humana.
- 67% del corpus no pertenece a ningún territorio (ruido HDBSCAN) y debe seguir siendo visible y honesto.

## Brand Commitments

- Tono serio e institucional: legítimo, digno, "casi gubernamental", precisión de instrumento científico (Design Manifest 22-09, confirmado 24-09).
- Nombre de trabajo: "Atlas de tesis UNAM" (proyecto NODO UNAM).
- **Marca: NodOS** (2026-09-25). El logo oficial está en `marca/`: `nodos-logo.svg`, en los azules de la escala de niveles del mapa (#143a6b, #2d65a8, #5b95cf, #9cc3e6), y `nodos-logo-blanco-sobre-marino.svg`, en blanco sobre #12294d. Los tres puntos pueden cambiar de color en video y branding para dar dinamismo; el logo oficial no.

## Evidence on Hand

- Corpus real: 609,154 tesis, 130 territorios, ~440 subtemas, 513 temas finos, vecindarios e5 top-100, 480,462 enlaces intra-tema.
- Evidencia visual del pipeline en `docs/evidencia_visual/`.
- No hay usuarios, testimonios, métricas de uso ni aval institucional: no inventarlos.

## Product Principles

1. El dato manda: la interfaz se retira y la jerarquía visual la pone el contenido, no el chrome.
2. Honestidad sobre el método: lo que es aproximado, curado o ruido se dice y se ve.
3. Orden por contenido, no por burocracia: las áreas administrativas son una lente, no la estructura.
4. De lo general a una tesis concreta en pocos pasos, sin perderse.

## Lo que hace ver genérica una UI (anti-patrones, 2026-09-24)

Objetivo acordado con el usuario: que el atlas deje de verse como una plantilla de dashboard generada por IA y se vea como un **producto web profesional**. Referencia de seriedad: Gapminder (elegante, discreto, sencillo). Estos patrones quedan **prohibidos por defecto**; usar alguno exige una razón de producto escrita, no de gusto.

**Identidad y estructura**
1. **Estética de Claude / de asistente de IA**: fondo crema cálido (#faf9f5 y parecidos), titulares serif «editoriales» con controles sans, bordes tenues. Identificado por el usuario («tipografía parecida a la de Claude»).
2. **Sin barra de navegación ni identidad de producto**: no hay marca, ni secciones, ni un lugar estable para «dónde estoy / qué más hay». Un producto tiene navegación global; una plantilla solo tiene un lienzo con controles encima. Identificado por el usuario.
3. **Todo flota sobre el lienzo**: leyenda, minimapa, ruta, fichas, relatos… como tarjetas blancas sueltas sobre el mapa, sin estructura de página (el patrón «lienzo + widgets» de los dashboards de plantilla).
4. **Título y barras sin carácter**: título en mayúsculas espaciadas, subtítulo gris, barra de filtros en el gris cálido típico. Identificado por el usuario («la barra de filtros no tiene identidad, usa ese gris típico de IA, así como el título»).

**Componentes**
5. **Chips y píldoras redondeadas**: botones de contorno con radio de 6-14 px, controles segmentados tipo píldora, chips de palabras clave, radio de 999 px. Identificado por el usuario.
6. **Botones de contorno en mayúsculas diminutas con tracking** (10-11 px, 0.06em) como único estilo de botón.
7. **Botones de cerrar circulares con borde** y glifos unicode (✕ ← → ↑↓) en lugar de un sistema de íconos dibujado.
8. **Etiquetas pequeñas en mayúsculas sobre los títulos** («eyebrows»: TERRITORIO, TEMA FINO AISLADO, TESIS SELECCIONADA) y micro-etiquetas en mayúsculas espaciadas por todas partes.
9. **Tarjetas con sombra suave y radio uniforme** (misma sombra y mismo radio en todo), paneles blancos flotantes.
10. **Plantilla de métricas**: cifra grande + etiqueta pequeña en cuadritos (KPI tiles) como forma por defecto de mostrar datos.
11. **Rejilla de tarjetas iguales** para organizar contenido (el «cardocalypse»).
12. **Pista de teclado tipo «Ctrl K» en un pill** junto al botón de búsqueda (paleta de comandos de SaaS).
13. **Cajas punteadas como llamada a la acción.**

**Tipografía y color**
14. **Monoespaciada como disfraz de «técnico»** en cifras, conteos, metadatos e IDs, en vez de cifras tabulares de la familia principal.
15. **Mezcla de 3-4 familias** (sans + serif + sans de rótulos + mono) sin un sistema.
16. **Acento «esmeralda/teal» genérico** como color de interfaz sin significado; degradados decorativos, brillos y resplandores.
17. **Grises cálidos desaturados** usados para todo (bordes, texto secundario, fondos) sin jerarquía.

**Contenido y copy**
18. **Jerga técnica de desarrollo expuesta al usuario** (e5-large, HDBSCAN, PaCMAP, «n=», versiones) como decoración de rigor en la interfaz principal.
19. **Texto de relleno confiado pero genérico** y notas de desarrollo visibles.
20. **Movimiento idéntico en todo** (mismo fundido en cada elemento) o efectos de brillo/partículas.
21. **Subtítulo de KPIs irrelevantes** al analizar un tema: la tira «Tesis · Periodo · Planteles · Programas · Asesores» bajo el título, que repite cifras sin responder ninguna pregunta del usuario. Identificado por el usuario. Una cifra entra solo si responde algo; si no, va en una frase o no va.
22. **Subtítulos innecesarios** (identificado por el usuario, 2026-09-24): frases bajo un título o una gráfica que repiten lo que la gráfica ya dice, como «48 tesis, de 1991 a 2013» sobre una línea de tiempo, «Tesis por año» bajo un histograma o «Cada círculo es un asesor…». También las notas de instrucción («cierra esta ficha para…») y los conteos en prosa («17 tesis no quedaron en ningún campo»). El dato se dice con la gráfica (ejes con números), con jerarquía visual (título, conteo alineado, color) o como un elemento más del sistema (una fila «Sin campo» en la lista). Una frase entra solo si dice algo que ninguna gráfica muestra y no puede mostrarse de otra forma.
23. **Énfasis falso** (identificado por el usuario, 2026-09-24): un encabezado o una tarjeta con fondo teñido de un color y una franja delgada más oscura del mismo color en el borde (arriba o a la izquierda). Da énfasis sin decir nada y hoy se reconoce como diseño generado por IA. El color debe llevar un dato: en NodOS, el **mapa de localización** del encabezado (la silueta del atlas con lo que describe la ficha marcado en su color) y los glifos del sistema. La jerarquía la dan el tamaño, el peso y las reglas finas.
24. **Fondo gris genérico de UI: lista negra** (identificado por el usuario, 2026-09-25). Nada de gris claro de relleno (#f5f5f5 y parecidos, el antiguo token `--surface`): ni en bandas, pies, tarjetas o paneles, ni en estados *hover* o activos, ni como relleno de gráficas. Sin excepciones, ni siquiera con razón de producto. El énfasis y la separación los dan la tinta, el subrayado, los filetes finos y el peso. Donde un bloque necesita fondo propio, como el pie, va en azul marino (`--pie-fondo`) con tinta blanca.

### Decisiones de corrección (aprobadas 2026-09-24)

- **Una sola familia: Libre Franklin**, con cifras tabulares (`tnum`) para todos los números. Razón: heredera de la Franklin Gothic, la grotesca del periodismo de datos y la imprenta institucional; sobria, legible en tamaños chicos y ajena tanto al serif «editorial» de Claude como a Inter y sus clones. Sustituye a Public Sans, Source Serif 4, Source Sans 3 y JetBrains Mono.
- **Barra de navegación global** con la marca a la izquierda, las secciones que ya existen (Mapa, Rutas, Introducción, Método) y la búsqueda como campo real. **Método** es una página nueva donde vive la información técnica (modelo, agrupamiento, proyección, advertencias), que sale del pie y de la leyenda. No se añaden enlaces a secciones que aún no existen (Taller general, Laboratorio).
- **Mayúsculas solo en los rótulos del mapa** (convención cartográfica que el usuario pidió el 23-09); el resto va en caja normal.

Fuentes: [925 Studios — AI slop design tells](https://www.925studios.co/blog/ai-slop-design-tells), [Mania Design — Spot the slop](https://www.mania.design/blog/spot-the-slop-a-ui-designers-guide-to-fixing-ai-defaults/), [SmoothUI — AI design slop](https://smoothui.dev/blog/ai-design-slop), [Fudge — claude.ai design](https://design.withfudge.com/share/claude.ai-design), guía de piso de calidad de la skill de diseño del entorno.

## Accessibility & Inclusion

- Respetar `prefers-reduced-motion` (ya implementado en deriva y vuelos).
- Color nunca como única codificación: nombres y conteos acompañan a los colores de área y de grupo.
