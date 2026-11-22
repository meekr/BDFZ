"""P6 照片相机匹配。

做法：在照片上沿可辨认的轮廓（学术中心檐口外沿/内院沿、跑道外沿、宿舍女儿墙/大庭院、体育中心斜坡檐口等）
人工描点（原图像素），存入 data/p6_traces.json；模型侧对应的三维曲线由 data/*.json 生成并按 0.5 m 加密。
代价 = 每个照片描点到投影后模型曲线的最近距离（照片→模型单向，故遮挡、出画不影响）。
use = "fit" 的描线参与求解，"check" 的只用于事后检验。

相机参数 p = [x, y, z, yaw°, pitch°, roll°, f, k1]：yaw 为视线方位（自 +X 逆时针），pitch 为俯角，
f 为像素焦距（按 W_WORK 宽）。
"""
import os, json, math, cv2, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W_WORK = 1180
SAMPLE_M = 0.5


def pattern_search(fun, x0, step, shrink=0.5, min_step=0.005, max_eval=8000):
    """坐标模式搜索（无 scipy 依赖）。"""
    x = np.array(x0, float); fx = fun(x); s = np.array(step, float); n = 0
    while s.max() > min_step and n < max_eval:
        imp = False
        for k in range(len(x)):
            if s[k] == 0:
                continue
            for sg in (1, -1):
                y = x.copy(); y[k] += sg * s[k]; fy = fun(y); n += 1
                if fy < fx - 1e-9:
                    x, fx, imp = y, fy, True
                    break
        if not imp:
            s *= shrink
    return x, fx


def rot(yaw, pitch, roll):
    y, p, r = np.radians([yaw, pitch, roll])
    d = np.array([np.cos(p) * np.cos(y), np.cos(p) * np.sin(y), -np.sin(p)])
    right = np.cross(d, [0, 0, 1]); right /= np.linalg.norm(right)
    up = np.cross(right, d)
    cr, sr = np.cos(r), np.sin(r)
    return d, cr * right + sr * up, -sr * right + cr * up


def project(P, p, W, H):
    C = np.array(p[:3]); d, rt, up = rot(*p[3:6]); f = p[6]
    Q = P - C
    z = Q @ d
    ok = z > 1
    x = (Q @ rt) / np.where(ok, z, 1)
    y = (Q @ up) / np.where(ok, z, 1)
    if len(p) > 7 and p[7]:
        k = 1 + p[7] * ((x * f) ** 2 + (y * f) ** 2) / (W / 2) ** 2
        x, y = x * k, y * k
    return W / 2 + f * x, H / 2 - f * y, ok


# ---------- 模型曲线 ----------
def _densify(poly, closed=True):
    poly = np.asarray(poly, float)
    if closed:
        poly = np.vstack([poly, poly[:1]])
    out = []
    for a, b in zip(poly[:-1], poly[1:]):
        n = max(1, int(np.linalg.norm(b[:2] - a[:2]) / SAMPLE_M))
        out += [a + (b - a) * t for t in np.arange(n) / n]
    return np.array(out)


def _load(name):
    return json.load(open(os.path.join(ROOT, 'data', name)))


def corners(poly, tol=2.0):
    a = cv2.approxPolyDP(np.asarray(poly, np.float32).reshape(-1, 1, 2), tol, True).reshape(-1, 2)
    return a.astype(float)


def _cloud_t(xy):
    P3 = _load('bldg_cloud_p3.json')
    ang = math.radians(P3.get('ramp_axis_deg', -10.0))
    u_s, u_n = P3.get('ramp_u', P3['ramp_y'])
    u = xy[:, 1] * math.cos(ang) + xy[:, 0] * math.sin(ang)
    return np.clip((u - u_s) / (u_n - u_s), 0.0, 1.0)


def curve(name):
    """返回 (N,3) 世界坐标点。name 可带 '@a:b'，取闭合轮廓从转角 a 到 b 的一段。"""
    if '@' in name:
        base, rng = name.split('@')
        a, b = (int(v) for v in rng.split(':'))
        P = curve(base)
        C = corners(_outline(base))
        ia, ib = (int(np.argmin(np.hypot(*(P[:, :2] - C[k]).T))) for k in (a, b))
        return P[ia:ib + 1] if ia <= ib else np.vstack([P[ia:], P[:ib + 1]])
    if name.startswith('cloud_level:') or name.startswith('cloud_court_level:'):
        parts = name.split(':')
        P3 = _load('bldg_cloud_p3.json')
        s, n = P3['levels'][parts[1]]
        dz = float(parts[2]) if len(parts) > 2 else 0.0
        sh = _load('bldg_cloud.json')['shell'][0]
        ring = max(sh['holes'], key=len) if name.startswith('cloud_court_level:') else sh['outer']
        xy = _densify(ring)
        t = _cloud_t(xy)
        return np.c_[xy, s + (n - s) * t + dz]
    if name in ('cloud_eave', 'cloud_court_eave'):
        D = _load('bldg_cloud.json'); L = D['levels']
        sh = D['shell'][0]
        ring = max(sh['holes'], key=len) if name == 'cloud_court_eave' else sh['outer']
        xy = _densify(ring)
        t = _cloud_t(xy)
        zs, zn = L['eave']['south'], L['eave']['north']
        return np.c_[xy, zs + (zn - zs) * t]
    if name in ('track_outer', 'track_center'):
        T = _load('_track_fit.json')
        c = np.array(T['center'])
        if name == 'track_center':
            return np.array([[c[0], c[1], 0.0]])
        a = np.radians(T['long_axis_deg_west_of_north'])
        ax = np.array([-np.sin(a), np.cos(a)]); nx = np.array([ax[1], -ax[0]])
        R = T['red_inner_radius'] + T['red_band_width']
        L = T['outer_bbox'][0] / 2 - R
        pts = [c + ax * t + nx * R for t in np.linspace(L, -L, int(2 * L / SAMPLE_M))]
        th = np.linspace(0, np.pi, int(np.pi * R / SAMPLE_M))
        pts += [c - ax * L + R * (np.cos(t) * nx - np.sin(t) * ax) for t in th]
        pts += [c + ax * t - nx * R for t in np.linspace(-L, L, int(2 * L / SAMPLE_M))]
        pts += [c + ax * L + R * (-np.cos(t) * nx + np.sin(t) * ax) for t in th]
        P = np.array(pts)
        return np.c_[P, np.full(len(P), 0.1)]
    if name == 'dorm_parapet':
        D = _load('bldg_dorm.json'); L = D['levels']
        # 与 bldg_dorm.py 屋顶挑檐构架顶高一致（z_body + 0.85 ≈ 19.0）
        z = L['ground'] + L['floors'] * L['floor_h'] + L['parapet']
        xy = _densify(D['shell'][0]['outer'])
        return np.c_[xy, np.full(len(xy), z)]
    if name.startswith('dorm_court:'):
        # dorm_court:<hole_idx>:<z>
        _, idx_s, z_s = name.split(':')
        D = _load('bldg_dorm.json')
        xy = _densify(D['shell'][0]['holes'][int(idx_s)])
        return np.c_[xy, np.full(len(xy), float(z_s))]
    if name == 'sports_eave':
        D = _load('bldg_sports.json'); L = D['levels']
        xy = _densify(D['outer'])
        x0, x1 = L.get('slope_x', [-148.0, -74.0])
        ew, ee = L.get('eave_west', L['eave']), L.get('eave_east', L['eave'])
        t = np.clip((xy[:, 0] - x0) / (x1 - x0), 0.0, 1.0)
        z = ew + (ee - ew) * t
        return np.c_[xy, z]
    raise KeyError(name)


def _outline(base):
    if base.startswith('cloud_level:'):
        base = 'cloud_eave'
    elif base.startswith('cloud_court_level:'):
        base = 'cloud_court_eave'
    elif base.startswith('dorm_court:'):
        idx = int(base.split(':')[1])
        return _load('bldg_dorm.json')['shell'][0]['holes'][idx]
    return {'cloud_eave': lambda: _load('bldg_cloud.json')['shell'][0]['outer'],
            'cloud_court_eave': lambda: max(_load('bldg_cloud.json')['shell'][0]['holes'], key=len),
            'dorm_parapet': lambda: _load('bldg_dorm.json')['shell'][0]['outer'],
            'sports_eave': lambda: _load('bldg_sports.json')['outer']}[base]()


# ---------- 求解 ----------
def _dist(px, P, p, W, H, s):
    u, v, ok = project(P, p, W, H)
    q = np.c_[u[ok], v[ok]] / s
    if len(q) == 0:
        return np.full(len(px), 1e3)
    if len(P) == 1:
        return np.hypot(*(px - q).T)
    return np.sqrt(((px[:, None, :] - q[None]) ** 2).sum(-1)).min(1)


class Photo:
    def __init__(self, name):
        T = _load('p6_traces.json')[name]
        self.name, self.T = name, T
        self.path = os.path.join(ROOT, T['photo'])
        im = cv2.imread(self.path)
        self.size = (im.shape[1], im.shape[0])
        self.s = W_WORK / im.shape[1]
        self.W, self.H = W_WORK, round(im.shape[0] * self.s)
        self.traces = [dict(t, px=np.array(t['px'], float), P=curve(t['curve'])) for t in T['traces']]

    def dists(self, p, use=None):
        return [(t, _dist(t['px'], t['P'], p, self.W, self.H, self.s)) for t in self.traces if use is None or t['use'] == use]

    def err(self, p):
        e = np.concatenate([d * t.get('w', 1.0) for t, d in self.dists(p, 'fit')])
        return float(np.sqrt((e ** 2).mean()))

    def fit(self, p0=None, restarts=8, seed=0):
        p0 = np.array(p0 if p0 is not None else self.T['p0'], float)
        p0 = np.r_[p0, np.zeros(8 - len(p0))]
        sc = np.array(self.T.get('scale', [5, 5, 5, 1.5, 1.5, 0.5, 30, 0.02 if self.T.get('distortion', True) else 0]), float)
        rng = np.random.default_rng(seed)
        best = (p0, self.err(p0))
        for k in range(restarts):
            st = best[0] + (rng.normal(0, 1.5, 8) * sc if k else 0)
            q, f = pattern_search(lambda q: self.err(st + q * sc), np.zeros(8), [1.0] * 8)
            if f < best[1]:
                best = (st + q * sc, f)
        return best

    def report(self, p):
        R = {}
        for t, d in self.dists(p):
            R[t['id']] = dict(curve=t['curve'], use=t['use'], n=len(d), median_px=round(float(np.median(d)), 1),
                              max_px=round(float(d.max()), 1), median_pct_width=round(float(np.median(d)) / self.size[0] * 100, 2))
        return R

    def overlay(self, p, out, groups=('cloud_roof', 'cloud_slab', 'track', 'sports', 'dorm', 'courts')):
        im = cv2.imread(self.path)
        sc = 1 / self.s
        Z = np.load(os.path.join(ROOT, 'data', '_feature_pts.npz'))
        cols = {'cloud_roof': (0, 0, 255), 'cloud_slab': (0, 200, 255), 'track': (0, 255, 0), 'sports': (255, 0, 255),
                'dorm': (255, 255, 0), 'courts': (255, 0, 0), 'annex': (0, 128, 255)}
        for g in groups:
            if g not in Z.files or not len(Z[g]):
                continue
            u, v, ok = project(Z[g], p, self.W, self.H)
            for a, b in zip(u[ok] * sc, v[ok] * sc):
                if 0 <= a < im.shape[1] and 0 <= b < im.shape[0]:
                    cv2.circle(im, (int(a), int(b)), 2, cols.get(g, (255, 255, 255)), -1)
        for t in self.traces:
            col = (255, 255, 255) if t['use'] == 'fit' else (0, 255, 255)
            for x, y in t['px']:
                cv2.drawMarker(im, (int(x), int(y)), col, cv2.MARKER_CROSS, 18, 2)
        cv2.imwrite(out, im, [cv2.IMWRITE_JPEG_QUALITY, 85])

    def save(self, p, rms):
        path = os.path.join(ROOT, 'data', 'cameras.json')
        D = json.load(open(path)) if os.path.exists(path) else {
            'note': '照片匹配相机（tools/p6_camera.py，描线见 p6_traces.json）。p = [x, y, z, yaw°, pitch°, roll°, f_px@W_WORK, k1]；'
                    'residual 为原图像素', 'W_WORK': W_WORK, 'cameras': {}}
        D['cameras'][self.name] = dict(photo=self.T['photo'], size=list(self.size), p=[round(float(v), 3) for v in p],
                                       lens_mm_36=round(float(p[6]) / W_WORK * 36, 1),
                                       fit_rms_px=round(rms, 1), residual=self.report(p))
        json.dump(D, open(path, 'w'), ensure_ascii=False, indent=1)


def blender_camera(p, W, H):
    d, rt, up = rot(*p[3:6])
    M = np.c_[rt, up, -d]
    sy = np.hypot(M[0, 0], M[1, 0])
    rx = np.arctan2(M[2, 1], M[2, 2]); ry = np.arctan2(-M[2, 0], sy); rz = np.arctan2(M[1, 0], M[0, 0])
    return list(p[:3]), [float(rx), float(ry), float(rz)], float(p[6] / W * 36)
