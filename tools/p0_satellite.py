"""P0: 卫星底图下载 + 图纸→卫星相似变换配准（倒角距离）。

输出 data/frames.json：每张图纸「像素 → 世界米」的相似变换。
世界坐标：+X 东，+Y 北，单位米；原点见 frames.json.origin。
"""
import math, os, json, sys, urllib.request, concurrent.futures as cf
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAT_DIR = os.path.join(ROOT, 'refs', 'satellite')
HI = os.path.join(ROOT, 'refs', 'drawings', '2024_built_hires')
Z = 19
LAT0, LON0 = 19.98399, 110.25632     # 初始参考点（OSM 校园多边形中心），原点之后改到庭院
HALF_E, HALF_N = 340.0, 220.0


def tile_xy(lat, lon, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def build_mosaic():
    os.makedirs(os.path.join(SAT_DIR, 'tiles'), exist_ok=True)
    dlat = HALF_N / 111320
    dlon = HALF_E / (111320 * math.cos(math.radians(LAT0)))
    x0, y0 = tile_xy(LAT0 + dlat, LON0 - dlon, Z)
    x1, y1 = tile_xy(LAT0 - dlat, LON0 + dlon, Z)
    tx = range(int(x0), int(x1) + 1); ty = range(int(y0), int(y1) + 1)

    def get(a):
        x, y = a
        p = os.path.join(SAT_DIR, 'tiles', f'{Z}_{x}_{y}.jpg')
        if not os.path.exists(p):
            url = f'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{Z}/{y}/{x}'
            req = urllib.request.Request(url, headers={'User-Agent': 'BDFZ-model/1.0'})
            open(p, 'wb').write(urllib.request.urlopen(req, timeout=30).read())
        return p
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(get, [(x, y) for y in ty for x in tx]))
    M = np.vstack([np.hstack([cv2.imread(os.path.join(SAT_DIR, 'tiles', f'{Z}_{x}_{y}.jpg')) for x in tx]) for y in ty])
    mpp = 156543.03392 * math.cos(math.radians(LAT0)) / 2 ** Z
    cx, cy = tile_xy(LAT0, LON0, Z)
    meta = dict(source='Esri World Imagery', zoom=Z, tile_origin=[tx[0], ty[0]], m_per_px=mpp,
                ref_latlon=[LAT0, LON0], ref_px=[(cx - tx[0]) * 256, (cy - ty[0]) * 256],
                note='仅本地校核用，不随成品分发')
    cv2.imwrite(os.path.join(SAT_DIR, 'mosaic.png'), M)
    json.dump(meta, open(os.path.join(SAT_DIR, 'mosaic.json'), 'w'), indent=2, ensure_ascii=False)
    return M, meta


def drawing_points(img, thresh, min_area, n=60000):
    bw = (img < thresh).astype(np.uint8)
    k, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    keep = st[:, cv2.CC_STAT_AREA] >= min_area; keep[0] = False
    ys, xs = np.nonzero(keep[lab])
    idx = np.random.default_rng(0).choice(len(xs), min(n, len(xs)), replace=False)
    return np.c_[xs[idx], ys[idx]].astype(float)


def chamfer_fit(pts, dt, s0, th0, piv_d, piv_s, grid):
    H, W = dt.shape
    P = np.c_[pts, np.ones(len(pts))]

    def mk(ds, dth, tx, ty):
        s = s0 * ds; th = th0 + math.radians(dth)
        R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]]) * s
        t = piv_s + np.array([tx, ty]) - R @ piv_d
        return np.hstack([R, t[:, None]])

    def cost(A):
        q = P @ A.T
        m = (q[:, 0] >= 0) & (q[:, 0] < W - 1) & (q[:, 1] >= 0) & (q[:, 1] < H - 1)
        if m.mean() < 0.5:
            return 99.0
        return float(np.mean(np.minimum(dt[q[m, 1].astype(int), q[m, 0].astype(int)], 15)))

    best = (1e9, (1, 0, 0, 0))
    for dsr, dthr, tr in grid:
        ds0, dth0, tx0, ty0 = best[1] if best[0] < 1e8 else (1, 0, 0, 0)
        for ds in np.arange(ds0 - dsr[0], ds0 + dsr[0] + 1e-9, dsr[1]):
            for dth in np.arange(dth0 - dthr[0], dth0 + dthr[0] + 1e-9, dthr[1]):
                for tx in np.arange(tx0 - tr[0], tx0 + tr[0] + 1e-9, tr[1]):
                    for ty in np.arange(ty0 - tr[0], ty0 + tr[0] + 1e-9, tr[1]):
                        c = cost(mk(ds, dth, tx, ty))
                        if c < best[0]:
                            best = (c, (ds, dth, tx, ty))
    A = mk(*best[1])
    prof = {f'{d:.3f}': round(cost(mk(best[1][0] * d, *best[1][1:])), 3) for d in (0.97, 0.98, 0.99, 0.995, 1.0, 1.005, 1.01, 1.02, 1.03)}
    return A, best[0], prof


if __name__ == '__main__':
    sat, meta = build_mosaic()
    print('mosaic', sat.shape, meta['m_per_px'])
