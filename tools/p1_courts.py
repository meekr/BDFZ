"""在卫星正射图上用标准尺寸球场线模板（倒角距离）拟合球场中心与朝向。"""
import sys, json; sys.path.insert(0, '/Users/perrylei/repos/BDFZ/tools')
from worldgrid import *

RES = 0.1


def court_lines(kind):
    if kind == 'tennis':
        L, W, Ws = 23.77, 10.97, 8.23
        seg = [((-L/2, -W/2), (L/2, -W/2)), ((-L/2, W/2), (L/2, W/2)), ((-L/2, -W/2), (-L/2, W/2)), ((L/2, -W/2), (L/2, W/2)),
               ((-L/2, -Ws/2), (L/2, -Ws/2)), ((-L/2, Ws/2), (L/2, Ws/2)), ((-6.40, -Ws/2), (-6.40, Ws/2)), ((6.40, -Ws/2), (6.40, Ws/2)),
               ((-6.40, 0), (6.40, 0)), ((0, -W/2 - 0.9), (0, W/2 + 0.9))]
    else:
        L, W = 28.0, 15.0
        seg = [((-L/2, -W/2), (L/2, -W/2)), ((-L/2, W/2), (L/2, W/2)), ((-L/2, -W/2), (-L/2, W/2)), ((L/2, -W/2), (L/2, W/2)), ((0, -W/2), (0, W/2))]
    pts = []
    for (a, b) in seg:
        n = int(np.hypot(b[0]-a[0], b[1]-a[1]) / 0.1) + 1
        pts += [(a[0] + (b[0]-a[0]) * t, a[1] + (b[1]-a[1]) * t) for t in np.linspace(0, 1, n)]
    return np.array(pts)


def fit(kind, c0, ang0, win=6.0, angwin=12.0):
    ext = (c0[0] - 25, c0[1] - 25, c0[0] + 25, c0[1] + 25)
    sat = warp('sat', RES, ext)
    g = cv2.cvtColor(sat, cv2.COLOR_BGR2GRAY)
    tophat = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, np.ones((9, 9), np.uint8))
    lines = (tophat > np.percentile(tophat, 93)).astype(np.uint8)
    dt = cv2.distanceTransform(1 - lines, cv2.DIST_L2, 3)
    T = court_lines(kind)
    best = (1e9, None)
    for stage, (dw, dstep, da, astep) in enumerate([(win, 0.5, angwin, 1.0), (1.0, 0.1, 1.5, 0.1)]):
        cx0, cy0, a0 = best[1] if best[1] else (c0[0], c0[1], ang0)
        for a in np.arange(a0 - da, a0 + da + 1e-9, astep):
            th = np.radians(a); R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
            P = T @ R.T
            for cx in np.arange(cx0 - dw, cx0 + dw + 1e-9, dstep):
                for cy in np.arange(cy0 - dw, cy0 + dw + 1e-9, dstep):
                    q = to_px(P + [cx, cy], RES, ext).astype(int)
                    ok = (q[:, 0] >= 0) & (q[:, 0] < dt.shape[1]) & (q[:, 1] >= 0) & (q[:, 1] < dt.shape[0])
                    c = np.minimum(dt[q[ok, 1], q[ok, 0]], 20).mean() * RES if ok.mean() > 0.9 else 99
                    if c < best[0]:
                        best = (c, (cx, cy, a))
    cx, cy, a = best[1]
    v = sat.copy()
    th = np.radians(a); R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    for p in to_px(T @ R.T + [cx, cy], RES, ext).astype(int):
        cv2.circle(v, tuple(p), 1, (0, 0, 255), -1)
    return dict(kind=kind, center=[round(float(cx), 2), round(float(cy), 2)], long_axis_deg_from_E=round(float(a) % 180, 2), mean_line_dist_m=round(float(best[0]), 3)), v


if __name__ == '__main__':
    jobs = {'tennis_N': ('tennis', (-138, 51), 110), 'tennis_S': ('tennis', (-131, 25), 110),
            'basket_W': ('basket', (-276, 24), 100), 'basket_NE': ('basket', (171, 47), 100)}
    out = {}; tiles = []
    for k, (kind, c, a) in jobs.items():
        out[k], v = fit(kind, c, a)
        tiles.append(cv2.resize(v, (300, 300)))
    cv2.imwrite('/Users/perrylei/repos/BDFZ/checks/p1_courts_fit.jpg', np.hstack(tiles))
    json.dump(out, open('/Users/perrylei/repos/BDFZ/data/_courts_fit.json', 'w'), indent=1)
    print(json.dumps(out, ensure_ascii=False))
