"""P2 体育及艺术中心门槛：外轮廓对 02（IoU、边缘）与对卫星屋面边缘。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_sports as PS, p2_fit as F

RES, EXT = PS.RES, PS.EXT
D = json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_sports.json')))


def main():
    ref = PS.mask(); H, W = ref.shape
    M = np.zeros((H, W), np.uint8)
    poly = wg.to_px(D['outer'], RES, EXT).astype(np.int32)
    cv2.fillPoly(M, [poly], 255)
    iou = ((M > 0) & (ref > 0)).sum() / ((M > 0) | (ref > 0)).sum()
    d02 = cv2.distanceTransform(255 - cv2.Canny(ref, 50, 150), cv2.DIST_L2, 5)[cv2.Canny(M, 50, 150) > 0] * RES
    _, _, dts = F.roof_edges(EXT, RES)
    ol = np.zeros((H, W), np.uint8); cv2.polylines(ol, [poly], True, 255, 1)
    ds = dts[ol > 0] * RES
    w = wg.to_world(np.c_[np.where(ol > 0)[::-1]], RES, EXT)
    R = dict(iou_vs_02=round(float(iou), 4), edge_vs_02=dict(median=round(float(np.median(d02)), 2), max=round(float(d02.max()), 2)),
             outer_vs_sat=dict(median=round(float(np.median(ds)), 2), p90=round(float(np.percentile(ds, 90)), 2), max=round(float(ds.max()), 2)))
    print(json.dumps(R, ensure_ascii=False))
    bad = w[ds > 1.5]
    print('>1.5 m', len(bad), 'of', len(ds))
    # 按 20 m 网格统计超限点
    if len(bad):
        k, cnt = np.unique((bad // 20 * 20).astype(int), axis=0, return_counts=True)
        print(sorted(zip(cnt.tolist(), k.tolist()), reverse=True)[:8])
    json.dump(R, open(os.path.join(wg.ROOT, 'data', '_p2_sports_gate.json'), 'w'), ensure_ascii=False, indent=1)
    vis = wg.warp('sat', res=RES, extent=EXT, border=0)
    cv2.polylines(vis, [poly], True, (0, 0, 255), 2)
    for x, y in wg.to_px(bad, RES, EXT).astype(int):
        cv2.circle(vis, (x, y), 2, (0, 255, 255), -1)
    cv2.imwrite(os.path.join(wg.ROOT, 'checks', 'p2_sports_outline.jpg'), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == '__main__':
    main()
