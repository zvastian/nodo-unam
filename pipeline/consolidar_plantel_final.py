"""Ultima pasada de consolidacion de plantel_estandarizado/plantel_display.

Encontrado con dos tecnicas nuevas (a peticion del usuario, "busca casos
similares"):
1. Clave laxa: ignora acentos + palabras de relleno (de, la, unidad,
   universidad, campus, unam, y, en) -- captura duplicados por orden de
   palabras o preposicion faltante que el detector original no veia.
2. Similitud de texto (SequenceMatcher >= 0.90) -- captura typos puntuales
   (letras de mas/de menos, palabras pegadas).

CRITICO: la tecnica 2 genero ~97 pares candidatos, la gran mayoria FALSOS
POSITIVOS (instituciones reales distintas que solo se parecen en texto,
ej. "Instituto de Ecologia" vs "Instituto de Geologia", "Universidad
Panamericana" vs "Universidad Latinoamericana", programas de posgrado en
disciplinas distintas). Cada fusion de esta lista fue revisada a mano;
solo se aplican las que son evidentemente la misma entidad con un error
tipografico, no una coincidencia de texto. Los rechazados se documentan
para que quede claro que se revisaron y se descartaron, no que se
pasaron por alto.
"""
from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_plantel_final_pass_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "plantel_final_pass_2026-09-20.csv"

# (estandarizado_viejo, estandarizado_nuevo, display_nuevo_o_None)
# display_nuevo=None => se calcula por mayoria simple entre lo que quede en el grupo fusionado
MERGES = [
    ("facultad quimica unam", "facultad de quimica unam", None),
    ("escuela de administracion y contaduria", "escuela de contaduria y administracion", None),
    ("escuela administracion contabilidad y economia", "escuela de administracion contabilidad y economia", None),
    ("escuela de mexicana de arquitectura", "escuela mexicana de arquitectura", None),
    ("de la secretaria de salud", "secretaria de salud", "Secretaría de Salud"),
    ("facultad de ingenieria division de estudios de posgrado unam", "division de estudios de posgrado facultad de ingenieria unam", None),
    ("centro panamericano de estudios superiores", "universidad centro panamericano de estudios superiores", None),
    ("programa unico de especializaciones en ingenieria", "programa unico de especializaciones de ingenieria", None),
    ("centro de estudios superiores martinez de la torre", "centro de estudios superiores de martinez de la torre", None),
    ("facultad de quimica division de estudios de postgrado unam", "facultad de quimica division de estudios de posgrado unam", None),
    ("facultad de filosofia y letras division de estudios de postgrado unam", "facultad de filosofia y letras division de estudios de posgrado unam", None),
    ("programa de posgrados en ciencias del mar y limnologia unam", "programa de posgrado en ciencias del mar y limnologia unam", None),
    ("programa de maestria ydoctorado en estudios mesoamericanos", "programa de maestria y doctorado en estudios mesoamericanos", None),
    ("universidad lasalle escuela de ingenieria", "universidad la salle escuela de ingenieria", None),
    ("facultad de filosofia yletras unam", "facultad de filosofia y letras unam", None),
    ("facultad de arquitetura unam", "facultad de arquitectura unam", None),
    ("cologio de ciencias y humanidades unidad academica de los ciclos profesional y de posgrado",
     "colegio de ciencias y humanidades unidad academica de los ciclos profesional y de posgrado",
     "Colegio de Ciencias y Humanidades, Unidad Académica de los Ciclos Profesional y de Posgrado"),
    ("colegio de ciencias y hunanidades unidad academica de los ciclos profesional y de posgrado",
     "colegio de ciencias y humanidades unidad academica de los ciclos profesional y de posgrado",
     "Colegio de Ciencias y Humanidades, Unidad Académica de los Ciclos Profesional y de Posgrado"),
    ("colegio de ciencias y humanidades unidad academica de los ciclos profesional y posgrado",
     "colegio de ciencias y humanidades unidad academica de los ciclos profesional y de posgrado",
     "Colegio de Ciencias y Humanidades, Unidad Académica de los Ciclos Profesional y de Posgrado"),
    ("universidad autonoma de guadalajara guadalajara jal", "universidad autonoma de guadalajara guadalajara", None),
    ("universidad don vasco uruapan mich", "universidad don vasco uruapan", None),
    ("escuela normal superior mexico df", "escuela normal superior de mexico", None),
    ("escuela nacional de esutusio profesionales acatlan", "escuela nacional de estudios profesionales acatlan", "Escuela Nacional de Estudios Profesionales Acatlán"),
    ("escuela nacional estudios profesionales acatlan", "escuela nacional de estudios profesionales acatlan", "Escuela Nacional de Estudios Profesionales Acatlán"),
    ("universidad del valle de mexico facultad de derecho", "universidad del valle de mexico escuela de derecho", None),
    ("instituto nacional de psiquiatria ramon de la fuente", "instituto nacional de psiquiatria ramon de la fuente muniz", None),
    ("programa de maestria y doctoradoadoado en ingenieria", "programa de maestria y doctorado en ingenieria", None),
    ("universidad autonoma de guadalajara escuela de odontologia", "universidad autonoma de guadalajara facultad de odontologia", None),
    ("universidad de sotavento campus orizaba", "universidad de sotavento orizaba", "Universidad de Sotavento, Campus Orizaba"),
]

# Casos revisados y DESCARTADOS explicitamente (instituciones/programas reales
# distintos, similitud de texto es coincidencia) -- documentado para que quede
# claro que se evaluaron, no que se ignoraron.
DESCARTADOS = [
    ("instituto de ecologia unam", "instituto de geologia unam", "institutos distintos (Ecologia != Geologia)"),
    ("instituto de biologia unam", "instituto de geologia unam", "institutos distintos"),
    ("instituto de biotecnologia unam", "instituto de biologia unam", "institutos distintos"),
    ("instituto de biotecnologia unam", "instituto de ecologia unam", "institutos distintos"),
    ("instituto de neurobiologia unam", "instituto de biologia unam", "institutos distintos"),
    ("programa de maestria y doctorado en ciencias bioquimicas", "programa de maestria y doctorado en ciencias quimicas", "programas de posgrado distintos (Bioquimicas != Quimicas)"),
    ("programa de posgrado en ciencias bioquimicas unam", "programa de posgrado en ciencias quimicas unam", "programas distintos"),
    ("programa de posgrado en ciencias bioquimicas unam", "programa de posgrado en ciencias biomedicas unam", "programas distintos"),
    ("programa de posgrado en ciencias fisicas unam", "programa de posgrado en ciencias quimicas unam", "programas distintos"),
    ("programa de posgrado en ciencias fisicas unam", "programa de posgrado en ciencias biomedicas unam", "programas distintos"),
    ("programa de posgrado en ciencias biologicas unam", "programa de posgrado en ciencias bioquimicas unam", "programas distintos"),
    ("programa de posgrado en ciencias biologicas unam", "programa de posgrado en ciencias fisicas unam", "programas distintos"),
    ("programa de posgrado en ciencias biologicas unam", "programa de posgrado en ciencias biomedicas unam", "programas distintos"),
    ("programa de posgrado en ciencias biologicas unam", "programa de posgrado en ciencias quimicas unam", "programas distintos"),
    ("instituto de investigaciones filologicas unam", "instituto de investigaciones filosoficas unam", "institutos distintos"),
    ("facultad de estudios superiores aragon unam", "facultad de estudios superiores zaragoza unam", "campus FES distintos"),
    ("facultad de estudios superiores acatlan unam", "facultad de estudios superiores iztacala unam", "campus FES distintos"),
    ("facultad de estudios superiores acatlan unam", "facultad de estudios superiores cuautitlan unam", "campus FES distintos"),
    ("facultad de estudios superiores aragon unam", "facultad de estudios superiores acatlan unam", "campus FES distintos"),
    ("facultad de estudios superiores iztacala unam", "facultad de estudios superiores zaragoza unam", "campus FES distintos"),
    ("instituto de geofisica unam", "instituto de fisica unam", "institutos distintos"),
    ("instituto de geologia unam", "instituto de geografia unam", "institutos distintos"),
    ("instituto de investigaciones biomedicas unam", "instituto de investigaciones juridicas unam", "institutos distintos"),
    ("instituto de investigaciones biomedicas unam", "instituto de investigaciones economicas unam", "institutos distintos"),
    ("instituto de investigaciones biomedicas unam", "instituto de investigaciones historicas unam", "institutos distintos"),
    ("instituto de investigaciones esteticas unam", "instituto de investigaciones historicas unam", "institutos distintos"),
    ("instituto de investigaciones antropologicas unam", "instituto de investigaciones filologicas unam", "institutos distintos"),
    ("instituto de investigaciones sociales unam", "instituto de investigaciones historicas unam", "institutos distintos"),
    ("escuela nacional de estudios superiores unidad morelia unam", "escuela nacional de estudios superiores unidad merida unam", "sedes ENES distintas (ya verificado)"),
    ("escuela nacional de estudios superiores unidad leon unam", "escuela nacional de estudios superiores unidad merida unam", "sedes ENES distintas"),
    ("escuela nacional de estudios superiores unidad leon unam", "escuela nacional de estudios superiores unidad morelia unam", "sedes ENES distintas"),
    ("escuela nacional de estudios superiores unidad merida unam", "escuela nacional de estudios superiores unidad juriquilla unam", "sedes ENES distintas"),
    ("escuela nacional de estudios superiores unidad morelia unam", "escuela nacional de estudios superiores unidad juriquilla unam", "sedes ENES distintas"),
    ("universidad panamericana", "universidad latinoamericana", "universidades distintas, no relacionadas"),
    ("escuela de psicologia", "a c escuela de psicologia", "'A.C.' sugiere escuela privada especifica distinta, no se asume duplicado"),
    ("escuela de pedagogia", "a c escuela de pedagogia", "misma razon: A.C. probablemente distinta"),
    ("a c escuela de psicologia", "a c escuela de sociologia", "escuelas distintas (Psicologia != Sociologia)"),
    ("universidad la salle escuela de contaduria y administracion", "universidad villa rica escuela de contaduria y administracion", "universidades distintas (La Salle != Villa Rica)"),
    ("universidad latina escuela de contaduria y administracion", "universidad villa rica escuela de contaduria y administracion", "universidades distintas"),
    ("universidad latina escuela de contaduria y administracion", "universidad la salle escuela de contaduria y administracion", "universidades distintas"),
    ("universidad autonoma de guadalajara escuela de odontologia", "universidad autonoma de guadalajara escuela de psicologia", "escuelas distintas"),
    ("universidad autonoma de guadalajara escuela de pedagogia", "universidad autonoma de guadalajara escuela de psicologia", "escuelas distintas"),
    ("universidad autonoma de guadalajara escuela de ingenieria", "universidad autonoma de guadalajara escuela de ingenieria civil", "posible distincion real (Ingenieria general != Ingenieria Civil)"),
    ("universidad autonoma de guadalajara escuela de arquitectura", "universidad autonoma de guadalajara facultad de arquitectura", "no se pudo confirmar si es la misma unidad, se deja para revision manual"),
    ("instituto nacional de cardiologia mexico", "instituto nacional de neurologia mexico", "institutos distintos"),
    ("universidad autonoma del estado de mexico", "universidad autonoma del estado de morelos", "universidades estatales distintas"),
    ("centro universitario texcoco", "centro universitario mexico", "instituciones distintas"),
    ("universidad anahuac escuela de psicologia", "universidad anahuac escuela de economia", "escuelas distintas"),
    ("universidad intercontinental escuela de psicologia", "universidad intercontinental escuela de pedagogia", "escuelas distintas"),
    ("universidad insurgentes plantel leon", "universidad insurgentes plantel xola", "planteles distintos (Leon != Xola)"),
    ("programa unico de especializaciones en economia", "programa unico de especializaciones en psicologia", "especialidades distintas"),
    ("programa unico de especializaciones en economia", "programa unico de especializaciones en derecho", "especialidades distintas"),
    ("programa de maestria y doctorado en ingenieria", "programa de maestria y doctorado en enfermeria", "posgrados distintos"),
    ("programa de maestria y doctorado en ingenieria", "programa de maestria y doctorado en linguistica", "posgrados distintos"),
    ("programa de maestria y doctorado en ingenieria", "programa de maestria y doctorado en geografia", "posgrados distintos"),
    ("programa de maestria y doctorado en musica", "programa de maestria y doctorado en linguistica", "posgrados distintos"),
    ("programa de maestria y doctorado en musica", "programa de maestria y doctorado en historia", "posgrados distintos"),
    ("programa de maestria y doctorado en psicologia", "programa de maestria y doctorado en musica", "posgrados distintos"),
    ("programa de maestria y doctorado en psicologia", "programa de maestria y doctorado en filosofia", "posgrados distintos"),
    ("programa de maestria y doctorado en psicologia", "programa de maestria y doctorado en pedagogia", "posgrados distintos"),
    ("programa de maestria y doctorado en pedagogia", "programa de maestria y doctorado en geografia", "posgrados distintos"),
    ("programa de maestria y doctorado en historia", "programa de maestria y doctorado en linguistica", "posgrados distintos"),
    ("programa de maestria y doctorado en letras", "programa de maestria y doctorado en historia", "posgrados distintos"),
    ("escuela de psicologia", "escuela de biologia", "escuelas distintas"),
]

DISPLAY_MAJORITY_THRESHOLD = 0.90


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()
    est_before = df["plantel_estandarizado"].nunique()

    audit_rows = []

    for old_est, new_est, forced_display in MERGES:
        mask = df["plantel_estandarizado"] == old_est
        count = int(mask.sum())
        if count == 0:
            print(f"AVISO: 0 filas para estandarizado={old_est!r}, se omite")
            continue
        df.loc[mask, "plantel_estandarizado"] = new_est
        audit_rows.append({
            "campo": "plantel_estandarizado",
            "valor_original": old_est,
            "valor_nuevo": new_est,
            "filas_afectadas": count,
            "regla": "revision_manual_similitud_2026-09-20",
        })
        print(f"  {count:>5}  est {old_est!r} -> {new_est!r}")

    # Recalcular consistencia de plantel_display SOLO para los grupos que cambiaron
    grupos_tocados = {new_est for _, new_est, _ in MERGES}
    forced = {new_est: disp for old_est, new_est, disp in MERGES if disp is not None}

    for est in grupos_tocados:
        sub = df.loc[df["plantel_estandarizado"] == est, "plantel_display"]
        counts = sub.value_counts()
        if est in forced:
            canonical = forced[est]
        elif len(counts) <= 1:
            continue
        else:
            top_share = counts.iloc[0] / counts.sum()
            if top_share < DISPLAY_MAJORITY_THRESHOLD:
                print(f"  AVISO: {est!r} quedo con display sin mayoria clara tras el merge: {dict(counts)} -- revisar a mano")
                continue
            canonical = counts.index[0]

        mask = (df["plantel_estandarizado"] == est) & (df["plantel_display"] != canonical)
        count = int(mask.sum())
        if count == 0:
            continue
        old_displays = df.loc[mask, "plantel_display"].unique().tolist()
        df.loc[mask, "plantel_display"] = canonical
        audit_rows.append({
            "campo": "plantel_display",
            "valor_original": f"{old_displays} (dentro de {est!r})",
            "valor_nuevo": canonical,
            "filas_afectadas": count,
            "regla": "recalculo_post_merge_2026-09-20",
        })
        print(f"  {count:>5}  disp (en {est!r}) -> {canonical!r}")

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    est_after = df["plantel_estandarizado"].nunique()
    assert n_after == n_before, f"Cambio en filas: {n_before} -> {n_after}"
    assert ids_after == ids_before, f"Cambio en thesis_id unicos: {ids_before} -> {ids_after}"

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"\nBackup escrito: {BACKUP_PATH.name}")

    df.to_parquet(DATA_PATH, index=False)

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(AUDIT_PATH, index=False, encoding="utf-8")

    descartados_path = ROOT / "pipeline" / "audits" / "plantel_descartados_2026-09-20.csv"
    pd.DataFrame(DESCARTADOS, columns=["valor_a", "valor_b", "motivo_no_fusion"]).to_csv(
        descartados_path, index=False, encoding="utf-8"
    )

    print(f"\nAudit log: {AUDIT_PATH}")
    print(f"Descartados (revisados, no fusionados): {descartados_path}  ({len(DESCARTADOS)} pares)")
    print(f"plantel_estandarizado unicos: {est_before} -> {est_after}")


if __name__ == "__main__":
    main()
