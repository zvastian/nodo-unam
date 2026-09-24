// Harness minimo de CDP: lanza Chrome headless, corre pasos {eval|wait|shot|mouse|clickAt|hoverAt|wheel|key} y vuelca consola.
// Uso: node tools/cdp.mjs <url> <steps.json> <outdir>
// Variables de entorno:
//   CHROME=<ruta al binario>   (por defecto: Chrome de Windows; en Linux, p. ej. /usr/bin/google-chrome o chromium)
//   SIZE=390,844               (tamano de ventana; por defecto 1600,900 = escritorio)
//   GPU=1                      (usa la GPU real via D3D11 en Windows; sin GPU, WebGL por software (swiftshader) subestima los fps)
// Ejemplo de pasos: [{"wait":9000,"eval":"document.getElementById('story-close').click();1"},{"wait":2500,"shot":"mapa"}]
// La app expone window.__debugAtlas = {state, selectNode, ...} para manejarla desde los pasos.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const [url, stepsPath, outDir] = process.argv.slice(2);
const steps = JSON.parse(fs.readFileSync(stepsPath, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const PORT = 9333;
const profile = path.resolve(outDir, 'profile');
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const gl = process.env.GPU ? ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'] : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'];
const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--no-sandbox',
  `--window-size=${process.env.SIZE || '1600,900'}`, ...gl,
  '--disable-extensions', '--no-first-run', '--no-default-browser-check', 'about:blank'
], { stdio: ['ignore','ignore','pipe'] }); chrome.on('error', e => console.log('SPAWN ERR', e.message));

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 150; i++) {
  try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); const l = await r.json(); target = l.find(t => t.type === 'page'); if (target) break; if (i%25===0) console.log('targets', l.map(t=>t.type)); } catch (e) { if (i%25===0) console.log('noconn', e.message); }
  await sleep(200);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0; const pending = new Map(); const logs = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  else if (m.method === 'Runtime.consoleAPICalled') logs.push(`[${m.params.type}] ` + m.params.args.map(a => a.value ?? a.description).join(' '));
  else if (m.method === 'Runtime.exceptionThrown') logs.push('[exception] ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
});
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send('Runtime.enable'); await send('Page.enable');
// (sin override de metricas: headless usa --window-size)
await send('Page.navigate', { url });

for (const s of steps) {
  if (s.wait) await sleep(s.wait);
  if (s.eval) {
    const r = await send('Runtime.evaluate', { expression: s.eval, awaitPromise: true, returnByValue: true });
    const v = r.result?.result?.value ?? r.result?.exceptionDetails?.exception?.description ?? r.result?.result?.description;
    console.log('EVAL', s.label || '', JSON.stringify(v));
  }
  if (s.mouse) { // {type, x, y, buttons, modifiers}
    await send('Input.dispatchMouseEvent', { button: 'left', clickCount: 1, ...s.mouse });
  }
  if (s.clickAt) { // evalua una expresion que devuelve [x,y] y hace clic REAL ahi
    const r = await send('Runtime.evaluate', { expression: s.clickAt, returnByValue: true });
    const [x, y] = r.result.result.value;
    for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1 });
    console.log('CLICK', s.label || '', Math.round(x), Math.round(y));
  }
  if (s.hoverAt) {
    const r = await send('Runtime.evaluate', { expression: s.hoverAt, returnByValue: true });
    const [x, y] = r.result.result.value;
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x - 3, y: y - 3, buttons: 0 });
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, buttons: 0 });
    console.log('HOVER', s.label || '', Math.round(x), Math.round(y));
  }
  if (s.wheel) await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: s.wheel.x, y: s.wheel.y, deltaX: 0, deltaY: s.wheel.dy });
  if (s.key) await send('Input.dispatchKeyEvent', s.key);
  if (s.shot) {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(outDir, s.shot + '.png'), Buffer.from(r.result.data, 'base64'));
    console.log('SHOT', s.shot);
  }
}
console.log('--- console ---\n' + logs.slice(-40).join('\n'));
ws.close(); chrome.kill();
process.exit(0);
