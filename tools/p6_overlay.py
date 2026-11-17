"""P6 叠图：照片 + 匹配相机工作台渲染（checks/_renders/*.png）。
左：50% 半透明叠加；右：渲染轮廓（Canny）描红叠在照片上。→ checks/photo_match_<name>.jpg"""
import os, sys, json, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make(name, width=1600):
    D = json.load(open(os.path.join(ROOT, 'data', 'cameras.json')))['cameras'][name]
    ph = cv2.imread(os.path.join(ROOT, D['photo']))
    rd = cv2.imread(os.path.join(ROOT, 'checks', '_renders', f'{name}.png'), cv2.IMREAD_UNCHANGED)
    if rd.shape[2] == 4:
        a = rd[:, :, 3:4] / 255.0
        rd = (rd[:, :, :3] * a + ph * (1 - a)).astype(np.uint8)
    blend = cv2.addWeighted(ph, 0.5, rd, 0.5, 0)
    ed = cv2.Canny(cv2.cvtColor(rd, cv2.COLOR_BGR2GRAY), 30, 90)
    ed = cv2.dilate(ed, np.ones((2, 2), np.uint8))
    line = ph.copy(); line[ed > 0] = (0, 0, 255)
    s = width / 2 / ph.shape[1]
    out = np.hstack([cv2.resize(blend, None, fx=s, fy=s, interpolation=cv2.INTER_AREA),
                     cv2.resize(line, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)])
    cv2.putText(out, f'{name}  fit rms {D["fit_rms_px"]} px', (10, 28), 0, 0.8, (255, 255, 255), 2)
    p = os.path.join(ROOT, 'checks', f'photo_match_{name}.jpg')
    cv2.imwrite(p, out, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return p


if __name__ == '__main__':
    names = sys.argv[1:] or list(json.load(open(os.path.join(ROOT, 'data', 'cameras.json')))['cameras'])
    for n in names:
        print(make(n))
