-- Lectura con IA pendiente (29-sep-2026): un análisis que se guardó con sus datos pero sin toda la
-- parte de IA porque se acabó el cupo (del sitio o de los proveedores). El carril de IA de la fila
-- (src/fila.js) lo completa cuando hay cupo, a su ritmo. Solo lo marca el Worker, nunca el cliente.
ALTER TABLE analisis ADD COLUMN ia_pendiente INTEGER NOT NULL DEFAULT 0;
