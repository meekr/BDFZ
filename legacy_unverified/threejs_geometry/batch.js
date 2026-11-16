import * as THREE from 'three';

/**
 * P5 静态几何合批。
 *
 * 场景里的檐口带、竖挺、格栅、房间隔墙都是同材质的小方块，
 * 每个方块一次 draw call，累计上万次。这里把每个建筑组内
 * **同材质的 BoxGeometry** 合并成一个 InstancedMesh：
 *   - 以组内局部坐标为基准，把每个 box 的位置/旋转/尺寸烘进实例矩阵；
 *   - 跳过屋面构件（剖切时要单独开关）与标记了 noFlat 的构件；
 *   - 不跨组合并，保证聚焦淡出（setFade）仍按建筑生效。
 */

const UNIT_BOX = new THREE.BoxGeometry(1, 1, 1);

export function batchGroup(group) {
  const buckets = new Map(); // material.uuid -> { material, items[] }
  const doomed = [];

  group.updateMatrixWorld(true);
  const invGroup = new THREE.Matrix4().copy(group.matrixWorld).invert();

  group.traverse(obj => {
    if (!obj.isMesh || obj.isInstancedMesh) return;
    if (!obj.geometry || obj.geometry.type !== 'BoxGeometry') return;
    if (obj.userData.noFlat) return;
    const mat = obj.material;
    if (!mat || Array.isArray(mat)) return;
    const key = mat.uuid + (obj.userData.isRoof ? '|roof' : '');
    if (!buckets.has(key)) buckets.set(key, { material: mat, items: [] });
    buckets.get(key).items.push(obj);
  });

  let merged = 0;
  buckets.forEach(({ material, items }) => {
    if (items.length < 3) return; // 太少的没必要合
    const inst = new THREE.InstancedMesh(UNIT_BOX, material, items.length);
    inst.castShadow = items.some(i => i.castShadow);
    inst.receiveShadow = items.some(i => i.receiveShadow);
    // 屋面构件合成一批后仍是"屋面"，剖切时整体隐藏
    if (items[0].userData.isRoof) inst.userData.isRoof = true;
    const m = new THREE.Matrix4();
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    items.forEach((it, i) => {
      const params = it.geometry.parameters || {};
      const sx = params.width || 1;
      const sy = params.height || 1;
      const sz = params.depth || 1;
      it.updateMatrixWorld(true);
      m.copy(invGroup).multiply(it.matrixWorld);
      m.decompose(p, q, s);
      s.set(s.x * sx, s.y * sy, s.z * sz);
      m.compose(p, q, s);
      inst.setMatrixAt(i, m);
      doomed.push(it);
    });
    inst.instanceMatrix.needsUpdate = true;
    group.add(inst);
    merged += items.length;
  });

  doomed.forEach(o => {
    if (o.parent) o.parent.remove(o);
    if (o.geometry && o.geometry !== UNIT_BOX) o.geometry.dispose();
  });

  return { merged, batches: buckets.size };
}

/** 对多个组依次合批，返回统计。 */
export function batchGroups(groups) {
  const stat = { merged: 0, batches: 0 };
  Object.values(groups).forEach(g => {
    if (!g || !g.isGroup) return;
    const r = batchGroup(g);
    stat.merged += r.merged;
    stat.batches += r.batches;
  });
  return stat;
}
