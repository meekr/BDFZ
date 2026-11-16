import * as THREE from 'three';

/**
 * 几何工具箱：把 three.js 的常用原语收敛成少量语义函数。
 * 所有几何生成器只做"数据 → 网格"，不自行计算位置或旋转。
 */

export function mesh(geo, mat, parent, opts) {
  const o = opts || {};
  const m = new THREE.Mesh(geo, mat);
  if (o.pos) m.position.set(o.pos[0], o.pos[1], o.pos[2]);
  if (o.rot) m.rotation.set(o.rot[0], o.rot[1], o.rot[2]);
  m.castShadow = o.cast !== false;
  m.receiveShadow = o.recv !== false;
  if (o.roof) {
    m.userData.isRoof = true;
    (parent.userData.roofs = parent.userData.roofs || []).push(m);
  }
  if (parent) parent.add(m);
  return m;
}

export function box(w, h, d, mat, parent, x, y, z, opts) {
  const o = Object.assign({}, opts || {}, { pos: [x, y, z] });
  return mesh(new THREE.BoxGeometry(w, h, d), mat, parent, o);
}

/** 由世界坐标 (x,z) 点列生成 Shape（shape.y = -z）。 */
export function shapeOf(pts) {
  const s = new THREE.Shape();
  if (!pts || !pts.length) return s;
  s.moveTo(pts[0][0], -pts[0][1]);
  for (let i = 1; i < pts.length; i++) s.lineTo(pts[i][0], -pts[i][1]);
  s.closePath();
  return s;
}

export function shapeWithHoles(outer, holes) {
  const s = shapeOf(outer);
  (holes || []).forEach(h => {
    const pts = h.polygon || h;
    if (!pts || pts.length < 3) return;
    const p = new THREE.Path();
    p.moveTo(pts[0][0], -pts[0][1]);
    for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], -pts[i][1]);
    p.closePath();
    s.holes.push(p);
  });
  return s;
}

/** 在高度 y 处铺一块水平面（extrude 厚度 thick）。 */
export function slab(shape, y, thick, mat, parent, opts) {
  const o = opts || {};
  const geo = new THREE.ExtrudeGeometry(shape, { depth: thick, bevelEnabled: false, curveSegments: 12 });
  const m = new THREE.Mesh(geo, mat);
  m.rotation.x = -Math.PI / 2;
  m.position.y = y;
  m.castShadow = o.cast !== false;
  m.receiveShadow = o.recv !== false;
  if (o.roof) {
    m.userData.isRoof = true;
    (parent.userData.roofs = parent.userData.roofs || []).push(m);
  }
  if (parent) parent.add(m);
  return m;
}

/** 水平面片（单层，无厚度）。 */
export function flat(shape, y, mat, parent, opts) {
  const geo = new THREE.ShapeGeometry(shape, 24);
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, y, 0);
  return mesh(geo, mat, parent, opts);
}

/** 沿多边形边生成竖直墙面（玻璃 + 竖挺）。 */
export function facade(pts, y0, h, o, parent) {
  const opts = o || {};
  const n = pts.length;
  const step = opts.step || 8;
  const glassMat = opts.glass;
  for (let i = 0; i < n; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const dx = p2[0] - p1[0];
    const dz = p2[1] - p1[1];
    const len = Math.hypot(dx, dz);
    if (len < 0.4) continue;
    const ang = Math.atan2(dz, dx);
    const mx = (p1[0] + p2[0]) / 2;
    const mz = (p1[1] + p2[1]) / 2;
    const wall = box(len, h, 0.22, glassMat, parent, mx, y0 + h / 2, mz);
    wall.rotation.y = -ang;
    const cols = Math.max(1, Math.round(len / step));
    for (let c = 0; c <= cols; c++) {
      const u = c / cols - 0.5;
      const px = mx + Math.cos(ang) * u * len;
      const pz = mz + Math.sin(ang) * u * len;
      const col = box(0.3, h + 0.08, 0.4, opts.mullion, parent, px, y0 + h / 2, pz);
      col.rotation.y = -ang;
    }
  }
}

/** 沿多边形边生成一圈水平带（檐口、腰线、木格栅）。 */
export function band(pts, y, thick, depth, mat, parent, expand) {
  const n = pts.length;
  const exp = expand || 0;
  for (let i = 0; i < n; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const dx = p2[0] - p1[0];
    const dz = p2[1] - p1[1];
    const len = Math.hypot(dx, dz);
    if (len < 0.4) continue;
    const ang = Math.atan2(dz, dx);
    const nx = -Math.sin(ang);
    const nz = Math.cos(ang);
    const mx = (p1[0] + p2[0]) / 2 + nx * exp;
    const mz = (p1[1] + p2[1]) / 2 + nz * exp;
    const b = box(len + exp, thick, depth, mat, parent, mx, y + thick / 2, mz);
    b.rotation.y = -ang;
  }
}

/** Sutherland–Hodgman 半平面裁剪：保留 a*x + b*z <= c 的部分。 */
export function clipHalfPlane(pts, a, b, c) {
  const out = [];
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const p = pts[i];
    const q = pts[(i + 1) % n];
    const dp = a * p[0] + b * p[1] - c;
    const dq = a * q[0] + b * q[1] - c;
    if (dp <= 0) out.push(p);
    if ((dp < 0 && dq > 0) || (dp > 0 && dq < 0)) {
      const t = dp / (dp - dq);
      out.push([p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]);
    }
  }
  return out;
}

/** 多边形面积（世界米²）。 */
export function polyArea(pts) {
  let s = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const q = pts[(i + 1) % pts.length];
    s += p[0] * q[1] - q[0] * p[1];
  }
  return Math.abs(s) / 2;
}

/** 多边形质心。 */
export function polyCentroid(pts) {
  let cx = 0;
  let cz = 0;
  let a = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const q = pts[(i + 1) % pts.length];
    const f = p[0] * q[1] - q[0] * p[1];
    a += f;
    cx += (p[0] + q[0]) * f;
    cz += (p[1] + q[1]) * f;
  }
  a *= 0.5;
  if (Math.abs(a) < 1e-9) {
    const n = pts.length;
    return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
  }
  return [cx / (6 * a), cz / (6 * a)];
}

/**
 * 向内斜切的挑檐：沿多边形外缘生成一圈"外低内高"的斜面。
 * 用自建 BufferGeometry 做四边形带，避免对每段 box 做复合旋转。
 *
 * @param pts   世界坐标多边形（外缘）
 * @param y     檐口顶面高度（内缘高度）
 * @param out   外挑长度（米）
 * @param drop  外缘相对内缘的下落（米，正值向下）
 */
export function eaveRing(pts, y, out, drop, mat, parent) {
  const n = pts.length;
  const pos = [];
  const idx = [];
  const normals = [];
  let vi = 0;
  for (let i = 0; i < n; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const dx = p2[0] - p1[0];
    const dz = p2[1] - p1[1];
    const len = Math.hypot(dx, dz);
    if (len < 0.4) continue;
    const nx = (-dz / len) * out;
    const nz = (dx / len) * out;
    // 四个角：内下 / 内上 / 外下 / 外上
    const a = [p1[0], y, p1[1]];
    const b = [p2[0], y, p2[1]];
    const c = [p2[0] + nx, y - drop, p2[1] + nz];
    const d = [p1[0] + nx, y - drop, p1[1] + nz];
    // 侧面（朝外）
    pos.push(...a, ...d, ...c, ...b);
    idx.push(vi, vi + 1, vi + 2, vi, vi + 2, vi + 3);
    for (let k = 0; k < 4; k++) normals.push(nx, 0, nz);
    vi += 4;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geo.setIndex(idx);
  const mesh_ = new THREE.Mesh(geo, mat);
  mesh_.castShadow = true;
  mesh_.receiveShadow = true;
  mesh_.userData.isRoof = true;
  mesh_.userData.noFlat = true;
  if (parent) parent.add(mesh_);
  return mesh_;
}

/** 沿多边形边缘的栏杆：立柱 + 扶手（世界坐标）。 */
export function railing(pts, y, h, mat, parent, step) {
  const n = pts.length;
  const gap = step || 2.4;
  for (let i = 0; i < n; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const dx = p2[0] - p1[0];
    const dz = p2[1] - p1[1];
    const len = Math.hypot(dx, dz);
    if (len < 1.0) continue;
    const ang = Math.atan2(dz, dx);
    // 扶手
    const rail = new THREE.Mesh(new THREE.BoxGeometry(len, 0.12, 0.12), mat);
    rail.position.set((p1[0] + p2[0]) / 2, y + h, (p1[1] + p2[1]) / 2);
    rail.rotation.y = -ang;
    parent.add(rail);
    // 横杆
    const mid = new THREE.Mesh(new THREE.BoxGeometry(len, 0.06, 0.06), mat);
    mid.position.set((p1[0] + p2[0]) / 2, y + h * 0.5, (p1[1] + p2[1]) / 2);
    mid.rotation.y = -ang;
    parent.add(mid);
    // 立柱
    const posts = Math.max(2, Math.round(len / gap));
    for (let k = 0; k <= posts; k++) {
      const t = k / posts;
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.08, h, 0.08), mat);
      post.position.set(p1[0] + dx * t, y + h / 2, p1[1] + dz * t);
      parent.add(post);
    }
  }
}

/** 百叶：在给定墙面上做一排水平叶片。 */
export function louver(pts, y0, h, mat, parent, spacing) {
  const n = pts.length;
  const gap = spacing || 0.45;
  for (let i = 0; i < n; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const dx = p2[0] - p1[0];
    const dz = p2[1] - p1[1];
    const len = Math.hypot(dx, dz);
    if (len < 1.5) continue;
    const ang = Math.atan2(dz, dx);
    const rows = Math.max(1, Math.floor(h / gap));
    for (let r = 0; r < rows; r++) {
      const yy = y0 + r * gap;
      const slat = new THREE.Mesh(new THREE.BoxGeometry(len, 0.08, 0.34), mat);
      slat.position.set((p1[0] + p2[0]) / 2, yy, (p1[1] + p2[1]) / 2);
      slat.rotation.y = -ang;
      slat.rotation.x = 0.32;   // 叶片下倾
      slat.castShadow = false;
      parent.add(slat);
    }
  }
}

/**
 * 多边形向内偏移（米）。用于"屋顶轮廓含挑檐"的情形：
 * 墙体要退到挑檐内侧，挑檐再从墙面向外挑到描图轮廓。
 *
 * 每个顶点沿角平分线内移 d / sin(θ/2)。
 */
export function insetPolygon(pts, d) {
  const n = pts.length;
  if (n < 3 || d <= 0) return pts.map(p => [p[0], p[1]]);
  const area2 = pts.reduce((s, p, i) => {
    const q = pts[(i + 1) % n];
    return s + (p[0] * q[1] - q[0] * p[1]);
  }, 0);
  const ccw = area2 > 0;   // 逆时针为正
  const out = [];
  for (let i = 0; i < n; i++) {
    const p = pts[i];
    const prev = pts[(i - 1 + n) % n];
    const next = pts[(i + 1) % n];
    const v1x = prev[0] - p[0], v1z = prev[1] - p[1];
    const v2x = next[0] - p[0], v2z = next[1] - p[1];
    const l1 = Math.hypot(v1x, v1z) || 1;
    const l2 = Math.hypot(v2x, v2z) || 1;
    const u1x = v1x / l1, u1z = v1z / l1;
    const u2x = v2x / l2, u2z = v2z / l2;
    // 角平分线方向
    let bx = u1x + u2x, bz = u1z + u2z;
    const bl = Math.hypot(bx, bz);
    if (bl < 1e-6) { out.push([p[0], p[1]]); continue; }
    bx /= bl; bz /= bl;
    // 内法向：按绕向决定
    const nx = ccw ? -bz : bz;
    const nz = ccw ? bx : -bx;
    // 相邻边夹角的一半
    const cosT = Math.max(-1, Math.min(1, u1x * u2x + u1z * u2z));
    const half = Math.acos(cosT) / 2;
    const sinHalf = Math.max(0.25, Math.sin(half));   // 限制尖角外溢
    const k = d / sinHalf;
    out.push([p[0] + nx * k, p[1] + nz * k]);
  }
  return out;
}
