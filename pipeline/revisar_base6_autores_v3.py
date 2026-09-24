import duckdb

path = "base6_homogeneizada_stream_v3.parquet"
con = duckdb.connect()

print("\n=== Conteo ===")
print(con.execute(f"""
SELECT count(*) AS n FROM read_parquet('{path}')
""").fetchdf())

print("\n=== Distribución autores ===")
print(con.execute(f"""
SELECT num_autores, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\n=== Ejemplos múltiples autores ===")
print(con.execute(f"""
SELECT
    thesis_id,
    "Año",
    autor_limpio_v2,
    autor_display,
    autores_limpios_v2,
    autores_display,
    num_autores,
    autor_ui,
    asesor_ui,
    num_asesores
FROM read_parquet('{path}')
WHERE num_autores > 1
LIMIT 30
""").fetchdf().to_string(index=False))
