"""P2 学术中心：从 02 屋顶平面（02_cloud 帧 = 对卫星屋面倒角拟合后的位置）提取轮廓 → data/bldg_cloud.json。

线宽补偿：白色区域经阈值+膨胀后比实际小约半个线宽，外扩 LINE_COMP 后再取轮廓。
"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg

RES = 0.15
EXT = (-130, -170, 90, 40)
LINE_COMP = 0.3          # m
GROUND_INSET = 2.5       # 架空层核心筒相对外轮廓内收（推定，P3 按照片定柱位）


def ink():
    d = cv2.cvtColor(wg.warp('02_cloud', res=RES, extent=EXT, interp=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return cv2.dilate((d < 110).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))


def component(bw, pt):
    n, lab = cv2.connectedComponents(255 - bw, connectivity=4)
    p = wg.to_px([pt], RES, EXT)[0].astype(int)
    return (lab == lab[p[1], p[0]]).astype(np.uint8) * 255


def fill_label_circles(mask):
    """图号圆圈在白色区域里留下圆形空洞，按圆度填回。"""
    cs, h = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    for i, c in enumerate(cs):
        if h[0][i][3] < 0:
            continue
        a, p = cv2.contourArea(c), cv2.arcLength(c, True)
        if p > 0 and 4 * np.pi * a / p ** 2 > 0.6 and a * RES * RES < 150:
            cv2.drawContours(mask, cs, i, 255, -1)
    return mask


def offset(mask, m):
    k = int(round(abs(m) / RES))
    if k == 0:
        return mask
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
    return cv2.dilate(mask, ker) if m > 0 else cv2.erode(mask, ker)


def polys(mask, eps=0.1, min_area=4.0):
    cs, h = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for i, c in enumerate(cs):
        if h[0][i][3] >= 0 or cv2.contourArea(c) * RES * RES < min_area:
            continue
        loops = [c]
        j = h[0][i][2]
        while j >= 0:
            if cv2.contourArea(cs[j]) * RES * RES >= min_area:
                loops.append(cs[j])
            j = h[0][j][0]
        rings = []
        for c2 in loops:
            ap = cv2.approxPolyDP(c2, eps / RES, True)[:, 0, :].astype(float)
            w = wg.to_world(ap + 0.0, RES, EXT)
            rings.append([[round(float(x), 2), round(float(y), 2)] for x, y in w])
        out.append(dict(outer=rings[0], holes=rings[1:], area=round(float(mask[mask > 0].size) * RES * RES, 1)))
    return out


def main():
    bw = ink()
    ring = fill_label_circles(component(bw, (-60, -20)))
    # 线宽补偿：外扩后再闭合内部的分隔细线
    shell = offset(cv2.morphologyEx(ring, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)), LINE_COMP)
    court = offset(component(bw, (-15, -55)), LINE_COMP)
    shell[court > 0] = 0
    core = offset(shell, -GROUND_INSET)
    S = polys(shell)
    C = polys(core)
    print('shell parts', len(S), [len(p['holes']) for p in S], [p['area'] for p in S])
    print('core parts', len(C), [len(p['holes']) for p in C])
    data = {
        'name': '学术中心',
        'frame': '02_cloud',
        'source': '02 屋顶平面（高清 03_roof_plan.jpg），按 frames.json 02_cloud 帧（对卫星屋面边缘倒角拟合）定位',
        'line_comp_m': LINE_COMP,
        'shell': S,
        'ground_core': {'inset_m': GROUND_INSET, 'note': '推定，P3 按照片定柱位', 'parts': C},
        'levels': {
            'note': '05 剖面：南翼 5/10/14.5/19，屋面 23.5；北翼 0/5/8/12.5，屋面 17，檐口 19。两翼之间在东、西两侧线性过渡（推定，P6 照片校核）',
            'south': [5.0, 10.0, 14.5, 19.0, 23.5],
            'north': [0.0, 5.0, 8.0, 12.5, 17.0],
            'eave': {'south': 23.5, 'north': 19.0},
            'ramp_y': [-55.0, -5.0],
            'ramp_axis_deg': -10.0,
            'ramp_u': [-55.0, -5.0],
        },
        'library': {
            'note': '05 剖面 ④：庭院南部单层，±0.00 至 +5.00，屋面即南侧台地标高。北界 y = −70 为推定',
            'clip_y_max': -70.0, 'z': [0.0, 5.0],
        },
    }
    json.dump(data, open(os.path.join(wg.ROOT, 'data', 'bldg_cloud.json'), 'w'), ensure_ascii=False, indent=1)
    vis = cv2.cvtColor(wg.warp('sat', res=RES, extent=EXT, border=0), cv2.COLOR_BGR2BGRA)[..., :3].copy()
    for p in S:
        for k, r in enumerate([p['outer']] + p['holes']):
            cv2.polylines(vis, [wg.to_px(r, RES, EXT).astype(np.int32)], True, (0, 0, 255) if k == 0 else (0, 255, 255), 2)
    for p in C:
        cv2.polylines(vis, [wg.to_px(p['outer'], RES, EXT).astype(np.int32)], True, (255, 0, 255), 1)
    cv2.imwrite(os.path.join(wg.ROOT, 'checks', 'p2_cloud_outline.jpg'), cv2.resize(vis, None, fx=0.5, fy=0.5), [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == '__main__':
    main()
