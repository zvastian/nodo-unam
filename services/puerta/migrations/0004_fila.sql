-- Fila del Laboratorio (29-sep-2026): un análisis que llegó sin lugar se guarda con estado «fila»
-- hasta que el Durable Object Fila lo corre; entonces pasa a «listo» con su resultado. Ocupa uno de
-- los 2 análisis guardados desde que entra. Los que ya existían quedan como «listo».
ALTER TABLE analisis ADD COLUMN estado TEXT NOT NULL DEFAULT 'listo';
