"""P2 宿舍综合楼：外轮廓取 02（02_dorm 帧），庭院取 01 彩色总平面的绿色区域（同一单栋校正作用于 01）→ data/bldg_dorm.json。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as PC

RES = 0.15
EXT = (80, -195, 215, 80)
SEED = (141.6, -52.0)
LINE_COMP = 0.3
H3 = lambda m: np.vstack([np.array(m), [0, 0, 1]])


def ensure_01_dorm():
    p = os.path.join(wg.ROOT, 'data', 'frames.json'); FR = json.load(open(p))
    C = H3(FR['frames']['02_dorm']['px_to_world']) @ np.linalg.inv(H3(FR['frames']['02']['px_to_world']))
    T = C @ H3(FR['frames']['01']['px_to_world'])
    FR['frames']['01_dorm'] = dict(file=FR['frames']['01']['file'], px_to_world=T[:2].round(8).tolist(),
                                   px_per_m=round(1 / float(np.hypot(T[0, 0], T[1, 0])), 4),
                                   note='01 按 02_dorm 的单栋校正（仅宿舍）')
    json.dump(FR, open(p, 'w'), ensure_ascii=False, indent=1); wg.FR = FR


def outer_mask():
    d = cv2.cvtColor(wg.warp('02_dorm', res=RES, extent=EXT, interp=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    bw = cv2.dilate((d < 110).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    _, lab = cv2.connectedComponents(255 - bw, connectivity=4)
    p = wg.to_px([SEED], RES, EXT)[0].astype(int)
    m = (lab == lab[p[1], p[0]]).astype(np.uint8) * 255
    cs, _ = cv2.findContours(cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    full = np.zeros_like(m); cv2.drawContours(full, [max(cs, key=cv2.contourArea)], -1, 255, -1)
    return PC.offset(full, LINE_COMP)


def courtyards(outer):
    img = wg.warp('01_dorm', res=RES, extent=EXT, interp=cv2.INTER_LINEAR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    g = ((hsv[..., 0] > 30) & (hsv[..., 0] < 75) & (hsv[..., 1] > 40) & (hsv[..., 2] > 60)).astype(np.uint8) * 255
    g = cv2.morphologyEx(g, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    g = cv2.morphologyEx(g, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    g[cv2.erode(outer, np.ones((15, 15), np.uint8)) == 0] = 0
    return g


def minus_cloud(mask):
    """02 上宿舍西北角与学术中心相连，按学术中心外轮廓切开（各自单独建模）。"""
    C = json.load(open(os.path.join(wg.ROOT, 'data', 'bldg_cloud.json')))['shell'][0]['outer']
    m = np.zeros_like(mask)
    cv2.fillPoly(m, [wg.to_px(C, RES, EXT).astype(np.int32)], 255)
    mask[cv2.dilate(m, np.ones((3, 3), np.uint8)) > 0] = 0
    _, lab, st, _ = cv2.connectedComponentsWithStats(mask)
    return ((lab == 1 + int(np.argmax(st[1:, 4]))) * 255).astype(np.uint8)


def regularize(G):
    """小庭院（< 150 m²）取最小外接矩形；大庭院保留形状。"""
    out = np.zeros_like(G)
    cs, _ = cv2.findContours(G, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    for c in cs:
        a = cv2.contourArea(c) * RES * RES
        if a < 20:
            continue
        if a < 150:
            cv2.fillPoly(out, [cv2.boxPoints(cv2.minAreaRect(c)).astype(np.int32)], 255)
        else:
            cv2.fillPoly(out, [cv2.approxPolyDP(c, 0.6 / RES, True)], 255)
    return out


def main():
    ensure_01_dorm()
    O = minus_cloud(outer_mask()); G = regularize(courtyards(O))
    shell = O.copy(); shell[G > 0] = 0
    # 复用 p2_cloud 的多边形化（它使用 p2_cloud 的 RES/EXT，这里临时替换）
    PC.RES, PC.EXT = RES, EXT
    parts = PC.polys(shell, eps=0.15, min_area=20)
    sizes = sorted([round(cv2.contourArea(wg.to_px(h, RES, EXT).astype(np.float32)) * RES * RES) for h in parts[0]['holes']])
    print('parts', len(parts), 'holes', len(parts[0]['holes']), sizes)
    data = dict(name='宿舍综合楼', frame='02_dorm（外轮廓）、01_dorm（庭院）', line_comp_m=LINE_COMP, shell=parts,
                levels=dict(ground=-0.2, floors=5, floor_h=3.6, parapet=1.2,
                            note='01 标 5F、±0.00 = 42.80；层高 3.6 m 为推定（07 为透视剖面，无法量取）。'
                                 '资料称四个单元高度由北向南递减，照片未见明显差异，暂取等高，P6 照片校核'))
    json.dump(data, open(os.path.join(wg.ROOT, 'data', 'bldg_dorm.json'), 'w'), ensure_ascii=False, indent=1)
    vis = wg.warp('sat', res=RES, extent=EXT, border=0)
    for k, r in enumerate([parts[0]['outer']] + parts[0]['holes']):
        cv2.polylines(vis, [wg.to_px(r, RES, EXT).astype(np.int32)], True, (0, 0, 255) if k == 0 else (0, 255, 255), 2)
    cv2.imwrite(os.path.join(wg.ROOT, 'checks', 'p2_dorm_outline.jpg'), cv2.resize(vis, None, fx=0.5, fy=0.5), [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == '__main__':
    main()
