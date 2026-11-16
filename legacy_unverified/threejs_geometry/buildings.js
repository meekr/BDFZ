import * as THREE from 'three';
import {
  box, mesh, slab, flat, facade, band, shapeOf, shapeWithHoles,
  clipHalfPlane, polyCentroid, eaveRing, railing, louver, insetPolygon,
} from './kit.js';
import { BUILDINGS, LEVELS, CLOUD_3F_ROOMS, INTERIORS } from '../data/index.js';

/**
 * 三栋建筑的体量生成。
 * 平面轮廓全部来自 02 屋顶平面的描图数据（世界米）；
 * 标高来自 05 剖面的读数（src/data/levels.json）。
 * 生成器本身不再做任何旋转或平移——轮廓已经是世界坐标。
 */

function floorShell(parent, shape, outerPts, y0, h, M, step) {
  slab(shape, y0, 0.7, M.slab, parent, { roof: false });
  facade(outerPts, y0 + 0.7, h, { glass: M.glass, mullion: M.mullion, step: step || 9 }, parent);
  band(outerPts, y0 + 0.15, 0.5, 1.6, M.white, parent, 0.8);
}

function roofPlate(parent, shape, y, M, thick) {
  return slab(shape, y, thick || 0.8, M.roof, parent, { roof: true });
}

/** 学术中心：板式体量 + 中央星形庭院 + 底层架空。 */
export function buildCloud(scene, groups, details, M) {
  const g = groups.cloud;
  const data = BUILDINGS.cloud;
  const lv = LEVELS.cloud;
  const outer = data.outer;
  const holes = data.holes || [];
  const shape = shapeWithHoles(outer, holes);
  const solid = shapeOf(outer);      // 无洞，用于屋面/楼板外圈
  const court = data.courtyard ? data.courtyard.polygon : null;

  const zSplit = data.centroid[1] + 8;   // 南翼（高中）在北翼之南（z 更大）

  // 南北翼各自的板形（洞口也要跟着裁）
  const clipWithHoles = (pts, holes, sign) => {
    const clip = (p) => (sign > 0
      ? clipHalfPlane(p, 0, 1, zSplit)
      : clipHalfPlane(p, 0, -1, -zSplit));
    const o = clip(pts);
    if (o.length < 3) return { outer: pts, holes };
    const hs = holes.map(h => ({ polygon: clip(h.polygon) })).filter(h => h.polygon.length > 2);
    return { outer: o, holes: hs };
  };
  const south = clipWithHoles(outer, holes, -1);
  const north = clipWithHoles(outer, holes, 1);
  const southOuter = south.outer;
  const northOuter = north.outer;
  const southShape = shapeWithHoles(southOuter, south.holes);
  const northShape = shapeWithHoles(northOuter, north.holes);

  // 1. 底层架空柱（白色 V/N 形斜柱）
  const baseY = lv.north_wing.ground;
  const pilotisH = lv.pilotis.height_m;
  const cols = [];
  const stepA = 26;
  for (let i = 0; i < outer.length; i++) {
    const p = outer[i];
    if (i % 2) continue;
    cols.push(p);
  }
  cols.forEach((p, i) => {
    const c1 = mesh(new THREE.CylinderGeometry(0.5, 0.75, pilotisH, 8), M.white, g,
      { pos: [p[0] - 0.9, baseY + pilotisH / 2, p[1]] });
    c1.rotation.z = (i % 2 ? 1 : -1) * 0.16;
    const c2 = mesh(new THREE.CylinderGeometry(0.5, 0.75, pilotisH, 8), M.white, g,
      { pos: [p[0] + 0.9, baseY + pilotisH / 2, p[1]] });
    c2.rotation.z = (i % 2 ? -1 : 1) * 0.16;
  });

  // 2. 北翼楼板：±0.00 / +5.00 / +8.00 / +12.50，屋面 +17.00，檐口 +19.00
  const nLevels = [lv.north_wing.ground].concat(lv.north_wing.floors);
  nLevels.forEach((y, i) => {
    const hh = (i === 0 ? pilotisH : (nLevels[i] - nLevels[i - 1])) - 0.7;
    slab(shape, y, 0.7, M.slab, g);
    facade(outer, y + 0.7, Math.max(2.4, hh), { glass: i % 2 ? M.glass : M.glassDark, mullion: M.mullion, step: 10 }, g);
    band(i === 0 ? outer : northOuter, y + 0.2, 0.5, 1.5, M.white, g, 0.25);
    // 实景照片显示立面是"连续窗带 + 白色实墙腰线"，不是整面玻璃幕墙。
    // 在窗带上方压一道实墙带，贴合照片的竖向比例。
    band(i === 0 ? outer : northOuter, y + 2.55, 1.15, 0.36, M.white, g, 0.3);
  });
  roofPlate(g, northShape, lv.north_wing.roof, M);
  // 北翼屋面天窗：三条与长边平行的采光带（位置按 02 屋面图的天窗符号）
  const nz = polyCentroid(northOuter);
  const nzs = northOuter.map(p => p[1]);
  const zMin = Math.min(...nzs);
  const zMax = Math.max(...nzs);
  [0.3, 0.55, 0.78].forEach((f, i) => {
    const zc = zMin + (zMax - zMin) * f;
    const len = 20 - i * 3;
    const sky = box(len, 0.5, 4.5, M.skylight, g, nz[0], lv.north_wing.roof + 0.9, zc,
      { roof: true, cast: false });
    sky.rotation.y = i % 2 ? 0.34 : -0.34;
  });
  // 屋脊折线：北翼屋面沿长轴一道起脊，两侧略低（直立锁边金属屋面的分水线）
  const ridgeLen = (nzs.length ? Math.max(...nzs) - Math.min(...nzs) : 60) * 0.86;
  const ridge = box(1.6, 0.5, ridgeLen, M.metal, g, nz[0], lv.north_wing.roof + 1.15,
    (zMin + zMax) / 2, { roof: true, cast: false });
  ridge.rotation.y = -0.34;

  // 直立锁边金属屋面的细肋（每 6 m 一道，仅示意）
  for (let k = -2; k <= 2; k++) {
    const rib = box(0.12, 0.22, Math.min(58, (zMax - zMin) * 0.8), M.metal, g,
      nz[0] + k * 11, lv.north_wing.roof + 0.85, (zMin + zMax) / 2, { roof: true, cast: false });
    rib.rotation.y = -0.34;
  }
  band(northOuter, lv.north_wing.parapet, 0.9, 1.1, M.white, g, 0.3);

  // 3. 南翼（高中）：架空层 +5.00，楼面 +10.00 / +14.50 / +19.00，屋面 +23.50
  const sLevels = [lv.south_wing.ground].concat(lv.south_wing.floors);
  sLevels.forEach((y, i) => {
    slab(shape, y, 0.8, M.slab, g);
    if (i > 0) {
      facade(southOuter, y + 0.8, Math.max(2.4, sLevels[i] - sLevels[i - 1] - 0.8),
        { glass: i % 2 ? M.glassDark : M.glass, mullion: M.mullion, step: 10 }, g);
      band(southOuter, y + 0.25, 0.55, 1.7, M.white, g, 0.3);
    }
  });
  roofPlate(g, southShape, lv.south_wing.roof, M);
  band(southOuter, lv.south_wing.roof - 0.6, 1.2, 2.2, M.roof, g, 0.4);

  // 4. 庭院：底层铺装与下沉广场
  if (court) {
    const courtPad = flat(shapeOf(court), baseY + 0.35, M.sand, g, { cast: false });
    courtPad.userData.noFlat = true;   // 庭院地面不参与剪影统计
    const cc = polyCentroid(court);
    for (let k = 0; k < 3; k++) {
      const r = 26 - k * 7;
      const ring = mesh(new THREE.RingGeometry(r - 0.7, r, 40), M.white, g,
        { pos: [cc[0], baseY + 0.42 + k * 0.22, cc[1]], rot: [-Math.PI / 2, 0, 0], cast: false });
      ring.userData.noFlat = true;
    }
    // 庭院风车连桥（X 形，两条对角板）
    for (let k = 0; k < 2; k++) {
      const b = box(46, 0.5, 7, M.white, g, cc[0], baseY + 4.6, cc[1]);
      b.rotation.y = (k ? 1 : -1) * 0.62;
      b.userData.noFlat = true;
    }
  }

  // 5. 图书馆（学术中心架空底部公共层）
  const lib = details.library;
  const libCenter = data.courtyard ? polyCentroid(data.courtyard.polygon) : [0, 0];
  for (let r = 0; r < 3; r++) {
    const rad = 9 + r * 4.2;
    mesh(new THREE.RingGeometry(rad - 0.55, rad, 28), M.wood, lib,
      { pos: [libCenter[0] - 18, 1.9, libCenter[1] - 6], rot: [-Math.PI / 2, 0, 0], cast: false });
    mesh(new THREE.RingGeometry(rad - 0.16, rad, 28), M.white, lib,
      { pos: [libCenter[0] - 18, 6.4, libCenter[1] - 6], rot: [-Math.PI / 2, 0, 0], cast: false });
  }
  // 6. 三层房间低模：房间轮廓来自 04 三层平面（世界坐标），只砌 2.6 m 高的薄隔墙。
  //    放在 details.cloud 里，剖切/三层视图时与 04 叠图对照。
  const roomGroup = details.cloud;
  const roomWalls = CLOUD_3F_ROOMS.rooms || [];
  roomWalls.forEach(r => {
    const pts = r.polygon;
    for (let i = 0; i < pts.length; i++) {
      const p1 = pts[i];
      const p2 = pts[(i + 1) % pts.length];
      const dx = p2[0] - p1[0];
      const dz = p2[1] - p1[1];
      const len = Math.hypot(dx, dz);
      if (len < 0.6 || len > 40) continue;
      const wall = box(len, 2.6, 0.16, M.white, roomGroup,
        (p1[0] + p2[0]) / 2, CLOUD_3F_ROOMS.level_m + 0.8 + 1.3, (p1[1] + p2[1]) / 2,
        { cast: false });
      wall.rotation.y = -Math.atan2(dz, dx);
    }
  });

  return { courtCenter: libCenter, roomCount: roomWalls.length };
}

/** 体育及艺术中心：L 形连续体量，西臂 24 m、南臂 16 m。 */
export function buildSportsArt(scene, groups, details, M) {
  const g = groups.sports;
  const data = BUILDINGS.sports;
  const lv = LEVELS.sports_art;
  const outer = data.outer;

  // L 形两个臂的分割线：过"内转角"与"外顶点"的直线。
  // 内转角 = 离多边形质心最近的顶点；外顶点 = 离内转角最远的顶点。
  const cen = polyCentroid(outer);
  let inner = outer[0];
  let bestD = Infinity;
  outer.forEach(p => {
    const d = (p[0] - cen[0]) ** 2 + (p[1] - cen[1]) ** 2;
    if (d < bestD) { bestD = d; inner = p; }
  });
  let apex = outer[0];
  let farD = -1;
  outer.forEach(p => {
    const d = (p[0] - inner[0]) ** 2 + (p[1] - inner[1]) ** 2;
    if (d > farD) { farD = d; apex = p; }
  });
  const bx = apex[0] - inner[0];
  const bz = apex[1] - inner[1];
  const bl = Math.hypot(bx, bz) || 1;
  const nx = bz / bl;          // 法向 = 母线转 90°
  const nz = -bx / bl;
  const c0 = nx * inner[0] + nz * inner[1];
  let sideA = clipHalfPlane(outer, nx, nz, c0);
  let sideB = clipHalfPlane(outer, -nx, -nz, -c0);
  if (sideA.length < 3) sideA = outer;
  if (sideB.length < 3) sideB = outer;
  // 西侧（x 更小）为体育中心臂，东侧为艺术中心臂
  const cxA = polyCentroid(sideA)[0];
  const cxB = polyCentroid(sideB)[0];
  const sportsOuter = cxA <= cxB ? sideA : sideB;
  const artOuter = cxA <= cxB ? sideB : sideA;
  // 02 描出的是**屋顶边缘（含挑檐）**。墙体必须退到挑檐内侧，
  // 挑檐再从墙面挑到这条轮廓，否则等于把挑檐算了两遍（剪影整体外扩 2.6 m）。
  const EAVE_OUT = 2.6;
  const sportsWall = insetPolygon(sportsOuter, EAVE_OUT);
  const artWall = insetPolygon(artOuter, 2.0);

  // 西臂：0 m 与 12 m 两层活动面，屋面 24 m
  [[lv.west_arm_sports.floor_1, 12.0, M.glass, 0.0],
   [lv.west_arm_sports.floor_2, 11.4, M.glassDark, 12.0]].forEach(([y0, h, glass], i) => {
    slab(shapeOf(sportsOuter), y0, 0.8, M.slab, g);
    facade(sportsOuter, y0 + 0.8, h, { glass, mullion: M.mullion, step: 6.5 }, g);
    band(sportsOuter, y0 + h, 0.9, 2.0, M.white, g, 0.3);
  });
  slab(shapeOf(sportsOuter), lv.west_arm_sports.roof - 0.9, 0.9, M.roof, g, { roof: true });
  for (let k = 0; k < 5; k++) {
    band(sportsOuter, 21.0 + k * 0.45, 0.14, 1.2, M.woodWarm, g, 0.9);
  }
  // 向内斜切铝板挑檐（外挑 2.6 m，沿描图轮廓）
  eaveRing(sportsOuter, lv.west_arm_sports.roof - 0.9, EAVE_OUT, 1.2, M.metal, g);

  // 南臂：一层通高，屋面 16 m
  slab(shapeOf(artOuter), 0, 0.8, M.slab, g);
  facade(artOuter, 0.8, lv.south_arm_art.roof - 1.6, { glass: M.glassDark, mullion: M.mullion, step: 7.5 }, g);
  slab(shapeOf(artOuter), lv.south_arm_art.roof - 0.9, 0.9, M.roof, g, { roof: true });
  eaveRing(artOuter, lv.south_arm_art.roof - 0.9, 2.0, 0.9, M.metal, g);
  // 屋面光伏板
  const ac = polyCentroid(artOuter);
  for (let r = 0; r < 4; r++) {
    box(58, 0.14, 6, M.solar, g, ac[0], lv.south_arm_art.roof + 0.9, ac[1] - 12 + r * 9,
      { roof: true, cast: false });
  }

  // L 形转角处的挑高架空贯通大厅（木吊顶 + 8 根巨柱）
  // L 转角处的挑高大厅：雨棚必须落在体量内。原来 34×34 的正方形有近一半
  // 探进 L 的凹口（剪影多出约 1.2k m²）。按四角点测，(-175,40) 处的 22×22
  // 是完整落在西臂内的位置。
  const corner = [-175, 40];
  box(22, 0.4, 22, M.woodWarm, g, corner[0], 11.8, corner[1]);
  [-13, 13].forEach(x => [-13, 13].forEach(z => {
    mesh(new THREE.CylinderGeometry(1.15, 1.15, 11.6, 8), M.white,
      g, { pos: [corner[0] + x, 5.8, corner[1] + z] });
  }));

  // ---- 内部场馆（剖切时显示）：位置/尺寸/朝向全部取自 03 首层（interiors.json） ----
  const dp = details.pool;
  const dg = details.gym;
  const da = details.art;
  const dt = details.theater;

  /** 在给定大厅内居中摆放一块水平面（大厅角度来自 03 的最小外接矩形）。 */
  const hallPlane = (hall, w, d, y, mat, parent) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), mat);
    m.rotation.x = -Math.PI / 2;
    m.rotation.z = hall.rot_deg * Math.PI / 180;
    m.position.set(hall.center[0], y, hall.center[1]);
    m.castShadow = false;
    parent.add(m);
    return m;
  };
  const hallRot = (hall) => hall.rot_deg * Math.PI / 180;

  // 1. 50 m 泳池（8 泳道）
  const P = INTERIORS.pool;
  hallPlane(P.hall, P.size[0], P.size[1], P.level_m, M.water, dp);
  const laneCount = 8;
  for (let lane = 1; lane < laneCount; lane++) {
    const off = -P.size[1] / 2 + lane * (P.size[1] / laneCount);
    const bar = box(P.size[0] - 2, 0.06, 0.2, M.white, dp,
      P.hall.center[0], P.level_m + 0.05, P.hall.center[1] + off, { cast: false });
    bar.rotation.y = -hallRot(P.hall);
  }
  // 出发台
  for (let lane = 0; lane < laneCount; lane++) {
    const off = -P.size[1] / 2 + (lane + 0.5) * (P.size[1] / laneCount);
    const st = box(1.0, 0.6, 1.0, M.white, dp,
      P.hall.center[0] + P.size[0] / 2 - 1.5, P.level_m + 0.5,
      P.hall.center[1] + off, { cast: false });
    st.rotation.y = -hallRot(P.hall);
  }

  // 2. 室内篮球馆（+12.00 层）
  const G = INTERIORS.gym;
  hallPlane(G.hall, G.size[0], G.size[1], G.level_m, M.woodWarm, dg);
  const gRot = hallRot(G.hall);
  for (let b = 0; b < 5; b++) {
    const off = -G.size[1] / 2 + (b + 0.5) * (G.size[1] / 5);
    const tr = box(G.size[0] + 6, 1.4, 0.5, M.truss, dg,
      G.hall.center[0], G.level_m + 8.8, G.hall.center[1] + off, { cast: false });
    tr.rotation.y = -gRot;
  }
  for (let r = 0; r < 5; r++) {
    const seat = box(2.0, 0.45, G.size[1], M.red, dg,
      G.hall.center[0] - G.size[0] / 2 - 1.5 - r * 0.8, G.level_m + 0.4 + r * 0.45,
      G.hall.center[1], { cast: false });
    seat.rotation.y = -gRot;
  }

  // 3. 剧场观众厅核心区（一层）：座椅沿大厅长轴阶梯布置
  const T = INTERIORS.theater;
  const tRot = hallRot(T.hall);
  const rows = 18;
  for (let r = 0; r < rows; r++) {
    const t = r / (rows - 1) - 0.5;
    const along = t * (T.size[0] - 3);
    const seat = box(1.6, 0.45, T.size[1] - 2, M.red, dt,
      T.hall.center[0] + Math.cos(-tRot) * along,
      T.level_m + 0.35 + r * 0.34,
      T.hall.center[1] + Math.sin(-tRot) * along, { cast: false });
    seat.rotation.y = -tRot;
  }

  // 4. 舞台、黑匣子与舞蹈室：相对观众厅核心区定位
  const stage = box(14, 1.6, T.size[1] - 2, M.wood, dt,
    T.hall.center[0] + Math.cos(-tRot) * (T.size[0] / 2 + 7),
    T.level_m + 1.2,
    T.hall.center[1] + Math.sin(-tRot) * (T.size[0] / 2 + 7), { cast: false });
  stage.rotation.y = -tRot;
  box(16, 9, 18, M.volcano, da,
    T.hall.center[0] - Math.cos(-tRot) * (T.size[0] / 2 + 10),
    5.0,
    T.hall.center[1] - Math.sin(-tRot) * (T.size[0] / 2 + 10), { cast: false });

  return { corner, center: cen, armCentroids: { sports: polyCentroid(sportsOuter), art: polyCentroid(artOuter) } };
}

/** 宿舍综合楼：外轮廓 + 采光天井，5 层 + 屋顶格栅。 */
export function buildDorm(scene, groups, details, M) {
  const g = groups.dorm;
  const data = BUILDINGS.dorm;
  const lv = LEVELS.dorm;
  const outer = data.outer;
  const holes = (data.holes || []).filter(h => h.area_m2 >= 25);
  const shape = shapeWithHoles(outer, holes);

  const fh = lv.floor_height_m;
  for (let f = 0; f < lv.levels; f++) {
    const y = lv.ground + f * fh;
    slab(shape, y, 0.65, M.slab, g);
    facade(outer, y + 0.65, fh - 0.9, { glass: f % 2 ? M.glass : M.glassDark, mullion: M.mullion, step: 9 }, g);
    band(outer, y + 0.12, 0.45, 1.4, M.white, g, 0.22);
  }
  // 外廊栏杆（沿每层外缘）与阳台板
  for (let f = 1; f < lv.levels; f++) {
    const y = lv.ground + f * fh;
    // 外廊在建筑轮廓之内（02 屋顶平面的屋面覆盖到轮廓线），因此不外挑楼板，
    // 只沿轮廓线立栏杆 —— 避免把平面剪影整体外扩 1.5 m 拉低 IoU。
    railing(outer, y + 0.08, 1.05, M.mullion, g, 2.2);
  }
  // 两端各一部外部钢梯：落点取多边形 x 极值处的**真实顶点**，
  // 不能直接用 bbox 的 minX/maxX 配 z=0（长条形建筑在 z=0 处并不覆盖到那个 x）。
  const xMinV = outer.reduce((a, p) => (p[0] < a[0] ? p : a), outer[0]);
  const xMaxV = outer.reduce((a, p) => (p[0] > a[0] ? p : a), outer[0]);
  [{ v: xMinV, out: -1 }, { v: xMaxV, out: 1 }].forEach(({ v, out }) => {
    for (let s2 = 0; s2 < lv.levels - 1; s2++) {
      const y = lv.ground + s2 * fh;
      box(1.4, fh - 0.2, 5.0, M.metal, g, v[0] + out * 1.3, y + fh / 2, v[1],
        { cast: false });
    }
    // 平台
    box(1.6, 0.16, 5.2, M.metal, g, v[0] + out * 1.3, lv.ground + (lv.levels - 1) * fh, v[1],
      { cast: false });
  });

  const roofY = lv.ground + lv.levels * fh;
  slab(shape, roofY, 0.75, M.roof, g, { roof: true });
  band(outer, roofY + 0.4, 0.5, 1.2, M.white, g, 0.25);

  // 屋顶白色轻型钢构遮阳格栅
  const RG = new THREE.Group();
  g.add(RG);
  RG.userData.roofs = [];
  g.userData.roofs = (g.userData.roofs || []).concat([RG]);
  // 格栅只落在屋面轮廓内（逐段判断中点是否在多边形内）
  const inside = (x, z) => {
    let c = false;
    for (let i = 0, j = outer.length - 1; i < outer.length; j = i++) {
      const xi = outer[i][0], zi = outer[i][1], xj = outer[j][0], zj = outer[j][1];
      if (((zi > z) !== (zj > z)) && (x < (xj - xi) * (z - zi) / (zj - zi) + xi)) c = !c;
    }
    return c;
  };
  const xs = outer.map(p => p[0]);
  const zs = outer.map(p => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);
  for (let x = minX + 6; x < maxX; x += 9) {
    for (let z = minZ + 6; z < maxZ; z += 2) {
      if (inside(x, z) && inside(x, z + 2)) {
        box(0.26, 0.4, 2, M.mullion, RG, x, roofY + 1.6, z + 1, { roof: true });
      }
    }
  }
  for (let z = minZ + 6; z < maxZ; z += 9) {
    for (let x = minX + 6; x < maxX; x += 2) {
      if (inside(x, z) && inside(x + 2, z)) {
        box(2, 0.4, 0.26, M.mullion, RG, x + 1, roofY + 1.6, z, { roof: true });
      }
    }
  }

  // 天井景观：铺地 + 棕榈
  const cy = details.courtyard;
  holes.forEach(h => {
    const c = h.centroid || polyCentroid(h.polygon);
    box(9, 0.3, 9, M.volcano, cy, c[0], 0.35, c[1], { cast: false });
    palm(cy, c[0], c[1], 6.0, M);
  });
  return { roofY };
}

function palm(parent, x, z, h, M) {
  mesh(new THREE.CylinderGeometry(0.2, 0.34, h, 6), M.trunk, parent, { pos: [x, h / 2 + 0.3, z] });
  for (let k = 0; k < 6; k++) {
    const a = k * Math.PI / 3;
    const leaf = mesh(new THREE.IcosahedronGeometry(2.2, 0), M.treeA, parent,
      { pos: [x + Math.cos(a) * 1.6, h + 0.4, z + Math.sin(a) * 1.6], scale: [1.2, 0.32, 1.2] });
    leaf.rotation.z = Math.cos(a) * 0.3;
    leaf.rotation.x = Math.sin(a) * 0.3;
  }
}
