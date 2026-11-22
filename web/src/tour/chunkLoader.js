import * as THREE from 'three';

const CHUNK_FILES = {
  sports: './interior_sports.glb',
  cloud:  './interior_cloud.glb',
  dorm:   './interior_dorm.glb',
};

// Blender world-space AABB triggers (xMin, xMax, yMin, yMax) for auto-loading interiors when walking near
const ZONE_BOUNDS = {
  sports: [-268, -72, -184, -44],
  cloud:  [-55,   52, -110,  14],
  dorm:   [140,  190,  -90, -38],
};

export class ChunkLoader {
  constructor(scene, gltfLoader, onStatus) {
    this.scene = scene;
    this.loader = gltfLoader;
    this.onStatus = onStatus || (() => {});
    this.chunks = {};       // zone -> { state: 'loading'|'ready', root: THREE.Group }
    this.activeZone = null;
    this.navWalkable = [];
    this.navReady = false;

    // Gentle moving interior fill light (no shadow map -> 0 shadow pass overhead!)
    this.interiorLight = new THREE.PointLight(0xfff5e4, 0, 55, 1.3);
    this.scene.add(this.interiorLight);
    this.interiorAmbient = new THREE.HemisphereLight(0xfffaf0, 0x9aa0a8, 0);
    this.scene.add(this.interiorAmbient);
  }

  async loadNav() {
    if (this.navReady) return this.navWalkable;
    const gltf = await this.loader.loadAsync('./nav_collision.glb');
    gltf.scene.traverse((o) => {
      if (o.isMesh) {
        o.visible = false;
        o.material.side = THREE.DoubleSide;
        this.navWalkable.push(o);
      }
    });
    this.scene.add(gltf.scene);
    this.navReady = true;
    return this.navWalkable;
  }

  async ensureZone(zone) {
    if (!zone || zone === 'exterior' || !CHUNK_FILES[zone]) return null;
    const entry = this.chunks[zone];
    if (entry?.state === 'ready') {
      entry.root.visible = true;
      return entry.root;
    }
    if (entry?.state === 'loading') return entry.promise;

    this.onStatus(`加载室内模型 (${zone})…`);
    const promise = this.loader.loadAsync(CHUNK_FILES[zone]).then((gltf) => {
      const root = gltf.scene;
      root.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = false;
        o.receiveShadow = true;
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of mats) {
          if (m.transparent && m.opacity > 0.9) m.transparent = false;
          if (m.transparent) {
            m.depthWrite = false;
            m.side = THREE.DoubleSide;
          }
          // Brighten interior matte surfaces slightly under WebGL tone mapping
          if (m.roughness !== undefined && m.emissiveIntensity === 0) {
            m.envMapIntensity = 0.85;
          }
        }
      });
      this.scene.add(root);
      this.chunks[zone] = { state: 'ready', root };
      this.onStatus(`室内已就绪 (${zone})`);
      return root;
    });
    this.chunks[zone] = { state: 'loading', promise };
    return promise;
  }

  detectZone(threePos) {
    // Convert Three.js (x, y, z) -> Blender (bx = x, by = -z, bz = y)
    const bx = threePos.x;
    const by = -threePos.z;
    const bz = threePos.y;
    for (const [zname, [x0, x1, y0, y1]] of Object.entries(ZONE_BOUNDS)) {
      if (bx >= x0 && bx <= x1 && by >= y0 && by <= y1) {
        if (zname === 'cloud') {
          // Inside Library, Art Gallery, or 3F North Wing
          const inLib = bx >= -42 && bx <= -2 && by >= -100 && by <= -70 && bz < 4.3;
          const inArt = bx >= -39 && bx <= -27 && by >= -59 && by <= -41 && bz < 3.4;
          const in3F  = bx >= -33 && bx <= 37 && by >= -17 && by <= 9 && bz >= 11.5;
          if (inLib || inArt || in3F) return 'cloud';
          continue;
        }
        if (zname === 'dorm') {
          if (bz >= 2.8) return 'dorm';
          continue;
        }
        if (zname === 'sports') {
          if (bz < 1.5) return 'sports';
          continue;
        }
      }
    }
    return 'exterior';
  }

  updateForPosition(threePos, isFps, forceZone = null) {
    const zone = forceZone || (isFps ? this.detectZone(threePos) : 'exterior');
    const inInterior = isFps && zone !== 'exterior';
    if (inInterior) {
      this.ensureZone(zone);
      this.interiorLight.position.set(threePos.x, threePos.y + 2.8, threePos.z);
      this.interiorLight.intensity = 18.0;
      this.interiorAmbient.intensity = 0.95;
    } else {
      this.interiorLight.intensity = 0.0;
      this.interiorAmbient.intensity = 0.0;
    }

    // Zone culling: only render active interior chunk to keep draw calls <= 300
    for (const [zname, entry] of Object.entries(this.chunks)) {
      if (entry.state === 'ready') {
        entry.root.visible = inInterior && zname === zone;
      }
    }
    this.activeZone = zone;
    return zone;
  }
}
