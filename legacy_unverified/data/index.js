import framesJson from './frames.json';
import levelsJson from './levels.json';
import trackJson from './track.json';
import courtsJson from './courts.json';
import siteJson from './site.json';
import interiorsJson from './interiors.json';
import cloudJson from './buildings/cloud.json';
import cloud3fRoomsJson from './buildings/cloud_3f_rooms.json';
import dormJson from './buildings/dorm.json';
import sportsJson from './buildings/sports.json';

/**
 * 图纸数据（P0/P1 产出）。
 *
 * 坐标约定（与 scripts/register.py 一致）：
 *   x 向东、z 向南、y 向上，单位米；
 *   原点 = 02 屋顶平面图幅中心；y = 0 对应 01 图绝对标高 37.00。
 *
 * 所有建筑轮廓取自 02 屋顶平面（Crossboundaries 2024 建成版），
 * 比例尺由 04 号图自带的 50 m 比例尺传递而来（见 frames.json.scale.chain）。
 */
export const FRAMES = framesJson;
export const LEVELS = levelsJson;
export const TRACK = trackJson;
export const COURTS = courtsJson;

/** 场地：用地范围、道路与出入口（由 scripts/trace_site.py 从 03/01 描出）。 */
export const SITE_DATA = siteJson;

/** 室内大厅与标准场馆定位（由 scripts/trace_interior.py 从 03 首层描出）。 */
export const INTERIORS = interiorsJson;

export const SCALE = {
  pxPerM: framesJson.scale.px_per_m_02_hires,
  mPerPx: framesJson.scale.m_per_px_02_hires,
};

/** 用地范围：由 03 号图三条主干道内缘围合反算（498.0 × 251.1 m，中心 (−6.3, −21.9)）。
 *  注：计划 3.1 曾按"叠图图片自身的长宽比"推出 532.4 × 295.8 m，
 *  但叠图图片覆盖的范围比用地红线大（含周边道路与绿化带），
 *  按图纸道路内缘反算才是用地本身，故作此更正。 */
export const SITE = {
  W: siteJson.bounds.width_m,
  D: siteJson.bounds.depth_m,
  chamfer: siteJson.chamfer_m,
  center: siteJson.bounds.center,
  polygon: siteJson.site_polygon,
  roads: siteJson.roads,
  entrances: siteJson.entrances,
  gateX: siteJson.gate_x,
};

export const BUILDINGS = {
  cloud: cloudJson,
  dorm: dormJson,
  sports: sportsJson,
};

/** 学术中心三层房间低模（由 04 三层平面直接变换得到）。 */
export const CLOUD_3F_ROOMS = cloud3fRoomsJson;

/** 跑道：中心取自 03 图上跑道分道线的质心，长轴沿图面 70°。 */
export const TRACK_GEO = {
  center: [-144.06, -52.64],
  longAxisDeg: 70,
  // three.js 里 local +x 经 rotation.y 映射到世界 (cosφ, -sinφ)；
  // 要让长轴指向图面 70°（世界 x/z 分量 (cos70, sin70)），取 φ = -70°。
  rotationY_deg: -70,
  straight: 84.39,
  rIn: 36.5,
  lanes: 8,
  laneW: 1.22,
  deck: LEVELS.track ? LEVELS.track.deck : 6.0,
};

/** 把世界坐标 (x,z) 列表转成 three.js 的 Shape（shape.y = -z）。 */
export function shapeFrom(pts, three) {
  const s = new three.Shape();
  if (!pts || !pts.length) return s;
  s.moveTo(pts[0][0], -pts[0][1]);
  for (let i = 1; i < pts.length; i++) s.lineTo(pts[i][0], -pts[i][1]);
  s.closePath();
  return s;
}

/** 带洞的外轮廓（洞口同样在世界坐标）。 */
export function shapeWithHoles(outer, holes, three) {
  const s = shapeFrom(outer, three);
  (holes || []).forEach(h => {
    const pts = h.polygon || h;
    if (!pts || pts.length < 3) return;
    const p = new three.Path();
    p.moveTo(pts[0][0], -pts[0][1]);
    for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], -pts[i][1]);
    p.closePath();
    s.holes.push(p);
  });
  return s;
}

/** 图面像素 → 世界米（用 frames.json 的仿射）。 */
export function pxToWorld(sheet, px, py) {
  const a = FRAMES.frames[sheet].affine;
  return [a[0][0] * px + a[0][1] * py + a[0][2], a[1][0] * px + a[1][1] * py + a[1][2]];
}

/** 世界米 → 图面像素。 */
export function worldToPx(sheet, x, z) {
  const a = FRAMES.frames[sheet].affine;
  const det = a[0][0] * a[1][1] - a[0][1] * a[1][0];
  const dx = x - a[0][2];
  const dz = z - a[1][2];
  return [(a[1][1] * dx - a[0][1] * dz) / det, (-a[1][0] * dx + a[0][0] * dz) / det];
}

/** 某张图纸的内嵌叠图平面参数：中心、尺寸（米）、旋转（弧度）。 */
export function sheetPlane(sheet) {
  const f = FRAMES.frames[sheet];
  const a = f.affine;
  const [w, h] = f.size;
  const corners = [[0, 0], [w, 0], [0, h], [w, h]].map(([px, py]) => pxToWorld(sheet, px, py));
  const xs = corners.map(c => c[0]);
  const zs = corners.map(c => c[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
  const widthM = Math.hypot(a[0][0], a[1][0]) * w;
  const heightM = Math.hypot(a[0][1], a[1][1]) * h;
  const rotRad = Math.atan2(a[1][0], a[0][0]);
  return { center: [cx, cz], widthM, heightM, rotRad, pxPerM: f.px_per_m };
}
