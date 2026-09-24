import duckdb

path = "base7_full_recovered.parquet"
con = duckdb.connect()

print(con.execute(f"""
SELECT "Año", source_record, count(*) AS n
FROM read_parquet('{path}')
WHERE "Año" IN (1905,1913,1960,1980,1985,1987,1989,1995,2026)
GROUP BY 1, 2
ORDER BY 1, 2
""").fetchdf().to_string(index=False))
