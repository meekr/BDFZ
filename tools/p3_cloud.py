"""P3 学术中心竖向与结构 → data/bldg_cloud_p3.json。

05 剖面（右 = 北翼，左 = 南翼）：
  北翼：架空 0 → +8.00，楼板 +8.00 / +12.50，屋面板 +17.00，挑檐 +19.00
  南翼：架空 +5.00 → +10.00，楼板 +10.00 / +14.50 / +19.00，屋面 +23.50
  楼板外挑（深灰带）超出玻璃面，取 1.2 m（wx_14、wx_18 目视）。
两翼之间各标高按 y 线性过渡（ramp_y，wx_14 可见楼板带平滑起伏）。
柱：架空层沿外缘与庭院缘，按间距布置，竖柱与斜柱交替（wx_18 为竖柱 2 根 + 斜柱 1 根的节奏，计数在 P6 相机匹配时核对）。
"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as PC

SLAB_OUT = 1.2       # 楼板外挑
CORE_IN = 7.0        # 底层围合核心内收（wx_18：围合墙在柱列之后）
COL_IN = 2.5         # 竖柱中心内收
SPACING = 8.4        # 柱距
LEVELS = {           # 名称: (南, 北)
    'pilotis': (5.0, 0.0),
    'f1': (10.0, 8.0),
    'f2': (14.5, 12.5),
    'f3': (19.0, 17.0),     # 北翼此处为屋面板
    'roof': (23.5, 19.0),   # 北翼为挑檐
}


def shell_mask():
    bw = PC.ink()
    ring = PC.fill_label_circles(PC.component(bw, (-60, -20)))
    shell = PC.offset(cv2.morphologyEx(ring, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)), PC.LINE_COMP)
    shell[PC.offset(PC.component(bw, (-15, -55)), PC.LINE_COMP) > 0] = 0
    return shell


def columns(shell):
    """沿内收 COL_IN 的等距线按 SPACING 采样；返回 [x, y, nx, ny, kind]，n 为指向外缘的单位法向。"""
    m = PC.offset(shell, -COL_IN)
    dist = cv2.distanceTransform(shell, cv2.DIST_L2, 5)
    gy, gx = np.gradient(cv2.GaussianBlur(dist, (0, 0), 3))
    cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        L = cv2.arcLength(c, True) * PC.RES
        if L < 20:
            continue
        p = c[:, 0, :].astype(float)
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(np.r_[p, p[:1]], axis=0).T))] * PC.RES
        n = max(3, int(round(L / SPACING)))
        for k in range(n):
            s = k * L / n
            i = int(np.searchsorted(seg, s)) % len(p)
            x, y = p[i]
            g = np.array([gx[int(y), int(x)], gy[int(y), int(x)]])
            g = -g / (np.linalg.norm(g) + 1e-9)          # 指向外缘（距离减小方向），像素坐标
            w = wg.to_world([[x, y]], PC.RES, PC.EXT)[0]
            out.append([round(float(w[0]), 2), round(float(w[1]), 2), round(float(g[0]), 3), round(float(-g[1]), 3),
                        'slant' if k % 3 == 2 else 'post'])
    return out


def main():
    shell = shell_mask()
    facade = PC.polys(PC.offset(shell, -SLAB_OUT), eps=0.1, min_area=4)
    core = PC.polys(PC.offset(shell, -CORE_IN), eps=0.1, min_area=4)
    cols = columns(shell)
    D = json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_cloud.json')))
    out = dict(source='05 剖面 + wx_14/wx_18', levels=LEVELS, ramp_y=D['levels']['ramp_y'],
               slab_out=SLAB_OUT, core_in=CORE_IN, col_in=COL_IN, spacing=SPACING,
               slab=D['shell'], facade=facade, core=core, columns=cols)
    json.dump(out, open(os.path.join(wg.ROOT, 'data', 'bldg_cloud_p3.json'), 'w'), ensure_ascii=False)
    print('facade parts', len(facade), 'core parts', len(core), 'columns', len(cols),
          'slant', sum(c[4] == 'slant' for c in cols))


if __name__ == '__main__':
    main()
