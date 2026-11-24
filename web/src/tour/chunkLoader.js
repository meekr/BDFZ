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


function createAnimatedPoolWaterMaterial() {
  const uniforms = {
    uTime: { value: 0 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    vertexShader: `
      varying vec3 vWorldPos;
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorldPos = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      varying vec3 vWorldPos;

      // 多向叠加自然室内泳池细微涟漪高度场解析梯度（无缝、丝滑、零贴图锯齿）
      vec3 poolWaveNormal(vec2 p, float t) {
        float gx = 0.0;
        float gz = 0.0;

        // 5 组不同波长与流速的细波交织，营造柔和真实水波粼粼感
        float p1 = dot(p, vec2(2.6, 1.9)) + t * 1.15;
        gx += cos(p1) * 2.6 * 0.013; gz += cos(p1) * 1.9 * 0.013;

        float p2 = dot(p, vec2(-2.1, 3.1)) + t * 0.92;
        gx += cos(p2) * (-2.1) * 0.011; gz += cos(p2) * 3.1 * 0.011;

        float p3 = dot(p, vec2(4.4, -3.6)) - t * 1.45;
        gx += cos(p3) * 4.4 * 0.007; gz += cos(p3) * (-3.6) * 0.007;

        float p4 = dot(p, vec2(-5.8, -4.2)) + t * 1.85;
        gx += cos(p4) * (-5.8) * 0.0045; gz += cos(p4) * (-4.2) * 0.0045;

        float p5 = dot(p, vec2(1.4, -7.2)) - t * 2.10;
        gx += cos(p5) * 1.4 * 0.0032; gz += cos(p5) * (-7.2) * 0.0032;

        return normalize(vec3(-gx, 1.0, -gz));
      }

      void main() {
        vec2 p = vWorldPos.xz;
        float t = uTime;
        vec3 N = poolWaveNormal(p, t);
        vec3 V = normalize(cameraPosition - vWorldPos);

        // 菲涅尔项：俯视清澈见底，平视映射天光与顶棚亮泽
        float NdotV = clamp(dot(N, V), 0.0, 1.0);
        float fresnel = pow(1.0 - NdotV, 3.2);

        // 柔和移动焦散微网
        float c1 = sin(p.x * 3.2 + p.y * 2.1 + t * 1.1) * sin(p.x * 2.5 - p.y * 3.4 - t * 0.85);
        float c2 = sin(p.x * 5.1 - p.y * 4.7 + t * 1.6) * sin(p.x * 4.3 + p.y * 5.2 - t * 1.3);
        float caustic = smoothstep(0.32, 0.92, c1 * 0.55 + c2 * 0.45 + 0.35);

        vec3 deepAqua = vec3(0.07, 0.56, 0.78);
        vec3 shallowAqua = vec3(0.28, 0.80, 0.92);
        vec3 skyRefl = vec3(0.84, 0.94, 0.99);

        vec3 baseCol = mix(deepAqua, shallowAqua, 0.35 + caustic * 0.42);
        vec3 col = mix(baseCol, skyRefl, clamp(fresnel * 0.72, 0.0, 0.72));

        // 沿 50m 泳池长轴顶棚 LED 灯阵 + 西侧落地窗天光的多向水波粼粼高光闪烁
        // 稍微放大波纹法线微扰，让低仰角视线能捕捉到错落跳跃的银白波光碎点
        vec3 Nspark = normalize(vec3(N.x * 2.35, 1.0, N.z * 2.35));
        vec3 R = reflect(-V, Nspark);

        vec3 L_north = normalize(vec3(-0.28, 0.30, -0.91)); // 北端顶灯与天光反射方向
        vec3 L_south = normalize(vec3(0.28, 0.32, 0.90));   // 南端对称反射（双端漫游均见波光）
        vec3 L_west  = normalize(vec3(-0.78, 0.44, -0.44)); // 西侧落地窗自然日光

        float gN = pow(max(dot(R, L_north), 0.0), 34.0);
        float gS = pow(max(dot(R, L_south), 0.0), 34.0);
        float gW = pow(max(dot(R, L_west),  0.0), 28.0);
        float specBroad = (gN + gS) * 0.36 + gW * 0.28;

        // 高频碎波尖峰闪烁（真实水波粼粼碎光）
        float hiWave = sin(p.x * 7.8 + p.y * 5.2 + t * 2.3) * sin(p.x * 6.1 - p.y * 8.4 - t * 1.9);
        float crest = smoothstep(0.45, 0.98, hiWave * 0.5 + 0.5);
        float sparkle = (pow(max(dot(R, L_north), 0.0), 95.0) + pow(max(dot(R, L_south), 0.0), 95.0) + pow(max(dot(R, L_west), 0.0), 75.0))
                        * (0.75 + 0.95 * crest);

        // 柔和涟漪明暗对比，增强肉眼可见的水波层次
        float rippleShade = clamp((N.x + N.z) * 2.4, -0.14, 0.14);
        col += vec3(0.08, 0.14, 0.16) * rippleShade;
        col += vec3(0.96, 0.99, 1.0) * (specBroad + sparkle);

        float alpha = clamp(0.36 + fresnel * 0.34 + specBroad * 0.25 + sparkle * 0.42, 0.34, 0.88);
        gl_FragColor = vec4(col, alpha);
      }
    `,
  });
  return { mat, uniforms };
}

export class ChunkLoader {
  constructor(scene, gltfLoader, onStatus, maxAniso = 1) {
    this.scene = scene;
    this.loader = gltfLoader;
    this.onStatus = onStatus || (() => {});
    this.maxAniso = maxAniso;
    this.poolWaterUniforms = null;
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
          for (const slot of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap']) {
            if (m[slot]) {
              m[slot].anisotropy = this.maxAniso;
              m[slot].needsUpdate = true;
            }
          }
          if (m.transparent && m.opacity > 0.9) m.transparent = false;
          if (m.transparent) {
            m.depthWrite = false;
            m.side = THREE.DoubleSide;
          }
          if (m.name === 'M_Int_PoolWater') {
            const { mat: waterMat, uniforms } = createAnimatedPoolWaterMaterial();
            this.poolWaterUniforms = uniforms;
            o.material = waterMat;
            o.renderOrder = 3;
          } else if (m.roughness !== undefined && m.emissiveIntensity === 0) {
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

  updateAnimation(now) {
    if (this.poolWaterUniforms && this.activeZone === 'sports') {
      this.poolWaterUniforms.uTime.value = now * 0.001;
    }
  }
}
