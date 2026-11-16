import * as THREE from 'three';
import { box, mesh, slab, flat, shapeOf } from './kit.js';
import { SITE, LEVELS } from '../data/index.js';

/**
 * 场地：用地范围、外围道路、北门、台地与标高。
 * 用地尺寸取自计划 3.1 复核后的等比例叠图平面（532.4 × 295.8 m）——
 * 旧版把叠图铺成 498 × 270 m，导致横向 −6.5%、纵向 −8.7% 的拉伸。
 */
export function buildSite(scene, groups, M) {
  const env = new THREE.Group();
  env.name = 'siteEnv';
  scene.add(env);

  const W = SITE.W;
  const D = SITE.D;
  const [cx, cz] = SITE.center || [0, 0];
  const x0 = cx - W / 2;
  const x1 = cx + W / 2;
  const z0 = cz - D / 2;
  const z1 = cz + D / 2;

  // 用地多边形：直接取 03 号图反算的用地红线（含西北切角）
  const sitePts = (SITE.polygon || []).map(p => [p[0], p[1]]);

  // 大地背景
  mesh(new THREE.PlaneGeometry(W * 1.9, D * 2.1), M.ground, env,
    { pos: [cx, -0.06, cz], rot: [-Math.PI / 2, 0, 0], cast: false });

  // 用地草坪
  slab(shapeOf(sitePts), 0.02, 0.1, M.grass, env, { cast: false });

  // 外围市政道路：中线与宽度取自 03 号图（site.json.roads）
  (SITE.roads || []).forEach(r => {
    if (r.orient === 'E-W') {
      const len = Math.abs(r.x1 - r.x0);
      mesh(new THREE.PlaneGeometry(len, r.width_m), M.roadDark, env,
        { pos: [(r.x0 + r.x1) / 2, 0.12, r.z], rot: [-Math.PI / 2, 0, 0], cast: false });
    } else {
      const len = Math.abs(r.z1 - r.z0);
      mesh(new THREE.PlaneGeometry(r.width_m, len), M.roadDark, env,
        { pos: [r.x, 0.12, (r.z0 + r.z1) / 2], rot: [-Math.PI / 2, 0, 0], cast: false });
    }
  });

  // 场地台地：南侧 +5.00 台地、北侧 −5.00 广场
  const southY = LEVELS.site.south_terrace;
  const northY = LEVELS.site.north_plaza;
  slab(shapeOf([
    [x0 + 6, z0 + D * 0.52], [x0 + W * 0.42, z0 + D * 0.52],
    [x0 + W * 0.42, z1 - 8], [x0 + 6, z1 - 8],
  ]), southY - 0.35, 0.3, M.paving, env, { cast: false });
  slab(shapeOf([
    [x0, z0], [x1, z0], [x1, z0 + D * 0.2], [x0, z0 + D * 0.2],
  ]), northY, 0.3, M.paving, env, { cast: false });

  // 北门：位置取自 01 图的「校主入口」标注（x ≈ 19）
  const gateX = SITE.gateX != null ? SITE.gateX : cx;
  const gateZ = z0 + 8;
  mesh(new THREE.CircleGeometry(15, 32), M.red, env,
    { pos: [gateX, 0.2, gateZ], rot: [-Math.PI / 2, 0, 0], cast: false });
  box(9, 3.8, 5, M.volcano, env, gateX - 16, 1.9, gateZ);
  box(9, 3.8, 5, M.volcano, env, gateX + 16, 1.9, gateZ);
  // 校名石：按实景照片的比例（约 9 × 2.2 × 2.4 m 的卧石 + 正面红色校名）
  box(9, 2.2, 2.4, M.stone, env, gateX, 1.1, gateZ - 4.5);
  box(7.6, 1.0, 0.16, M.gateSign, env, gateX, 1.25, gateZ - 5.7);

  // 地下车库主坡道（成智路方向，抬高操场正下方）
  box(9, 0.5, 15, M.volcano, env, gateX - 45, 0.3, gateZ + 4, { cast: false });
  const ramp = box(7.5, 0.2, 13, M.roadDark, env, gateX - 45, -0.5, gateZ + 4, { cast: false });
  ramp.rotation.x = 0.14;

  // 其余出入口（01 图标注换算）：铺装通道 ＋ 两侧门柱
  (SITE.entrances || []).forEach(en => {
    if (en.id === 'north-main') return;
    const [ex, ez] = en.pos;
    const north = en.id.startsWith('north');
    // 从用地边界向内铺 18 m 通道
    const inward = north ? 1 : -1;
    const path = box(9, 0.14, 18, M.paving, env, ex, 0.16, ez + inward * 9, { cast: false });
    path.userData.noFlat = true;
    // 两侧门柱
    [-6, 6].forEach(dx => {
      box(0.9, 2.6, 0.9, M.volcano, env, ex + dx, 1.3, ez + inward * 1.5);
    });
    // 消防出口用红色标识牌区分
    if (en.id.indexOf('fire') > -1) {
      box(3.2, 0.9, 0.14, M.gateSign, env, ex, 2.2, ez + inward * 1.5, { cast: false });
    }
  });

  return { sitePts, W, D, gateX, gateZ, env };
}
