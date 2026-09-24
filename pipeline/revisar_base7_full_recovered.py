import duckdb

path = "base7_full_recovered.parquet"
con = duckdb.connect()

print("\n=== Total ===")
print(con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{path}')
""").fetchdf())

print("\n=== Source record ===")
print(con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\n=== Años recuperados ===")
print(con.execute(f"""
SELECT "Año", source_record, count(*) AS n
FROM read_parquet('{path}')
WHERE "Año" IN (1905,1913,1960,1980,1985,1987,1989,1995,2026)
GROUP BY 1, 2
ORDER BY 1, 2
""").fetchdf().to_string(index=False))

print("\n=== ID range ===")
print(con.execute(f"""
SELECT
    min(thesis_id) AS min_id,
    max(thesis_id) AS max_id,
    count(DISTINCT thesis_id) AS distinct_ids,
    count(*) AS n
FROM read_parquet('{path}')
""").fetchdf())

print("\n=== thesis_id_old cobertura ===")
print(con.execute(f"""
SELECT
    source_record,
    count(*) AS n,
    count(NULLIF(trim(thesis_id_old), '')) AS thesis_id_old_no_vacio
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\n=== Distribución autores ===")
print(con.execute(f"""
SELECT source_record, num_autores, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1, 2
ORDER BY 1, 2
""").fetchdf())

print("\n=== Distribución asesores ===")
print(con.execute(f"""
SELECT source_record, num_asesores, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1, 2
ORDER BY 1, 2
""").fetchdf())

print("\n=== Top plantel_display ===")
print(con.execute(f"""
SELECT plantel_display, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY n DESC
LIMIT 40
""").fetchdf().to_string(index=False))

print("\n=== Años completos ===")
print(con.execute(f"""
SELECT "Año", count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf().to_string(index=False))
