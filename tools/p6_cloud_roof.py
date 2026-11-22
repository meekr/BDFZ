"""P6 学术中心屋面：坡屋面网格与采光天窗数据 → data/bldg_cloud_roof.json。

照片（wx_01、wx_02、wx_08、wx_23、wx_35）：
- 深灰蓝金属直立锁边坡屋面，沿每翼中线有屋脊、转角处有斜脊，外缘一圈浅色金属檐口顶边；
- 东西两处条形采光井上方覆盖暗框玻璃天窗（wx_02、wx_23）。
采用 cv2.Subdiv2D + 严格点在多边形内检验生成干净三角网，避免 bmesh triangle_fill 在多洞凹多边形上的跨洞破面。
"""
import sys, os, json, math, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as PC, p3_cloud as P3

SLOPE = 0.055
CAP = 11.0
RIM = 1.2
GRID_STEP = 2.8      # 内部规则网格间距 (m)


def roof_z_base(x, y):
    t = float(P3.ramp_t(x, y))
    s, n = P3.LEVELS['roof']
    return s + t * (n - s)


def triangulate_panel(panel_mask, edge_dist_m):
    """在 panel_mask 内部用等距点 + 轮廓点做 Delaunay 三角化，严格过滤洞内和外侧三角形。"""
    H, W = panel_mask.shape
    cs, h = cv2.findContours(panel_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    pts = []
    for c in cs:
        if cv2.contourArea(c) * PC.RES * PC.RES < 4.0:
            continue
        ap = cv2.approxPolyDP(c, 0.25 / PC.RES, True)[:, 0, :].astype(float)
        # 加密长边，保证网格贴合圆角与脊线
        for i in range(len(ap)):
            a, b = ap[i], ap[(i + 1) % len(ap)]
            n = max(1, int(math.hypot(*(b - a)) * PC.RES / GRID_STEP))
            for k in range(n):
                pts.append(tuple(a + (b - a) * (k / n)))
    step_px = max(2, int(round(GRID_STEP / PC.RES)))
    ys, xs = np.mgrid[step_px // 2:H:step_px, step_px // 2:W:step_px]
    inside = panel_mask[ys, xs] > 0
    for x, y in zip(xs[inside], ys[inside]):
        pts.append((float(x), float(y)))

    sub = cv2.Subdiv2D((0, 0, W + 1, H + 1))
    uniq = list({(round(x, 1), round(y, 1)) for x, y in pts})
    for p in uniq:
        sub.insert((float(p[0]), float(p[1])))

    verts, idx, faces = [], {}, []

    def vid(x, y):
        k = (round(x, 1), round(y, 1))
        if k not in idx:
            xi, yi = int(np.clip(round(x), 0, W - 1)), int(np.clip(round(y), 0, H - 1))
            d = float(edge_dist_m[yi, xi])
            w = wg.to_world([[x, y]], PC.RES, PC.EXT)[0]
            wx, wy = float(w[0]), float(w[1])
            z = roof_z_base(wx, wy) + 0.22 + SLOPE * min(d, CAP)
            idx[k] = len(verts)
            verts.append([round(wx, 2), round(wy, 2), round(z, 3)])
        return idx[k]

    for t in sub.getTriangleList():
        a, b, c = t[0:2], t[2:4], t[4:6]
        cx = int(round((a[0] + b[0] + c[0]) / 3))
        cy = int(round((a[1] + b[1] + c[1]) / 3))
        if not (0 <= cx < W and 0 <= cy < H):
            continue
        if panel_mask[cy, cx] == 0:
            continue
        # 再检查三条边中点均在掩膜内，彻底杜绝跨窄缝/跨天窗的错误三角形
        ok = True
        for p1, p2 in ((a, b), (b, c), (c, a)):
            mx, my = int(round((p1[0] + p2[0]) / 2)), int(round((p1[1] + p2[1]) / 2))
            if not (0 <= mx < W and 0 <= my < H and panel_mask[my, mx] > 0):
                ok = False
                break
        if not ok:
            continue
        ia, ib, ic = vid(*a), vid(*b), vid(*c)
        if len({ia, ib, ic}) == 3:
            faces.append([ia, ib, ic])
    return verts, faces


def main():
    shell = P3.shell_mask()
    # 屋面板边缘距离场（含外缘和内院缘，但先把两个小采光井填平后再算距离场，使屋脊沿翼中线平滑）
    cs, h = cv2.findContours(shell, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    shell_no_sky = shell.copy()
    skylights = []
    for i, c in enumerate(cs):
        if h[0][i][3] < 0:
            continue
        area = cv2.contourArea(c) * PC.RES * PC.RES
        if 4.0 <= area < 500.0:      # 东西两处条形采光井（中央星形庭院 > 3000 m²）
            cv2.drawContours(shell_no_sky, cs, i, 255, -1)
            ap = cv2.approxPolyDP(c, 0.15 / PC.RES, True)[:, 0, :].astype(float)
            w = wg.to_world(ap, PC.RES, PC.EXT)
            skylights.append([[round(float(x), 2), round(float(y), 2)] for x, y in w])
    edge_dist_m = cv2.distanceTransform(shell_no_sky, cv2.DIST_L2, 5) * PC.RES
    # panel_mask：外缘和内院缘内收 RIM，同时保留采光井开口（略外扩 0.2 m 留边框）
    panel_mask = PC.offset(shell_no_sky, -RIM)
    for sky in skylights:
        poly = wg.to_px(sky, PC.RES, PC.EXT).astype(np.int32)
        cv2.fillPoly(panel_mask, [poly], 0)
    verts, faces = triangulate_panel(panel_mask, edge_dist_m)
    panel = PC.polys(panel_mask, eps=0.1, min_area=4)
    edge = PC.polys(shell, eps=0.1, min_area=4)
    out = dict(source='tools/p6_cloud_roof.py：照片所见屋脊/斜脊 + 05 剖面 + Delaunay 严格防破面三角网',
               slope=SLOPE, cap=CAP, rim=RIM,
               ramp_axis_deg=P3.RAMP_AXIS_DEG, ramp_u=P3.RAMP_U,
               note='z = 屋面标高(u) + slope × min(d, cap)；采光井单独生成暗框玻璃天窗',
               mesh=dict(verts=verts, faces=faces),
               skylights=skylights,
               panel=panel, edge=edge)
    json.dump(out, open(os.path.join(wg.ROOT, 'data', 'bldg_cloud_roof.json'), 'w'), ensure_ascii=False)
    print('roof mesh v/f', len(verts), len(faces), 'skylights', len(skylights))


if __name__ == '__main__':
    main()
