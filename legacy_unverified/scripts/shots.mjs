/**
 * shots —— 生成写文档/README 用的展示截图（非验收用）。
 *
 * 走和 check:align 一样的 Chrome DevTools Protocol，不引入额外依赖。
 * 产物写入 reports/shots/。
 *
 * 用法：node scripts/shots.mjs
 */

import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const CHROME = process.env.CHROME_PATH
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT = join(ROOT, 'reports', 'shots');
const W = 1800;
const H = 1150;

const SHOTS = [
  ['overview', "window.__app.focus('overview', true)"],
  ['plan-overlay', "(() => { window.__app.focus('overview', true); window.__app.setPlanOverlay(1); return 1; })()"],
  ['learning-center', "window.__app.focus('cloud')"],
  ['cutaway-pool', "window.__app.focus('pool')"],
];

function launch() {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-shots-'));
  const p = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + dir,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
    '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--window-size=' + W + ',' + H, 'about:blank'
  ], { stdio: ['ignore', 'pipe', 'pipe'] });
  return new Promise((res, rej) => {
    let buf = '';
    const t = setTimeout(() => rej(new Error('Chrome 启动超时')), 30000);
    p.stderr.on('data', d => {
      buf += d.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(t); res({ proc: p, ws: m[1] }); }
    });
    p.on('exit', c => { clearTimeout(t); rej(new Error('Chrome 退出 ' + c)); });
  });
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); }
  open() {
    return new Promise((res, rej) => {
      this.sock = new WebSocket(this.ws);
      this.sock.onopen = () => res();
      this.sock.onerror = rej;
      this.sock.onmessage = ev => {
        const m = JSON.parse(ev.data);
        if (m.id && this.pending.has(m.id)) {
          const { resolve: r, reject: j } = this.pending.get(m.id);
          this.pending.delete(m.id);
          m.error ? j(new Error(JSON.stringify(m.error))) : r(m.result);
        }
      };
    });
  }
  send(method, params, sessionId) {
    const id = ++this.id;
    const msg = { id, method, params: params || {} };
    if (sessionId) msg.sessionId = sessionId;
    return new Promise((r, j) => {
      this.pending.set(id, { resolve: r, reject: j });
      this.sock.send(JSON.stringify(msg));
    });
  }
  close() { try { this.sock.close(); } catch (_) {} }
}

async function main() {
  const dist = join(ROOT, 'dist', 'index.html');
  if (!existsSync(dist)) throw new Error('缺少 dist/index.html，先运行 npm run build');

  const { proc, ws } = await launch();
  const cdp = new CDP(ws);
  await cdp.open();
  const { targetInfos } = await cdp.send('Target.getTargets');
  const page = targetInfos.find(t => t.type === 'page');
  const { sessionId } = await cdp.send('Target.attachToTarget',
    { targetId: page.targetId, flatten: true });
  const send = (m, p) => cdp.send(m, p || {}, sessionId);

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride',
    { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: pathToFileURL(dist).href });

  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    const r = await send('Runtime.evaluate',
      { expression: '!!(window.__app && window.__app.scene)', returnByValue: true });
    if (r.result && r.result.value) break;
    await new Promise(r2 => setTimeout(r2, 300));
  }

  if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true });
  for (const [name, expr] of SHOTS) {
    await send('Runtime.evaluate',
      { expression: `(() => { ${expr}; return 1; })()`, returnByValue: true });
    await new Promise(r => setTimeout(r, 1900));
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(OUT, name + '.png'), Buffer.from(shot.data, 'base64'));
    console.log('写入 reports/shots/' + name + '.png');
  }
  cdp.close();
  proc.kill('SIGTERM');
}

main().then(() => process.exit(0)).catch(e => {
  console.error('shots 失败：' + e.message);
  process.exit(1);
});
