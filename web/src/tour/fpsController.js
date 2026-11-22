import * as THREE from 'three';

const EYE_HEIGHT = 1.65;
const WALK_SPEED = 5.2;
const SPRINT_SPEED = 9.5;
const MAX_STEP_UP = 1.35;
const MAX_STEP_DOWN = 2.6;

export class FPSController {
  constructor(camera, domElement, getWalkables) {
    this.camera = camera;
    this.dom = domElement;
    this.getWalkables = getWalkables;
    this.enabled = false;
    this.yaw = 0;        // Three.js rotation.y (rad)
    this.pitch = 0;      // Three.js rotation.x (rad)
    this.feetPos = new THREE.Vector3(-16, -5.95, -74);
    this.keys = new Set();
    this.joy = { x: 0, y: 0 };
    this.dragging = false;
    this.lastPtr = null;
    this.pointerMoved = false;
    this.ray = new THREE.Raycaster();
    this.glide = null;

    this._onKeyDown = (e) => {
      if (!this.enabled) return;
      const k = e.code;
      if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight'].includes(k)) {
        this.keys.add(k);
        this.glide = null;
      }
    };
    this._onKeyUp = (e) => this.keys.delete(e.code);

    this._onPtrDown = (e) => {
      if (!this.enabled || e.button !== 0) return;
      this.dragging = true;
      this.pointerMoved = false;
      this.lastPtr = [e.clientX, e.clientY];
    };
    this._onPtrMove = (e) => {
      if (!this.enabled || !this.dragging || !this.lastPtr) return;
      const dx = e.clientX - this.lastPtr[0];
      const dy = e.clientY - this.lastPtr[1];
      if (Math.hypot(dx, dy) > 3) this.pointerMoved = true;
      this.lastPtr = [e.clientX, e.clientY];
      this.yaw -= dx * 0.0038;
      this.pitch = THREE.MathUtils.clamp(this.pitch - dy * 0.0032, -1.15, 1.15);
      this._applyCamera();
    };
    this._onPtrUp = () => {
      this.dragging = false;
      this.lastPtr = null;
    };

    window.addEventListener('keydown', this._onKeyDown);
    window.addEventListener('keyup', this._onKeyUp);
    this.dom.addEventListener('pointerdown', this._onPtrDown);
    window.addEventListener('pointermove', this._onPtrMove);
    window.addEventListener('pointerup', this._onPtrUp);
  }

  setPoseBlender(bPos, yawDeg, pitchDeg = 0) {
    // Blender (bx, by, bz) -> Three (x=bx, y=bz, z=-by)
    // Blender yaw=0 is +X (East), yaw=90 is +Y (North = Three -Z)
    // Three camera default looks down -Z (Three yaw=0 -> North = Blender yaw 90°)
    this.feetPos.set(bPos[0], bPos[2], -bPos[1]);
    this.yaw = THREE.MathUtils.degToRad(yawDeg - 90);
    this.pitch = THREE.MathUtils.degToRad(pitchDeg);
    this.glide = null;
    this._applyCamera();
  }

  glideTo(targetFeetThree, durMs = 550) {
    this.glide = {
      t0: performance.now(),
      dur: durMs,
      from: this.feetPos.clone(),
      to: targetFeetThree.clone(),
    };
  }

  _sampleGround(x, z, refY) {
    const meshes = this.getWalkables();
    if (!meshes.length) return refY;
    this.ray.set(new THREE.Vector3(x, refY + MAX_STEP_UP, z), new THREE.Vector3(0, -1, 0));
    this.ray.far = MAX_STEP_UP + MAX_STEP_DOWN;
    const hits = this.ray.intersectObjects(meshes, false);
    if (!hits.length) return null;
    // Choose hit closest to refY to handle multi-story floors cleanly!
    let best = hits[0].point.y;
    let bestD = Math.abs(best - refY);
    for (const h of hits) {
      const d = Math.abs(h.point.y - refY);
      if (d < bestD) { best = h.point.y; bestD = d; }
    }
    return best;
  }

  _applyCamera() {
    this.camera.rotation.order = 'YXZ';
    this.camera.rotation.y = this.yaw;
    this.camera.rotation.x = this.pitch;
    this.camera.rotation.z = 0;
    this.camera.position.set(this.feetPos.x, this.feetPos.y + EYE_HEIGHT, this.feetPos.z);
  }

  update(dt, now) {
    if (!this.enabled) return;
    if (this.glide) {
      const k = Math.min(1, (now - this.glide.t0) / this.glide.dur);
      const e = k < 0.5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2;
      this.feetPos.lerpVectors(this.glide.from, this.glide.to, e);
      if (k >= 1) this.glide = null;
      this._applyCamera();
      return;
    }

    let fwd = 0, strafe = 0;
    if (this.keys.has('KeyW') || this.keys.has('ArrowUp')) fwd += 1;
    if (this.keys.has('KeyS') || this.keys.has('ArrowDown')) fwd -= 1;
    if (this.keys.has('KeyD') || this.keys.has('ArrowRight')) strafe += 1;
    if (this.keys.has('KeyA') || this.keys.has('ArrowLeft')) strafe -= 1;
    fwd += this.joy.y;
    strafe += this.joy.x;

    if (Math.abs(fwd) > 0.01 || Math.abs(strafe) > 0.01) {
      const speed = (this.keys.has('ShiftLeft') || this.keys.has('ShiftRight')) ? SPRINT_SPEED : WALK_SPEED;
      const sin = Math.sin(this.yaw), cos = Math.cos(this.yaw);
      const len = Math.min(1, Math.hypot(fwd, strafe));
      const nf = fwd / (Math.hypot(fwd, strafe) || 1) * len;
      const ns = strafe / (Math.hypot(fwd, strafe) || 1) * len;
      const dx = (-sin * nf + cos * ns) * speed * dt;
      const dz = (-cos * nf - sin * ns) * speed * dt;

      const nx = THREE.MathUtils.clamp(this.feetPos.x + dx, -305, 225);
      const nz = THREE.MathUtils.clamp(this.feetPos.z + dz, -130, 215);
      const gy = this._sampleGround(nx, nz, this.feetPos.y);
      if (gy !== null) {
        this.feetPos.set(nx, THREE.MathUtils.lerp(this.feetPos.y, gy, 0.45), nz);
      }
      this._applyCamera();
    }
  }
}
