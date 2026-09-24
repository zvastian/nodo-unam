# ADR-0003: Vecindario semántico híbrido — precómputo (atlas 50k) + generación on-demand

- **Estado**: Aceptado — decisión previa del usuario, formalizada el 2026-09-20.
- **Contexto**: El atlas semántico (Explorar) está construido sobre una muestra de 50,000 tesis, no el corpus completo de 609,156. Precomputar vecindarios para las 609k excede el volumen razonable de precómputo (ver ADR-0001) y probablemente no aporta valor proporcional, dado que gran parte de esa cola larga nunca se visita. Al mismo tiempo, el producto quiere permitir que cualquier usuario busque su propia tesis (dentro o fuera de las 50k) y obtenga su vecindario.
- **Decisión**: Modelo híbrido:
  - Las ~50,000 tesis del atlas semántico usan vecindarios **precalculados** (`neighborhood_by_thesis/*.json`), servidos estáticamente vía R2 (ADR-0001).
  - Para una tesis fuera de ese subset (o un tema que el usuario escribe libremente), el vecindario se calcula **on-demand** vía el endpoint vivo (`/api/explore/neighborhood/{id}` o el script de generación on-demand ya existente), que embebe la consulta y busca contra el índice completo.
- **Consecuencias**:
  - (+) Cobertura completa del corpus sin pagar el costo de precomputar 12x más archivos de los que realmente se visitan.
  - (+) Permite el caso de uso "busca tu propio tema", que es distinto de "navega el atlas ya construido".
  - (-) El endpoint on-demand es **cómputo en vivo por request** (embedding + búsqueda de vecinos), con el mismo perfil de riesgo/costo que el Worker de rerank con IA: necesita el mismo tratamiento de autenticación + cuota antes de exponerse públicamente (ver Fase 3a en `development.md`). Hoy no lo tiene — es el causante del bug visto en producción (fallback roto que expone detalles de FastAPI/uvicorn al usuario).
  - (-) Requiere que la UI comunique con claridad cuándo una respuesta viene de datos precalculados (instantánea) vs. cuándo dispara cómputo en vivo (latencia, posible cuota).
- **Pendiente de decisión**: mecanismo exacto de auth + cuota para el endpoint on-demand (compartir infraestructura con el gating del Worker de IA, o uno independiente más permisivo dado que es más barato que una llamada a Groq).
