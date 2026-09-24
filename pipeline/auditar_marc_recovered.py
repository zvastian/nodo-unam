import duckdb
import pandas as pd

path = "recovery/processed/marc_recovered_all.parquet"
con = duckdb.connect()

print("\n=== Total ===")
print(con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{path}')
""").fetchdf())

print("\n=== Columnas ===")
print(con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{path}')
""").fetchdf().to_string(index=False))

print("\n=== Cobertura columnas clave ===")
cols = [
    "biblionumber",
    "system_number",
    "titulo_marc",
    "autor_marc",
    "sustentantes_marc",
    "asesores_marc",
    "anio_produccion_marc",
    "tipo_estudios_marc",
    "plantel_marc",
    "instituciones_otorgantes_marc",
    "entidades_participantes_marc",
    "texto_completo_url",
    "temas_marc",
]

for c in cols:
    try:
        df = con.execute(f"""
        SELECT
            '{c}' AS columna,
            count(*) AS total,
            count(NULLIF(trim(cast("{c}" AS VARCHAR)), '')) AS no_vacios
        FROM read_parquet('{path}')
        """).fetchdf()
        print(df.to_string(index=False))
    except Exception as e:
        print(c, "ERROR", e)

print("\n=== Top plantel_marc ===")
print(con.execute(f"""
SELECT plantel_marc, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY n DESC
LIMIT 50
""").fetchdf().to_string(index=False))

print("\n=== Top tipo_estudios_marc ===")
print(con.execute(f"""
SELECT tipo_estudios_marc, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY n DESC
LIMIT 50
""").fetchdf().to_string(index=False))

print("\n=== Ejemplos ===")
df = con.execute(f"""
SELECT
    target_year,
    biblionumber,
    system_number,
    titulo_marc,
    autor_marc,
    sustentantes_marc,
    asesores_marc,
    tipo_estudios_marc,
    plantel_marc,
    texto_completo_url
FROM read_parquet('{path}')
LIMIT 20
""").fetchdf()

pd.set_option("display.max_colwidth", 120)
pd.set_option("display.width", 220)
print(df.to_string(index=False))
