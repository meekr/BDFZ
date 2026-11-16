"""P1 描图：从 02 屋顶平面提取矢量数据（世界米）。

关键做法：02 上的建筑外轮廓是**粗实线**，内部房间线、网格、铺装都是细线。
对深色像素做"腐蚀 → 膨胀"只保留粗线，再从图幅外泛洪，
即可一次分出三栋建筑体量以及学术中心的中央庭院：

  绿灯  = 体育及艺术中心（L 形）
  蓝/黄 = 学术中心（外环 + 中央庭院）
  红    = 宿舍综合楼

输出：
  src/data/buildings/*.json      外轮廓、中央庭院、屋面开洞（世界米）
  src/data/track.json            400 m 跑道外缘参数
  reports/align/trace_overlay.png 描图叠回 02 的检查图

用法：python3 scripts/trace.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, REPORTS, load_sheet, read_json, write_json

TOL_M = 0.2
DARK_THR = 120
BUILDINGS = {
    # 名称 → 该建筑体量在屋面上所在的近似位置（高清像素；锚点允许落在线或空白上）
    "sports": {"name": "体育及艺术中心", "anchor": (1377, 2113)},
    "cloud": {"name": "学术中心（翔云）", "anchor": (2688, 1621)},
    "dorm": {"name": "宿舍综合楼", "anchor": (3754, 1576)},
}


def thick_strokes(gray):
    """只保留粗实线（建筑外轮廓）。"""
    dark = (gray < DARK_THR).astype(np.uint8)
    core = cv2.dilate(cv2.erode(dark, np.ones((3, 3), np.uint8)), np.ones((9, 9), np.uint8))
    thick = dark & core
    return cv2.morphologyEx(thick, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def enclosed(thick):
    """从图幅外泛洪，得到被粗线围住的区域。"""
    ff = thick.copy()
    k = np.zeros((thick.shape[0] + 2, thick.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    return ((ff != 2) & (~thick.astype(bool))).astype(np.uint8)


def fill_holes(m):
    m = (m > 0).astype(np.uint8)
    ff = m.copy()
    k = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    return ((ff == 0) | (m > 0)).astype(np.uint8)


def biggest_component(mask, min_area=0):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    best, area_ = 0, min_area
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > area_:
            best, area_ = i, st[i, cv2.CC_STAT_AREA]
    return (lab == best).astype(np.uint8) if best else np.zeros_like(mask)


def polygonize(mask, tol_px, min_area_px):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [cv2.approxPolyDP(c, tol_px, True).reshape(-1, 2).astype(np.float64)
            for c in cnts if cv2.contourArea(c) >= min_area_px]


def holes_of(mask, tol_px, min_area_px):
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return []
    out = []
    for c, h in zip(cnts, hier[0]):
        if h[3] == -1 or cv2.contourArea(c) < min_area_px:
            continue
        out.append(cv2.approxPolyDP(c, tol_px, True).reshape(-1, 2).astype(np.float64))
    return out


def area(pts):
    x, y = np.asarray(pts, dtype=np.float64)[:, 0], np.asarray(pts, dtype=np.float64)[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def px_to_world(pts, aff):
    pts = np.asarray(pts, dtype=np.float64)
    p = np.concatenate([pts, np.ones((len(pts), 1))], axis=1)
    return (p @ np.asarray(aff, dtype=np.float64).T)[:, :2]


def simplify_world(pts, tol_m=TOL_M):
    arr = np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.approxPolyDP(arr, tol_m, True).reshape(-1, 2).astype(np.float64)


def rp(pts, nd=3):
    return [[round(float(v), nd) for v in p] for p in np.asarray(pts)]


def bbox(pts):
    p = np.asarray(pts)
    return {"min": [round(float(v), 2) for v in p.min(0)],
            "max": [round(float(v), 2) for v in p.max(0)],
            "size": [round(float(v), 2) for v in (p.max(0) - p.min(0))]}


def obb(pts):
    r = cv2.minAreaRect(np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2))
    (cx, cy), (w, h), ang = r
    # 把角度归一化到长轴方向（-90…90），方便直接读"轴向"
    if w < h:
        w, h = h, w
        ang += 90.0
    while ang > 90:
        ang -= 180
    while ang <= -90:
        ang += 180
    return {"center": [round(cx, 2), round(cy, 2)], "length_m": round(w, 2),
            "width_m": round(h, 2), "long_axis_deg": round(ang, 2)}


def centroid(pts):
    p = np.asarray(pts, dtype=np.float64)
    x, y = p[:, 0], p[:, 1]
    a = 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
    if abs(a) < 1e-9:
        return [round(float(p.mean(0)[0]), 2), round(float(p.mean(0)[1]), 2)]
    cx = np.sum((x + np.roll(x, -1)) * (x * np.roll(y, -1) - np.roll(x, -1) * y)) / (6 * a)
    cy = np.sum((y + np.roll(y, -1)) * (x * np.roll(y, -1) - np.roll(x, -1) * y)) / (6 * a)
    return [round(float(cx), 2), round(float(cy), 2)]


def round_corners(pts, radius_m):
    """把折线角点做圆弧化：返回 (点列, 是否为弧段) 的混合描述。

    这里只输出"圆角半径建议"，实际网格生成用 polyShape(pts, r) 处理，
    所以数据里同时保留折线顶点与建议半径。
    """
    return radius_m


def build_geometry(g02, aff02, ppu02):
    """按粗轮廓分割建筑体量，并用"凸包归属"把屋面开洞归到各建筑。

    粗轮廓把屋面切成若干封闭空白块：建筑墙内的整片屋面板是最大的一块；
    中央庭院、采光天井、中庭是另外的独立空白块。它们共同组成一栋建筑的
    完整平面轮廓，因此：

      1. 三个最大的空白块 = 三栋建筑主体（按质心 x 排序：西→东 = 体育、
         学术、宿舍）；
      2. 某栋建筑的完整轮廓 = 该主体 ∪ 所有质心落在其凸包内的空白块，再填洞；
      3. 这些被并入的空白块就是该建筑的"洞口"（庭院 / 天井 / 中庭）。
    """
    thick = thick_strokes(g02)
    enc = enclosed(thick)
    n, lab, st, cn = cv2.connectedComponentsWithStats(enc, 8)
    tol_px = TOL_M * ppu02
    px_per_m2 = ppu02 ** 2

    blocks = [(i, float(st[i, cv2.CC_STAT_AREA])) for i in range(1, n)
              if st[i, cv2.CC_STAT_AREA] / px_per_m2 > 20.0]
    blocks.sort(key=lambda t: -t[1])
    if len(blocks) < 3:
        raise RuntimeError("封闭空白块不足 3 个，粗轮廓提取失败")
    mains = sorted(blocks[:3], key=lambda t: cn[t[0]][0])
    names_by_x = ["sports", "cloud", "dorm"]
    print(f"  封闭空白块 {len(blocks)} 个；三个主体：")
    for key, (i, a) in zip(names_by_x, mains):
        print(f"    {BUILDINGS[key]['name']}: {a / px_per_m2:.0f} m²，质心 "
              f"({cn[i][0]:.0f}, {cn[i][1]:.0f})")

    result = {}
    for key, (main_id, _) in zip(names_by_x, mains):
        main_mask = (lab == main_id).astype(np.uint8)
        cnts, _ = cv2.findContours(main_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        main_cnt = max(cnts, key=cv2.contourArea)
        hull = cv2.convexHull(main_cnt)
        hull32 = hull.astype(np.int32)

        members = [main_id]
        inner_blocks = []
        for j, a_px in blocks:
            if j == main_id:
                continue
            cx, cy = cn[j]
            if cv2.pointPolygonTest(hull32, (float(cx), float(cy)), False) < 0:
                continue
            members.append(j)
            inner_blocks.append((j, a_px))

        union = np.zeros_like(main_mask)
        for j in members:
            union[lab == j] = 1
        # 主体与庭院之间隔着粗轮廓线本身，先闭运算跨过线条再接成一体
        bridge_px = max(9, int(round(2.2 * ppu02 * TOL_M)) + 9)
        solid = cv2.morphologyEx(union, cv2.MORPH_CLOSE,
                                 np.ones((bridge_px, bridge_px), np.uint8))
        solid = fill_holes(solid)
        solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE,
                                 np.ones((bridge_px, bridge_px), np.uint8))
        solid = fill_holes(solid)

        outer = max((simplify_world(px_to_world(ap, aff02))
                     for ap in polygonize(solid, tol_px, 3000)), key=area)

        holes = []
        for j, a_px in sorted(inner_blocks, key=lambda t: -t[1]):
            sub = cv2.morphologyEx((lab == j).astype(np.uint8), cv2.MORPH_CLOSE,
                                   np.ones((5, 5), np.uint8))
            polys = [simplify_world(px_to_world(ap, aff02))
                     for ap in polygonize(sub, tol_px, 0.002 * sub.size)]
            if not polys:
                continue
            poly = max(polys, key=area)
            holes.append({
                "area_m2": round(area(poly), 1),
                "polygon": rp(poly),
                "centroid": centroid(poly),
            })
        holes.sort(key=lambda h: -h["area_m2"])

        result[key] = {
            "name": BUILDINGS[key]["name"],
            "source": "02 屋顶平面（粗轮廓 + 凸包归属的封闭空白块）",
            "outer": rp(outer),
            "outer_area_m2": round(area(outer), 1),
            "centroid": centroid(outer),
            "bbox": bbox(outer),
            "obb": obb(outer),
            "holes": holes,
            "corner_radius_m": 6.0,
        }

    # 补充：宿舍的采光天井/小庭院在 02 上用细线绘制，不被粗轮廓围成独立空白块，
    # 改从屋面浅灰填充的孔洞里取（孔洞内的空白 = 天井）。
    tone = ((g02 >= 198) & (g02 <= 246)).astype(np.uint8)
    tone = cv2.morphologyEx(tone, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    tone = biggest_component(tone, 100000)
    dorm_outer = np.asarray(result["dorm"]["outer"], dtype=np.float32)
    inv = np.linalg.inv(aff02)
    dorm_px = np.concatenate([dorm_outer.astype(np.float64),
                              np.ones((len(dorm_outer), 1))], 1) @ inv.T
    dorm_px = dorm_px[:, :2].astype(np.int32)
    for hp in holes_of(tone, tol_px, 120):
        c = hp.mean(axis=0)
        if cv2.pointPolygonTest(dorm_px.reshape(-1, 1, 2), (float(c[0]), float(c[1])), False) < 0:
            continue
        w = simplify_world(px_to_world(hp, aff02))
        a = area(w)
        if a < 25:
            continue
        result["dorm"]["holes"].append({
            "area_m2": round(a, 1), "polygon": rp(w), "centroid": centroid(w),
            "kind": "lightwell" if a <= 150 else "courtyard",
        })
    result["dorm"]["holes"].sort(key=lambda h: -h["area_m2"])

    cloud_holes = result["cloud"]["holes"]
    if cloud_holes:
        court = max(cloud_holes, key=lambda h: h["area_m2"])
        result["cloud"]["courtyard"] = court
        result["cloud"]["courtyard_role"] = "中央露天庭院（星形）"
    dorm_holes = result["dorm"]["holes"]
    result["dorm"]["courtyard_count"] = len([h for h in dorm_holes if h["area_m2"] > 150])
    result["dorm"]["lightwell_count"] = len([h for h in dorm_holes if 25 <= h["area_m2"] <= 150])

    return result


def track_data(g03, ppu03):
    """400 m 跑道：03 图上跑道的两条外缘平行边（70°）法向间距。"""
    sub = (g03 < 205).astype(np.uint8)
    lines = cv2.HoughLinesP(sub, 1, np.pi / 7200, threshold=150, minLineLength=600, maxLineGap=30)
    rhos = []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
            if not (69.0 < ang < 71.0):
                continue
            if math.hypot(x2 - x1, y2 - y1) < 600:
                continue
            th = math.radians(ang)
            rhos.append(-math.sin(th) * x1 + math.cos(th) * y1)
    if not rhos:
        return None
    rhos.sort()
    merged = []
    for r in rhos:
        if not merged or r - merged[-1] > 6:
            merged.append(r)
        else:
            merged[-1] = (merged[-1] + r) / 2
    return {
        "sheet": "03",
        "long_axis_angle_img_deg": 70.0,
        "outer_span_px": round(merged[-1] - merged[0], 1),
        "outer_span_m": round((merged[-1] - merged[0]) / ppu03, 2),
        "note": "03 图上跑道长边平行线（70°）的法向间距，含跑道外侧缓冲区，"
                "不是 400 m 标准跑道外缘的理论 177 m。",
    }


def draw_overlay(g02, frames, buildings):
    canvas = cv2.cvtColor(cv2.resize(g02, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA),
                          cv2.COLOR_GRAY2BGR)
    inv = np.linalg.inv(np.array(frames["frames"]["02"]["affine"], dtype=np.float64))
    colors = {"cloud": (0, 0, 215), "dorm": (0, 150, 0), "sports": (200, 90, 0)}
    for name, b in buildings.items():
        col = colors.get(name, (128, 0, 128))
        for poly, thick in [(b["outer"], 3)] + [(h["polygon"], 2) for h in b["holes"]]:
            p = np.asarray(poly, dtype=np.float64)
            p = np.concatenate([p, np.ones((len(p), 1))], axis=1) @ inv.T
            cv2.polylines(canvas, [(p[:, :2] * 0.5).astype(np.int32).reshape(-1, 1, 2)],
                          True, col, thick)
    REPORTS.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(REPORTS / "trace_overlay.png"), canvas)
    print("写入 reports/align/trace_overlay.png")


def main() -> int:
    frames = read_json(DATA / "frames.json")
    ppu02 = frames["scale"]["px_per_m_02_hires"]
    ppu03 = frames["scale"]["px_per_m_03_hires"]
    aff02 = np.array(frames["frames"]["02"]["affine"], dtype=np.float64)

    print("描图 02 屋顶平面 …")
    g02 = load_sheet("02")
    buildings = build_geometry(g02, aff02, ppu02)

    outdir = DATA / "buildings"
    outdir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for key, b in buildings.items():
        write_json(outdir / f"{key}.json", b)
        o = b["obb"]
        summary[key] = {
            "outer_area_m2": b["outer_area_m2"],
            "length_m": o["length_m"],
            "width_m": o["width_m"],
            "long_axis_deg": o["long_axis_deg"],
            "vertices": len(b["outer"]),
            "holes": len(b["holes"]),
            "largest_hole_m2": b["holes"][0]["area_m2"] if b["holes"] else 0,
        }
        print(f"  {b['name']}: 面积 {b['outer_area_m2']:.0f} m²  "
              f"外包 {b['bbox']['size']} m  长轴 {o['length_m']}×{o['width_m']} m @ "
              f"{o['long_axis_deg']}°  洞口 {len(b['holes'])}")

    tr = track_data(load_sheet("03"), ppu03)
    if tr:
        write_json(DATA / "track.json", tr)
        print(f"  跑道外缘法向间距 {tr['outer_span_m']} m")

    write_json(REPORTS / "trace_summary.json", {"scale": frames["scale"], "buildings": summary,
                                               "track": tr})
    draw_overlay(g02, frames, buildings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
