import * as THREE from 'three';

const UP = new THREE.Vector3(0, 1, 0);

export class TeleportHelper {
  constructor(scene, camera, domElement, fps, getWalkables) {
    this.scene = scene;
    this.camera = camera;
    this.dom = domElement;
    this.fps = fps;
    this.getWalkables = getWalkables;
    this.ray = new THREE.Raycaster();
    this.ndc = new THREE.Vector2();
    this.target = null;
    this._normal = new THREE.Vector3();
    this._normalMat = new THREE.Matrix3();
    this._quat = new THREE.Quaternion();

    // 高精度解析 SDF 瞬移落点标尺：基于 fwidth 屏幕空间抗锯齿，任意斜视角均锐利不糊，并按视距自适应缩放
    const geo = new THREE.PlaneGeometry(2, 2);
    geo.rotateX(-Math.PI / 2);
    this.uniforms = {
      uTime: { value: 0 },
      uFade: { value: 1.0 },
    };
    const mat = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
      vertexShader: `
        varying vec2 vUv;
        void main() {
          vUv = uv * 2.0 - 1.0;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform float uTime;
        uniform float uFade;
        varying vec2 vUv;

        void main() {
          float r = length(vUv);
          if (r > 1.0) discard;
          float aa = max(fwidth(r) * 1.25, 0.008);

          // 1. 精致纤细主蓝环（半径 0.78，环宽 0.075）+ 内侧白描边提亮，红跑道/绿草地/灰广场均清晰
          float dRing = abs(r - 0.78);
          float outerRing = 1.0 - smoothstep(0.036 - aa, 0.036 + aa, dRing);
          float innerWhite = 1.0 - smoothstep(0.015 - aa, 0.015 + aa, abs(r - 0.78));

          // 2. 柔和呼吸扩散细波纹
          float phase = fract(uTime * 0.55);
          float pulseR = mix(0.26, 0.92, phase);
          float pulseAlpha = (1.0 - phase) * (1.0 - phase) * 0.48;
          float pulseRing = (1.0 - smoothstep(0.018 - aa, 0.018 + aa, abs(r - pulseR))) * pulseAlpha;

          // 3. 精致中心落点圆点（外蓝内白）+ 极淡柔光底盘
          float dotBlue = 1.0 - smoothstep(0.14 - aa, 0.14 + aa, r);
          float dotWhite = 1.0 - smoothstep(0.075 - aa, 0.075 + aa, r);
          float discGlow = (1.0 - smoothstep(0.0, 0.78, r)) * 0.11;

          vec3 colBlue = vec3(0.16, 0.54, 1.0);
          vec3 colLight = vec3(0.88, 0.96, 1.0);

          float alpha = clamp(outerRing * 0.90 + pulseRing + dotBlue * 0.92 + discGlow, 0.0, 1.0) * uFade;
          vec3 col = mix(colBlue, colLight, clamp(innerWhite * 0.55 + dotWhite * 0.85, 0.0, 1.0));
          gl_FragColor = vec4(col, alpha);
        }
      `,
    });

    this.ring = new THREE.Mesh(geo, mat);
    this.ring.visible = false;
    this.ring.renderOrder = 10;
    this.scene.add(this.ring);

    this.dom.addEventListener('pointermove', (e) => {
      if (!this.fps.enabled || this.fps.dragging) {
        this.ring.visible = false;
        return;
      }
      this.ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
      this.ray.setFromCamera(this.ndc, this.camera);
      this.ray.far = 85;
      const hits = this.ray.intersectObjects(this.getWalkables(), false);
      const hit = hits.find((h) => h.distance > 1.2 && Math.abs(h.point.y - this.fps.feetPos.y) < 6.5);
      if (hit) {
        this.target = hit.point.clone();

        // 计算表面世界法线，确保标尺紧贴平地与斜坡/看台
        if (hit.face) {
          this._normalMat.getNormalMatrix(hit.object.matrixWorld);
          this._normal.copy(hit.face.normal).applyMatrix3(this._normalMat).normalize();
          if (this._normal.y < 0) this._normal.negate();
        } else {
          this._normal.copy(UP);
        }
        this._quat.setFromUnitVectors(UP, this._normal);
        this.ring.quaternion.copy(this._quat);
        this.ring.position.copy(hit.point).addScaledVector(this._normal, 0.03);

        // 视距自适应柔和缩放：近处精致小巧 (0.20 m 半径)，远处保持清晰易点 (上限 0.52 m)
        const radius = THREE.MathUtils.clamp(0.15 + hit.distance * 0.011, 0.20, 0.52);
        this.ring.scale.setScalar(radius);

        // 极远距离轻微淡出，视觉更自然
        this.uniforms.uFade.value = THREE.MathUtils.clamp(1.12 - hit.distance / 95.0, 0.45, 0.96);
        this.ring.visible = true;
      } else {
        this.target = null;
        this.ring.visible = false;
      }
    });

    this.dom.addEventListener('pointerleave', () => {
      this.hide();
    });

    this.dom.addEventListener('pointerup', () => {
      if (!this.fps.enabled || this.fps.pointerMoved || !this.target) return;
      this.fps.glideTo(this.target, 550);
    });
  }

  update(now) {
    if (this.ring.visible) {
      this.uniforms.uTime.value = now * 0.001;
    }
  }

  hide() {
    this.ring.visible = false;
    this.target = null;
  }
}
