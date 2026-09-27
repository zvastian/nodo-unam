"""Mide el servicio de datos desplegado (Modal o Cloud Run): arranque en frío, latencia despierto y
paridad con una referencia local.

  python services/lab/medir_remoto.py URL [--referencia http://127.0.0.1:8770] [--frio]

Lee la clave compartida de services/puerta/pruebas/claves.local.json (o de LAB_CLAVE). Con
--frio espera a que el contenedor se apague (scaledown de 2 min) y mide un segundo arranque.
Solo usa urllib: corre con cualquier Python.
"""
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).parent


def pedir(url, cuerpo=None, clave="", espera=180):
    h = {"Content-Type": "application/json", "X-Lab-Clave": clave}
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    r = urllib.request.Request(url, data=datos, headers=h, method="POST" if datos else "GET")
    t0 = time.perf_counter()
    with urllib.request.urlopen(r, timeout=espera) as resp:
        out = json.loads(resp.read())
    return out, time.perf_counter() - t0


def main():
    args = sys.argv[1:]
    url = args[0].rstrip("/")
    ref = args[args.index("--referencia") + 1].rstrip("/") if "--referencia" in args else ""
    clave = os.getenv("LAB_CLAVE") or json.loads((AQUI.parent / "puerta/pruebas/claves.local.json").read_text())["labClave"]
    casos = json.loads((AQUI / "casos_evaluacion.json").read_text(encoding="utf8"))

    salud, t = pedir(url + "/salud", espera=300)
    print(f"primera respuesta (/salud): {t:.1f} s  arranque interno: {salud.get('arranque_s')} s")

    tiempos, emb, ctx, iguales = [], [], [], 0
    for c in casos:
        entrada = {k: v for k, v in c.items() if k != "caso"}
        out, t = pedir(url + "/v1/contexto", entrada, clave)
        tiempos.append(t)
        emb.append(out["tiempos_ms"]["embedding"])
        ctx.append(out["tiempos_ms"]["contexto"])
        if ref:
            local, _ = pedir(ref + "/v1/contexto", entrada, clave)
            # Campo por campo, salvo los tiempos (como en la prueba de Docker).
            same = {k: v for k, v in out.items() if k != "tiempos_ms"} == {k: v for k, v in local.items() if k != "tiempos_ms"}
            iguales += same
            print(f"  {c['caso']:<14} {t*1000:6.0f} ms  {'igual' if same else 'DISTINTO'} a la referencia")
        else:
            print(f"  {c['caso']:<14} {t*1000:6.0f} ms")
    med = statistics.median
    print(f"despierto: mediana {med(tiempos)*1000:.0f} ms de ida y vuelta "
          f"(embedding {med(emb)} ms, contexto {med(ctx)} ms, red y cola {med(tiempos)*1000 - med(emb) - med(ctx):.0f} ms)")
    if ref:
        print(f"paridad: {iguales}/{len(casos)} casos idénticos")

    if "--frio" in args:
        print("esperando 150 s a que se apague el contenedor...")
        time.sleep(150)
        entrada = {k: v for k, v in casos[0].items() if k != "caso"}
        _, t = pedir(url + "/v1/contexto", entrada, clave, espera=300)
        print(f"análisis con arranque en frío: {t:.1f} s")


if __name__ == "__main__":
    main()
