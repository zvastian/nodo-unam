import duckdb
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

IN = Path("base7_full_recovered.parquet")
OUT_DIR = Path("outputs/base7_visual_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "tesis_por_anio_drop_audit.png"
OUT_CSV = OUT_DIR / "tesis_por_anio_drop_audit.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

con = duckdb.connect()

df = con.execute(f"""
SELECT
    "Año" AS anio,
    count(*) AS n
FROM read_parquet('{IN.as_posix()}')
WHERE "Año" IS NOT NULL
GROUP BY 1
ORDER BY 1
""").fetchdf()

df["anio"] = df["anio"].astype(int)
df["n"] = df["n"].astype(int)

# Completar años faltantes para que los huecos se vean como caídas reales.
full = pd.DataFrame({"anio": range(df["anio"].min(), df["anio"].max() + 1)})
df = full.merge(df, on="anio", how="left").fillna({"n": 0})
df["n"] = df["n"].astype(int)

# Métricas visuales de caída interanual.
df["n_prev"] = df["n"].shift(1)
df["diff_abs"] = df["n"] - df["n_prev"]
df["pct_change"] = (df["diff_abs"] / df["n_prev"]) * 100

# Flag: caída fuerte si baja más de 35% y al menos 300 tesis.
df["drop_flag"] = (df["pct_change"] <= -35) & (df["diff_abs"] <= -300)

df.to_csv(OUT_CSV, index=False, encoding="utf-8")

fig, ax = plt.subplots(figsize=(18, 8))

# Barras base.
ax.bar(df["anio"], df["n"], width=0.85, alpha=0.65)

# Línea suavizada de 5 años para detectar tendencia.
df["rolling_5"] = df["n"].rolling(window=5, center=True, min_periods=1).mean()
ax.plot(df["anio"], df["rolling_5"], linewidth=2.5, label="Promedio móvil 5 años")

# Marcar caídas drásticas con puntos y etiquetas.
drops = df[df["drop_flag"]].copy()
ax.scatter(drops["anio"], drops["n"], s=90, zorder=5, label="Caída drástica")

for _, r in drops.iterrows():
    label = f"{int(r['anio'])}\n{int(r['pct_change'])}%"
    ax.annotate(
        label,
        xy=(r["anio"], r["n"]),
        xytext=(0, 18),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        arrowprops=dict(arrowstyle="->", lw=0.8)
    )

# Banda visual: años que acabas de recuperar.
recovered_years = [1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026]
for y in recovered_years:
    ax.axvline(y, linestyle="--", linewidth=0.8, alpha=0.35)

ax.set_title("Tesis por año — auditoría visual de caídas drásticas", fontsize=16)
ax.set_xlabel("Año")
ax.set_ylabel("Número de tesis")
ax.legend()

# Ticks cada 5 años para no saturar.
years = df["anio"].tolist()
tick_years = [y for y in years if y % 5 == 0]
ax.set_xticks(tick_years)
ax.tick_params(axis="x", rotation=60)

# Truco visual: usar grid horizontal y margen superior.
ax.grid(axis="y", alpha=0.25)
ax.set_ylim(0, df["n"].max() * 1.12)

plt.tight_layout()
plt.savefig(OUT_PNG, dpi=200)
plt.close()

print("LISTO")
print("PNG:", OUT_PNG)
print("CSV:", OUT_CSV)
print("\nCaídas detectadas:")
if len(drops):
    print(drops[["anio", "n_prev", "n", "diff_abs", "pct_change"]].to_string(index=False))
else:
    print("No se detectaron caídas con el umbral actual.")
