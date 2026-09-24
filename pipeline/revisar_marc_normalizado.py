import duckdb

path = "recovery/processed/marc_recovered_normalized.parquet"
con = duckdb.connect()

print(con.execute(f"""
SELECT count(*) AS n FROM read_parquet('{path}')
""").fetchdf())

print("\nTop plantel_display")
print(con.execute(f"""
SELECT plantel_display, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY n DESC
LIMIT 40
""").fetchdf())

print("\nTop nivel_estandar")
print(con.execute(f"""
SELECT nivel_estandar, count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY n DESC
""").fetchdf())

print("\nAños")
print(con.execute(f"""
SELECT "Año", count(*) AS n
FROM read_parquet('{path}')
GROUP BY 1
ORDER BY 1
""").fetchdf())

print("\nCasos sospechosos de plantel")
print(con.execute(f"""
SELECT plantel_marc_original, plantel_estandarizado, plantel_display, count(*) AS n
FROM read_parquet('{path}')
WHERE lower(plantel_display) LIKE '%universidad nacional autónoma%'
   OR lower(plantel_display) LIKE '%universidad nacional autonoma%'
   OR lower(plantel_estandarizado) LIKE '%universidad nacional autonoma%'
GROUP BY 1,2,3
ORDER BY n DESC
""").fetchdf())
