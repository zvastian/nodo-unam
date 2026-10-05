-- Reintentos de la IA (1.0.6, 2026-10-05). Antes, una sección que faltaba por salida inválida o por
-- error del proveedor dejaba el análisis terminado para siempre: solo la falta de cupo lo dejaba
-- pendiente. Ahora también queda pendiente, con un tope de reintentos y una espera entre ellos.
--   ia_intentos:  fallos de IA registrados (no cuenta la falta de cupo).
--   ia_siguiente: el carril no lo toma antes de esta hora (UTC, ISO); NULL = cuando haya cupo.
ALTER TABLE analisis ADD COLUMN ia_intentos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE analisis ADD COLUMN ia_siguiente TEXT;
