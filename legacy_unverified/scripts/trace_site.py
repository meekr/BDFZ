"""P1：从 03/01 号图描出场地信息，写入 src/data/site.json。

内容：
  - 用地范围（由 03 图道路内缘反算，带西北切角）
  - 四条外围道路的中线（03 图上的长直线）
  - 出入口位置（01 彩色总平面上的入口标注换算到世界坐标）

用法：python3 scripts/trace_site.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, load_sheet, read_json, write_json

# 01 图上的入口标注（图幅像素，2500 px 宽的高清版）
#   北侧：主入口 MAIN ENTRANCE / 员工入口 PERSONNEL / 消防紧急出口 EAST ENTRANCE
#   南侧：开敞式人行入口 / 次入口 EVERYDAY / 消防紧急出口 FIRE EXIT
ENTRANCE_PX_01 = [
    ("north-main", "校主入口", 1328, 62),
    ("north-personnel", "员工入口", 626, 62),
    ("north-fire", "东北角消防紧急出口", 2274, 62),
    ("south-open", "开敞式人行入口", 610, 1130),
    ("south-everyday", "次入口", 1892, 1130),
    ("south-fire", "东南角消防紧急出口", 2075, 1130),
]


def road_lines(g, aff, ppm):
    d = (g < 190).astype(np.uint8)
    lines = cv2.HoughLinesP(d, 1, np.pi / 3600, threshold=400,
                            minLineLength=2500, maxLineGap=20)
    hor, ver = [], []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
        L = math.hypot(x2 - x1, y2 - y1)
        if ang < 2 or ang > 178:
            hor.append((L, (y1 + y2) / 2, x1, x2))
        elif 88 < ang < 92:
            ver.append((L, (x1 + x2) / 2, y1, y2))

    def wz(py):
        return float((np.array([0, py, 1.0]) @ aff.T)[1])

    def wx(px):
        return float((np.array([px, 0, 1.0]) @ aff.T)[0])

    h, v = [], []
    for L, y, x1, x2 in sorted(hor, reverse=True):
        z = wz(y)
        if any(abs(z - s["z"]) < 2 for s in h):
            continue
        h.append({"z": round(z, 2), "x0": round(wx(x1), 1), "x1": round(wx(x2), 1),
                  "length_px": int(L)})
        if len(h) >= 6:
            break
    for L, x, y1, y2 in sorted(ver, reverse=True):
        xx = wx(x)
        if any(abs(xx - s["x"]) < 2 for s in v):
            continue
        v.append({"x": round(xx, 2), "z0": round(min(wz(y1), wz(y2)), 1),
                  "z1": round(max(wz(y1), wz(y2)), 1), "length_px": int(L)})
        if len(v) >= 4:
            break
    return h, v


def main() -> int:
    fr = read_json(DATA / "frames.json")
    ppm03 = fr["frames"]["03"]["px_per_m"]
    aff03 = np.array(fr["frames"]["03"]["affine"], dtype=np.float64)
    aff01 = np.array(fr["frames"]["01"]["affine"], dtype=np.float64)
    g03 = load_sheet("03")

    hor, ver = road_lines(g03, aff03, ppm03)
    print("水平长线（世界 z）:", [s["z"] for s in hor])
    print("竖直长线（世界 x）:", [s["x"] for s in ver])

    # 用地范围：由三条主干道的内缘围合（03 图上最长的水平/竖直线）
    north = min(s["z"] for s in hor)
    # 南侧椰海大道由多条边线（绿化带）组成，用地红线取最内侧那条
    south = min(s["z"] for s in hor if 60 < s["z"] < 200)
    south_road_outer = max(s["z"] for s in hor if 60 < s["z"] < 200)
    west = min(s["x"] for s in ver)
    east = max(s["x"] for s in ver)
    W = round(east - west, 1)
    D = round(south - north, 1)
    cx = round((west + east) / 2, 1)
    cz = round((north + south) / 2, 1)
    print(f"用地范围：{W} × {D} m，中心 ({cx}, {cz})")

    chamfer = 42.0
    site_poly = [
        [round(west + chamfer, 1), round(north, 1)],
        [round(east, 1), round(north, 1)],
        [round(east, 1), round(south, 1)],
        [round(west, 1), round(south, 1)],
        [round(west, 1), round(north + chamfer, 1)],
    ]

    entrances = []
    for key, label, px, py in ENTRANCE_PX_01:
        w = np.array([px, py, 1.0]) @ aff01.T
        x = float(w[0])
        # 标注点落在道路外侧，按南北吸附到用地边界（北 −147 / 南 +104 附近）
        z = north if key.startswith("north") else south
        entrances.append({"id": key, "label": label,
                          "pos": [round(x, 1), round(float(z), 1)],
                          "label_pos": [round(x, 1), round(float(w[1]), 1)]})
        print(f"  {key:16s} {label:12s} 边界点 ({x:7.1f},{z:7.1f})")

    roads = [
        {"name": "成智路", "orient": "E-W", "z": round(north - 9, 1),
         "x0": round(west - 60, 1), "x1": round(east + 60, 1), "width_m": 18},
        {"name": "永椰路", "orient": "N-S", "x": round(west - 9, 1),
         "z0": round(north - 60, 1), "z1": round(south + 60, 1), "width_m": 18},
        {"name": "椰海大道", "orient": "E-W",
         "z": round((south + south_road_outer) / 2, 1),
         "x0": round(west - 60, 1), "x1": round(east + 60, 1), "width_m": 22},
    ]
    if ver:
        east_line = max(ver, key=lambda s: s["x"])
        roads.append({"name": "东侧市政路（名称待核）", "orient": "N-S", "x": east_line["x"],
                      "z0": east_line["z0"], "z1": east_line["z1"], "width_m": 16})

    out = {
        "source": "03 总平面线稿（用地/道路）＋ 01 彩色总平面（出入口）",
        "px_per_m": round(ppm03, 4),
        "note": "用地范围由三条主干道内缘围合，西北角切角 42 m（目视 03 图）；"
                "出入口位置由 01 图上的入口标注换算。",
        "bounds": {"west": west, "east": east, "north": north, "south": south,
                   "width_m": W, "depth_m": D, "center": [cx, cz]},
        "chamfer_m": chamfer,
        "site_polygon": site_poly,
        "gate_x": next(e["pos"][0] for e in entrances if e["id"] == "north-main"),
        "area_m2": round(W * D - chamfer * chamfer / 2, 0),
        "roads": roads,
        "entrances": entrances,
        "detected_lines": {"horizontal_z": hor, "vertical_x": ver},
    }
    write_json(DATA / "site.json", out)
    print(f"写入 src/data/site.json（用地 {W}×{D} m，入口 {len(entrances)} 处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
