---
name: NodOS
description: Atlas semántico de 609,154 tesis de la UNAM y Laboratorio para ubicar una tesis en proceso.
colors:
  papel: "#ffffff"
  tinta: "#1a1a1a"
  tinta-2: "#4d4d4d"
  tinta-3: "#6e6e6e"
  filete: "#e0e0e0"
  filete-fuerte: "#c2c2c2"
  reticula: "#f0f0f0"
  enlace: "#1d4f91"
  marino-pie: "#12294d"
  ocre-marca: "#d9a04a"
  area-sin: "#9a9a9a"
  area-fisico-matematicas: "#3566a8"
  area-biologicas-salud: "#0f7d5c"
  area-sociales: "#c98a2e"
  area-humanidades: "#b8412f"
  nivel-licenciatura: "#9cc3e6"
  nivel-especialidad: "#5b95cf"
  nivel-maestria: "#2d65a8"
  nivel-doctorado: "#143a6b"
  noche-fondo: "#0f1422"
  noche-papel: "#161c2a"
  noche-tinta: "#eceae4"
  noche-tinta-2: "#bcc2cf"
  noche-tinta-3: "#8f98ab"
  noche-filete: "#283044"
  noche-filete-fuerte: "#3b4559"
  noche-enlace: "#8fb8f2"
  noche-area-sin: "#8c93a3"
  noche-area-fisico-matematicas: "#5b93e6"
  noche-area-biologicas-salud: "#27a97c"
  noche-area-sociales: "#b0801c"
  noche-area-humanidades: "#e0567a"
typography:
  portada:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(34px, 3.3vw, 46px)"
    fontWeight: 800
    lineHeight: 1.06
    letterSpacing: "-0.025em"
    fontFeature: "\"tnum\" 1"
  titulo-seccion:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.005em"
    fontFeature: "\"tnum\" 1"
  destacado:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.4
    fontFeature: "\"tnum\" 1"
  entrada:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\" 1"
  pregunta:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4
    fontFeature: "\"tnum\" 1"
  cuerpo:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: "\"tnum\" 1"
  campo:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\" 1"
  subtitulo:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.55
    fontFeature: "\"tnum\" 1"
  meta:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "\"tnum\" 1"
  nota:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "\"tnum\" 1"
  grafica:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.3
    fontFeature: "\"tnum\" 1"
  rotulo-mapa:
    fontFamily: "Libre Franklin, Helvetica Neue, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.06em"
    fontFeature: "\"tnum\" 1"
rounded:
  recto: "0px"
  boton: "2px"
  barra: "3px"
  punto: "50%"
spacing:
  movil: "16px"
  margen: "24px"
  ficha: "32px"
  columnas: "56px"
  seccion-arriba: "44px"
  seccion-abajo: "36px"
  lomo: "92px"
components:
  boton-accion:
    backgroundColor: "{colors.tinta}"
    textColor: "{colors.papel}"
    rounded: "{rounded.boton}"
    padding: "11px 18px"
    typography: "{typography.subtitulo}"
  boton-texto:
    textColor: "{colors.tinta}"
    rounded: "{rounded.recto}"
    padding: "0"
    typography: "{typography.subtitulo}"
  enlace:
    textColor: "{colors.enlace}"
    typography: "{typography.cuerpo}"
  barra-navegacion:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.tinta-2}"
    height: "56px"
    padding: "0 24px"
    typography: "{typography.meta}"
  barra-estado:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.tinta-2}"
    height: "54px"
    padding: "6px 24px"
    typography: "{typography.meta}"
  ficha-portada:
    backgroundColor: "{colors.marino-pie}"
    textColor: "{colors.papel}"
    rounded: "{rounded.recto}"
    padding: "{spacing.ficha}"
    typography: "{typography.portada}"
  pie:
    backgroundColor: "{colors.marino-pie}"
    textColor: "{colors.papel}"
    padding: "44px 24px"
    typography: "{typography.meta}"
  nota-flotante:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.recto}"
    padding: "10px 12px"
    typography: "{typography.nota}"
---

<!-- Encabezados de sección en inglés por el formato DESIGN.md (las herramientas los leen tal cual);
     el contenido va en español, como toda la documentación del proyecto. -->

# Design System: NodOS

## Overview

**Creative North Star: «La lámina de atlas»**

NodOS se diseña como una lámina impresa de un atlas de referencia, no como un tablero de software. El papel es blanco y tiene grano. La tinta es casi negra y ordena todo con tamaño, peso y filetes finos. El color se reserva para los datos: el área administrativa de cada tesis, su nivel de estudios y el campo temático donde cae. Cada página abre como una lámina de prensa, con un filete superior de 3 px, y cada sección tiene un título subrayado y cierra con un filete de pelo. En el Laboratorio, la tesis del usuario se trata como un volumen empastado. Su portada es un bloque de color pleno con el título a tamaño de cubierta. Al bajar, un lomo vertical la sigue por el margen izquierdo con el título escrito de abajo arriba.

El tono es serio, casi gubernamental, con precisión de instrumento científico; la referencia declarada es Gapminder. La densidad es de lectura larga en laptop: columnas amplias, renglones de 52 a 70 caracteres y espacio vertical generoso entre secciones. Hay dos excepciones al papel. El mapa ocupa todo el lienzo en el atlas. Y hay bloques de fondo pleno cuando la página se quedaría vacía: la portada de la tesis y el pie. Esos bloques siempre llevan un dato o la marca.

Rechazos confirmados por el usuario:
- la estética de asistente de IA (crema cálido, serif editorial);
- el patrón «lienzo con widgets flotantes»;
- los chips y las píldoras;
- las etiquetas en mayúsculas sobre los títulos;
- las tarjetas con sombra;
- los grises de relleno;
- el énfasis falso de caja teñida con franja;
- los halos y resplandores;
- las páginas casi todas en blanco.

El modo noche es opcional y está en Ajustes. Es un homenaje a las ventanas de ónix de la Biblioteca Central, que se iluminan al anochecer.

**Key Characteristics:**
- Papel blanco con grano, tinta casi negra, un solo azul de interfaz para enlaces y foco.
- El color codifica datos (área, nivel y campo), nunca decora.
- Una sola familia, Libre Franklin, con cifras tabulares en todo número.
- Láminas: filete de prensa, títulos subrayados, secciones cerradas con filete fino.
- Bloques de fondo pleno con tinta blanca, solo si llevan un dato o la marca.
- Sin sombras, sin radios salvo 2 px en botones, sin chips.

## Colors

La paleta es tinta sobre papel, más dos escalas de datos: cuatro áreas administrativas y cuatro niveles de estudio. El color de cada campo temático lo asigna el mapa.

### Primary
- **Azul de hemeroteca** (`enlace`): el único color de interfaz. Se usa en enlaces, foco de teclado y el anillo de selección. Es sobrio para no competir con los colores de los datos.

### Secondary
- **Marino de colofón** (`marino-pie`): el fondo del pie y de la portada de la tesis antes de conocer su área. Siempre lleva tinta blanca encima.
- **Ocre de marca** (`ocre-marca`): el acento de la marca NodOS. Solo aparece en el ícono de «Apoya este proyecto», en el pie.

### Tertiary
Escala de **áreas administrativas**. Cada tesis lleva el color de su área en su punto del mapa, en la barra de su programa y en las gráficas:
- **Azul físico-matemático** (`area-fisico-matematicas`): Físico-Matemáticas e Ingenierías.
- **Verde biológico** (`area-biologicas-salud`): Biológicas, Químicas y de la Salud.
- **Ocre social** (`area-sociales`): Ciencias Sociales.
- **Almagre humanístico** (`area-humanidades`): Humanidades y Artes.
- **Gris sin área** (`area-sin`): tesis sin área registrada. Es el único gris con significado.

Escala de **niveles de estudio**. Es una rampa de azul, del más claro al más oscuro: Licenciatura, Especialidad, Maestría y Doctorado (`nivel-*`). Se dibuja con los cuatro puntos del glifo de nivel. De noche la rampa se invierte: más avanzado es más luminoso.

### Neutral
- **Papel** (`papel`): fondo de todo. Es blanco neutro, nunca crema.
- **Tinta** (`tinta`): texto principal, títulos, filetes de prensa y el botón de acción.
- **Tinta segunda** (`tinta-2`, 8.5:1): texto secundario y navegación en reposo.
- **Tinta tercera** (`tinta-3`, 5.1:1): el mínimo para texto chico. Se usa en metadatos, etiquetas de fila y estados pendientes.
- **Filete** (`filete`): la única línea fina, entre renglones y al cerrar secciones.
- **Filete fuerte** (`filete-fuerte`): el subrayado de los títulos de sección, los ejes y el borde de la nota flotante.
- **Retícula** (`reticula`): solo líneas de retícula en gráficas y mapa. Nunca es un relleno.

### Named Rules
**La regla del color con dato.** Un color que no codifica área, nivel, campo o marca no entra en la página. La interfaz es tinta sobre papel, y el único color de interfaz es el azul de enlace.

**La regla de la lista negra del gris.** No hay grises claros de relleno en ninguna parte: ni en bandas, pies, tarjetas o paneles, ni en estados *hover* o activos, ni como relleno de gráficas. Sin excepciones. La separación la dan la tinta, el subrayado, los filetes y el peso.

**La regla del bloque anclado.** Una página casi toda en blanco se ve vacía y se corrige con un bloque de fondo pleno que lleve un dato: el color del área o del campo, oscurecido (`color-mix` en OKLCH con 72 % del color y el resto negro; 55 % de noche) para que la tinta blanca lea bien. Si no hay dato, va el marino del pie. Nunca un teñido pálido con franja ni un gris.

## Typography

**Display Font:** Libre Franklin (con Helvetica Neue, Arial)
**Body Font:** Libre Franklin
**Label/Mono Font:** ninguna. No hay monoespaciada.

**Character:** es una sola grotesca, heredera de la Franklin Gothic del periodismo de datos y la imprenta institucional. La jerarquía sale del tamaño, el peso (400 a 800) y el interletrado, nunca de una segunda familia.

### Hierarchy
- **Portada** (800, clamp de 34 a 46 px, 1.06, −0.025em): el título de la tesis en su ficha. Máximo 22 caracteres por renglón y renglones equilibrados (`text-wrap: balance`). Es lo primero que se lee en la página.
- **Título de sección** (700, 24 px, 1.25): los títulos de cada sección de la lámina, subrayados.
- **Destacado** (600, 19 px, 1.4): la frase principal de una sección, como el riesgo de los objetivos o el nombre de un asesor. Máximo unos 46 caracteres por renglón.
- **Entrada** (400, 19 px, 1.5): el texto que escribió el usuario (su Problematiza), dentro de la portada. Máximo unos 56 caracteres por renglón.
- **Pregunta** (600, 18 px, 1.4): cada pregunta de investigación sugerida.
- **Cuerpo** (400, 15 px, 1.55): el texto corrido.
- **Campo** (400, 16 px, 1.5): lo que el usuario escribe sobre papel (objetivos, palabras clave, programa).
- **Subtítulo** (600, 15 px): los títulos dentro de una sección y el texto del botón de acción.
- **Meta** (400, 14 px): la navegación, la barra de estado, la fila de metadatos y las listas de tesis.
- **Nota** (400, 13 px, a veces 12.5 px): la nota flotante, los estados pendientes y la cabecera de lámina.
- **Gráfica** (400, 12 px): números y nombres en ejes y leyendas de las gráficas.
- **Rótulo de mapa** (700, 11 px, 0.06em, en MAYÚSCULAS): solo los rótulos del mapa.

### Named Rules
**La regla de una sola voz.** Todo el producto usa Libre Franklin, y todo número lleva cifras tabulares (`"tnum" 1`), también dentro de botones, campos y gráficas.

**La regla de las mayúsculas cartográficas.** Las MAYÚSCULAS solo aparecen en los rótulos del mapa, por convención cartográfica. Todo lo demás va en caja normal: no hay etiquetas en mayúsculas sobre los títulos.

**La regla de la portada.** En una ficha, el título es lo más grande y más pesado de la página. Nada compite con él.

## Layout

La página es una **lámina** centrada de hasta 1280 px, con 24 px de margen (16 px en móvil).
- **Cabecera de lámina:** filete superior de 3 px en tinta, rótulo a la izquierda y fecha a la derecha, a 12.5 px. Es el remate de prensa.
- **Secciones:** 44 px arriba y 36 px abajo, cerradas con un filete fino.
- **Columnas:** la lectura va a la izquierda. El acompañamiento (el mapa reducido del análisis, la escalera de Bloom) va a la derecha, en una columna de 360 a 420 px con 40 a 56 px de separación.
- **Contenido de ancho completo:** las gráficas que filtran y las listas largas usan todo el ancho, en dos mitades iguales.
- **Lomo:** en las páginas de una tesis, la columna izquierda (92 px) guarda el lomo. Es una línea vertical con el título escrito de abajo arriba, que aparece cuando la portada sale de la vista y se queda fijo al bajar.

**Barras fijas:** la navegación (56 px) y, en el Laboratorio, la barra de estado (54 px) debajo. Las dos llevan fondo de papel y un filete inferior; no tienen sombra.

**Adaptación:**
- a 1100 px, lo que va en pares pasa a una columna;
- a 860 px, las columnas de la lámina se apilan y el mapa sube arriba;
- a 640 px, desaparece el lomo, la portada va a sangre (sin margen lateral) y los títulos bajan de tamaño: la portada a 30 px y la entrada a 17 px.

### Named Rules
**La regla de la lámina.** Toda sección empieza con su título subrayado y termina con un filete fino. La página se lee de arriba abajo como una lámina, no como una rejilla de tarjetas.

**La regla de la tesis como volumen.** En el Laboratorio, la tesis es un libro: portada de color pleno arriba, lomo en el margen y colofón en el pie azul marino.

## Elevation & Depth

El sistema es plano: no hay ninguna sombra. La profundidad sale de tres cosas:
- el orden de lectura;
- los filetes: el fino de 1 px, el subrayado de 2 px y el de prensa de 3 px;
- los bloques de fondo pleno de la portada y el pie.

Las barras fijas se separan del contenido con un filete inferior. La nota flotante lleva un borde de filete fuerte, no una sombra. El grano del papel va detrás de todo el contenido, así que las barras, el mapa y los bloques de color quedan lisos encima.

### Named Rules
**La regla sin sombras.** Si algo necesita separarse, lleva un filete. Si necesita pesar, lleva un fondo pleno con dato. Nunca una sombra ni un resplandor.

## Shapes

Todo es rectangular y de ángulo recto.
- **Botones:** radio de 2 px. Es la única curva de la interfaz.
- **Puntos de dato:** círculos (50 %) para los puntos del mapa, los de nivel, los de leyenda y el anillo de programa.
- **Barras de gráfica** (`barra`): terminan con un radio de 3 px en el extremo del valor.
- **Iconos:** dibujados con un solo trazo de 1.6 px, extremos redondeados y sin relleno. Nada de glifos unicode como «✕» o «→».

## Components

### Buttons
- **Botón de acción** (`boton-accion`): bloque de tinta con texto blanco en seminegritas, radio de 2 px y 11 × 18 px de relleno. Es para la acción que concluye algo, como «Guardar las 15» o «Analizar mi tesis». Al pasar el cursor se tiñe del color del contexto (campo o área). Deshabilitado, baja al 40 % de opacidad.
- **Acción de texto** (`boton-texto`): texto en tinta, seminegritas, con una flecha dibujada al final. Al pasar el cursor se subraya con el color del contexto. Es la acción principal en las fichas del atlas.
- **Botón secundario:** texto en tinta, sin caja, que se subraya al pasar el cursor. Los estados *hover* nunca son un fondo gris.

### Cards / Containers
No hay tarjetas.
- **Ficha-portada:** bloque de color pleno, a todo el ancho de la columna, con 32 px de relleno. Dentro, los tokens de tinta cambian a los del pie: blanco al 100 % y al 70 %. Cambia de color con una transición de 700 ms cuando se conoce el área.
- **Lo demás:** filas separadas por filetes finos.

### Inputs / Fields
**La ficha se escribe** (construido el 27-sep-2026 en el boceto del Laboratorio). El formulario escribe dentro de la misma ficha-portada que después encabeza el análisis.
- **Portada:**
  - el título, con la tipografía de portada;
  - la Problematiza, con la de entrada;
  - la fila meta: programa, grado y periodo.
- **Sin caja:** un campo no tiene caja ni fondo, solo un filete inferior (filete fuerte).
  - Al pasar el cursor, el filete pasa a tinta segunda.
  - Con foco, el filete sube a 2 px en tinta. Sobre la portada, la tinta es blanca.
- **Sobre papel:** los campos usan la tipografía de campo, 16 px.
- **Programa:** autocompletado sobre los programas del corpus.
  - La lista va fuera de la portada, con los tokens de papel.
  - Cada opción lleva la barra de su área y su número de tesis en tinta tercera, con la coincidencia en negritas.
  - La opción activa se subraya; no tiene fondo.
- **Grado:** radios nativos con aspecto de pestañas de texto subrayadas, precedidos por los cuatro puntos de nivel.
- **Periodo:** dos años y la línea de tiempo de dos puntos del análisis, más «no aplica».
- **El color lleva un dato:**
  - antes de elegir programa, la portada es azul marino;
  - al elegirlo, toma el color del área más común del programa, con la transición de 700 ms.
- **Objetivos:** renglones numerados, separados por filete. El renglón con foco subraya su filete en tinta.
  - A la derecha, la escalera de Bloom se dibuja en vivo.
  - Los verbos ambiguos van bajo los nombres de nivel, con un corchete sobre los peldaños posibles, en cursiva y tinta tercera.
  - Bajo un objetivo, una nota de 13.5 px en tinta segunda solo cuando hay un caso límite del léxico.
- **Errores:** debajo del campo, en español llano, en tinta con un ícono de trazo. El campo se marca con filete de 2 px. Sin rojo.
- **Palabras clave:** texto separado por comas, nunca chips.

### Navigation
- **Barra global** (`barra-navegacion`): el logo de NodOS a la izquierda y las secciones como texto a 14 px en tinta segunda. La sección activa va en tinta, seminegritas, con subrayado de 2 px. A la derecha van las acciones de texto.
- **Pestañas:** son texto con subrayado, nunca un control segmentado tipo píldora.

### Barra de estado del Laboratorio (`barra-estado`)
- **Mascota:** el personaje de NodOS cambia de color en cada hallazgo: gris al buscar, color del área al ubicar la tesis y color del campo después.
- **Texto:** el paso actual; lo importante va en tinta, en negritas.
- **Guiones de avance:** a la derecha, uno por sección. Son trazos de 3 px que se llenan de tinta cuando la sección está lista y después llevan a ella.

### Glifos de ficha
Una gramática fija, compartida por las fichas del atlas y las del Laboratorio:
- **Puntos de nivel:** cuatro círculos de 7 px, llenos hasta el nivel de la tesis.
- **Barra de área:** 2 × 13 px en el color del área.
- **Anillo de programa:** un círculo con contorno en el color del área.
- **Punto de plantel:** un punto de 5 px en tinta segunda.
- **Guion del campo:** 12 × 2 px, antes de cada objeto de estudio.

### Gráficas que filtran
Cada gráfica del perfil (años, áreas, niveles, campos, programas, planteles) es también un filtro.
- **Barras:** la tenue (20 % del color) es el total y la llena es lo que queda tras filtrar.
- **Selección:** un valor elegido va en negritas.
- **Vacíos:** los valores en cero bajan al 45 %.
- **Ejes:** los números van en los ejes, no en subtítulos.

### Escalera de Bloom
Seis peldaños rectos. Cada verbo se escribe sobre su peldaño en negritas. Los tramos entre niveles con objetivo son:
- continuos si los niveles son contiguos;
- punteados, con la leyenda «sin …», si se salta alguno.

La escalera se dibuja con el léxico, no con IA. En el formulario se dibuja en vivo.

### Preguntas sugeridas
Cada pregunta lleva a la izquierda su tipo (Comparación, Rastreo, Explicación, Evaluación, Prospectiva, Exploración). Cada tipo tiene un diagrama fijo en el color del campo. A la derecha va la pregunta en 18 px seminegritas y, debajo, «Método: …».

### Nota flotante (`nota-flotante`)
Papel, borde de filete fuerte y 13 px, sin sombra. Sigue al cursor.

### Estados pendientes
Una frase a 14 px en tinta tercera, sobre una barra de 2 px que se llena y se vacía.

### Pie (`pie`)
Banda azul marino con el logo en blanco, enlaces en blanco y texto al 70 %. El único acento es el ocre de «Apoya este proyecto». Encima de la parte legal lleva un filete blanco al 18 %.

### Movimiento
- **Aparición:** 500 ms, subiendo 6 px.
- **Barras y trazos:** crecen en 450 a 700 ms con `cubic-bezier(.2,.7,.2,1)`.
- **Cambios de color:** 700 ms.
- **Secuencia:** cada sección aparece cuando su dato está listo, con un leve escalonado entre elementos.
- **Movimiento reducido:** todo esto se desactiva con `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** poner el color solo donde lleva un dato: área, nivel, campo o marca. El azul de enlace es el único color de interfaz.
- **Do** anclar las páginas casi en blanco con un bloque de fondo pleno que lleve un dato, oscurecido con `color-mix` al 72 % (55 % de noche), con tinta blanca.
- **Do** abrir las páginas con la cabecera de lámina (filete de 3 px) y subrayar los títulos de sección (2 px en filete fuerte, 8 px de separación).
- **Do** decir las cifras con la gráfica: ejes con números, un conteo alineado o una fila más del sistema (por ejemplo, «Sin campo»).
- **Do** usar cifras tabulares en todo número y Libre Franklin en todo texto.
- **Do** dar el énfasis en el mapa con contraste de tinta y gris, tamaño, anotación o contornos.
- **Do** mantener el modo noche con los mismos componentes; solo cambian los tokens.

### Don't:
- **Don't** usar grises claros de relleno (como `#f5f5f5`), ni en estados *hover*, ni en gráficas.
- **Don't** usar cajas teñidas con franja de color en el borde (énfasis falso), ni degradados, brillos, halos o anillos de resplandor para destacar.
- **Don't** usar chips, píldoras, controles segmentados redondeados ni radios mayores de 2 px en la interfaz.
- **Don't** poner etiquetas en mayúsculas espaciadas sobre los títulos. Las mayúsculas son solo para los rótulos del mapa.
- **Don't** usar tarjetas con sombra, rejillas de tarjetas iguales ni cuadritos de cifra grande con etiqueta chica.
- **Don't** usar fuentes monoespaciadas, serif editorial ni fondos crema.
- **Don't** poner subtítulos que repiten la gráfica, notas de instrucción ni conteos en prosa.
- **Don't** separar elementos con « · » ni mostrar identificadores internos (como `TH_…`) al usuario.
- **Don't** usar el escudo, los logotipos ni los colores institucionales de la UNAM (azul Pantone 294, oro 130), ni escribir un color fijo fuera de los tokens.
