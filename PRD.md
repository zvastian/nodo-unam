# PRD — NODO UNAM

- **Estado**: Borrador en definición conjunta, iniciado 2026-09-20.
- **Cómo leer este documento**: lo marcado **[ABIERTO]** es una propuesta de borrador, no una decisión — se resuelve en conversación o se deriva a un RFC en `rfc/` si el debate lo amerita. Lo no marcado es lo ya confirmado.

## 1. Problema central

**[ABIERTO — borrador a confirmar/editar]**: Nadie ha explorado ni puesto a disposición pública el corpus completo de tesis de la UNAM (609,156 registros, 1873–2026). Un estudiante que empieza su tesis no tiene forma de saber qué ya se ha investigado sobre su tema; un investigador no tiene una vista agregada de la producción académica institucional; y la comunidad de datos abiertos no tiene acceso a este acervo a esta escala.

## 2. Audiencias (en orden de prioridad)

1. **Estudiantes** redactando su tesis — uso general, es la puerta de entrada del producto. Necesitan saber qué ya se investigó sobre su tema para no repetir trabajo y encontrar huecos de investigación.
2. **Investigadores / bibliotecólogos** — misma app, exigencia de calidad e infraestructura más alta. Servidos principalmente por **Taller** (ver §4, fuera del MVP inicial).
3. **Comunidad de datos abiertos** — canal *distinto* a la app: publicar el corpus como dataset público (Kaggle / HuggingFace Datasets). Mismo activo de datos, distribución y audiencia completamente distintas de la app interactiva.

## 3. Propuesta de valor por audiencia

- **Estudiantes**: descubrir en segundos qué tesis existen sobre un tema, evitar duplicar trabajo, identificar huecos de investigación reales.
- **Investigadores/bibliotecólogos**: métricas y visualizaciones agregadas sobre producción académica institucional (tendencias por programa/plantel/año, redes de asesores) — condicionado a que Taller alcance el rigor metodológico necesario (ver RFC-0001).
- **Comunidad de datos abiertos**: primer dataset público y masivo de tesis de la UNAM, habilita investigación derivada de terceros que hoy no existe.

## 4. Alcance

### v0 — lanzable ya (sin nueva infraestructura de seguridad)
- **Explorar** (atlas semántico) — ya funciona en producción.
- **Laboratorio Tier 1**: búsqueda de vecinos semánticos precalculados (50k tesis del atlas, ver ADR-0003) — sin LLM, sin auth, sin cuota, costo marginal ~cero.

### v1 — requiere infraestructura de auth + cuota (ver Fase 3a en `development.md`)
- **Laboratorio Tier 2**: comparaciones generadas por LLM, preguntas de investigación sugeridas, detección de anacronismos (el Worker de Groq).

### Fase 2 del producto — redefinido 2026-09-21 (ver ADR-0012)
- **Taller** pivota de "4 vistas fijas" a un **constructor de análisis en vivo**: filtro por texto libre + dimensiones (año/área/nivel/programa/plantel), cruce de dos dimensiones, gráfica instantánea vía SQL. Backend ya existe (`workshop_service.py::analyze()`); falta el frontend.
- **Nobel** deja de ser sección propia — se fusiona en Explorar como (a) "Nobel más cercano" en la vista de vecindario de una tesis, (b) nodos de Nobel visualmente distintos dentro del atlas, descubribles al navegar.

### Canal aparte — no es parte de la app
- **Dataset público** (Kaggle/HuggingFace) del corpus de 609,156 tesis. Depende de resolver la decisión de licenciamiento/PII (§6) y de la limpieza de Fase 1 (versionado, dedup) para poder etiquetar releases con confianza.

> El orden relativo de v0 / dataset público / v1 está en discusión — ver [`rfc/0001-mvp-scope-laboratorio-tiers.md`](rfc/0001-mvp-scope-laboratorio-tiers.md).

## 5. Fuera de alcance (explícito)

- Cobertura de vecindario precalculado para las 609,156 tesis completas — solo el subset de 50k del atlas semántico se precalcula; el resto se resuelve on-demand (ADR-0003), no se persigue cobertura total precalculada.
- Automatización completa de reentrenamiento del modelo semántico (equivalente a MLOps nivel 4) — el corpus no cambia con frecuencia suficiente para justificarlo hoy.
- Taller como producto terminado para investigadores — ver §4.

## 6. Riesgos y restricciones abiertas

- **[RESUELTO 2026-09-20] Licenciamiento/PII del dataset público**: nombres reales de autores/asesores NO se incluyen en el dataset descargable de Kaggle — un CSV masivo es una superficie de exposición distinta a mostrarlos uno por uno en la app interactiva (ya públicos vía catálogo UNAM). Ver ADR-0009.
- **[ABIERTO] Economía unitaria de Laboratorio Tier 2** — ver RFC-0001, punto 2.
- **[ABIERTO] Rigor metodológico de Taller** — ver RFC-0001, punto 3.

## 7. Métrica de éxito del MVP

**[ABIERTO — sin definir todavía]**: ¿qué significa que NODO UNAM "funcionó"? Candidatos a discutir: usuarios activos, búsquedas realizadas en Explorar, descargas del dataset abierto, tasa de conversión a registro para Laboratorio Tier 2, algo distinto. Pendiente de que el usuario decida cuál(es) de estas métricas es la que de verdad le importa.

## 8. Decisiones abiertas — checklist

- [ ] Confirmar o reescribir el problema central (§1).
- [ ] Resolver RFC-0001 (split de tiers, orden de lanzamiento, economía unitaria, rigor de Taller).
- [ ] Licenciamiento/PII del dataset público (§6).
- [ ] Métrica(s) de éxito del MVP (§7).
