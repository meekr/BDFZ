"""P7 门槛：网页预设视点截图（checks/_web/<id>.jpg，?clean&view=<id>，16:9）与同机位 Blender 渲染（renders/<id>.jpg）对比。
指标：网页边缘到 Blender 边缘的倒角距离（中位、p90，占画面宽度）；叠图 → checks/p7_web_vs_blender_<id>.jpg（红 = Blender 边缘）。"""
import os, json, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def edges(im):
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.5)
    return cv2.Canny(g, 40, 110)


def main():
    out = {}
    for v in json.load(open(os.path.join(ROOT, 'data', 'views.json')))['views']:
        w = cv2.imread(os.path.join(ROOT, 'checks', '_web', f"{v['id']}.jpg"))
        b = cv2.imread(os.path.join(ROOT, 'renders', f"{v['id']}.jpg"))
        if w is None or b is None:
            continue
        b = cv2.resize(b, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_AREA)
        ew, eb = edges(w), edges(b)
        dt = cv2.distanceTransform(255 - eb, cv2.DIST_L2, 5)
        d = dt[ew > 0]
        # 只统计双方都有的结构边缘：剔除 > 30 px 的（树形、阴影、纹理差异）
        dd = d[d < 30]
        out[v['id']] = dict(median_pct=round(float(np.median(dd)) / w.shape[1] * 100, 3),
                            p90_pct=round(float(np.percentile(dd, 90)) / w.shape[1] * 100, 3),
                            matched_frac=round(float(len(dd) / max(1, len(d))), 2))
        ov = cv2.addWeighted(w, 0.6, b, 0.4, 0)
        ov[cv2.dilate(eb, np.ones((2, 2), np.uint8)) > 0] = (0, 0, 255)
        s = 0.5
        im = np.hstack([cv2.resize(w, None, fx=s, fy=s), cv2.resize(ov, None, fx=s, fy=s)])
        cv2.putText(im, f"{v['id']}  web | web+blender edges (red)  median {out[v['id']]['median_pct']}% W", (10, 24), 0, 0.6, (0, 0, 0), 2)
        cv2.imwrite(os.path.join(ROOT, 'checks', f"p7_web_vs_blender_{v['id']}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump(out, open(os.path.join(ROOT, 'data', '_p7_web_gate.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
