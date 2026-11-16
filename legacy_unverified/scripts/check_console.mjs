/**
 * check:console —— 打开构建产物，收集运行期报错/异常，并跑一遍主要交互路径。
 *
 * 计划 P5 的验收项「离线打开无报错」用这个脚本执行：
 *   npm run build && npm run check:console
 * 有 error/exception 时退出码非 0。
 */

import { spawn } from 'node:child_process';
import { mkdtempSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const CHROME = process.env.CHROME_PATH
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const EXERCISE = `(() => {
  const a = window.__app;
  const seen = [];
  a.TARGETS.forEach(t => { a.focus(t.id, true); seen.push(t.id); });
  a.setCutaway(true);
  for (let m = 0; m < 5; m++) a.setPlanOverlay(m);
  a.setPlanOverlay(0);
  a.setFloorOverlay(true);
  a.setSectionOverlay(true);
  a.setFloorOverlay(false);
  a.setSectionOverlay(false);
  a.setOrthoTop();
  a.setFlatRender(true);
  a.setFlatRender(false);
  a.setPerspective();
  a.setCutaway(false);
  a.setPlanOverlay(0);
  a.setFloorOverlay(false);
  a.setSectionOverlay(false);
  // 固定机位，保证两次测到的可见集一致（draw call 受视锥裁剪影响）
  a.camera.position.set(320, 300, 320);
  a.controls.target.set(0, 0, 0);
  a.controls.update();
  return seen.length;
})()`;

function launch() {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-console-'));
  const p = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + dir,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
    '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--window-size=1400,900', 'about:blank'
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
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.errors = []; }
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
          return;
        }
        if (m.method === 'Runtime.exceptionThrown') {
          const d = m.params.exceptionDetails;
          this.errors.push('EXC: ' + ((d.exception && d.exception.description) || d.text));
        }
        if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
          this.errors.push('ERR: ' + m.params.args.map(a => a.value || a.description).join(' '));
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
  await send('Page.navigate', { url: pathToFileURL(dist).href });

  const deadline = Date.now() + 60000;
  let ready = false;
  while (Date.now() < deadline) {
    const r = await send('Runtime.evaluate',
      { expression: '!!(window.__app && window.__app.scene)', returnByValue: true });
    if (r.result && r.result.value) { ready = true; break; }
    await new Promise(r2 => setTimeout(r2, 300));
  }
  if (!ready) throw new Error('页面未就绪（window.__app 缺失）');

  const n = await send('Runtime.evaluate', { expression: EXERCISE, returnByValue: true });
  const stats = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(() => {
      const r = window.__app.renderer;
      let meshes = 0, inst = 0, tris = 0;
      window.__app.scene.traverse(o => {
        if (o.isInstancedMesh) inst++;
        else if (o.isMesh) meshes++;
        if (o.isMesh && o.geometry) {
          const g = o.geometry;
          const c = g.index ? g.index.count
            : (g.attributes.position ? g.attributes.position.count : 0);
          tris += c / 3;
        }
      });
      return { meshes, instanced: inst, triangles: Math.round(tris),
               drawCalls: r.info.render.calls, geometries: r.info.memory.geometries,
               textures: r.info.memory.textures, batch: window.__app.batchStat || null };
    })()`
  });
  await new Promise(r => setTimeout(r, 2500));

  cdp.close();
  proc.kill('SIGTERM');

  const targets = (n.result && n.result.value) || 0;
  if (cdp.errors.length) {
    console.error(`运行期报错 ${cdp.errors.length} 条（已遍历 ${targets} 个聚焦目标）：`);
    cdp.errors.slice(0, 20).forEach(e => console.error('  ' + e));
    process.exit(1);
  }
  console.log(`无运行期报错（已遍历 ${targets} 个聚焦目标，切换叠图/剖切/正交/平色渲染）`);
  const st = (stats.result && stats.result.value) || {};
  console.log(`场景：${st.meshes} 网格（含 ${st.instanced} 个实例化）· ` +
              `${st.triangles} 三角面 · ${st.drawCalls} draw call · ` +
              `${st.geometries} 几何体 · ${st.textures} 贴图` +
              (st.batch ? `（合批 ${st.batch.merged} 个方块 → ${st.batch.batches} 批）` : ''));
}

main().then(() => process.exit(0)).catch(e => {
  console.error('check:console 失败：' + e.message);
  process.exit(1);
});
