import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const params = new URLSearchParams(location.search);
const clean = params.has('clean');
if (clean) document.body.classList.add('clean');
const mobile = matchMedia('(max-width: 640px), (pointer: coarse)').matches;

// Blender（Z 向上）→ glTF / three（Y 向上）
const b2t = ([x, y, z]) => new THREE.Vector3(x, z, -y);

const app = document.getElementById('app');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: params.has('capture') });
renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1.5 : 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
app.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(innerWidth, innerHeight);
Object.assign(labelRenderer.domElement.style, { position: 'fixed', inset: '0', pointerEvents: 'none' });
document.body.appendChild(labelRenderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xcfdbe6);
scene.fog = new THREE.Fog(0xcfdbe6, 1500, 5000);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.5;

const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 1, 8000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minDistance = 15;
controls.maxDistance = 2500;

// 与 Blender 日光一致：太阳在西南，高度 40°
scene.add(new THREE.HemisphereLight(0xe3edf7, 0x7d8670, 1.3));
const sun = new THREE.DirectionalLight(0xfff4e5, 3.2);
sun.position.copy(b2t([-0.627, -0.439, 0.643]).multiplyScalar(600));
sun.castShadow = true;
sun.shadow.mapSize.setScalar(mobile ? 2048 : 4096);
Object.assign(sun.shadow.camera, { left: -380, right: 380, top: 300, bottom: -300, near: 10, far: 1500 });
sun.shadow.bias = -0.0005;
sun.shadow.normalBias = 0.4;
scene.add(sun, sun.target);

const far = new THREE.Mesh(new THREE.PlaneGeometry(10000, 10000), new THREE.MeshLambertMaterial({ color: 0x6f7c62 }));
far.rotation.x = -Math.PI / 2;
far.position.y = -6.5;
far.receiveShadow = true;
scene.add(far);

const status = document.getElementById('status');
const panel = document.getElementById('panel');
if (mobile) panel.classList.add('collapsed');
panel.querySelector('header').onclick = () => panel.classList.toggle('collapsed');
const info = await (await fetch('./scene.json')).json();

// ---------- 视点 ----------
let hfov = 2 * Math.atan(18 / 40);
function applyFov() {
  camera.aspect = innerWidth / innerHeight;
  // 保持横向视场与 Blender 相机（横向 36 mm 画幅）一致
  // 竖屏时不再严格保持横向视场，否则建筑缩得过小
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(hfov / 2) / Math.max(camera.aspect, 0.8)));
  camera.updateProjectionMatrix();
}
let tween = null;
function setView(id, animate = true) {
  const v = info.views.views.find((x) => x.id === id);
  if (!v) return;
  const to = { pos: b2t(v.eye), tgt: b2t(v.target), hfov: 2 * Math.atan(18 / v.lens) };
  document.querySelectorAll('#views button').forEach((b) => b.classList.toggle('on', b.dataset.id === id));
  if (!animate) {
    camera.position.copy(to.pos); controls.target.copy(to.tgt); hfov = to.hfov; applyFov(); controls.update();
    return;
  }
  tween = { t0: performance.now(), dur: 1200, from: { pos: camera.position.clone(), tgt: controls.target.clone(), hfov }, to };
}
function stepTween(now) {
  if (!tween) return;
  const k = Math.min(1, (now - tween.t0) / tween.dur);
  const e = k < 0.5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2;
  camera.position.lerpVectors(tween.from.pos, tween.to.pos, e);
  controls.target.lerpVectors(tween.from.tgt, tween.to.tgt, e);
  hfov = tween.from.hfov + (tween.to.hfov - tween.from.hfov) * e;
  applyFov();
  if (k === 1) tween = null;
}
controls.addEventListener('start', () => { tween = null; document.querySelectorAll('#views button').forEach((b) => b.classList.remove('on')); });
const viewsEl = document.getElementById('views');
for (const v of info.views.views) {
  const b = document.createElement('button');
  b.textContent = v.label; b.dataset.id = v.id;
  b.onclick = () => setView(v.id);
  viewsEl.appendChild(b);
}
setView(params.get('view') || 'aerial', false);

// ---------- 模型 ----------
const draco = new DRACOLoader();
const loader = new GLTFLoader().setDRACOLoader(draco);
const t0 = performance.now();
const gltf = await loader.loadAsync('./bdfz.glb', (e) => {
  if (e.total) status.textContent = `加载模型… ${Math.round((e.loaded / e.total) * 100)}%`;
});
const model = gltf.scene;
const layers = { building: [], landscape: [], site: [] };
const byBldg = {};
model.traverse((o) => {
  let p = o, layer, bldg;
  while (p && !layer) { layer = p.userData.layer; bldg = p.userData.bldg; p = p.parent; }
  o.userData.layer = layer; o.userData.bldg = bldg;
  if (!o.isMesh) return;
  o.castShadow = layer !== 'site';
  o.receiveShadow = true;
  if (layer) layers[layer].push(o);
  if (bldg) (byBldg[bldg] ||= []).push(o);
  const mats = Array.isArray(o.material) ? o.material : [o.material];
  for (const m of mats) if (m.transparent && m.opacity > 0.9) m.transparent = false;
});
scene.add(model);
status.textContent = `模型 ${(performance.now() - t0).toFixed(0)} ms`;

document.querySelectorAll('[data-layer]').forEach((cb) => {
  cb.onchange = () => layers[cb.dataset.layer].forEach((o) => (o.visible = cb.checked));
});

// ---------- 标注与信息卡 ----------
const card = document.getElementById('card');
function showCard(id) {
  const b = info.buildings.find((x) => x.id === id);
  if (!b) return;
  document.getElementById('card-name').textContent = b.name;
  document.getElementById('card-sub').textContent = b.sub;
  document.getElementById('card-facts').replaceChildren(...b.facts.map((f) => Object.assign(document.createElement('li'), { textContent: f })));
  document.getElementById('card-src').textContent = `依据：${b.src}`;
  card.hidden = false;
}
document.getElementById('card-close').onclick = () => (card.hidden = true);
const labels = [];
for (const b of info.buildings) {
  const objs = byBldg[b.id];
  if (!objs) continue;
  const box = new THREE.Box3();
  objs.forEach((o) => box.expandByObject(o));
  const el = Object.assign(document.createElement('div'), { className: 'label', textContent: b.name });
  el.style.pointerEvents = 'auto';
  el.onclick = () => showCard(b.id);
  const lab = new CSS2DObject(el);
  lab.position.set((box.min.x + box.max.x) / 2, box.max.y + 10, (box.min.z + box.max.z) / 2);
  scene.add(lab);
  labels.push(lab);
}
document.getElementById('labels-toggle').onchange = (e) => labels.forEach((l) => (l.visible = e.target.checked));

const ray = new THREE.Raycaster();
let down = null;
renderer.domElement.addEventListener('pointerdown', (e) => (down = [e.clientX, e.clientY]));
renderer.domElement.addEventListener('pointerup', (e) => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
  ray.setFromCamera(new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
  const hit = ray.intersectObjects(layers.building.filter((o) => o.visible), false)[0];
  if (hit && hit.object.userData.bldg) showCard(hit.object.userData.bldg);
});

// ---------- 图纸叠图 ----------
const [X0, Y0, X1, Y1] = info.overlays.extent;
const overlayMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.75, depthWrite: false, toneMapped: false, polygonOffset: true, polygonOffsetFactor: -2 });
const overlay = new THREE.Mesh(new THREE.PlaneGeometry(X1 - X0, Y1 - Y0), overlayMat);
overlay.rotation.x = -Math.PI / 2;
overlay.position.copy(b2t([(X0 + X1) / 2, (Y0 + Y1) / 2, info.overlays.z]));
overlay.visible = false;
overlay.renderOrder = 2;
scene.add(overlay);
const texLoader = new THREE.TextureLoader();
const texCache = {};
const sel = document.getElementById('overlay');
for (const o of info.overlays.items) sel.appendChild(Object.assign(document.createElement('option'), { value: o.id, textContent: o.label }));
sel.onchange = async () => {
  const item = info.overlays.items.find((o) => o.id === sel.value);
  if (!item) { overlay.visible = false; return; }
  const tex = (texCache[item.id] ||= await texLoader.loadAsync(`./${item.file}`));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  overlayMat.map = tex; overlayMat.needsUpdate = true; overlay.visible = true;
};
document.getElementById('overlay-opacity').oninput = (e) => (overlayMat.opacity = +e.target.value);

// ---------- 循环 ----------
const statsEl = document.getElementById('stats');
statsEl.hidden = !params.has('stats');
let frames = 0, tLast = performance.now(), fps = 0;
addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  labelRenderer.setSize(innerWidth, innerHeight);
  applyFov();
});
renderer.setAnimationLoop((now) => {
  stepTween(now);
  controls.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
  frames++;
  if (now - tLast > 1000) {
    fps = (frames * 1000) / (now - tLast); frames = 0; tLast = now;
    if (!statsEl.hidden) statsEl.textContent = `${fps.toFixed(0)} fps · ${renderer.info.render.calls} draw calls · ${(renderer.info.render.triangles / 1000).toFixed(0)}k tris`;
  }
});

// 供 DevTools 检查
window.__bdfz = { renderer, scene, camera, setView, get fps() { return fps; }, ready: true };
