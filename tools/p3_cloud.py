"""P3 学术中心竖向与结构 → data/bldg_cloud_p3.json。

05 剖面（右 = 北翼，左 = 南翼）：
  北翼：架空 0 → +8.00，楼板 +8.00 / +12.50，屋面板 +17.00，挑檐 +19.00
  南翼：架空 +5.00 → +10.00，楼板 +10.00 / +14.50 / +19.00，屋面 +23.50
  楼板外挑（深灰带）超出玻璃面，取 1.2 m（wx_14、wx_18 目视）。
两翼之间各标高按 y 线性过渡（ramp_y，wx_14 可见楼板带平滑起伏）。
柱：架空层沿外缘与庭院缘，按间距布置。P6 匹配相机反投影核对后按翼区分：
  北翼（y > ramp_y 北端）：柱距 8.4 m，全为斜柱（wx_01 东北立面连续 4 根斜柱，柱距 8.1–8.7 m）；
  南翼（y < ramp_y 南端）：柱距 4.2 m，竖柱 2 根 + 斜柱 1 根（wx_18 南端 72 m 内 15 根，平均 4.8 m，竖 9 斜 6）；
  过渡段柱距按 y 线性插值。
"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as PC

SLAB_OUT = 1.2       # 楼板外挑
CORE_IN = 7.0        # 底层围合核心内收（wx_18：围合墙在柱列之后）
COL_IN = 2.5         # 竖柱中心内收
SPACING = (4.2, 8.4) # 柱距（南翼, 北翼），见文件头
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


def columns(shell, ramp_y):
    """沿内收 COL_IN 的等距线按 SPACING（随 y 过渡）布柱；返回 [x, y, nx, ny, kind]，n 为指向外缘的单位法向。"""
    y_s, y_n = ramp_y
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
        W = wg.to_world(p, PC.RES, PC.EXT)
        t = np.clip((W[:, 1] - y_s) / (y_n - y_s), 0, 1)       # 0 = 南翼，1 = 北翼
        step = SPACING[0] + (SPACING[1] - SPACING[0]) * t
        # 先按局部柱距累计出柱数，再整体缩放使首尾闭合
        u = np.r_[0, np.cumsum(np.diff(seg) / step)]
        n = max(3, int(round(u[-1])))
        k_south = 0
        for k in range(n):
            i = int(np.searchsorted(u, k * u[-1] / n)) % len(p)
            x, y = p[i]
            g = np.array([gx[int(y), int(x)], gy[int(y), int(x)]])
            g = -g / (np.linalg.norm(g) + 1e-9)          # 指向外缘（距离减小方向），像素坐标
            w = W[i]
            if t[i] > 0.5:
                kind = 'slant'
            else:
                kind = 'slant' if k_south % 3 == 2 else 'post'
                k_south += 1
            out.append([round(float(w[0]), 2), round(float(w[1]), 2), round(float(g[0]), 3), round(float(-g[1]), 3), kind])
    return out


def main():
    shell = shell_mask()
    facade = PC.polys(PC.offset(shell, -SLAB_OUT), eps=0.1, min_area=4)
    core = PC.polys(PC.offset(shell, -CORE_IN), eps=0.1, min_area=4)
    D = json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_cloud.json')))
    cols = columns(shell, D['levels']['ramp_y'])
    out = dict(source='05 剖面 + wx_14/wx_18；柱距与柱型经 P6 相机匹配（wx_01、wx_18）校正', levels=LEVELS, ramp_y=D['levels']['ramp_y'],
               slab_out=SLAB_OUT, core_in=CORE_IN, col_in=COL_IN, spacing=SPACING,
               slab=D['shell'], facade=facade, core=core, columns=cols)
    json.dump(out, open(os.path.join(wg.ROOT, 'data', 'bldg_cloud_p3.json'), 'w'), ensure_ascii=False)
    print('facade parts', len(facade), 'core parts', len(core), 'columns', len(cols),
          'slant', sum(c[4] == 'slant' for c in cols))


if __name__ == '__main__':
    main()
