-- Esquema inicial de D1 (ADR-0015, paso 2). Cada fila lleva el id de usuario de Supabase
-- (el «sub» del JWT). El Worker filtra siempre por ese id, nunca por uno que mande el cliente.

-- Análisis guardados: máximo 2 por usuario (MAX_ANALISIS_GUARDADOS).
CREATE TABLE analisis (
  id       TEXT PRIMARY KEY,
  usuario  TEXT NOT NULL,
  titulo   TEXT NOT NULL,
  entrada  TEXT NOT NULL,           -- JSON: lo que escribió el usuario
  resultado TEXT NOT NULL,          -- JSON: contexto de datos (y, en el paso 3, la parte de IA)
  creado   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX analisis_usuario ON analisis (usuario, creado);

-- Tesis del atlas guardadas por el usuario (id interno de la tesis; no se muestra).
CREATE TABLE tesis_guardadas (
  usuario  TEXT NOT NULL,
  tesis    TEXT NOT NULL,
  creado   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (usuario, tesis)
) WITHOUT ROWID;

-- Análisis nuevos por usuario y día (hora de la Ciudad de México).
CREATE TABLE cuota_diaria (
  usuario  TEXT NOT NULL,
  dia      TEXT NOT NULL,
  n        INTEGER NOT NULL,
  PRIMARY KEY (usuario, dia)
) WITHOUT ROWID;

-- Tope global del sitio por día y tipo: 'datos' ahora; 'groq' y 'workers_ai' en el paso 3.
CREATE TABLE cuota_sitio (
  dia      TEXT NOT NULL,
  tipo     TEXT NOT NULL,
  n        INTEGER NOT NULL,
  PRIMARY KEY (dia, tipo)
) WITHOUT ROWID;
