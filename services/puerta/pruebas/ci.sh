#!/usr/bin/env bash
# Pruebas del Worker contra `wrangler dev` y el servicio de datos simulado, en el CI (Linux; usa
# pkill, que Git Bash en Windows no trae: ahí, los mismos pasos a mano, como dice el README).
# Sin cuenta de Cloudflare, sin Modal y sin IA: no gasta nada.
#   1. puerta.test.mjs (11) y la prueba de estrés (50 a la vez) con pruebas/wrangler.ci.jsonc;
#   2. fila.test.mjs (4) con pruebas/wrangler.fila.jsonc (un lugar y un proxy lento).
# Correr desde services/puerta: bash pruebas/ci.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f pruebas/claves.local.json ] || npm run claves --silent
cp .dev.vars pruebas/.dev.vars
LAB_CLAVE=$(grep '^LAB_CLAVE=' .dev.vars | cut -d= -f2-)
ESTADO=$(mktemp -d)   # registros y servicio simulado
UNO=$(mktemp -d)      # estado de la fase 1
DOS=$(mktemp -d)      # estado de la fase 2: aparte, porque el contador del límite por IP también se guarda ahí

limpiar() {
  pkill -f "wrangler dev" 2>/dev/null || true
  pkill -f workerd 2>/dev/null || true
  pkill -f servicio_simulado 2>/dev/null || true
  rm -f pruebas/.dev.vars
  rm -rf "$ESTADO" "$UNO" "$DOS"
}
trap limpiar EXIT

esperar() { # esperar URL
  for _ in $(seq 1 90); do curl -sf -m 3 -o /dev/null "$1" && return 0; sleep 1; done
  echo "no respondió: $1"; return 1
}
levantar() { # levantar config.jsonc directorio-de-estado
  npx wrangler d1 migrations apply nodos --local -c "$1" --persist-to "$2" > /dev/null
  npx wrangler dev -c "$1" --persist-to "$2" --port 8787 --ip 127.0.0.1 > "$ESTADO/wrangler.log" 2>&1 &
  esperar http://127.0.0.1:8787/api/salud || { tail -40 "$ESTADO/wrangler.log"; return 1; }
}
bajar() { pkill -f "wrangler dev" 2>/dev/null || true; pkill -f workerd 2>/dev/null || true; sleep 2; }

LAB_CLAVE="$LAB_CLAVE" node pruebas/servicio_simulado.mjs > "$ESTADO/simulado.log" 2>&1 &
esperar http://127.0.0.1:8770/salud

echo "== Worker con la fila de 2 lugares (wrangler.ci.jsonc)"
levantar pruebas/wrangler.ci.jsonc "$UNO"
node --test pruebas/puerta.test.mjs
node pruebas/estres.mjs 50
bajar

echo "== Worker con un lugar y el proxy lento (wrangler.fila.jsonc)"
levantar pruebas/wrangler.fila.jsonc "$DOS"
node --test pruebas/fila.test.mjs
bajar
echo "Listo: pruebas del Worker completas."
