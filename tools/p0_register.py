"""P0 配准：01/02/03/04 → 卫星正射底图 → 世界坐标（米）。

链路：03(高清) → 卫星；02 → 03 半尺寸；01 → 03 半尺寸；04 → 02。
每一步都是相似变换（等比缩放 + 旋转 + 平移），以倒角距离为代价在初值附近细化。
初值 tools/p0_init.json 来自 2026-11-16 的全局粗搜索（过程见 docs/P0_记录.md）。
世界坐标：+X 东，+Y 北，单位米；原点 = 学术中心中央庭院（04 内院轮廓质心）。
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p0_satellite import *

OUT = os.path.join(ROOT, 'data', 'frames.json')
CHK = os.path.join(ROOT, 'checks')
INIT = json.load(open(os.path.join(ROOT, 'tools', 'p0_init.json')))
FINE = [((0.006, 0.002), (0.3, 0.1), (6, 2)), ((0.002, 0.0005), (0.06, 0.02), (2, 0.5))]


def sim(A):
    return math.hypot(A[0, 0], A[1, 0]), math.degrees(math.atan2(A[1, 0], A[0, 0]))


def h3(A):
    return np.vstack([np.asarray(A), [0, 0, 1]])


def refine(pts, dt, A0, piv):
    s0, th0 = sim(A0)
    return chamfer_fit(pts, dt, s0, math.radians(th0), piv, A0[:, :2] @ piv + A0[:, 2], FINE)


def dark_mask(img, th, amin):
    bw = (img < th).astype(np.uint8)
    k, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    keep = st[:, cv2.CC_STAT_AREA] >= amin; keep[0] = False
    return (keep[lab]).astype(np.uint8) * 255


def sample(mask, n=60000):
    ys, xs = np.nonzero(mask)
    i = np.random.default_rng(0).choice(len(xs), min(n, len(xs)), replace=False)
    return np.c_[xs[i], ys[i]].astype(float)


def overlay(base_bgr, mask, A, color, path, scale=0.4, crop=None):
    w = cv2.warpAffine(mask, np.asarray(A)[:2], (base_bgr.shape[1], base_bgr.shape[0]), flags=cv2.INTER_NEAREST)
    v = base_bgr.copy(); v[w > 0] = color
    if crop: v = v[crop[1]:crop[3], crop[0]:crop[2]]
    cv2.imwrite(path, cv2.resize(v, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    os.makedirs(CHK, exist_ok=True)
    sat = cv2.imread(os.path.join(SAT_DIR, 'mosaic.png'))
    meta = json.load(open(os.path.join(SAT_DIR, 'mosaic.json')))
    mpp = meta['m_per_px']
    satg = cv2.cvtColor(sat, cv2.COLOR_BGR2GRAY)
    dt_sat = cv2.distanceTransform(255 - cv2.Canny(cv2.GaussianBlur(satg, (5, 5), 0), 40, 120), cv2.DIST_L2, 5)

    d03 = cv2.imread(os.path.join(HI, '04_line_site.jpg'), 0)
    d02 = cv2.imread(os.path.join(HI, '03_roof_plan.jpg'), 0)
    d01 = cv2.imread(os.path.join(HI, '02_color_site.jpg'))
    d04 = cv2.imread(os.path.join(HI, '05_cloud_3f.jpg'), 0)
    rep = {}

    # 03 → 卫星
    m03 = dark_mask(d03, 120, 200)
    A03, c, prof = refine(sample(m03), dt_sat, np.array(INIT['03_to_sat']), np.array([4960.5, 3508.]))
    rep['03'] = dict(cost_px=c, scale_profile=prof)

    # 02 / 01 → 03 半尺寸
    half = cv2.resize(d03, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    dt_h = cv2.distanceTransform(255 - dark_mask(half, 150, 60), cv2.DIST_L2, 5)
    m02 = dark_mask(d02[:int(d02.shape[0] * 0.8)], 150, 60)
    A02h, c, prof = refine(sample(m02), dt_h, np.array(INIT['02_to_03half']), np.array([2480.5, 1754.]))
    rep['02'] = dict(cost_px=c, scale_profile=prof)
    e01 = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(d01, cv2.COLOR_BGR2GRAY), (3, 3), 0), 60, 160)
    A01h, c, prof = refine(sample(e01), dt_h, np.array(INIT['01_to_03half']), np.array([1250., 787.]))
    rep['01'] = dict(cost_px=c, scale_profile=prof)

    # 04 → 02（学术中心外轮廓 + 内院轮廓）
    bw4 = (d04 < 100).astype(np.uint8)
    k, lab, st, _ = cv2.connectedComponentsWithStats(bw4, 8)
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    plate = (lab == big).astype(np.uint8) * 255
    cnts, hier = cv2.findContours(plate, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outer = max([cc for cc, hh in zip(cnts, hier[0]) if hh[3] < 0], key=cv2.contourArea)
    hole = max([cc for cc, hh in zip(cnts, hier[0]) if hh[3] >= 0], key=cv2.contourArea)
    pts04 = np.vstack([outer[:, 0, :], hole[:, 0, :]]).astype(float)[::3]
    dt02 = cv2.distanceTransform(255 - dark_mask(d02, 150, 60), cv2.DIST_L2, 5)
    A04, c, prof = refine(pts04, dt02, np.array(INIT['04_to_02']), pts04.mean(0))
    rep['04'] = dict(cost_px=c, scale_profile=prof)

    # 复合到卫星像素
    H03 = h3(A03); H02 = H03 @ np.diag([2, 2, 1]) @ h3(A02h); H01 = H03 @ np.diag([2, 2, 1]) @ h3(A01h); H04 = H02 @ h3(A04)

    # 原点：04 内院质心
    M = cv2.moments(hole); hc = np.array([M['m10'] / M['m00'], M['m01'] / M['m00'], 1.0])
    o = (H04 @ hc)[:2]
    # 卫星像素 → 世界米（Y 轴翻转向北）
    S2W = np.array([[mpp, 0, -mpp * o[0]], [0, -mpp, mpp * o[1]], [0, 0, 1]])
    lat0, lon0 = meta['ref_latlon']; rpx = meta['ref_px']
    e_m = (o[0] - rpx[0]) * mpp; n_m = -(o[1] - rpx[1]) * mpp
    olat = lat0 + n_m / 111320.0; olon = lon0 + e_m / (111320.0 * math.cos(math.radians(lat0)))

    frames = dict(
        version=1, updated='2026-11-16',
        world=dict(axes='+X 东, +Y 北, +Z 上；单位米', origin='学术中心中央庭院（04 内院轮廓质心），Z=0 对应 01 图 43.00 (±0.00)',
                   origin_latlon=[round(olat, 7), round(olon, 7)], scale_source='Esri World Imagery z19 正射底图（跑道外包 176.8×91.8 m 与 400 m 标准 8 道 176.9×92.5 m 吻合）'),
        frames={}, report=rep)
    for key, H, fn in [('01', H01, '02_color_site.jpg'), ('02', H02, '03_roof_plan.jpg'), ('03', H03, '04_line_site.jpg'), ('04', H04, '05_cloud_3f.jpg')]:
        W = S2W @ H
        s, th = sim(W[:2])
        frames['frames'][key] = dict(file=f'refs/drawings/2024_built_hires/{fn}', px_to_world=np.round(W[:2], 8).tolist(),
                                     px_per_m=round(1 / s, 4), image_up_vs_north_deg=round(-th if False else th, 3))
    frames['sat'] = dict(file='refs/satellite/mosaic.png', px_to_world=np.round(S2W[:2], 8).tolist(), px_per_m=round(1 / mpp, 4))
    json.dump(frames, open(OUT, 'w'), indent=2, ensure_ascii=False)

    # 检查图
    overlay(sat, m03, H03, (0, 255, 255), os.path.join(CHK, 'p0_03_on_satellite.jpg'))
    overlay(sat, cv2.Canny(d01[:, :, 1], 60, 160), H01, (255, 0, 255), os.path.join(CHK, 'p0_01_on_satellite.jpg'))
    overlay(sat, dark_mask(d02, 150, 60), H02, (0, 255, 0), os.path.join(CHK, 'p0_02_on_satellite.jpg'))
    overlay(cv2.cvtColor(d02, cv2.COLOR_GRAY2BGR), (d04 < 100).astype(np.uint8) * 255, A04, (0, 0, 255),
            os.path.join(CHK, 'p0_04_on_02.jpg'), scale=0.5, crop=(1300, 700, 3400, 2600))
    print(json.dumps({k: dict(px_per_m=v['px_per_m'], rot=v['image_up_vs_north_deg']) for k, v in frames['frames'].items()}, ensure_ascii=False))
    print(json.dumps(rep, ensure_ascii=False))
    print('origin', frames['world']['origin_latlon'])


if __name__ == '__main__':
    main()
