-- Lugares del mapa guardados (27-sep-2026): campos, temas y subtemas. «lugar» es «nivel:id»
-- (macro:31, meso:…, micro:…); «datos» guarda cómo se muestra (nombre, nivel, tamaño, color).
CREATE TABLE lugares_guardados (
  usuario  TEXT NOT NULL,
  lugar    TEXT NOT NULL,
  datos    TEXT,
  creado   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (usuario, lugar)
) WITHOUT ROWID;
