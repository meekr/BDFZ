"""P1：从 03 总平面线稿描出室外/室内球场，写入 src/data/courts.json。

方法：03 上图场是带边线的矩形（外圈缓冲区 + 内圈场地线），
用轮廓 + minAreaRect 找 150–900 m²、长宽比 1.4–3.2 的矩形，
再按世界坐标归类：

  - 田径场东北侧沿斜向排列的 5 块小球场（≈17.5 × 10.6 m，图面 −55°）
  - 操场西侧篮球场（≈30.6 × 18.1 m，图面 160°）
  - 体育中心西侧两片球场（同尺寸，位于建筑轮廓内 → 室内场）

用法：python3 scripts/trace_courts.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, load_sheet, read_json, write_json

ARM_INSIDE = ("sports",)  # 用于判断哪些球场落在建筑轮廓内


def load_sports_polygon():
    p = DATA / "buildings" / "sports.json"
    if not p.exists():
        return None
    return np.array(json_load(p)["outer"], np.float32)


def json_load(p):
    return read_json(p)


def detect(g, ppm, aff, win, amin, amax, armin, armax):
    sub = g[win[1]:win[3], win[0]:win[2]]
    d = (sub < 200).astype(np.uint8)
    d = cv2.morphologyEx(d, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(d, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < amin * ppm ** 2 or a > amax * ppm ** 2:
            continue
        (cx, cy), (w, h), ang = cv2.minAreaRect(c)
        if min(w, h) < 1e-6:
            continue
        ar = max(w, h) / min(w, h)
        if not (armin < ar < armax):
            continue
        wx = np.array([cx + win[0], cy + win[1], 1.0]) @ aff.T
        out.append({
            "center": [round(float(wx[0]), 1), round(float(wx[1]), 1)],
            "size": [round(max(w, h) / ppm, 1), round(min(w, h) / ppm, 1)],
            "rot_deg": round(-(ang % 180.0) if (ang % 180.0) < 90 else 180 - (ang % 180.0), 1),
            "area_m2": round(a / ppm ** 2, 1),
        })
    return out


def main() -> int:
    fr = read_json(DATA / "frames.json")
    ppm = fr["frames"]["03"]["px_per_m"]
    aff = np.array(fr["frames"]["03"]["affine"], dtype=np.float64)
    g = load_sheet("03")

    small = detect(g, ppm, aff, (2600, 800, 5400, 3300), 120, 220, 1.4, 2.2)
    full = detect(g, ppm, aff, (300, 300, 9600, 6700), 330, 650, 1.4, 2.2)

    polys = {}
    for key in ("cloud", "dorm", "sports"):
        f = DATA / "buildings" / f"{key}.json"
        if f.exists():
            polys[key] = np.array(read_json(f)["outer"], np.float32)

    def inside(key, x, z):
        poly = polys.get(key)
        if poly is None:
            return False
        return cv2.pointPolygonTest(poly, (float(x), float(z)), False) >= 0

    def dedup(items, min_dist=5.0):
        out = []
        for c in sorted(items, key=lambda t: -t["area_m2"]):
            if all(math.hypot(c["center"][0] - o["center"][0],
                              c["center"][1] - o["center"][1]) > min_dist for o in out):
                out.append(c)
        return out

    courts = []
    # 5 块斜向小球场：按 z 从小到大（自北向南）排序
    small.sort(key=lambda c: c["center"][1])
    for i, c in enumerate(small[:5], 1):
        courts.append({
            "id": f"small-{i}", "kind": "outdoor-small",
            "label": f"小球场 {i}",
            "center": c["center"], "size": c["size"], "rot_deg": c["rot_deg"],
            "level_m": 0.16, "source": "03 图 NE 斜向排列",
        })

    # 标准尺寸球场：剔除落在建筑轮廓内的（那些是庭院/中庭，不是球场），
    # 并把嵌套的"缓冲区 + 场地线"两个轮廓去重
    full = dedup([c for c in full
                  if abs(c["size"][0] - 30.6) < 3.0 and abs(c["size"][1] - 18.1) < 2.5
                  and not any(inside(k, *c["center"]) for k in ("cloud", "dorm", "sports"))])
    full.sort(key=lambda c: (c["center"][0], c["center"][1]))
    idx = 0
    for c in full:
        x, z = c["center"]
        idx += 1
        indoor = inside("sports", x, z)
        courts.append({
            "id": f"court-{idx}",
            "kind": "indoor-court" if indoor else "outdoor-court",
            "label": ("室内球场" if indoor else "室外球场") + f" {idx}",
            "center": [x, z], "size": c["size"], "rot_deg": c["rot_deg"],
            # 室内场：篮球馆在 +12.00 层；室外场在地面
            "level_m": 12.9 if indoor else 0.16,
            "source": "03 图",
        })

    out = {
        "source": "03 总平面线稿（scripts/trace_courts.py）",
        "px_per_m": round(ppm, 4),
        "note": "室外场铺在地面；落在体育中心轮廓内的记为室内场，抬到 +12.00 层，"
                "剖切时可见。旋转角为图面矩形长轴相对 x 轴的角度（顺时针为正）。",
        "count": len(courts),
        "courts": courts,
    }
    write_json(DATA / "courts.json", out)
    for c in courts:
        print(f"  {c['id']:9s} {c['kind']:13s} ({c['center'][0]:7.1f},{c['center'][1]:7.1f}) "
              f"{c['size'][0]:5.1f}×{c['size'][1]:4.1f} m  {c['rot_deg']:6.1f}°  y={c['level_m']}")
    print(f"共 {len(courts)} 块")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
