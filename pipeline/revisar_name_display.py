import duckdb

path = "recovery/processed/marc_recovered_normalized.parquet"
con = duckdb.connect()

print(con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{path}')
""").fetchdf().to_string(index=False))

print("\nEjemplos con asesor:")
print(con.execute(f"""
SELECT
    autor_limpio_v2,
    autor_display,
    asesor_limpio_v2,
    asesor_display,
    asesores_limpios_v2,
    asesores_display,
    num_asesores,
    asesor_ui
FROM read_parquet('{path}')
WHERE num_asesores > 1
LIMIT 10
""").fetchdf().to_string(index=False))
