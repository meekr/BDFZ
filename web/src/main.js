// ---------- 居中高质感三维加载器状态机 ----------
const loaderOverlay = document.getElementById('loader-overlay');
const loaderProgressBar = document.getElementById('loader-progress-bar');
const loaderStatusText = document.getElementById('loader-status-text');
const loaderPercent = document.getElementById('loader-percent');

function updateLoader(pct, text) {
  const clamped = Math.min(100, Math.max(0, pct));
  if (loaderProgressBar) loaderProgressBar.style.width = `${clamped}%`;
  if (loaderPercent) loaderPercent.textContent = `${Math.round(clamped)}%`;
  if (loaderStatusText && text) loaderStatusText.textContent = text;
}

function dismissLoader() {
  if (!loaderOverlay) return;
  updateLoader(100, '载入就绪，正在呈现校园…');
  setTimeout(() => {
    loaderOverlay.classList.add('loaded');
  }, 420);
}

const githubLink = document.getElementById('github-link');
if (githubLink) {
  githubLink.onclick = (e) => e.stopPropagation();
}

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { ChunkLoader } from './tour/chunkLoader.js';
import { FPSController } from './tour/fpsController.js';
import { TeleportHelper } from './tour/teleport.js';
import { Minimap } from './tour/minimap.js';

const params = new URLSearchParams(location.search);
const clean = params.has('clean');
if (clean) document.body.classList.add('clean');
const mobile = matchMedia('(max-width: 640px), (pointer: coarse)').matches;

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

const maxAniso = renderer.capabilities.getMaxAnisotropy();
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xdbe6ef);
scene.fog = new THREE.Fog(0xdbe6ef, 900, 2900);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.58;

// 轻量渐变天穹（海口晴空蓝天 -> 柔和海平线薄雾，零额外纹理加载）
const skyGeo = new THREE.SphereGeometry(2800, 24, 16);
const skyMat = new THREE.ShaderMaterial({
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  uniforms: {
    topColor: { value: new THREE.Color(0x6da6db) },
    midColor: { value: new THREE.Color(0xb8d4ea) },
    bottomColor: { value: new THREE.Color(0xdbe6ef) },
  },
  vertexShader: 'varying vec3 vW; void main(){ vW = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `
    uniform vec3 topColor; uniform vec3 midColor; uniform vec3 bottomColor;
    varying vec3 vW;
    void main() {
      float h = clamp(normalize(vW).y, 0.0, 1.0);
      vec3 c = mix(bottomColor, midColor, smoothstep(0.0, 0.22, h));
      c = mix(c, topColor, smoothstep(0.18, 0.78, h));
      gl_FragColor = vec4(c, 1.0);
    }
  `,
});
scene.add(new THREE.Mesh(skyGeo, skyMat));

const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 1.2, 3200);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minDistance = 8;
controls.maxDistance = 1800;

scene.add(new THREE.HemisphereLight(0xe6f0fa, 0x7d8670, 1.25));
const SUN_DIR = b2t([-0.627, -0.439, 0.643]).normalize();
const sun = new THREE.DirectionalLight(0xfff4e5, 3.2);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(mobile ? 2048 : 4096);
sun.shadow.bias = -0.00025;
sun.shadow.normalBias = 0.055;
scene.add(sun, sun.target);

let lastShadowMode = null;
const lastShadowCenter = new THREE.Vector3(1e9, 1e9, 1e9);
function updateSunShadow(focusPos, isFps) {
  if (isFps) {
    // FPS 模式：动态聚焦 130×130 m 高密阴影视锥（4096px ≈ 3.2 cm/纹素），并按 1 m 格点对齐防止阴影抖动
    const sx = Math.round(focusPos.x);
    const sz = Math.round(focusPos.z);
    if (lastShadowMode !== 'fps' || Math.abs(sx - lastShadowCenter.x) >= 2 || Math.abs(sz - lastShadowCenter.z) >= 2) {
      lastShadowMode = 'fps';
      lastShadowCenter.set(sx, 0, sz);
      sun.target.position.set(sx, focusPos.y, sz);
      sun.position.copy(sun.target.position).addScaledVector(SUN_DIR, 260);
      Object.assign(sun.shadow.camera, { left: -65, right: 65, top: 65, bottom: -65, near: 10, far: 520 });
      sun.shadow.normalBias = 0.035;
      sun.shadow.camera.updateProjectionMatrix();
    }
  } else if (lastShadowMode !== 'orbit') {
    lastShadowMode = 'orbit';
    sun.target.position.set(-40, 0, 50);
    sun.position.copy(sun.target.position).addScaledVector(SUN_DIR, 560);
    Object.assign(sun.shadow.camera, { left: -340, right: 340, top: 270, bottom: -270, near: 20, far: 1150 });
    sun.shadow.normalBias = 0.065;
    sun.shadow.camera.updateProjectionMatrix();
  }
}
updateSunShadow(new THREE.Vector3(-40, 0, 50), false);

const far = new THREE.Mesh(new THREE.PlaneGeometry(8000, 8000), new THREE.MeshLambertMaterial({ color: 0x768468 }));
far.rotation.x = -Math.PI / 2;
far.position.y = -6.5;
far.receiveShadow = true;
scene.add(far);

const statusEl = document.getElementById('status');
const panel = document.getElementById('panel');
const panelToggle = document.getElementById('panel-toggle');
function setPanelCollapsed(collapsed) {
  panel.classList.toggle('collapsed', collapsed);
  if (panelToggle) {
    panelToggle.setAttribute('aria-expanded', String(!collapsed));
    panelToggle.title = collapsed ? '展开面板' : '折叠面板';
  }
}
if (mobile) setPanelCollapsed(true);
panel.querySelector('header').onclick = () => setPanelCollapsed(!panel.classList.contains('collapsed'));
updateLoader(12, '正在连接场景空间元数据…');
const info = await (await fetch('./scene.json')).json();
updateLoader(26, '元数据就绪，正在准备三维主模型…');
const tourStops = info.tour?.stops || [];

// ---------- 视点与双模状态 ----------
let mode = 'orbit'; // 'orbit' | 'fps'
let hfov = 2 * Math.atan(18 / 40);
function applyFov() {
  camera.aspect = innerWidth / innerHeight;
  if (mode === 'fps') {
    camera.fov = mobile ? 66 : 60;
    camera.near = 0.22;
    camera.far = 1600;
  } else {
    camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(hfov / 2) / Math.max(camera.aspect, 0.8)));
    camera.near = 1.2;
    camera.far = 3200;
  }
  camera.updateProjectionMatrix();
}

let tween = null;
function setView(id, animate = true) {
  if (mode === 'fps') exitTour(false);
  const v = info.views.views.find((x) => x.id === id);
  if (!v) return;
  const to = { pos: b2t(v.eye), tgt: b2t(v.target), hfov: 2 * Math.atan(18 / v.lens) };
  document.querySelectorAll('#views button').forEach((b) => b.classList.toggle('on', b.dataset.id === id));
  if (!animate) {
    camera.position.copy(to.pos); controls.target.copy(to.tgt); hfov = to.hfov; applyFov(); controls.update();
    return;
  }
  tween = { t0: performance.now(), dur: 1100, from: { pos: camera.position.clone(), tgt: controls.target.clone(), hfov }, to };
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

// ---------- 模型与分包加载器 ----------
const draco = new DRACOLoader();
const loader = new GLTFLoader().setDRACOLoader(draco);
const chunkLoader = new ChunkLoader(scene, loader, (msg) => { statusEl.textContent = msg; }, maxAniso);

const t0 = performance.now();
const gltf = await loader.loadAsync('./bdfz.glb', (e) => {
  if (e.total) {
    const ratio = e.loaded / e.total;
    const pct = 26 + ratio * 62;
    const mb = (e.loaded / 1024 / 1024).toFixed(1);
    const totalMb = (e.total / 1024 / 1024).toFixed(1);
    updateLoader(pct, `正在解算建筑空间与纹理贴图 (${mb}/${totalMb} MB)…`);
    statusEl.textContent = `加载模型… ${Math.round(ratio * 100)}%`;
  }
});
updateLoader(92, '正在解算 Draco 空间网格并烘焙材质…');
const model = gltf.scene;
const layers = { building: [], landscape: [], site: [], people: [] };
const byBldg = {};
model.traverse((o) => {
  let p = o, layer, bldg;
  while (p && !layer) { layer = p.userData.layer; bldg = p.userData.bldg; p = p.parent; }
  o.userData.layer = layer; o.userData.bldg = bldg;
  if (!o.isMesh) return;
  o.castShadow = layer !== 'site' && !/CourtFloor|CourtLawn|Island_|PlazaAccent|CourtGrass|VectorLines|Track_Lanes|Road_Markings/.test(o.name);
  o.receiveShadow = true;
  if (layer && layers[layer]) layers[layer].push(o);
  if (bldg) (byBldg[bldg] ||= []).push(o);
  const mats = Array.isArray(o.material) ? o.material : [o.material];
  for (const m of mats) {
    for (const slot of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap']) {
      if (m[slot]) {
        m[slot].anisotropy = maxAniso;
        m[slot].needsUpdate = true;
      }
    }
    if (m.transparent && m.opacity > 0.9) m.transparent = false;
    if (m.transparent) { m.depthWrite = false; m.side = THREE.DoubleSide; }
    if (m.name === 'M_SportsGlass') { m.envMapIntensity = 1.45; }
    if (m.name === 'M_Paving' && m.normalMap) { m.normalScale?.set(0.32, 0.32); }
  }
});
scene.add(model);
statusEl.textContent = `室外主包 ${(performance.now() - t0).toFixed(0)} ms`;
updateLoader(98, '初始化光照系统与交互视点…');
dismissLoader();

const showPeople = params.get('people') !== '0';
const peopleCb = document.querySelector('[data-layer="people"]');
if (peopleCb && !showPeople) {
  peopleCb.checked = false;
  layers.people.forEach((o) => (o.visible = false));
}
document.querySelectorAll('[data-layer]').forEach((cb) => {
  cb.onchange = () => layers[cb.dataset.layer]?.forEach((o) => (o.visible = cb.checked));
});

// ---------- 建筑标注与信息卡 ----------
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
const labelsToggle = document.getElementById('labels-toggle');
labelsToggle.onchange = (e) => labels.forEach((l) => (l.visible = mode === 'orbit' && e.target.checked));

const ray = new THREE.Raycaster();
let down = null;
renderer.domElement.addEventListener('pointerdown', (e) => (down = [e.clientX, e.clientY]));
renderer.domElement.addEventListener('pointerup', (e) => {
  if (mode !== 'orbit' || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
  ray.setFromCamera(new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
  const hit = ray.intersectObjects(layers.building.filter((o) => o.visible), false)[0];
  if (hit && hit.object.userData.bldg) showCard(hit.object.userData.bldg);
});

// ---------- 第一人称漫游引擎（FPS + Teleport + Minimap + Guided Tour + Photo Modal） ----------
const fps = new FPSController(camera, renderer.domElement, () => chunkLoader.navWalkable);
const teleport = new TeleportHelper(scene, camera, renderer.domElement, fps, () => chunkLoader.navWalkable);

let currentStopIdx = 0;
let autoTimer = null;
let forcedZone = null;

const btnOrbit = document.getElementById('btn-mode-orbit');
const btnFps = document.getElementById('btn-mode-fps');
const secOrbit = document.getElementById('sec-orbit-views');
const secStops = document.getElementById('sec-tour-stops');
const stopsEl = document.getElementById('stops');
const tourBar = document.getElementById('tour-bar');
const tourSel = document.getElementById('tour-select');
const tourAutoBtn = document.getElementById('tour-auto');
const minimapWrap = document.getElementById('minimap-wrap');
const mmFloorEl = document.getElementById('mm-floor');
const photoModal = document.getElementById('photo-modal');
const joyPad = document.getElementById('joy-pad');
const joyKnob = document.getElementById('joy-knob');

const minimap = new Minimap(document.getElementById('minimap'), info.overlays.extent, tourStops, (id) => goToStop(id));

for (let i = 0; i < tourStops.length; i++) {
  const st = tourStops[i];
  const isIndoor = st.zone !== 'exterior';
  const cleanLabel = st.label.replace(/（室内）$/, '');
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'stop-item';
  b.setAttribute('role', 'option');
  b.setAttribute('aria-selected', 'false');
  b.dataset.id = st.id;

  const num = document.createElement('span');
  num.className = 'stop-num';
  num.textContent = String(i + 1).padStart(2, '0');

  const name = document.createElement('span');
  name.className = 'stop-name';
  name.textContent = cleanLabel;

  const badge = document.createElement('span');
  badge.className = isIndoor ? 'stop-badge indoor' : 'stop-badge';
  badge.textContent = isIndoor ? '室内' : '室外';

  b.append(num, name, badge);
  b.onclick = () => goToStop(st.id);
  stopsEl.appendChild(b);

  const opt = document.createElement('option');
  opt.value = st.id;
  opt.textContent = `${i + 1}/${tourStops.length} ${cleanLabel}`;
  tourSel.appendChild(opt);
}

function updateStopUI(st) {
  tourSel.value = st.id;
  const cleanLabel = st.label.replace(/（室内）$/, '');
  mmFloorEl.textContent = `${cleanLabel} · ${st.floor}`;
  minimap.setActiveStop(st.id);
  document.querySelectorAll('#stops button').forEach((b) => {
    const active = b.dataset.id === st.id;
    b.classList.toggle('on', active);
    b.setAttribute('aria-selected', String(active));
    if (active) b.scrollIntoView({ block: 'nearest' });
  });
  document.getElementById('photo-title').textContent = st.label;
  document.getElementById('photo-floor').textContent = st.floor;
  document.getElementById('photo-desc').textContent = st.desc;
  document.getElementById('photo-credit').textContent = st.credit || '';
  const img = document.getElementById('photo-img');
  if (st.photo) { img.src = `./${st.photo}`; img.hidden = false; } else { img.hidden = true; }
}

async function goToStop(id) {
  const idx = tourStops.findIndex((s) => s.id === id);
  if (idx < 0) return;
  currentStopIdx = idx;
  const st = tourStops[idx];
  if (mode !== 'fps') await enterTour(id);
  else {
    await chunkLoader.loadNav();
    if (st.zone !== 'exterior') await chunkLoader.ensureZone(st.zone);
    forcedZone = st.zone;
    fps.setPoseBlender(st.pos, st.yaw, st.pitch || 0);
    chunkLoader.updateForPosition(fps.feetPos, true, forcedZone);
    updateStopUI(st);
  }
}

async function enterTour(stopId = 'north_gate') {
  tween = null;
  mode = 'fps';
  controls.enabled = false;
  card.hidden = true;
  labels.forEach((l) => (l.visible = false));
  btnOrbit.classList.remove('on'); btnOrbit.setAttribute('aria-selected', 'false');
  btnFps.classList.add('on'); btnFps.setAttribute('aria-selected', 'true');
  secOrbit.hidden = true;
  secStops.hidden = false;
  tourBar.hidden = false;
  minimapWrap.hidden = false;
  if (mobile) joyPad.hidden = false;
  applyFov();

  await chunkLoader.loadNav();
  const st = tourStops.find((s) => s.id === stopId) || tourStops[0];
  currentStopIdx = Math.max(0, tourStops.indexOf(st));
  if (st.zone !== 'exterior') await chunkLoader.ensureZone(st.zone);
  forcedZone = st.zone;
  fps.enabled = true;
  fps.setPoseBlender(st.pos, st.yaw, st.pitch || 0);
  chunkLoader.updateForPosition(fps.feetPos, true, forcedZone);
  updateStopUI(st);
}

function exitTour(restoreAerial = true) {
  stopAutoTour();
  mode = 'orbit';
  fps.enabled = false;
  forcedZone = null;
  teleport.hide();
  chunkLoader.updateForPosition(fps.feetPos, false);
  controls.enabled = true;
  btnOrbit.classList.add('on'); btnOrbit.setAttribute('aria-selected', 'true');
  btnFps.classList.remove('on'); btnFps.setAttribute('aria-selected', 'false');
  secOrbit.hidden = false;
  secStops.hidden = true;
  tourBar.hidden = true;
  minimapWrap.hidden = true;
  setPhotoOpen(false);
  joyPad.hidden = true;
  labels.forEach((l) => (l.visible = labelsToggle.checked));
  applyFov();
  if (restoreAerial) setView('aerial', true);
}

const tourPhotoBtn = document.getElementById('tour-photo-btn');
const icPlay = tourAutoBtn.querySelector('.ic-play');
const icPause = tourAutoBtn.querySelector('.ic-pause');
const autoLabel = tourAutoBtn.querySelector('.tb-auto-label');

function setPhotoOpen(open) {
  photoModal.hidden = !open;
  tourPhotoBtn.classList.toggle('on', open);
}

function stopAutoTour() {
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
  tourAutoBtn.classList.remove('on');
  if (icPlay) icPlay.hidden = false;
  if (icPause) icPause.hidden = true;
  if (autoLabel) autoLabel.textContent = '自动导览';
}

btnOrbit.onclick = () => { if (mode !== 'orbit') exitTour(true); };
btnFps.onclick = () => { if (mode !== 'fps') enterTour(tourStops[currentStopIdx]?.id || 'north_gate'); };
document.getElementById('tour-exit').onclick = () => exitTour(true);
document.getElementById('tour-prev').onclick = () => goToStop(tourStops[(currentStopIdx - 1 + tourStops.length) % tourStops.length].id);
document.getElementById('tour-next').onclick = () => goToStop(tourStops[(currentStopIdx + 1) % tourStops.length].id);
tourSel.onchange = () => goToStop(tourSel.value);
tourPhotoBtn.onclick = () => setPhotoOpen(photoModal.hidden);
document.getElementById('photo-close').onclick = () => setPhotoOpen(false);
tourAutoBtn.onclick = () => {
  if (autoTimer) { stopAutoTour(); return; }
  tourAutoBtn.classList.add('on');
  if (icPlay) icPlay.hidden = true;
  if (icPause) icPause.hidden = false;
  if (autoLabel) autoLabel.textContent = '暂停导览';
  autoTimer = setInterval(() => {
    goToStop(tourStops[(currentStopIdx + 1) % tourStops.length].id);
  }, 5500);
};
window.addEventListener('keydown', (e) => {
  if (e.code === 'Escape' && mode === 'fps') exitTour(true);
  if (mode === 'fps' && ['KeyW', 'KeyA', 'KeyS', 'KeyD'].includes(e.code)) forcedZone = null;
});

// 移动端虚拟摇杆
let joyOrigin = null;
joyPad.addEventListener('pointerdown', (e) => {
  joyPad.setPointerCapture(e.pointerId);
  const r = joyPad.getBoundingClientRect();
  joyOrigin = [r.left + r.width / 2, r.top + r.height / 2];
});
joyPad.addEventListener('pointermove', (e) => {
  if (!joyOrigin) return;
  const dx = e.clientX - joyOrigin[0], dy = e.clientY - joyOrigin[1];
  const d = Math.min(34, Math.hypot(dx, dy));
  const a = Math.atan2(dy, dx);
  const kx = Math.cos(a) * d, ky = Math.sin(a) * d;
  joyKnob.style.transform = `translate(${kx}px, ${ky}px)`;
  fps.joy.x = kx / 34;
  fps.joy.y = -ky / 34;
  forcedZone = null;
});
const resetJoy = () => { joyOrigin = null; joyKnob.style.transform = ''; fps.joy.x = 0; fps.joy.y = 0; };
joyPad.addEventListener('pointerup', resetJoy);
joyPad.addEventListener('pointercancel', resetJoy);

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
const overlaySlider = document.getElementById('overlay-opacity');
const overlaySliderWrap = document.getElementById('overlay-slider-wrap');
const overlayValEl = document.getElementById('overlay-val');

function syncOverlaySlider() {
  const v = +overlaySlider.value;
  overlaySlider.style.setProperty('--attr-min', overlaySlider.min || '0.1');
  overlaySlider.style.setProperty('--attr-max', overlaySlider.max || '1');
  overlaySlider.style.setProperty('--control-value', String(v));
  const pct = `${Math.round(v * 100)}%`;
  overlaySlider.setAttribute('aria-valuetext', pct);
  if (overlayValEl) overlayValEl.textContent = sel.value ? pct : '未启用';
  overlaySlider.disabled = !sel.value;
  if (overlaySliderWrap) overlaySliderWrap.classList.toggle('disabled', !sel.value);
}
syncOverlaySlider();

sel.onchange = async () => {
  const item = info.overlays.items.find((o) => o.id === sel.value);
  syncOverlaySlider();
  if (!item) { overlay.visible = false; return; }
  const tex = (texCache[item.id] ||= await texLoader.loadAsync(`./${item.file}`));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  overlayMat.map = tex; overlayMat.needsUpdate = true; overlay.visible = true;
};
overlaySlider.oninput = () => {
  overlayMat.opacity = +overlaySlider.value;
  syncOverlaySlider();
};

// URL 参数直达第一人称站点 (?mode=fps&stop=indoor_gym)
if (params.get('mode') === 'fps') {
  enterTour(params.get('stop') || 'north_gate');
}

// ---------- 渲染主循环 ----------
const statsEl = document.getElementById('stats');
statsEl.hidden = !params.has('stats');
let frames = 0, tLast = performance.now(), tPrev = performance.now(), fpsRate = 0;
addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  labelRenderer.setSize(innerWidth, innerHeight);
  applyFov();
});
renderer.setAnimationLoop((now) => {
  const dt = Math.min(0.05, (now - tPrev) / 1000);
  tPrev = now;
  if (mode === 'fps') {
    fps.update(dt, now);
    chunkLoader.updateForPosition(fps.feetPos, true, forcedZone);
    chunkLoader.updateAnimation(now);
    teleport.update(now);
    updateSunShadow(fps.feetPos, true);
    if (!minimapWrap.hidden) minimap.render(fps.feetPos, fps.yaw);
  } else {
    stepTween(now);
    controls.update();
    updateSunShadow(controls.target, false);
  }
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
  frames++;
  if (now - tLast > 1000) {
    fpsRate = (frames * 1000) / (now - tLast); frames = 0; tLast = now;
    if (!statsEl.hidden) {
      statsEl.textContent = `${fpsRate.toFixed(0)} fps · ${renderer.info.render.calls} draw calls · ${(renderer.info.render.triangles / 1000).toFixed(0)}k tris`;
    }
  }
});

window.__bdfz = {
  renderer, scene, camera, setView, enterTour, exitTour, goToStop,
  get mode() { return mode; }, get fps() { return fpsRate; }, ready: true,
};
