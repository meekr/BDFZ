"""P2 体育及艺术中心：外轮廓（02 → 卫星单栋拟合）与斜坡金属屋面网格 → data/bldg_sports.json。

P6 多视角校正（wx_03/wx_04/wx_19/wx_35 + 08 长轴剖透视）：
- 西翼与西南转角（x ≤ -148）：檐口 Z 14.0 m，屋脊高出檐口 3.5 m（Z 17.5 m）；
- 东南翼（x = -148 → -74，向学术中心西南角延伸）：檐口由 Z 14.0 m 线性下降至 Z 3.5 m，
  屋脊高出檐口由 3.5 m 收敛至 1.0 m（东端屋脊 Z 4.5 m），与 wx_04、wx_19、08 长剖面一致。
- 西翼东侧面向田径场建阶梯看台（wx_03、wx_04、wx_31、wx_36 实景确认）。
"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_fit as F, p2_cloud as PC

RES = 0.2
EXT = (-310, -195, -70, -20)
SEED = (-200, -150)
LINE_COMP = 0.3
GROUND = -6.0        # 01：体育中心 ±0.00 = 37.00
EAVE_WEST = 14.0     # 西翼/西南角檐口（wx_04/wx_35 校正）
EAVE_EAST = 3.5      # 东南翼东端檐口（wx_04/wx_19 校正）
SLOPE_X0 = -148.0    # 开始向东下坡的 X 坐标（西南转角 C3）
SLOPE_X1 = -74.0     # 东南翼东端 X 坐标（C4）
RIDGE_D = 22.0       # 屋脊离外缘距离上限
RISE_WEST = 3.5      # 西翼屋脊高出檐口
RISE_EAST = 1.0      # 东端屋脊高出檐口


def eave_z(x):
    t = float(np.clip((x - SLOPE_X0) / (SLOPE_X1 - SLOPE_X0), 0.0, 1.0))
    return EAVE_WEST + (EAVE_EAST - EAVE_WEST) * t


def rise_h(x):
    t = float(np.clip((x - SLOPE_X0) / (SLOPE_X1 - SLOPE_X0), 0.0, 1.0))
    return RISE_WEST + (RISE_EAST - RISE_WEST) * t


def fit_frame():
    outer = F.outline('02', EXT, RES, SEED)
    _, _, dt = F.roof_edges(EXT, RES)
    M, par, _, st = F.fit(outer, dt, search=20, res=RES)
    F.save_frame('02_sports', '02', M, EXT, RES, st, '02 屋顶平面对卫星体育及艺术中心屋面边缘倒角拟合（tools/p2_fit.py）')
    return st


def mask():
    d = cv2.cvtColor(wg.warp('02_sports', res=RES, extent=EXT, interp=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    bw = cv2.dilate((d < 110).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    _, lab = cv2.connectedComponents(255 - bw, connectivity=4)
    p = wg.to_px([SEED], RES, EXT)[0].astype(int)
    m = (lab == lab[p[1], p[0]]).astype(np.uint8) * 255
    cs, _ = cv2.findContours(cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    full = np.zeros_like(m); cv2.drawContours(full, [max(cs, key=cv2.contourArea)], -1, 255, -1)
    return PC.offset(full, LINE_COMP)


def roof_mesh(m, outer_px):
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5) * RES
    H, W = m.shape
    pts = [tuple(p) for p in outer_px]
    for d in np.arange(3, RIDGE_D + 3, 3.0):          # 等距线
        cs, _ = cv2.findContours((dist >= d).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        for c in cs:
            ap = cv2.approxPolyDP(c, 0.4 / RES, True)[:, 0, :]
            pts += [tuple(p.astype(float)) for p in ap]
    sub = cv2.Subdiv2D((0, 0, W + 1, H + 1))
    uniq = list({(round(x, 1), round(y, 1)) for x, y in pts})
    for p in uniq:
        sub.insert((float(p[0]), float(p[1])))
    poly = outer_px.astype(np.float32).reshape(-1, 1, 2)
    verts, idx, faces = [], {}, []

    def vid(x, y):
        k = (round(x, 1), round(y, 1))
        if k not in idx:
            xi, yi = int(np.clip(round(x), 0, W - 1)), int(np.clip(round(y), 0, H - 1))
            w = wg.to_world([[x, y]], RES, EXT)[0]
            wx = float(w[0])
            z = eave_z(wx) + rise_h(wx) * min(float(dist[yi, xi]), RIDGE_D) / RIDGE_D
            idx[k] = len(verts); verts.append([round(wx, 2), round(float(w[1]), 2), round(z, 3)])
        return idx[k]
    for t in sub.getTriangleList():
        a, b, c = t[0:2], t[2:4], t[4:6]
        cen = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3)
        if cv2.pointPolygonTest(poly, cen, False) <= 0:
            continue
        faces.append([vid(*a), vid(*b), vid(*c)])
    # 外缘点强制为当地檐口高度
    for p in outer_px:
        v = verts[idx[(round(float(p[0]), 1), round(float(p[1]), 1))]]
        v[2] = round(eave_z(v[0]), 3)
    return verts, faces


def main():
    st = fit_frame()
    m = mask()
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    ap = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 0.12 / RES, True)[:, 0, :].astype(float)
    outer_w = [[round(float(x), 2), round(float(y), 2)] for x, y in wg.to_world(ap, RES, EXT)]
    verts, faces = roof_mesh(m, ap)
    data = dict(name='体育及艺术中心', frame='02_sports', fit=st, line_comp_m=LINE_COMP, outer=outer_w,
                levels=dict(ground=GROUND, floor2=0.0, eave=EAVE_WEST, eave_west=EAVE_WEST, eave_east=EAVE_EAST,
                            slope_x=[SLOPE_X0, SLOPE_X1], ridge=EAVE_WEST + RISE_WEST,
                            rise_west=RISE_WEST, rise_east=RISE_EAST,
                            note='01：±0.00 = 37.00（Z −6），2F；二层楼面取操场平台 43.00（Z 0）。'
                                 'P6 wx_04/wx_19/wx_35 联合校正：西翼檐口 Z 14.0（屋脊 17.5），东南翼自 x=-148 向东线性降至 x=-74 檐口 Z 3.5（屋脊 4.5）'),
                roof=dict(verts=verts, faces=faces, ridge_d=RIDGE_D))
    json.dump(data, open(os.path.join(wg.ROOT, 'data', 'bldg_sports.json'), 'w'), ensure_ascii=False)
    print('fit', st, 'outer pts', len(outer_w), 'roof v/f', len(verts), len(faces))


if __name__ == '__main__':
    main()
