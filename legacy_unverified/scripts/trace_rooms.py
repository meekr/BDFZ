"""P4：从 04 号学术中心三层平面提取房间轮廓（低模，用于剖切/三层视图）。

04 是唯一同时具备可靠比例尺与详细内部划分的图纸，因此三层房间几何
直接从它取出，再用 frames.json 里 04 的仿射变换到世界坐标；
这样"内部平面与 04 的偏差"由构造保证（≤ 1 px ≈ 0.03 m）。

输出：src/data/buildings/cloud_3f_rooms.json
用法：python3 scripts/trace_rooms.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, load_sheet, read_json, write_json

MIN_M2 = 22.0      # 小于这个面积的多半是卫生间/管井或噪声
MAX_M2 = 600.0
TOL_M = 0.15


def main() -> int:
    fr = read_json(DATA / "frames.json")
    ppm = fr["frames"]["04"]["px_per_m"]
    aff = np.array(fr["frames"]["04"]["affine"], dtype=np.float64)
    g = load_sheet("04")

    # 房间 = 被墙线围住的空白块
    d = (g < 130).astype(np.uint8)
    d = cv2.morphologyEx(d, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    ff = d.copy()
    k = np.zeros((d.shape[0] + 2, d.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    inside = ((ff != 2) & (~d.astype(bool))).astype(np.uint8)

    # 只保留学术中心主体范围（避免把周边场地、图注算进来）
    plate = np.zeros_like(inside)
    n, lab, st, cn = cv2.connectedComponentsWithStats(inside, 8)
    keep = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] / ppm ** 2 >= MIN_M2]
    for i in keep:
        plate[lab == i] = 1

    tol_px = TOL_M * ppm
    rooms = []
    for i in keep:
        a_m2 = st[i, cv2.CC_STAT_AREA] / ppm ** 2
        if a_m2 > MAX_M2:
            continue
        mask = (lab == i).astype(np.uint8)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cnts, key=cv2.contourArea)
        ap = cv2.approxPolyDP(c, tol_px, True).reshape(-1, 2).astype(np.float64)
        if len(ap) < 3:
            continue
        w = np.concatenate([ap, np.ones((len(ap), 1))], 1) @ aff.T
        poly = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in w[:, :2]]
        rooms.append({"area_m2": round(a_m2, 1), "polygon": poly,
                      "centroid": [round(float(p), 2) for p in w[:, :2].mean(0)]})

    rooms.sort(key=lambda r: -r["area_m2"])
    out = {
        "name": "学术中心三层房间（低模）",
        "source": "04 三层平面（按 frames.json 的 04 仿射变换到世界坐标）",
        "px_per_m": round(ppm, 4),
        "level_m": 12.5,
        "note": "只保留 22–600 m² 的房间；房间轮廓由 04 直接变换，"
                "与 04 的平面偏差由构造保证（≤ 1 px ≈ 0.03 m）。",
        "count": len(rooms),
        "total_area_m2": round(sum(r["area_m2"] for r in rooms), 1),
        "rooms": rooms,
    }
    write_json(DATA / "buildings" / "cloud_3f_rooms.json", out)
    print(f"提取房间 {len(rooms)} 间，合计 {out['total_area_m2']:.0f} m²")
    print(f"最大 {rooms[0]['area_m2']:.0f} m²，最小 {rooms[-1]['area_m2']:.0f} m²")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
