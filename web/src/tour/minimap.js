export class Minimap {
  constructor(canvas, extent, stops, onJumpStop) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.fullExtent = extent; // [X0, Y0, X1, Y1] of overlay_01.jpg ([-330, -220, 330, 220])
    // 裁切图纸顶部与最右侧大片空白留白，让校园主体铺满小地图画幅（保持 ~3:2 比例且坐标映射 100% 精确）
    this.viewExtent = [-320, -210, 260, 140];
    this.stops = stops;
    this.onJumpStop = onJumpStop;
    this.activeStopId = null;
    this.bg = new Image();
    this.bg.src = './overlay_01.jpg';
    this.bgReady = false;
    this.bg.onload = () => { this.bgReady = true; };

    this.canvas.addEventListener('click', (e) => {
      const r = this.canvas.getBoundingClientRect();
      const px = (e.clientX - r.left) * (this.canvas.width / r.width);
      const py = (e.clientY - r.top) * (this.canvas.height / r.height);
      const scale = this.canvas.width / 220;
      let best = null, bestD = 22 * scale;
      for (const st of this.stops) {
        const [sx, sy] = this._worldToPx(st.pos[0], st.pos[1]);
        const d = Math.hypot(sx - px, sy - py);
        if (d < bestD) { best = st; bestD = d; }
      }
      if (best) this.onJumpStop(best.id);
    });
  }

  setActiveStop(id) {
    this.activeStopId = id;
  }

  _worldToPx(bx, by) {
    const [X0, Y0, X1, Y1] = this.viewExtent;
    const u = (bx - X0) / (X1 - X0);
    const v = (Y1 - by) / (Y1 - Y0);
    return [u * this.canvas.width, v * this.canvas.height];
  }

  render(feetThree, threeYaw) {
    const ctx = this.ctx;
    const W = this.canvas.width, H = this.canvas.height;
    const s = W / 220;
    ctx.clearRect(0, 0, W, H);

    ctx.fillStyle = '#edf2f7';
    ctx.fillRect(0, 0, W, H);
    if (this.bgReady) {
      const [FX0, FY0, FX1, FY1] = this.fullExtent;
      const [VX0, VY0, VX1, VY1] = this.viewExtent;
      const iw = this.bg.naturalWidth || this.bg.width;
      const ih = this.bg.naturalHeight || this.bg.height;
      const sx = ((VX0 - FX0) / (FX1 - FX0)) * iw;
      const sy = ((FY1 - VY1) / (FY1 - FY0)) * ih;
      const sw = ((VX1 - VX0) / (FX1 - FX0)) * iw;
      const sh = ((VY1 - VY0) / (FY1 - FY0)) * ih;
      ctx.drawImage(this.bg, sx, sy, sw, sh, 0, 0, W, H);
      ctx.fillStyle = 'rgba(255, 255, 255, 0.10)';
      ctx.fillRect(0, 0, W, H);
    }

    for (const st of this.stops) {
      const [sx, sy] = this._worldToPx(st.pos[0], st.pos[1]);
      const active = st.id === this.activeStopId;
      if (active) {
        ctx.beginPath();
        ctx.arc(sx, sy, 7.6 * s, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(24, 24, 27, 0.20)';
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(sx, sy, (active ? 4.6 : 3.5) * s, 0, Math.PI * 2);
      ctx.fillStyle = st.zone === 'exterior' ? '#18181b' : '#c2410c';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = (active ? 1.8 : 1.3) * s;
      ctx.stroke();
    }

    const bx = feetThree.x, by = -feetThree.z;
    const [px, py] = this._worldToPx(bx, by);
    const canvasAng = -Math.PI / 2 - threeYaw;

    const grad = ctx.createRadialGradient(px, py, 2 * s, px, py, 26 * s);
    grad.addColorStop(0, 'rgba(37, 99, 235, 0.44)');
    grad.addColorStop(1, 'rgba(37, 99, 235, 0.04)');
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.arc(px, py, 26 * s, canvasAng - 0.52, canvasAng + 0.52);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(px, py, 5.0 * s, 0, Math.PI * 2);
    ctx.fillStyle = '#2563eb';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.0 * s;
    ctx.stroke();
  }
}
