import * as THREE from 'three';

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

    // Ground reticle ring
    const geo = new THREE.RingGeometry(0.35, 0.55, 24);
    geo.rotateX(-Math.PI / 2);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x2f88ff, transparent: true, opacity: 0.78, side: THREE.DoubleSide, depthWrite: false,
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
      this.ray.far = 95;
      const hits = this.ray.intersectObjects(this.getWalkables(), false);
      const hit = hits.find((h) => h.distance > 1.2 && Math.abs(h.point.y - this.fps.feetPos.y) < 6.5);
      if (hit) {
        this.target = hit.point.clone();
        this.ring.position.set(hit.point.x, hit.point.y + 0.06, hit.point.z);
        this.ring.visible = true;
      } else {
        this.target = null;
        this.ring.visible = false;
      }
    });

    this.dom.addEventListener('pointerup', () => {
      if (!this.fps.enabled || this.fps.pointerMoved || !this.target) return;
      this.fps.glideTo(this.target, 550);
    });
  }

  hide() {
    this.ring.visible = false;
    this.target = null;
  }
}
