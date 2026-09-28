-- Mi espacio (27-sep-2026): lo que se muestra de cada tesis guardada viaja con ella (título, año,
-- programa… del catálogo público), para no descargar los datos del mapa al abrir Mi espacio; y los
-- asesores guardados, con la misma idea.

ALTER TABLE tesis_guardadas ADD COLUMN datos TEXT;   -- JSON: titulo, anio, programa, nivel, plantel, area

-- Asesores guardados por el usuario. «asesor» es el nombre normalizado (minúsculas, sin acentos),
-- que es como el catálogo los unifica; «datos» guarda cómo se muestran.
CREATE TABLE asesores_guardados (
  usuario  TEXT NOT NULL,
  asesor   TEXT NOT NULL,
  datos    TEXT,                    -- JSON: nombre, programa, plantel, total, ultimo, area
  creado   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (usuario, asesor)
) WITHOUT ROWID;
