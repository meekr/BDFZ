"""P2 宿舍门槛：外轮廓对 02（IoU、边缘偏差）与对卫星屋面边缘。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_dorm as PD, p2_fit as F

RES, EXT = PD.RES, PD.EXT
D = json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_dorm.json')))


def main():
    ref = PD.minus_cloud(PD.outer_mask())
    H, W = ref.shape
    M = np.zeros((H, W), np.uint8)
    cv2.fillPoly(M, [wg.to_px(D['shell'][0]['outer'], RES, EXT).astype(np.int32)], 255)
    iou = ((M > 0) & (ref > 0)).sum() / ((M > 0) | (ref > 0)).sum()
    em, er = cv2.Canny(M, 50, 150), cv2.Canny(ref, 50, 150)
    d02 = cv2.distanceTransform(255 - er, cv2.DIST_L2, 5)[em > 0] * RES
    _, _, dts = F.roof_edges(EXT, RES)
    ol = np.zeros((H, W), np.uint8)
    cv2.polylines(ol, [wg.to_px(D['shell'][0]['outer'], RES, EXT).astype(np.int32)], True, 255, 1)
    w = wg.to_world(np.c_[np.where(ol > 0)[::-1]], RES, EXT)
    dsat = dts[ol > 0] * RES
    main_part = w[:, 0] > 102          # 主体；连接体与学术中心相接的边不计
    ds = dsat[main_part]
    R = dict(iou_vs_02=round(float(iou), 4), edge_vs_02=dict(median=round(float(np.median(d02)), 2), max=round(float(d02.max()), 2)),
             outer_vs_sat=dict(median=round(float(np.median(ds)), 2), p90=round(float(np.percentile(ds, 90)), 2), max=round(float(ds.max()), 2)))
    print(json.dumps(R, ensure_ascii=False))
    bad = w[main_part][ds > 1.5]
    if len(bad):
        print('>1.5 m', len(bad), 'of', len(ds), 'y 范围', np.percentile(bad[:, 1], [0, 50, 100]).round(1).tolist())
    json.dump(R, open(os.path.join(wg.ROOT, 'data', '_p2_dorm_gate.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
