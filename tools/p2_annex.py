"""P2 学术中心周边低层体量：02 上未覆盖的四个独立块（东北楼梯块、西南长条、南侧两块）→ data/bldg_annex.json。
位置用全图重标定后的 02 帧；对卫星屋面边缘只做复核，不单独拟合（块小，屋顶为种植屋面，边缘检测不可靠）。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as PC

RES = 0.15
EXT = (-110, -160, 80, 20)
BLOCKS = {   # 名称: (种子点, 顶面 Z, 依据)
    # 02 上另有东北 (58,-4)、西南 (-75,-102) 两块：卫星为深色下沉区（阴影、树），判为下沉庭院，P5 建
    'S_East': ((44.1, -118.3), 5.0, 'wx_01：金属屋面，约一层，顶与学术中心南翼架空层地面 +5.00 齐'),
    'S_West': ((14.5, -130.8), 5.0, 'wx_01：金属屋面，约一层，顶与学术中心南翼架空层地面 +5.00 齐'),
}


def main():
    PC.RES, PC.EXT = RES, EXT
    d = cv2.cvtColor(wg.warp('02', res=RES, extent=EXT, interp=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    bw = cv2.dilate((d < 110).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    _, lab = cv2.connectedComponents(255 - bw, connectivity=4)
    out = {}
    for k, (seed, top, note) in BLOCKS.items():
        p = wg.to_px([seed], RES, EXT)[0].astype(int)
        m = (lab == lab[p[1], p[0]]).astype(np.uint8) * 255
        m = PC.offset(PC.fill_label_circles(m), 0.3)
        parts = PC.polys(m, eps=0.12, min_area=50)
        part = max(parts, key=lambda q: q['area'])
        out[k] = dict(outer=part['outer'], area=part['area'], top=top, note=note)
        print(k, len(part['outer']), part['area'])
    json.dump(dict(name='学术中心周边低层体量', frame='02', base_z=-6.0, blocks=out,
                   note='功能未定（02/03 图例编号与 01 不一一对应）；P6 照片确认'),
              open(os.path.join(wg.ROOT, 'data', 'bldg_annex.json'), 'w'), ensure_ascii=False, indent=1)
    # 复核：对卫星屋面/种植屋面边缘（灰度梯度）
    s = wg.warp('sat', res=RES, extent=EXT, border=0)
    ed = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY), (5, 5), 0), 30, 90)
    dt = cv2.distanceTransform(255 - ed, cv2.DIST_L2, 5) * RES
    vis = s.copy(); R = {}
    for k, b in out.items():
        poly = wg.to_px(b['outer'], RES, EXT).astype(np.int32)
        ol = np.zeros(dt.shape, np.uint8); cv2.polylines(ol, [poly], True, 255, 1)
        dd = dt[ol > 0]
        R[k] = dict(median=round(float(np.median(dd)), 2), p90=round(float(np.percentile(dd, 90)), 2))
        cv2.polylines(vis, [poly], True, (0, 0, 255), 2)
    print(json.dumps(R))
    json.dump(R, open(os.path.join(wg.ROOT, 'data', '_p2_annex_gate.json'), 'w'), indent=1)
    cv2.imwrite(os.path.join(wg.ROOT, 'checks', 'p2_annex_outline.jpg'), vis, [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == '__main__':
    main()
