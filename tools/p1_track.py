"""在卫星正射图上拟合标准 400 m 跑道（IAAF：直道 84.39 m，内突沿半径 36.5 m，道宽 1.22 m）。"""
import sys, json; sys.path.insert(0, '/Users/perrylei/repos/BDFZ_V3/tools')
from worldgrid import *

RES = 0.1
STRAIGHT, R0, LANE = 84.39, 36.5, 1.22


def stadium(r, n_per_m=4):
    pts = []
    for sx in (-1, 1):
        ys = np.linspace(-STRAIGHT / 2, STRAIGHT / 2, int(STRAIGHT * n_per_m))
        pts += [(sx * r, y) for y in ys]
    for sy in (-1, 1):
        ts = np.linspace(0, np.pi, int(np.pi * r * n_per_m))
        pts += [(r * np.cos(t), sy * (STRAIGHT / 2 + r * np.sin(t))) for t in ts]
    return np.array(pts)


def edges_dt(ext):
    sat = warp('sat', RES, ext)
    hsv = cv2.cvtColor(sat, cv2.COLOR_BGR2HSV)
    red = ((((hsv[..., 0] < 12) | (hsv[..., 0] > 165)) & (hsv[..., 1] > 70) & (hsv[..., 2] > 70))).astype(np.uint8)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    red = cv2.morphologyEx(red, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    e = cv2.Canny(red * 255, 50, 150)
    return sat, cv2.distanceTransform(255 - e, cv2.DIST_L2, 3)


def main(c0=(-177.3, -12.2), a0=19.7):
    ext = (c0[0] - 110, c0[1] - 110, c0[0] + 110, c0[1] + 110)
    sat, dt = edges_dt(ext)
    def cost(p):
        cx, cy, ang, rin, wout = p
        th = np.radians(ang); Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        P = np.vstack([stadium(rin, 2), stadium(rin + wout, 2)]) @ Rm.T
        q = to_px(P + [cx, cy], RES, ext).astype(int)
        return float(np.minimum(dt[q[:, 1], q[:, 0]], 30).mean() * RES)

    # 坐标下降：逐参数一维搜索，步长逐级减半
    p = [c0[0], c0[1], a0, R0, 8 * LANE]
    steps = [2.0, 2.0, 0.5, 0.5, 0.5]
    cur = cost(p)
    for _ in range(8):
        for _ in range(4):
            for k in range(5):
                for d in (-1, 1):
                    while True:
                        q = list(p); q[k] += d * steps[k]
                        c = cost(q)
                        if c < cur:
                            p, cur = q, c
                        else:
                            break
        steps = [x / 2 for x in steps]
    best = (cur, tuple(p))
    cx, cy, ang, rin, wout = best[1]
    th = np.radians(ang); Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    v = sat.copy()
    for r in (rin, rin + wout):
        for p in to_px(stadium(r) @ Rm.T + [cx, cy], RES, ext).astype(int):
            cv2.circle(v, tuple(p), 2, (255, 255, 0), -1)
    cv2.imwrite('/Users/perrylei/repos/BDFZ_V3/checks/p1_track_fit.jpg', cv2.resize(v, None, fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA))
    out = dict(center=[round(float(cx), 2), round(float(cy), 2)], long_axis_deg_west_of_north=round(float(ang), 2),
               red_inner_radius=round(float(rin), 2), red_band_width=round(float(wout), 2),
               outer_bbox=[round(float(STRAIGHT + 2 * (rin + wout)), 2), round(float(2 * (rin + wout)), 2)],
               mean_edge_dist_m=round(float(best[0]), 3))
    json.dump(out, open('/Users/perrylei/repos/BDFZ_V3/data/_track_fit.json', 'w'), indent=1)
    print(out)


main()
