# NodOS — Atlas de tesis UNAM (proyecto NODO UNAM)

Mapa semántico navegable de 609,154 tesis de la UNAM. El trabajo activo es la **interfaz** en
`prototypes/atlas_vecindario_mvp/index.html` (un solo archivo: HTML + CSS + JS, sin build).

## Leer antes de tocar nada

- `PRODUCT.md`: usuarios, propósito y la lista de **24 anti-patrones de UI genérica** acordada
  con el usuario. Ninguno se reintroduce sin una razón de producto escrita.
- `development.md`: bitácora completa. Lee al menos «Estado del proyecto y hoja de ruta
  (2026-09-25)», que es la lista viva de pendientes, y la última sección.

## Correr la interfaz

```sh
cd prototypes/atlas_vecindario_mvp
python -m http.server 8765        # abrir http://127.0.0.1:8765/index.html
```

Los datos (`prototypes/atlas_vecindario_mvp/data/`, unos 160 MB) están versionados. Son
estáticos y se generan con los scripts de `pipeline/`, que dependen de datos locales que **no**
están en el repo. Desde la nube se trabaja la interfaz, no el pipeline.

## Verificar cambios visuales

`tools/cdp.mjs` lanza Chrome headless, ejecuta pasos en JSON y guarda capturas:

```sh
CHROME=/usr/bin/chromium SIZE=1600,900 node tools/cdp.mjs "http://127.0.0.1:8765/index.html" steps.json out/
CHROME=/usr/bin/chromium SIZE=390,844  node tools/cdp.mjs ...   # móvil
```

- La intro se abre sola: el primer paso suele ser
  `{"wait":9000,"eval":"document.getElementById('story-close').click();1"}`.
- `window.__debugAtlas` expone `state` y `selectNode` para manejar la app desde los pasos.
- Revisa siempre escritorio **y** móvil, y la consola (el harness la vuelca al final).
- Sin GPU, WebGL corre por software: los fps medidos así subestiman el rendimiento real.
- Las capturas headless a veces muestran un panel a medio deslizar. Antes de reportarlo como bug,
  mide con `getBoundingClientRect`.

## Reglas del proyecto

- **Privacidad.** Nunca mostrar ni versionar nombres de autor (los asesores sí se muestran).
  Si regeneras datos del prototipo, corre `python pipeline/limpiar_autores_atlas.py` antes de
  commitear. No versionar notebooks con outputs, `docs/` personales ni datos crudos.
- **Secretos.** Hay 4 scripts en `app/AI Pipeline/Scripts/` fuera de git porque tienen API keys.
  Las keys se leen de variables de entorno.
- **Identidad.** El proyecto es independiente y no oficial: no usar escudo, logotipos ni colores
  institucionales de la UNAM. Modo día (claro) predeterminado y modo noche opcional para toda la interfaz, en Ajustes, con los iconos de las ventanas de ónix de la Biblioteca Central (v4.18). Todo color de interfaz sale de tokens CSS (`--paper`, `--ink`…); no escribir colores fijos.
- **Diseño.** Acordar la estrategia visual con el usuario **antes** de codificar; nada de aplicar
  conceptos o plantillas por gusto. Referencia: Gapminder (serio, discreto, sencillo).
  Tipografía: solo Libre Franklin. Mayúsculas solo en los rótulos del mapa.
- **Versiones.** Semver en `#app-version`, en el pie. Cada versión se registra en
  `development.md` con qué cambió, por qué y cómo se verificó.
- **Idioma.** Español, tanto en la interfaz como en la documentación.
