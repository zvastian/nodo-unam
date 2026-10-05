-- Aviso por correo cuando la IA de un análisis que esperó se completa (1.0.7, 2026-10-05). Aquí solo
-- el registro; el envío llega después, con la baja de correos y el aviso de privacidad al día.
--   avisar:  0 = no hace falta; 1 = estuvo pendiente (seguro: lo marcó el Worker);
--            2 = estimado: análisis del 1-oct (día de CDMX) posteriores al lugar 55, el tope de IA
--                de ese día, que el carril completó después. D1 no guardaba ese historial.
--   avisado: cuándo se mandó el correo (UTC, ISO); NULL = todavía no.
ALTER TABLE analisis ADD COLUMN avisar INTEGER NOT NULL DEFAULT 0;
ALTER TABLE analisis ADD COLUMN avisado TEXT;
