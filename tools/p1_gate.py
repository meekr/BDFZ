"""P1 门槛：道路边缘分段复测（卫星灰度半高宽），与 data/site.json 中的直线边缘比较。"""
import sys, os, json, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg

S = json.load(open(os.path.join(wg.ROOT, 'data', 'site.json')))
RES = 0.25


def grey(ext):
    img = wg.warp('sat', res=RES, extent=ext, border=0)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(float)
    return ((hsv[..., 1] < 50) & (hsv[..., 2] > 50) & (hsv[..., 2] < 190)).astype(float)


def nearest_run(coord, p, lo, hi, thr=0.5, gap=4):
    """取与模型区间重叠最多的灰度连续段，返回 (下缘, 上缘)。"""
    idx = np.where(p > thr)[0]
    if not len(idx):
        return None
    best = None
    for r in np.split(idx, np.where(np.diff(idx) > gap)[0] + 1):
        if len(r) < 8:
            continue
        a, b = sorted((coord[r[0]], coord[r[-1]]))
        ov = min(b, hi) - max(a, lo)
        if best is None or ov > best[0]:
            best = (ov, a, b)
    return None if best is None or best[0] <= 0 else best[1:]


def check(name, horizontal, lo, hi, span, excl=(), step=40):
    errs, seg = [], 0
    for a in np.arange(span[0], span[1] - step + 1, step):
        if any(a < e1 and a + step > e0 for e0, e1 in excl):
            continue
        if horizontal:
            ext = (a, lo - 6, a + step, hi + 6); m = grey(ext); p = m.mean(1)
            coord = ext[3] - (np.arange(len(p)) + 0.5) * RES
        else:
            ext = (lo - 6, a, hi + 6, a + step); m = grey(ext); p = m.mean(0)
            coord = ext[0] + (np.arange(len(p)) + 0.5) * RES
        e = nearest_run(coord, p, lo, hi)
        if e is None:
            continue
        seg += 1; errs += [abs(e[0] - lo), abs(e[1] - hi)]
    errs = np.array(errs)
    return dict(name=name, segments=seg, median=round(float(np.median(errs)), 2), max=round(float(errs.max()), 2))


def main():
    R = {r['name']: r for r in S['roads']}
    def band(n, axis):
        r = R[n]; c = r['centerline'][0][axis]; w = r['width'] / 2
        return c - w, c + w
    jx = [(-375, -330), (-110, -80), (15, 50)]   # 路口、斑马线
    jy = [(80, 180), (-280, -200), (-30, 0)]
    out = [
        check('南侧北幅', True, *band('南侧道路北幅', 1), (-320, 320), jx),
        check('南侧南幅', True, *band('南侧道路南幅', 1), (-320, 320), jx),
        check('北侧行车道', True, *R['北侧城市道路（成智路）']['carriageway_y'], (-320, 320), jx + [(-60, 20)]),
        check('西侧西幅', False, *band('西侧城市道路西幅', 0), (-200, 80), (), 40),
        check('西侧东幅', False, *band('西侧城市道路东幅', 0), (-200, 80), (), 40),
    ]
    for o in out:
        print('{name}: 段数 {segments}，中位 {median} m，最大 {max} m'.format(**o))
    json.dump(out, open(os.path.join(wg.ROOT, 'data', '_p1_gate.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
