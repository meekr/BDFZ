"""P2 通用：单栋轮廓（02 图白色区域）对卫星屋面边缘的倒角拟合，结果写成 frames.json 中的 02_<key> 帧。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg


def roof_edges(ext, res):
    s = wg.warp('sat', res=res, extent=ext, border=0)
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)
    roof = ((hsv[..., 1] < 45) & (hsv[..., 2] > 140)).astype(np.uint8) * 255
    roof = cv2.morphologyEx(roof, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ed = cv2.Canny(roof, 50, 150)
    return s, ed, cv2.distanceTransform(255 - ed, cv2.DIST_L2, 5)


def outline(key, ext, res, seed):
    d = cv2.cvtColor(wg.warp(key, res=res, extent=ext, interp=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    bw = cv2.dilate((d < 110).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    _, lab = cv2.connectedComponents(255 - bw, connectivity=4)
    p = wg.to_px([seed], res, ext)[0].astype(int)
    m = cv2.morphologyEx((lab == lab[p[1], p[0]]).astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cs, key=cv2.contourArea)[:, 0, :].astype(float)


def fit(outer, dt, fix_scale=False, search=60, res=0.2):
    H, W = dt.shape; c = outer.mean(0)

    def tf(par):
        tx, ty, a, sc = par; ca, sa = np.cos(np.radians(a)), np.sin(np.radians(a)); q = outer - c
        return np.c_[ca * q[:, 0] - sa * q[:, 1], sa * q[:, 0] + ca * q[:, 1]] * sc + c + [tx, ty]

    def score(pts):
        p = np.round(pts).astype(int); ok = (p[:, 0] >= 0) & (p[:, 0] < W) & (p[:, 1] >= 0) & (p[:, 1] < H)
        v = np.full(len(p), 40.0); v[ok] = dt[p[ok, 1], p[ok, 0]]; return np.mean(np.minimum(v, 15))
    r = int(search / res); st0 = max(1, int(0.6 / res))
    v, par = min(((score(tf((tx, ty, 0, 1))), [tx, ty, 0., 1.]) for tx in range(-r, r + 1, st0)
                  for ty in range(-r, r + 1, st0)), key=lambda t: t[0])
    keys = [0, 1, 2] if fix_scale else [0, 1, 2, 3]
    for st in [(2, 0.5, 0.01), (1, 0.25, 0.005), (0.5, 0.1, 0.002), (0.25, 0.05, 0.001)]:
        imp = True
        while imp:
            imp = False
            for k in keys:
                for sg in (1, -1):
                    p2 = list(par); p2[k] += sg * [st[0], st[0], st[1], st[2]][k]; v2 = score(tf(p2))
                    if v2 < v - 1e-6:
                        par, v, imp = p2, v2, True
    fitted = tf(par)
    ok = (fitted[:, 0] >= 0) & (fitted[:, 0] < W) & (fitted[:, 1] >= 0) & (fitted[:, 1] < H)
    p = np.round(fitted[ok]).astype(int); dd = dt[p[:, 1], p[:, 0]] * res
    # 网格像素空间的相似变换（3x3）
    a, sc = np.radians(par[2]), par[3]
    A = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]) * sc
    M = np.eye(3); M[:2, :2] = A; M[:2, 2] = c - A @ c + par[:2]
    stats = dict(median=round(float(np.median(dd)), 2), p90=round(float(np.percentile(dd, 90)), 2), max=round(float(dd.max()), 2))
    return M, par, fitted, stats


def save_frame(name, base, M, ext, res, stats, note):
    _, P2W = wg.frame(base)
    T = wg.grid_to_world(res, ext) @ M @ wg.world_to_grid(res, ext) @ P2W
    p = os.path.join(wg.ROOT, 'data', 'frames.json'); FR = json.load(open(p))
    s = float(np.hypot(T[0, 0], T[1, 0]))
    FR['frames'][name] = dict(file=FR['frames'][base]['file'], px_to_world=T[:2].round(8).tolist(),
                              px_per_m=round(1 / s, 4), note=note, fit=stats)
    json.dump(FR, open(p, 'w'), ensure_ascii=False, indent=1)
    wg.FR = FR
