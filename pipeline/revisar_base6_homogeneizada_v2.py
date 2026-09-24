import duckdb

path = "base6_homogeneizada_stream_v2.parquet"
con = duckdb.connect()

print("\n=== Conteo ===")
print(con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{path}')
""").fetchdf())

print("\n=== Distribución asesores ===")
print(con.execute(f"""
SELECT num_asesores, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\n=== Source used ===")
print(con.execute(f"""
SELECT asesores_source_used, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY n DESC
""").fetchdf())

print("\n=== Ejemplos 5+ asesores recientes ===")
print(con.execute(f"""
SELECT
    thesis_id,
    "Año",
    asesores_source_used,
    asesor_ui,
    num_asesores,
    asesores_limpios_v2,
    asesores_display
FROM read_parquet('{path}')
WHERE num_asesores >= 5
  AND "Año" >= 2023
LIMIT 20
""").fetchdf().to_string(index=False))
