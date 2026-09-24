import duckdb

path = "outputs/plantel_fix_stream/base_plantel_corregido_stream.parquet"

con = duckdb.connect()

print("\nTotal filas:")
print(con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{path}')
""").fetchdf())

print("\nSerie restante de unidad de posgrado unam:")
print(con.execute(f"""
SELECT
    "Año" AS anio,
    count(*) AS n
FROM read_parquet('{path}')
WHERE plantel_estandarizado_corregido = 'unidad de posgrado unam'
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\nTop planteles corregidos que antes eran unidad de posgrado:")
print(con.execute(f"""
SELECT
    plantel_estandarizado_corregido,
    count(*) AS n
FROM read_parquet('{path}')
WHERE plantel_estandarizado = 'unidad de posgrado unam'
GROUP BY 1
ORDER BY n DESC
LIMIT 30
""").fetchdf())

print("\nComparación antes/después:")
print(con.execute(f"""
SELECT
    plantel_estandarizado,
    plantel_estandarizado_corregido,
    count(*) AS n
FROM read_parquet('{path}')
WHERE plantel_estandarizado = 'unidad de posgrado unam'
GROUP BY 1, 2
ORDER BY n DESC
""").fetchdf())
