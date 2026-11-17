"""P5 地表：卫星 → 派生分类（草地 / 铺装 / 树冠）与树位点。只输出分类色块与点位，不含影像本身。
产物：blender/textures/landcover.png（0.5 m/px，范围 EXT）、data/trees.json。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg

EXT = (-300, -190, 210, 95); RES = 0.5
COL = {'grass': (70, 125, 80), 'paving': (170, 178, 182), 'soil': (95, 130, 160)}   # BGR


def footprints(shape):
    m = np.zeros(shape, np.uint8)
    for f in ('bldg_cloud', 'bldg_dorm'):
        cv2.fillPoly(m, [wg.to_px(json.load(open(os.path.join(wg.ROOT, 'data', f + '.json')))['shell'][0]['outer'], RES, EXT).astype(np.int32)], 255)
    cv2.fillPoly(m, [wg.to_px(json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_sports.json')))['outer'], RES, EXT).astype(np.int32)], 255)
    for b in json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_annex.json')))['blocks'].values():
        cv2.fillPoly(m, [wg.to_px(b['outer'], RES, EXT).astype(np.int32)], 255)
    S = json.load(open(os.path.join(wg.ROOT, 'data', 'site.json')))
    T = S['track']; c = wg.to_px([T['center']], RES, EXT)[0]
    cv2.ellipse(m, (tuple(c), (T['outer_bbox'][1] / RES + 12, T['outer_bbox'][0] / RES + 12), T['long_axis_deg_west_of_north']), 255, -1) \
        if False else cv2.ellipse(m, (tuple(float(v) for v in c), (T['outer_bbox'][1] / RES + 12, T['outer_bbox'][0] / RES + 12), -T['long_axis_deg_west_of_north']), 255, -1)
    return m


def main():
    s = wg.warp('sat', res=RES, extent=EXT, border=0).astype(float)
    B, G, R = s[..., 0], s[..., 1], s[..., 2]
    exg = 2 * G - R - B
    hsv = cv2.cvtColor(s.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(float)
    veg = (exg > 18) & (hsv[..., 2] > 45)
    gray = cv2.cvtColor(s.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(float)
    texr = cv2.blur(np.abs(gray - cv2.blur(gray, (5, 5))), (7, 7))
    soil = (R > G + 8) & (R > B + 20) & (hsv[..., 1] > 50)
    fp = footprints(veg.shape) > 0
    veg = cv2.morphologyEx(veg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    tree = veg & (texr > 8.5) & ~fp
    tree = cv2.morphologyEx(tree.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # 地表分类图
    lc = np.zeros(s.shape, np.uint8); lc[:] = COL['paving']
    lc[soil] = COL['soil']; lc[veg] = COL['grass']
    lc = cv2.medianBlur(lc, 5)
    cv2.imwrite(os.path.join(wg.ROOT, 'blender', 'textures', 'landcover.png'), lc)
    # 树位：树冠掩膜距离变换的局部极大，间距 ≥ 6 m
    dt = cv2.distanceTransform(tree, cv2.DIST_L2, 5)
    mx = cv2.dilate(dt, np.ones((int(6 / RES),) * 2, np.uint8))
    ys, xs = np.where((dt == mx) & (dt * RES >= 1.5))
    pts = wg.to_world(np.c_[xs, ys], RES, EXT)
    rad = dt[ys, xs] * RES
    # 去重（平台区等距复制点）
    keep, used = [], np.zeros(len(pts), bool)
    order = np.argsort(-rad)
    for i in order:
        if used[i]:
            continue
        keep.append(i); used |= np.hypot(*(pts - pts[i]).T) < 5.0
    trees = [[round(float(pts[i][0]), 1), round(float(pts[i][1]), 1), round(float(min(rad[i] + 1.0, 6.0)), 1)] for i in keep]
    json.dump(dict(source='卫星树冠分类（ExG + 纹理）距离变换极大值；[x, y, 冠幅半径 m]', extent=EXT, trees=trees),
              open(os.path.join(wg.ROOT, 'data', 'trees.json'), 'w'))
    print('trees', len(trees), 'veg %', round(veg.mean() * 100, 1))
    vis = s.astype(np.uint8).copy()
    for x, y, r in trees:
        p = wg.to_px([[x, y]], RES, EXT)[0].astype(int); cv2.circle(vis, tuple(p), int(r / RES), (0, 255, 255), 1)
    cv2.imwrite(os.path.join(wg.ROOT, 'checks', 'p5_trees_on_satellite.jpg'), np.hstack([vis, lc]), [cv2.IMWRITE_JPEG_QUALITY, 80])


if __name__ == '__main__':
    main()
