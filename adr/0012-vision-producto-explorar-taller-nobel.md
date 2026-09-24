# ADR-0012: Redefinición de producto — Nobel se fusiona en Explorar, Taller pivota a constructor de análisis

- **Estado**: Aceptado (2026-09-21).

## Contexto

Sesión de "reconstrucción desde cero" del producto (2026-09-20/21), tras cerrar la Fase 1 (datos limpios). Análisis sección por sección de Inicio/Explorar/Taller/Laboratorio/Nobel reveló:

- **Nobel** no tenía ninguna justificación de producto documentada — ni en `nodo_unam.md` ni en ningún otro lado — más allá de problemas de deploy. El usuario aclaró la intención real, nunca antes escrita: (a) "¿qué premio Nobel está semánticamente más cercano a tu tesis?", y (b) un easter egg — encontrarse un nodo de Nobel visualmente destacado mientras se navega el atlas de tesis. Se verificó que el atlas de Nobel se embebió con el mismo modelo (`paraphrase-multilingual-MiniLM-L12-v2`) que las tesis — viven en el mismo espacio semántico, la comparación es válida técnicamente, no solo cosmética.
- **Taller**: el usuario recordaba haber construido una función determinística de búsqueda libre por texto + estadísticas al vuelo (ej. buscar "messi" en títulos), pero no sabía si sobrevivía y la sentía desconectada del resto. Se encontró: el backend (`workshop_service.py::analyze()`) está completo y funcional — filtro por texto en título, `group_by`/`compare_by` sobre cualquier dimensión, conteos SQL en vivo. El frontend nunca se terminó — solo existe un placeholder ("Fase siguiente — Constructor de análisis") en `index.html`.

## Decisión

1. **Nobel deja de ser una pestaña independiente.** Se fusiona como capa dentro de Explorar:
   - Vista de vecindario de una tesis: tarjeta destacada con el premio Nobel semánticamente más cercano (mismo cálculo de similitud coseno ya usado para vecinos de tesis, contra el índice de Nobel).
   - Nodos de Nobel visualmente distintos dentro del atlas principal (color/brillo/ícono especial) — descubribles al navegar, sin sección propia.
2. **Taller pivota de "4 vistas fijas" a un constructor de análisis en vivo.** Se construye el frontend faltante sobre el backend `analyze()` ya existente: elegir dimensión, filtrar por texto libre + año/área/nivel/programa/plantel, cruzar con una segunda dimensión, gráfica generada al instante. Bubbles/Ranking/Heatmap/Series actuales no se eliminan — se convierten en plantillas rápidas precargadas dentro del constructor, no en el techo de lo que Taller puede hacer.
3. **Laboratorio** sin cambios respecto a lo ya decidido — sigue pendiente la resolución formal de RFC-0001 (Tier 1/Tier 2).

## Consecuencias

- (+) Nobel dejar de ser un "¿por qué existe esto?" sin respuesta — se vuelve una función coherente con la misión central.
- (+) Taller deja de depender de dimensiones precodificadas — un investigador puede hacer preguntas que nadie anticipó de antemano.
- (-) Requiere reconstruir el atlas semántico sobre el corpus completo y ya limpio (ver Fase de Explorar en `development.md`) — el atlas actual en producción sigue corriendo sobre datos pre-limpieza.
- (-) Requiere construir el frontend del constructor de análisis desde cero (el backend ya existe, no es trabajo nuevo de datos, es trabajo de UI).

## Pendiente inmediato

Regenerar los embeddings semánticos sobre `data/public/data_unam.parquet` (o el maestro interno) — el texto que se embebe incluye `programa`, `area` y `plantel`, los tres campos corregidos en la Fase 1. El atlas actual (`app/semantic_full/`, `app/Nodos/`) corre sobre una muestra de 50k construida antes de esa limpieza, desde el `Base.parquet` viejo (mismo hallazgo que ADR-0004). Decisión ya registrada previamente por el usuario en `nodo_unam.md` (no ejecutada hasta ahora): abandonar la muestra de 50k, reconstruir sobre el corpus completo de 609,156.
