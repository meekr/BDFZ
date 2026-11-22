export class Minimap {
  constructor(canvas, extent, stops, onJumpStop) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.extent = extent; // [X0, Y0, X1, Y1] Blender world meters
    this.stops = stops;
    this.onJumpStop = onJumpStop;
    this.bg = new Image();
    this.bg.src = './overlay_01.jpg';
    this.bgReady = false;
    this.bg.onload = () => { this.bgReady = true; };

    this.canvas.addEventListener('click', (e) => {
      const r = this.canvas.getBoundingClientRect();
      const px = (e.clientX - r.left) * (this.canvas.width / r.width);
      const py = (e.clientY - r.top) * (this.canvas.height / r.height);
      // Find nearest tour stop within 18 px
      let best = null, bestD = 20;
      for (const st of this.stops) {
        const [sx, sy] = this._worldToPx(st.pos[0], st.pos[1]);
        const d = Math.hypot(sx - px, sy - py);
        if (d < bestD) { best = st; bestD = d; }
      }
      if (best) this.onJumpStop(best.id);
    });
  }

  _worldToPx(bx, by) {
    const [X0, Y0, X1, Y1] = this.extent;
    const u = (bx - X0) / (X1 - X0);
    const v = (Y1 - by) / (Y1 - Y0);
    return [u * this.canvas.width, v * this.canvas.height];
  }

  render(feetThree, threeYaw) {
    const ctx = this.ctx;
    const W = this.canvas.width, H = this.canvas.height;
    ctx.clearRect(0, 0, W, H);
    if (this.bgReady) {
      ctx.drawImage(this.bg, 0, 0, W, H);
      ctx.fillStyle = 'rgba(255,255,255,0.18)';
      ctx.fillRect(0, 0, W, H);
    } else {
      ctx.fillStyle = '#dce6ef';
      ctx.fillRect(0, 0, W, H);
    }
    // Draw clickable tour stop pins
    for (const st of this.stops) {
      const [sx, sy] = this._worldToPx(st.pos[0], st.pos[1]);
      ctx.beginPath();
      ctx.arc(sx, sy, 3.6, 0, Math.PI * 2);
      ctx.fillStyle = st.zone === 'exterior' ? '#2f6db5' : '#e0533c';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
    // Draw player dot & 60 deg FOV cone
    const bx = feetThree.x, by = -feetThree.z;
    const [px, py] = this._worldToPx(bx, by);
    // Three yaw=0 looks North (-Z => canvas up = -PI/2)
    const canvasAng = -Math.PI / 2 - threeYaw;
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.arc(px, py, 20, canvasAng - 0.52, canvasAng + 0.52);
    ctx.closePath();
    ctx.fillStyle = 'rgba(47, 109, 181, 0.32)';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(px, py, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#e53935';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}
