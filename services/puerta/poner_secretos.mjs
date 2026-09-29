// Sube los secretos de producción del Worker y la clave compartida de Modal, sin que pasen por
// ningún otro lado (ni la terminal ni un chat). Lee .secretos.produccion (ignorado por git), genera
// LAB_CLAVE, manda todo a `wrangler secret bulk` por la entrada estándar y a Modal, y al terminar
// borra el archivo. Nunca imprime un valor, solo nombres.
//   node poner_secretos.mjs
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';

const ARCHIVO = new URL('.secretos.produccion', import.meta.url);
// nombre: forma esperada (solo para avisar de un valor pegado en el lugar equivocado)
const CLAVES = {
  TURNSTILE_SECRET: /^0x4[A-Za-z0-9_-]{20,}$/,
  GROQ_API_KEY: /^gsk_[A-Za-z0-9]{20,}$/,
  SUPABASE_SERVICE_KEY: /^sb_secret_[A-Za-z0-9_-]{10,}$/,
  MODAL_KEY: /^wk-[A-Za-z0-9]+$/,
  MODAL_SECRET: /^ws-[A-Za-z0-9]+$/,
};

if (!existsSync(ARCHIVO)) {
  writeFileSync(ARCHIVO, Object.keys(CLAVES).map((k) => k + '=').join('\n') + '\n');
  console.log('Listo el archivo services/puerta/.secretos.produccion (ignorado por git).');
  console.log('Pega cada valor después del «=», guarda y vuelve a correr: node poner_secretos.mjs');
  process.exit(0);
}

const valores = {};
for (const linea of readFileSync(ARCHIVO, 'utf8').split(/\r?\n/)) {
  const m = /^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/.exec(linea);
  if (m && m[1] in CLAVES) valores[m[1]] = m[2].replace(/^["']|["']$/g, '');
}
const faltan = Object.keys(CLAVES).filter((k) => !valores[k]);
if (faltan.length) { console.error('Faltan: ' + faltan.join(', ') + '. No se subió nada.'); process.exit(1); }
const raros = Object.entries(CLAVES).filter(([k, re]) => !re.test(valores[k])).map(([k]) => k);
if (raros.length) {
  console.error('Estos no tienen la forma esperada (¿pegados en el lugar equivocado?): ' + raros.join(', ') + '. No se subió nada.');
  process.exit(1);
}

// La clave compartida entre el Worker y Modal: nueva, de 32 bytes, que nadie tiene que ver.
valores.LAB_CLAVE = randomBytes(32).toString('base64url');

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const w = spawnSync(npx, ['wrangler', 'secret', 'bulk', '--env', 'produccion'], {
  input: JSON.stringify(valores), stdio: ['pipe', 'inherit', 'inherit'], shell: process.platform === 'win32',
});
if (w.status !== 0) { console.error('wrangler falló; el archivo se conserva para reintentar.'); process.exit(1); }

const mo = spawnSync('modal', ['secret', 'create', 'nodos-lab', 'LAB_CLAVE=' + valores.LAB_CLAVE, '--force'], { stdio: ['ignore', 'ignore', 'inherit'] });
if (mo.status !== 0) {
  console.error('Modal falló. El Worker ya tiene la clave nueva; vuelve a correr el script para regenerarla en los dos.');
  process.exit(1);
}

unlinkSync(ARCHIVO);
console.log('Subidos al Worker (produccion): ' + Object.keys(valores).join(', ') + '.');
console.log('Modal: secreto «nodos-lab» con la LAB_CLAVE nueva. El archivo de secretos se borró.');
