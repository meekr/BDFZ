/**
 * check:align —— 把模型渲染成正交顶视图，与 02 屋顶平面比较。
 *
 * 不引入 Playwright / Puppeteer 依赖：直接通过 Chrome DevTools Protocol
 * 驱动本机已安装的 Chrome（macOS 默认路径，可用 CHROME_PATH 覆盖），
 * 在页面里调用 window.__app.setOrthoTop() 切到正交顶视，
 * 再用 Page.captureScreenshot 取图。
 *
 * 用法：node scripts/check_align.mjs [--out reports/align]
 */

import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const CHROME = process.env.CHROME_PATH
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const args = process.argv.slice(2);
const outDir = (() => {
  const i = args.indexOf('--out');
  return resolve(ROOT, i > -1 ? args[i + 1] : 'reports/align');
})();

const W = 2000;
const H = 1414;

function launch() {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-align-'));
  const p = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + dir,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
    '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--disable-gpu-sandbox', '--window-size=' + W + ',' + H,
    'about:blank'
  ], { stdio: ['ignore', 'pipe', 'pipe'] });
  return new Promise((res, rej) => {
    let buf = '';
    const t = setTimeout(() => rej(new Error('Chrome 启动超时: ' + buf.slice(-400))), 30000);
    p.stderr.on('data', d => {
      buf += d.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(t); res({ proc: p, ws: m[1] }); }
    });
    p.on('exit', c => { clearTimeout(t); rej(new Error('Chrome 退出 ' + c)); });
  });
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.events = []; }
  open() {
    return new Promise((res, rej) => {
      const sock = new WebSocket(this.ws);
      this.sock = sock;
      sock.onopen = () => res();
      sock.onerror = e => rej(e);
      sock.onmessage = ev => {
        const msg = JSON.parse(ev.data);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve: r, reject: j } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) j(new Error(JSON.stringify(msg.error)));
          else r(msg.result);
        } else if (msg.method) this.events.push(msg);
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
  const { proc, ws } = await launch();
  const cdp = new CDP(ws);
  await cdp.open();

  const targets = await cdp.send('Target.getTargets');
  const page = targets.targetInfos.find(t => t.type === 'page');
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId: page.targetId, flatten: true });
  const send = (m, p) => cdp.send(m, p || {}, sessionId);

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride',
    { width: W, height: H, deviceScaleFactor: 1, mobile: false });

  const url = pathToFileURL(join(ROOT, 'dist/index.html')).href;
  await send('Page.navigate', { url });

  // 等待模型就绪
  const deadline = Date.now() + 60000;
  let ready = false;
  while (Date.now() < deadline) {
    const r = await send('Runtime.evaluate', {
      expression: '!!(window.__app && window.__app.setOrthoTop && window.__app.scene)',
      returnByValue: true
    });
    if (r.result && r.result.value === true) { ready = true; break; }
    await new Promise(r2 => setTimeout(r2, 400));
  }
  if (!ready) throw new Error('页面未就绪（window.__app 缺失）');

  // 正交顶视：覆盖 02 图的全部画幅（用 frames.json 的世界范围）
  const bounds = await send('Runtime.evaluate', {
    expression: `(() => {
      const fr = window.__app.data.FRAMES;
      const a = fr.frames['02'].affine;
      const [w, h] = fr.frames['02'].size;
      const pts = [[0,0],[w,0],[0,h],[w,h]].map(([px,py]) => [a[0][0]*px+a[0][1]*py+a[0][2], a[1][0]*px+a[1][1]*py+a[1][2]]);
      const xs = pts.map(p=>p[0]), zs = pts.map(p=>p[1]);
      return { x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs) };
    })()`,
    returnByValue: true
  });
  const b = bounds.result.value;
  await send('Runtime.evaluate', {
    expression: `(() => {
      window.__app.setOrthoTop(${JSON.stringify(b)});
      window.__app.setPlanOverlay(0);
      window.__app.setSectionOverlay(false);
      window.__app.setFloorOverlay(false);
      window.__app.setCutaway(false);
      window.__app.setFlatRender(true);
      ['topbar','sidebar','info','bottombar','intro','labelLayer','scaleBar','cutHint','crumb']
        .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
      document.querySelectorAll('.poi-label,.dim-label').forEach(e => e.style.display='none');
      document.querySelectorAll('#labelLayer *').forEach(e => e.style.display='none');
      document.querySelectorAll('.dim-label').forEach(e => e.style.display='none');
      return true;
    })()`,
    returnByValue: true
  });
  await new Promise(r => setTimeout(r, 1200));

  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  // 球场单独一层：验证"球场摆位"这条链路（数据 → 相机 → 像素）
  await send('Runtime.evaluate', {
    expression: "(() => { const a = window.__app; a.setFlatRender(true, ['courts']); return true; })()",
    returnByValue: true
  });
  await new Promise(r => setTimeout(r, 700));
  {
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    writeFileSync(join(outDir, 'model_courts_only.png'), Buffer.from(shot.data, 'base64'));
  }
  await send('Runtime.evaluate', {
    expression: "(() => { window.__app.setFlatRender(false); window.__app.setFlatRender(true); return true; })()",
    returnByValue: true
  });
  await new Promise(r => setTimeout(r, 500));

  const shots = [['all', null], ['cloud', ['cloud']], ['dorm', ['dorm']], ['sports', ['sports']]];
  for (const [name, layers] of shots) {
    await send('Runtime.evaluate', {
      expression: `(() => {
        window.__app.setLayers(${layers ? JSON.stringify(layers) : 'null'});
        return true;
      })()`,
      returnByValue: true
    });
    await new Promise(r => setTimeout(r, 500));
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    writeFileSync(join(outDir, name === 'all' ? 'model_top.png' : `model_${name}.png`),
      Buffer.from(shot.data, 'base64'));
  }

  cdp.close();
  proc.kill('SIGTERM');
  console.log('写入 ' + join(outDir, 'model_top.png'));
  console.log('世界范围 ' + JSON.stringify(b));
}

main().then(() => process.exit(0)).catch(e => {
  console.error('check:align 失败：' + e.message);
  process.exit(1);
});
