# RFC-0001: Alcance del MVP — split de Laboratorio en tiers y orden de lanzamiento

- **Estado**: En discusión (abierto 2026-09-20). No es una decisión tomada — es una propuesta a debatir. Cuando se resuelva, la decisión final se registra en un ADR nuevo que cite este RFC.
- **Autor de la propuesta**: revisión de senior DE, sesión 2026-09-20.

## Contexto

`PRD.md` declaró "Núcleo del MVP = Explorar + Laboratorio" como innegociable. Laboratorio (el Worker de rerank con LLM) depende de infraestructura de auth + cuota que no existe hoy (ver Fase 3a en `development.md`). Declarar un feature "innegociable" cuando su prerrequisito de seguridad no existe bloquea todo el lanzamiento detrás del problema más difícil del proyecto.

## Pregunta a resolver

¿Se lanza NODO UNAM como un solo paquete monolítico (Explorar + Laboratorio completo, esperando a que exista auth+cuota), o se divide el alcance para lanzar antes lo que ya es seguro y barato?

## Propuesta

**1. Dividir Laboratorio en dos tiers:**
- **Tier 1 (lanzable ya, costo marginal ~cero)**: búsqueda de vecinos semánticos, ya construida y precalculada para 50k tesis (ver ADR-0003) — sin LLM, sin auth, sin cuota, servida estática desde R2. Responde la pregunta central del usuario ("¿qué se ha hecho sobre mi tema?") sin riesgo de costo/abuso.
- **Tier 2 (el LLM: comparaciones, preguntas de investigación, detección de anacronismos)**: gateado detrás de registro + cuota, se lanza cuando esa infraestructura exista — no bloquea el lanzamiento de Tier 1.

**2. Modelar la economía unitaria de Tier 2 antes de fijar una cuota.** "Miles de personas" pegándole a Groq por request sin cálculo de costo-por-usuario-por-día es una apuesta, no un plan. Estimar: costo por llamada × cuota diaria propuesta × usuarios activos esperados, y fijar la cuota (¿10/día? ¿5/día?) con ese número en mano.

**3. Taller no se toca hasta tener el mismo rigor metodológico que el dataset** (`nota_metodologica.md` es el precedente correcto dentro del propio proyecto), o se marca visiblemente como "vista preliminar/experimental" mientras tanto. Es la audiencia (investigadores/bibliotecólogos) que más va a escrutinar metodología — exponer criterios "elegidos discrecionalmente" sin advertencia es un riesgo de credibilidad específico para ese público.

**4. Reordenar la secuencia de lanzamiento**, cuestionando el orden implícito actual:
`(a) limpiar Fase 1 → (b) publicar dataset abierto → (c) lanzar Tier 1 de Laboratorio → (d) construir auth/cuota → (e) lanzar Tier 2`
en vez de un solo lanzamiento monolítico. El dataset abierto es la pieza de menor riesgo de ingeniería (cero cómputo en vivo) y mayor payoff de credibilidad, y de paso obliga a pagar la deuda de Fase 1 que hay que pagar de todas formas.

## Alternativas consideradas

- **Mantener el alcance monolítico tal como estaba en el PRD original**: más simple de comunicar, pero el lanzamiento completo queda rehén de construir auth+cuota antes de mostrar nada al público.
- **Lanzar Taller también en v0**: descartado en la propia propuesta por el riesgo de credibilidad frente a la audiencia investigadora (punto 3).

## Decisiones pendientes de este RFC
- [ ] ¿Se acepta el split Tier 1 / Tier 2 de Laboratorio?
- [ ] ¿Se acepta el reordenamiento de secuencia (dataset abierto antes que Tier 2)?
- [ ] ¿Quién y cuándo hace el cálculo de economía unitaria de Tier 2?
- [ ] ¿Taller se congela hasta tener nota metodológica, o se marca como experimental y se muestra igual?
