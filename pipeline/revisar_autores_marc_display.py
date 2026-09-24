import duckdb

path = "recovery/processed/marc_recovered_normalized.parquet"
con = duckdb.connect()

print(con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{path}')
""").fetchdf().to_string(index=False))

print("\nEjemplos autores:")
print(con.execute(f"""
SELECT
    biblionumber,
    "Año",
    autor_limpio_v2,
    autor_display,
    autores_limpios_v2,
    autores_display,
    num_autores,
    autor_ui
FROM read_parquet('{path}')
LIMIT 20
""").fetchdf().to_string(index=False))

print("\nMúltiples autores, si existen:")
print(con.execute(f"""
SELECT
    biblionumber,
    "Año",
    autor_limpio_v2,
    autor_display,
    autores_limpios_v2,
    autores_display,
    num_autores,
    autor_ui
FROM read_parquet('{path}')
WHERE num_autores > 1
LIMIT 20
""").fetchdf().to_string(index=False))
