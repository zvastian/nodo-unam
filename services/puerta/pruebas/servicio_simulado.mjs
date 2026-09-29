// Servicio de datos simulado para las pruebas del Worker en el CI y la prueba de estrés: responde
// como services/lab (misma forma de /v1/contexto, sin el modelo ni los 3 GB de artefactos) con el
// contexto de ejemplo del Laboratorio. Exige X-Lab-Clave como el real.
//   LAB_CLAVE=… PUERTO=8770 RETRASO_MS=300 node pruebas/servicio_simulado.mjs
import http from 'node:http';
import { readFileSync } from 'node:fs';

const PUERTO = +(process.env.PUERTO || 8770);
const RETRASO_MS = +(process.env.RETRASO_MS || 300);   // lo que tarda el real (embedding y búsqueda)
const CLAVE = process.env.LAB_CLAVE || '';
const ejemplo = JSON.parse(readFileSync(new URL('../../../prototypes/atlas_vecindario_mvp/lab/datos_ejemplo.json', import.meta.url), 'utf8'));
delete ejemplo.entrada;
let atendidas = 0, simultaneas = 0, maxSimultaneas = 0;

http.createServer((req, res) => {
  const responder = (status, cuerpo) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(cuerpo)); };
  if (req.method === 'GET' && req.url === '/salud') return responder(200, { ok: true, atendidas, max_simultaneas: maxSimultaneas });
  if (!req.url.startsWith('/v1/')) return responder(404, { detail: 'no' });
  if (CLAVE && req.headers['x-lab-clave'] !== CLAVE) return responder(401, { detail: 'sin clave' });
  const partes = [];
  req.on('data', (p) => partes.push(p));
  req.on('end', async () => {
    let e;
    try { e = JSON.parse(Buffer.concat(partes).toString('utf8')); } catch { return responder(422, { detail: [{ loc: ['body'], msg: 'json' }] }); }
    if (typeof e.title !== 'string' || e.title.length < 3) return responder(422, { detail: [{ loc: ['body', 'title'], msg: 'corto' }] });
    simultaneas++; maxSimultaneas = Math.max(maxSimultaneas, simultaneas);
    await new Promise((r) => setTimeout(r, RETRASO_MS));
    simultaneas--; atendidas++;
    responder(200, { ...ejemplo, tiempos_ms: { embedding: RETRASO_MS, contexto: 0 } });
  });
}).listen(PUERTO, '127.0.0.1', () => console.log(`servicio simulado en :${PUERTO} (retraso ${RETRASO_MS} ms)`));
