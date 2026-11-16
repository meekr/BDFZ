"""P2 学术中心门槛：模型顶视剪影 vs 02 图（IoU）与 vs 卫星屋面边缘（倒角距离）。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as P

D = json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_cloud.json')))
RES, EXT = P.RES, P.EXT
H, W = int(round((EXT[3] - EXT[1]) / RES)), int(round((EXT[2] - EXT[0]) / RES))


def raster(part):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [wg.to_px(part['outer'], RES, EXT).astype(np.int32)], 255)
    for h in part['holes']:
        cv2.fillPoly(m, [wg.to_px(h, RES, EXT).astype(np.int32)], 0)
    return m


def main():
    M = raster(D['shell'][0])
    bw = P.ink()
    ref = P.fill_label_circles(P.component(bw, (-60, -20)))
    ref = P.offset(cv2.morphologyEx(ref, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)), P.LINE_COMP)
    ref[P.offset(P.component(bw, (-15, -55)), P.LINE_COMP) > 0] = 0
    iou = ((M > 0) & (ref > 0)).sum() / ((M > 0) | (ref > 0)).sum()
    # 与 02 图的边缘偏差
    def edist(a, b):
        ea = cv2.Canny(a, 50, 150); eb = cv2.Canny(b, 50, 150)
        dt = cv2.distanceTransform(255 - eb, cv2.DIST_L2, 5)
        return dt[ea > 0] * RES
    d02 = edist(M, ref)
    # 与卫星屋面边缘：只取外轮廓
    s = wg.warp('sat', res=RES, extent=EXT, border=0)
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)
    roof = ((hsv[..., 1] < 45) & (hsv[..., 2] > 140)).astype(np.uint8) * 255
    roof = cv2.morphologyEx(roof, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    es = cv2.Canny(roof, 50, 150)
    dts = cv2.distanceTransform(255 - es, cv2.DIST_L2, 5)
    out = np.zeros((H, W), np.uint8)
    cv2.polylines(out, [wg.to_px(D['shell'][0]['outer'], RES, EXT).astype(np.int32)], True, 255, 1)
    dsat = dts[out > 0] * RES
    R = dict(iou_vs_02=round(float(iou), 4),
             edge_vs_02=dict(median=round(float(np.median(d02)), 2), max=round(float(d02.max()), 2)),
             outer_vs_sat=dict(median=round(float(np.median(dsat)), 2), p90=round(float(np.percentile(dsat, 90)), 2),
                               max=round(float(dsat.max()), 2)))
    print(json.dumps(R, ensure_ascii=False))
    json.dump(R, open(os.path.join(wg.ROOT, 'data', '_p2_cloud_gate.json'), 'w'), ensure_ascii=False, indent=1)
    # 卫星外缘偏差大于 1.5 m 的位置
    ys, xs = np.where((out > 0) & (dts * RES > 1.5))
    if len(xs):
        w = wg.to_world(np.c_[xs, ys], RES, EXT)
        print('>1.5 m 点数', len(xs), '范围', w.min(0).round(1).tolist(), w.max(0).round(1).tolist())


if __name__ == '__main__':
    main()
