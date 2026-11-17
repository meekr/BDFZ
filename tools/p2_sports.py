"""P2 体育及艺术中心：外轮廓（02 → 卫星单栋拟合）与四坡屋面网格 → data/bldg_sports.json。

屋面高度 = 檐口 + 坡度 × min(到外缘距离, RIDGE_D)，在等距线 + 内部网格点上做 Delaunay 三角化，
得到沿 L 形两翼的屋脊（与卫星、wx_35 所见的四坡屋面一致）。
"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_fit as F, p2_cloud as PC

RES = 0.2
EXT = (-310, -195, -70, -20)
SEED = (-200, -150)
LINE_COMP = 0.3
GROUND = -6.0        # 01：体育中心 ±0.00 = 37.00
EAVE = 13.0          # P6 wx_35 匹配相机：屋面外沿与 Z 13 投影重合（原按 07 透视剖面推定为 Z 7，偏低 6 m）
RIDGE_D = 22.0       # 屋脊离外缘距离上限（卫星屋脊线）
RISE = 4.0           # 屋脊高出檐口（推定）


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
            z = EAVE + RISE * min(dist[yi, xi], RIDGE_D) / RIDGE_D
            w = wg.to_world([[x, y]], RES, EXT)[0]
            idx[k] = len(verts); verts.append([round(float(w[0]), 2), round(float(w[1]), 2), round(float(z), 3)])
        return idx[k]
    for t in sub.getTriangleList():
        a, b, c = t[0:2], t[2:4], t[4:6]
        cen = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3)
        if cv2.pointPolygonTest(poly, cen, False) <= 0:
            continue
        faces.append([vid(*a), vid(*b), vid(*c)])
    # 外缘点强制为檐口高度
    for p in outer_px:
        verts[idx[(round(float(p[0]), 1), round(float(p[1]), 1))]][2] = EAVE
    return verts, faces


def main():
    st = fit_frame()
    m = mask()
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    ap = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 0.12 / RES, True)[:, 0, :].astype(float)
    outer_w = [[round(float(x), 2), round(float(y), 2)] for x, y in wg.to_world(ap, RES, EXT)]
    verts, faces = roof_mesh(m, ap)
    data = dict(name='体育及艺术中心', frame='02_sports', fit=st, line_comp_m=LINE_COMP, outer=outer_w,
                levels=dict(ground=GROUND, floor2=0.0, eave=EAVE, ridge=EAVE + RISE,
                            note='01：±0.00 = 37.00（Z −6），2F。二层楼面取操场平台 43.00（Z 0）；檐口 Z 13 由 P6 wx_35 匹配相机校正（07 透视剖面推定的 Z 7 偏低），屋脊 = 檐口 + 4 m 仍为推定'),
                roof=dict(verts=verts, faces=faces, ridge_d=RIDGE_D))
    json.dump(data, open(os.path.join(wg.ROOT, 'data', 'bldg_sports.json'), 'w'), ensure_ascii=False)
    print('fit', st, 'outer pts', len(outer_w), 'roof v/f', len(verts), len(faces))


if __name__ == '__main__':
    main()
