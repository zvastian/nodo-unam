import duckdb

path = "base7_kaggle_clean.parquet"
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

print("\n=== Source record ===")
print(con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\n=== thesis_id_old ===")
print(con.execute(f"""
SELECT
    source_record,
    count(*) AS n,
    count(NULLIF(trim(thesis_id_old), '')) AS thesis_id_old_no_vacio
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())
