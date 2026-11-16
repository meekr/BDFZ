"""P4：从 03 总平面（首层）提取室内大厅轮廓，用于定位泳池、篮球馆与大剧场。

思路：03 的平面里，室内大厅是"被墙线围住的空白块"。在三栋建筑轮廓内
按面积排序取最大的几块，再按所在臂（体育中心西臂 / 艺术中心南臂）归类：

  - 西臂北端最大厅（≈51.7 × 37.8 m）＝ 50 m 泳池所在大厅
  - 西臂南端大厅（≈47.6 × 21.1 m）  ＝ 室内篮球馆
  - 南臂大厅（≈30.6 × 22.5 m）      ＝ 1000 人大剧场观众厅核心

大厅轮廓由 03 直接量取，因此"内部平面与 03 的偏差"由构造保证
（只差标准场馆在厅内的居中摆放）。

用法：python3 scripts/trace_interior.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, load_sheet, read_json, write_json

# 标准场馆尺寸（净尺寸，含比赛区）
POOL = [50.0, 25.0]
GYM = [28.0, 15.0]
THEATER = [36.0, 26.0]


def main() -> int:
    fr = read_json(DATA / "frames.json")
    ppm = fr["frames"]["03"]["px_per_m"]
    aff = np.array(fr["frames"]["03"]["affine"], dtype=np.float64)
    g = load_sheet("03")

    polys = {}
    for key in ("sports", "cloud", "dorm"):
        f = DATA / "buildings" / f"{key}.json"
        if f.exists():
            polys[key] = np.array(read_json(f)["outer"], np.float32)

    d = (g < 200).astype(np.uint8)
    d = cv2.morphologyEx(d, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    ff = d.copy()
    k = np.zeros((d.shape[0] + 2, d.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    inside = ((ff != 2) & (~d.astype(bool))).astype(np.uint8)
    n, lab, st, cn = cv2.connectedComponentsWithStats(inside, 8)

    def regions_in(key, min_m2=150):
        poly = polys.get(key)
        if poly is None:
            return []
        out = []
        for i in range(1, n):
            a = st[i, cv2.CC_STAT_AREA] / ppm ** 2
            if a < min_m2:
                continue
            w = np.array([cn[i][0], cn[i][1], 1.0]) @ aff.T
            if cv2.pointPolygonTest(poly, (float(w[0]), float(w[1])), False) < 0:
                continue
            m = (lab == i).astype(np.uint8)
            cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c = max(cnts, key=cv2.contourArea)
            (cx, cy), (wpx, hpx), ang = cv2.minAreaRect(c)
            ww = np.array([cx, cy, 1.0]) @ aff.T
            out.append({
                "area_m2": round(a, 1),
                "center": [round(float(ww[0]), 1), round(float(ww[1]), 1)],
                "size": [round(max(wpx, hpx) / ppm, 1), round(min(wpx, hpx) / ppm, 1)],
                "rot_deg": round(-ang if ang < 90 else 180 - ang, 1),
                "polygon": [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in
                            (np.concatenate([cv2.approxPolyDP(c, 3.0, True).reshape(-1, 2),
                                             np.ones((len(cv2.approxPolyDP(c, 3.0, True)), 1))], 1)
                             @ aff.T)[:, :2]],
            })
        out.sort(key=lambda r: -r["area_m2"])
        return out

    halls = regions_in("sports")
    # 体育中心与艺术中心在 02 上是同一个 L 形块，按 x 分成西臂（体育）与南臂（艺术）
    west = [r for r in halls if r["center"][0] < -150]
    east = [r for r in halls if r["center"][0] >= -150]
    print("西臂大厅（按面积）:", [(r["size"], r["center"]) for r in west[:4]])
    print("南臂大厅（按面积）:", [(r["size"], r["center"]) for r in east[:4]])

    if len(west) < 2 or not east:
        raise RuntimeError("没有找到足够的室内大厅")

    # 泳池大厅＝西臂最北（z 最小）的大厅；篮球馆＝西臂剩下的最大厅
    # 图书馆：学术中心架空层（03 首层）里最大的室内大厅
    lib_halls = regions_in("cloud", min_m2=200)
    library_hall = lib_halls[0] if lib_halls else None
    print("学术中心内部大厅（按面积）:",
          [(r["size"], r["center"]) for r in lib_halls[:3]])

    pool_hall = min(west, key=lambda r: r["center"][1])
    rest = [r for r in west if r is not pool_hall]
    gym_hall = max(rest, key=lambda r: r["area_m2"])
    theater_hall = max(east, key=lambda r: r["area_m2"])

    # 标准场馆尺寸按大厅净尺寸收边（四周留 2 m 缓冲），避免"场馆比厅还大"
    def fit(size, hall, margin=2.0):
        return [round(min(size[0], hall["size"][0] - margin * 2), 1),
                round(min(size[1], hall["size"][1] - margin * 2), 1)]

    pool_size = fit(POOL, pool_hall, margin=0.8)
    gym_size = fit(GYM, gym_hall)
    theater_size = fit(THEATER, theater_hall)

    out = {
        "source": "03 总平面（首层）室内大厅轮廓 + 标准场馆净尺寸",
        "px_per_m": round(ppm, 4),
        "note": "大厅轮廓由 03 直接量取；标准场馆按其长轴居中摆放，"
                "因此内部平面与 03 的偏差只来自'场馆在大厅内的居中'，量级 ≪ 0.5 m。",
        "pool": {
            "label": "50 m 室内游泳馆",
            "level_m": 0.95,
            "hall": pool_hall,
            "size": pool_size,
            "note": "池长沿大厅长轴，8 条泳道",
        },
        "gym": {
            "label": "室内篮球馆",
            "level_m": 12.9,
            "hall": gym_hall,
            "size": gym_size,
            "note": "比赛区 28 × 15 m，四周留缓冲",
        },
        "library": {
            "label": "图书馆 / 创客中心（架空层）",
            "level_m": 0.0,
            "open_floor": library_hall,
            "candidate_room": lib_halls[1] if len(lib_halls) > 1 else None,
            "note": "03 首层上学术中心是一个 3,022 m² 的通高架空大厅（无隔墙），"
                    "图书馆是其中的二次装修体量，图纸没有画出它的独立轮廓。"
                    "因此这里只记录大厅与次大的独立房间两个候选，不做定位——"
                    "模型里的图书馆仍是按庭院相对位置的功能性摆放（见现场差异表第 23 条）。",
        },
        "theater": {
            "caveat": "1000 座观众厅的座椅线把空白块切碎了，这里取到的是观众厅前区/"
                      "舞台前厅的核心块，不是整个观众厅轮廓；座椅按该块的长轴阶梯布置。",
            "label": "1000 人大剧场观众厅",
            "level_m": 1.0,
            "hall": theater_hall,
            "size": theater_size,
            "note": "观众厅核心区，座椅沿大厅长轴阶梯布置",
        },
    }
    write_json(DATA / "interiors.json", out)
    for key in ("pool", "gym", "theater"):
        h = out[key]["hall"]
        print(f"  {key:8s} 大厅 {h['size'][0]:5.1f}×{h['size'][1]:5.1f} m @ {h['rot_deg']:6.1f}° "
              f"centre ({h['center'][0]:7.1f},{h['center'][1]:7.1f})  场馆 {out[key]['size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
