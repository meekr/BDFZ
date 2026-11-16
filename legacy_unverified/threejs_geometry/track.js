import * as THREE from 'three';
import { box, mesh } from './kit.js';
import { TRACK_GEO, LEVELS } from '../data/index.js';

/**
 * 400 m 标准田径场。
 *
 * 关键修正（计划 3.3）：旧版把跑道直道沿局部 X 轴再转 −21.2°，
 * 结果长轴接近东西向，与图纸相差约 48°。现在：
 *   - 中心取自 03 图上跑道分道线的质心（世界米）；
 *   - 长轴方向由 03 图上分道线的图面角（70°）直接换算，
 *     即 three.js 里 rotation.y = −70°。
 */
export function buildTrack(scene, groups, M) {
  const g = groups.track;
  const { center, straight, rIn, lanes, laneW, deck } = TRACK_GEO;
  const rOut = rIn + lanes * laneW;
  const halfS = straight / 2;

  const root = new THREE.Group();
  root.position.set(center[0], 0, center[1]);
  root.rotation.y = TRACK_GEO.rotationY_deg * Math.PI / 180;
  g.add(root);

  // 抬高操场台面（下方为地下车库）：台面沿跑道自身的碗形外缘，不是矩形
  const stadiumShape = (rad) => {
    const s = new THREE.Shape();
    s.moveTo(-halfS, rad);
    s.lineTo(halfS, rad);
    s.absarc(halfS, 0, rad, Math.PI / 2, -Math.PI / 2, true);
    s.lineTo(-halfS, -rad);
    s.absarc(-halfS, 0, rad, -Math.PI / 2, Math.PI / 2, true);
    return s;
  };
  const deckGeo = new THREE.ExtrudeGeometry(stadiumShape(rOut + 3.2),
    { depth: deck, bevelEnabled: false, curveSegments: 40 });
  deckGeo.rotateX(-Math.PI / 2);
  mesh(deckGeo, M.stone, root, { cast: false });

  // 塑胶跑道面层
  const shape = stadiumShape(rOut + 1.6);
  const geo = new THREE.ShapeGeometry(shape, 40);
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, deck + 0.08, 0);
  mesh(geo, M.track, root, { cast: false });

  // 分道线
  for (let k = 0; k <= lanes; k++) {
    const r = rIn + k * laneW;
    const pts = [];
    pts.push(new THREE.Vector3(-halfS, deck + 0.1, r), new THREE.Vector3(halfS, deck + 0.1, r));
    for (let a = Math.PI / 2; a >= -Math.PI / 2; a -= 0.08) {
      pts.push(new THREE.Vector3(halfS + Math.cos(a) * r, deck + 0.1, Math.sin(a) * r));
    }
    pts.push(new THREE.Vector3(halfS, deck + 0.1, -r), new THREE.Vector3(-halfS, deck + 0.1, -r));
    for (let a = -Math.PI / 2; a >= -Math.PI * 1.5; a -= 0.08) {
      pts.push(new THREE.Vector3(-halfS + Math.cos(a) * r, deck + 0.1, Math.sin(a) * r));
    }
    root.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), M.lineW));
  }

  // 场内 105 × 68 m 足球场（天然草）
  const pitch = new THREE.PlaneGeometry(straight, rIn * 2);
  mesh(pitch, M.pitch, root, { pos: [0, deck + 0.09, 0], rot: [-Math.PI / 2, 0, 0], cast: false });
  const fy = deck + 0.12;
  const line = (pairs) => {
    const pts = pairs.map(p => new THREE.Vector3(p[0], fy, p[1]));
    pts.push(pts[0]);
    root.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), M.lineW));
  };
  line([[-halfS, -rIn], [halfS, -rIn], [halfS, rIn], [-halfS, rIn]]);
  line([[0, -rIn], [0, rIn]]);
  const circle = [];
  for (let i = 0; i <= 48; i++) {
    const a = i / 48 * Math.PI * 2;
    circle.push([9.15 * Math.cos(a), 9.15 * Math.sin(a)]);
  }
  line(circle);

  // 西侧清水混凝土看台：8 级踏步，沿直道方向展开，贴着跑道外缘
  // （跑道长轴近南北向，故西侧是一段直道；看台在局部 +z 侧）
  const steps = 8;
  for (let i = 0; i < steps; i++) {
    box(straight + 14, 0.5 + i * 0.001, 1.35, M.stone, root, 0,
      deck + 0.25 + i * 0.5, rOut + 4.5 + i * 1.35, { cast: false });
  }
  // 看台顶部栏杆与两端挡墙
  for (let k = -1; k <= 1; k += 2) {
    box(1.2, steps * 0.5 + 1.2, 1.2, M.stone, root, k * (straight / 2 + 7),
      deck + (steps * 0.5) / 2, rOut + 4.5, { cast: false });
  }

  // 车库柱网（剖切时可见）
  const dTrack = groups.detailTrack;
  for (let i = -3; i <= 3; i++) {
    for (let j = -2; j <= 2; j++) {
      box(1.1, deck - 0.4, 1.1, M.metal, dTrack, i * 13, (deck - 0.4) / 2, j * 15, { cast: false });
    }
  }

  return { center, rOut, halfS, deck };
}
