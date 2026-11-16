"""计算模型正交顶视剪影与 02 屋顶平面的偏差（计划 5.4）。

输入：
  reports/align/model_top.png             check_align.mjs 产出的平色剪影
  reports/align/ref_02_in_model_frame.png 02 图纸在模型画幅下的参考图（可选，本脚本自建）

输出：
  reports/align/metrics.json   每个建筑的中位/最大偏差、IoU
  reports/align/metrics.md     可读报告

判定：中位偏差 ≤ 0.5 m，最大 ≤ 1.5 m，IoU ≥ 0.97（计划 5.4）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, REPORTS, load_sheet, read_json

W, H = 2000, 1414


def world_window():
    fr = read_json(DATA / "frames.json")
    a = np.array(fr["frames"]["02"]["affine"], dtype=np.float64)
    w, h = fr["frames"]["02"]["size"]
    pts = np.array([[0, 0], [w, 0], [0, h], [w, h]], dtype=np.float64)
    ws = np.concatenate([pts, np.ones((4, 1))], 1) @ a.T
    return (ws[:, 0].min(), ws[:, 0].max(), ws[:, 1].min(), ws[:, 1].max(), fr)


def reference_frame(win):
    x0, x1, z0, z1, fr = win
    g02 = load_sheet("02")
    inv = np.linalg.inv(np.array(fr["frames"]["02"]["affine"], dtype=np.float64))
    us = np.arange(W)
    vs = np.arange(H)
    wx = x0 + (us + 0.5) / W * (x1 - x0)
    wz = z0 + (vs + 0.5) / H * (z1 - z0)
    WX, WZ = np.meshgrid(wx, wz)
    P = np.stack([WX, WZ, np.ones_like(WX)], -1).reshape(-1, 3)
    Q = P @ inv.T
    mapx = Q[:, 0].reshape(H, W).astype(np.float32)
    mapy = Q[:, 1].reshape(H, W).astype(np.float32)
    return cv2.remap(g02, mapx, mapy, cv2.INTER_LINEAR, borderValue=255)


def building_mask_from_polygons(win, kind):
    """用描图多边形栅格化出参考剪影（作为模型目标的真值）。"""
    x0, x1, z0, z1, _ = win
    d = json.loads((DATA / "buildings" / f"{kind}.json").read_text(encoding="utf-8"))
    mask = np.zeros((H, W), np.uint8)

    def to_px(p):
        return (int(round((p[0] - x0) / (x1 - x0) * W)), int(round((p[1] - z0) / (z1 - z0) * H)))

    outer = np.array([to_px(p) for p in d["outer"]], np.int32)
    cv2.fillPoly(mask, [outer], 255)
    for h in d.get("holes", []):
        hp = np.array([to_px(p) for p in h["polygon"]], np.int32)
        cv2.fillPoly(mask, [hp], 0)
    return mask > 0


def model_mask(png):
    img = cv2.imread(str(png))
    if img is None:
        raise FileNotFoundError(png)
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    # 平色材质 = #222222（不受光照），近似取所有暗像素
    return (b < 90) & (g < 90) & (r < 90)


def metrics_for(model, ref, px_per_m):
    inter = np.logical_and(model, ref).sum()
    union = np.logical_or(model, ref).sum()
    iou = float(inter) / float(union) if union else 0.0
    # 双向最近距离（用距离变换）
    dt_ref = cv2.distanceTransform((~ref).astype(np.uint8), cv2.DIST_L2, 5)
    dt_mod = cv2.distanceTransform((~model).astype(np.uint8), cv2.DIST_L2, 5)
    d1 = dt_ref[model]
    d2 = dt_mod[ref]
    d = np.concatenate([d1, d2]) / px_per_m
    if d.size == 0:
        return {"iou": iou, "median_m": None, "p95_m": None, "max_m": None}
    # 多出/缺失分开计：模型是"含挑檐与腰线带"的实体，参考是"墙面轮廓"，
    # 因此多出量≈出挑面积、缺失量≈0 —— 这是 IoU 达不到 0.97 的物理原因。
    excess = float(np.logical_and(model, ~ref).sum()) / (px_per_m ** 2)
    deficit = float(np.logical_and(ref, ~model).sum()) / (px_per_m ** 2)
    return {
        "iou": round(iou, 4),
        "median_m": round(float(np.median(d)), 3),
        "p95_m": round(float(np.percentile(d, 95)), 3),
        "max_m": round(float(d.max()), 3),
        "excess_m2": round(excess, 1),
        "deficit_m2": round(deficit, 1),
    }


def threef_check(win):
    """学术中心三层（计划 5.4 第 3 条）：模型 3F 轮廓/内院 ↔ 04 三层平面（变换后）。"""
    x0, x1, z0, z1, fr = win
    f04 = fr["frames"].get("04") or {}
    plate_poly = f04.get("plate_polygon")
    court_poly = f04.get("courtyard_polygon")
    cloud_p = DATA / "buildings" / "cloud.json"
    if not plate_poly or not court_poly or not cloud_p.exists():
        return None
    cloud = json.loads(cloud_p.read_text(encoding="utf-8"))
    k = W / (x1 - x0)

    def poly_mask(pts):
        m = np.zeros((H, W), np.uint8)
        p = np.array([[ (x - x0) * k, (z - z0) * k] for x, z in pts], np.int32)
        cv2.fillPoly(m, [p], 1)
        return m

    def poly_from(mask):
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        return max(cnts, key=cv2.contourArea)

    def dist_stats(a, b):
        """a、b 两张掩膜的双向最近距离（米）。"""
        ca, cb = poly_from(a), poly_from(b)
        if ca is None or cb is None:
            return None
        da = cv2.distanceTransform(1 - b, cv2.DIST_L2, 5)
        db = cv2.distanceTransform(1 - a, cv2.DIST_L2, 5)
        pa = ca.reshape(-1, 2)
        pb = cb.reshape(-1, 2)
        da_vals = np.array([da[y, x] for x, y in pa])
        db_vals = np.array([db[y, x] for x, y in pb])
        # 距离变换是按像素计，中心化后每个像素约 1 px
        d = np.concatenate([da_vals, db_vals]) / k
        inter = float((a & b).sum())
        union = float((a | b).sum())
        return {
            "median_m": round(float(np.median(d)), 3),
            "p95_m": round(float(np.percentile(d, 95)), 3),
            "max_m": round(float(d.max()), 3),
            "iou": round(inter / union, 4) if union else None,
        }

    # 模型 3F：外环减内院
    outer = poly_mask(cloud["outer"])
    hole = poly_mask(cloud["courtyard"]["polygon"]) if cloud.get("courtyard") else np.zeros_like(outer)
    model_plate = (outer & (1 - hole))
    ref_plate = poly_mask(plate_poly)
    model_court = hole
    ref_court = poly_mask(court_poly)

    return {
        "plate": dist_stats(model_plate, ref_plate),
        "courtyard": dist_stats(model_court, ref_court),
        "note": "04 的楼板是「室内空白并集填洞」，其边界是外墙内表面；模型外环是外表面，"
                "因此外环会有一层墙厚的系统偏移（约 0.3–0.5 m）。内院比较不含此项。",
    }


def courts_check(win):
    """首层与场地（计划 5.4 第 2 条）：把"球场单独一层"的顶视渲染与 03 描图结果比对。

    走的是完整链路：courts.json → 几何 → 相机 → 像素 → 检测 → 与数据比对，
    因此能验到"摆位"而不只是"数据自洽"。
    """
    x0, x1, z0, z1, _ = win
    png = REPORTS / "model_courts_only.png"
    data_p = DATA / "courts.json"
    if not png.exists() or not data_p.exists():
        return None
    k = W / (x1 - x0)
    img = cv2.imread(str(png))
    mask = (img.min(axis=2) < 200).astype(np.uint8)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    drawn = []
    for c in cnts:
        if cv2.contourArea(c) < 800:
            continue
        (cx, cy), (w, h), ang = cv2.minAreaRect(c)
        drawn.append({
            "center": [round(cx / k + x0, 1), round(cy / k + z0, 1)],
            "size": [round(max(w, h) / k, 1), round(min(w, h) / k, 1)],
        })

    src = json.loads(data_p.read_text(encoding="utf-8"))
    expect = [c for c in src["courts"] if c["kind"].startswith("outdoor")]
    rows, dmax = [], 0.0
    for e in expect:
        if not drawn:
            break
        near = min(drawn, key=lambda d: (d["center"][0] - e["center"][0]) ** 2
                  + (d["center"][1] - e["center"][1]) ** 2)
        d = round(((near["center"][0] - e["center"][0]) ** 2
                   + (near["center"][1] - e["center"][1]) ** 2) ** 0.5, 2)
        dmax = max(dmax, d)
        rows.append({"id": e["id"], "expected": e["center"], "drawn": near["center"],
                     "size_expected": e["size"], "size_drawn": near["size"],
                     "offset_m": d})
    ok = [r for r in rows if r["offset_m"] <= 1.0]
    return {
        "count_expected": len(expect), "count_drawn": len(drawn),
        "matched": rows, "median_offset_m": round(float(np.median(
            [r["offset_m"] for r in rows])), 2) if rows else None,
        "max_offset_m": round(dmax, 2) if rows else None,
        "within_1m": len(ok),
    }


def section_check():
    """P2/P3：模型楼层标高 ↔ 05 剖面图上实测的长横线（竖向偏差）。"""
    path = DATA / "levels.json"
    if not path.exists():
        return None
    fr = read_json(DATA / "frames.json")
    f05 = fr["frames"].get("05")
    if not f05:
        return None
    vert = f05["vertical"]
    ppm = vert["px_per_m"]
    y0 = vert["y0_px"]

    g = load_sheet("05")
    # 只取剖面内容所在的纵向区间，找长度 > 800 px 的水平线（楼层线/屋面线/地面线）
    rows = []
    x0, x1 = 2588, 6718          # 剖面内容横向范围（图纸像素）
    for y in range(2100, 3400):
        row = (g[y, x0:x1] < 200)
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        starts = np.where(d == 1)[0]
        ends = np.where(d == -1)[0] - 1
        total = int(row.sum())
        longest = max((int(b - a) for a, b in zip(starts, ends)), default=0)
        # 楼板/屋面线可能被剖切填充打断，因此同时看"总长度"
        if longest > 800 or total > 1400:
            rows.append((y, max(longest, total)))

    # 相邻行聚类（同一条线可能占 2–4 px）
    lines = []
    for y, ln in rows:
        if lines and y - lines[-1]["y"] <= 3:
            lines[-1]["y"] = y
            lines[-1]["len"] = max(lines[-1]["len"], ln)
        else:
            lines.append({"y": y, "len": ln})
    elevs = [round((y0 - l["y"]) / ppm, 2) for l in lines]

    lv = json.loads(path.read_text(encoding="utf-8"))
    targets = []

    def add(name, v):
        if isinstance(v, (int, float)):
            targets.append((name, float(v)))

    # 05 只剖学术中心（南北向），因此只核学术中心的标高；体育/艺术/宿舍不在该剖切线上
    for wing, d in (lv.get("cloud") or {}).items():
        if isinstance(d, dict):
            for k, v in d.items():
                if k.startswith("height"):   # 合成量（净高），不是图上线
                    continue
                add(f"cloud.{wing}.{k}", v)

    matched = []
    for name, e in targets:
        if not elevs:
            break
        nearest = min(elevs, key=lambda t: abs(t - e))
        matched.append({"name": name, "target_m": e, "drawn_m": nearest,
                        "residual_m": round(abs(nearest - e), 3)})

    used = [m for m in matched if m["residual_m"] <= 2.0]
    # 楼层线（ground/floor）与屋面线分开统计：屋面楼板有厚度，
    # 图上同时存在板底与板顶两条线，取最近线会出现 0.5–0.9 m 的"表观偏差"。
    floor_like = [m for m in used if ("roof" not in m["name"] and "parapet" not in m["name"])]
    roof_like = [m for m in used if m not in floor_like]
    res = [m["residual_m"] for m in used]
    return {
        "px_per_m": round(ppm, 3),
        "y0_px": y0,
        "drawn_elevations_m": elevs,
        "matched": matched,
        "median_residual_m": round(float(np.median(res)), 3) if res else None,
        "max_residual_m": round(float(np.max(res)), 3) if res else None,
        "matched_count": len(used),
        "target_count": len(matched),
        "floor_median_m": round(float(np.median([m["residual_m"] for m in floor_like])), 3) if floor_like else None,
        "floor_max_m": round(max(m["residual_m"] for m in floor_like), 3) if floor_like else None,
        "roof_median_m": round(float(np.median([m["residual_m"] for m in roof_like])), 3) if roof_like else None,
        "roof_max_m": round(max(m["residual_m"] for m in roof_like), 3) if roof_like else None,
    }


def interior_check(px_per_m):
    """P4：室内场馆是否落在 03 描出的大厅内，以及余量（米）。"""
    path = DATA / "interiors.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for key in ("pool", "gym", "theater"):
        v = d.get(key)
        if not v:
            continue
        hall, size = v["hall"], v["size"]
        out[key] = {
            "hall_m": hall["size"],
            "venue_m": size,
            "margin_m": [round(hall["size"][0] - size[0], 2),
                         round(hall["size"][1] - size[1], 2)],
            "center": hall["center"],
            "rot_deg": hall["rot_deg"],
            "fits": all(hall["size"][i] >= size[i] for i in (0, 1)),
        }
    return out


def main() -> int:
    win = world_window()
    x0, x1, z0, z1, fr = win
    px_per_m = W / (x1 - x0)
    png = REPORTS / "model_top.png"
    model = model_mask(png)
    ref_img = reference_frame(win)
    cv2.imwrite(str(REPORTS / "ref_02_in_model_frame.png"), ref_img)

    # 参考剪影：用描图多边形（与 02 图纸逐点比对过）
    out = {}
    for kind in ("cloud", "dorm", "sports"):
        per = REPORTS / f"model_{kind}.png"
        mmod = model_mask(per) if per.exists() else model
        ref = building_mask_from_polygons(win, kind)
        m = metrics_for(mmod, ref, px_per_m)
        out[kind] = m
        print(f"{kind}: IoU {m['iou']}  中位 {m['median_m']} m  P95 {m['p95_m']} m  最大 {m['max_m']} m")

    # 全校区（三栋合并）
    ref_all = np.zeros((H, W), bool)
    for kind in ("cloud", "dorm", "sports"):
        ref_all |= building_mask_from_polygons(win, kind)
    all_m = metrics_for(model, ref_all, px_per_m)
    out["all"] = all_m
    print(f"三栋合计: IoU {all_m['iou']}  中位 {all_m['median_m']} m  "
          f"P95 {all_m['p95_m']} m  最大 {all_m['max_m']} m")

    # 叠加图
    vis = cv2.cvtColor(ref_img, cv2.COLOR_GRAY2BGR)
    vis[model] = (0, 0, 255) if False else vis[model]
    overlay = vis.copy()
    overlay[ref_all & ~model] = (0, 180, 0)
    overlay[model & ~ref_all] = (0, 0, 220)
    overlay[model & ref_all] = (180, 120, 0)
    cv2.imwrite(str(REPORTS / "metrics_overlay.png"), overlay)

    threef = threef_check(win)
    if threef:
        print("学术中心三层（对照 04）：")
        for key, cn in (("plate", "外环"), ("courtyard", "内院")):
            st = threef[key]
            if st:
                print(f"  {cn}: 中位 {st['median_m']} m  P95 {st['p95_m']} m  "
                      f"最大 {st['max_m']} m  IoU {st['iou']}")

    courts = courts_check(win)
    if courts:
        print("球场摆位（首层与场地）：")
        for m in courts["matched"]:
            print(f"  {m['id']:9s} 数据 ({m['expected'][0]:7.1f},{m['expected'][1]:7.1f})  "
                  f"渲染 ({m['drawn'][0]:7.1f},{m['drawn'][1]:7.1f})  偏 {m['offset_m']:5.2f} m")
        print(f"  渲染到 {courts['count_drawn']} 块、数据 {courts['count_expected']} 块；"
              f"中位 {courts['median_offset_m']} m，最大 {courts['max_offset_m']} m，"
              f"≤1 m 的 {courts['within_1m']}/{courts['count_expected']}")

    section = section_check()
    if section:
        print("剖面（05）竖向核对：")
        for m in section["matched"]:
            flag = "" if m["residual_m"] <= 0.5 else ("  ← 超差" if m["residual_m"] > 2.0 else "")
            print(f"  {m['name']:28s} 目标 {m['target_m']:6.2f}  图上 {m['drawn_m']:6.2f}  "
                  f"差 {m['residual_m']:5.2f} m{flag}")
        print(f"  命中 {section['matched_count']}/{section['target_count']}，"
              f"中位 {section['median_residual_m']} m，最大 {section['max_residual_m']} m")

    interior = interior_check(px_per_m)
    if interior:
        print("室内场馆（P4）：")
        for k, v in interior.items():
            print(f"  {k}: 大厅 {v['hall_m']} ⊃ 场馆 {v['venue_m']}，余量 {v['margin_m']} m，"
                  f"朝向 {v['rot_deg']}°{'（贴合）' if v['fits'] else '（放不下）'}")

    report = {
        "generated": "2026-11-14",
        "window_world": {"x0": round(x0, 2), "x1": round(x1, 2), "z0": round(z0, 2), "z1": round(z1, 2)},
        "px_per_m_in_render": round(px_per_m, 3),
        "targets": {"median_le_m": 0.5, "max_le_m": 1.5, "iou_ge": 0.97},
        "buildings": out,
        "interiors": interior,
        "section": section,
        "courts": courts,
        "three_f": threef,
    }
    (REPORTS / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")

    lines = ["# 对齐偏差报告（模型正交顶视 ↔ 02 屋顶平面）", "",
             f"- 画幅：x {x0:.1f}…{x1:.1f} m，z {z0:.1f}…{z1:.1f} m，{px_per_m:.2f} px/m",
             f"- 通过标准：中位 ≤ 0.5 m，最大 ≤ 1.5 m，IoU ≥ 0.97", "",
             "| 建筑 | IoU | 中位 (m) | P95 (m) | 最大 (m) | 多出 (m²) | 缺失 (m²) | 判定 |",
             "|---|---|---|---|---|---|---|---|"]
    for k, m in out.items():
        ok = (m["iou"] >= 0.97 and (m["median_m"] or 9) <= 0.5 and (m["max_m"] or 9) <= 1.5)
        lines.append(f"| {k} | {m['iou']} | {m['median_m']} | {m['p95_m']} | {m['max_m']} | "
                     f"{m.get('excess_m2', '')} | {m.get('deficit_m2', '')} | "
                     f"{'通过' if ok else '未达'} |")
    lines += ["",
              "> 「多出」＝模型比图纸轮廓多出的面积（挑檐、腰线带、屋面格栅等实体出挑）；"
              "「缺失」＝图纸有而模型没有的面积。缺失接近 0 说明没有漏掉体量，"
              "IoU 上不去主要因为模型按实体建模、含出挑。", ""]
    if threef:
        lines += ["", "## 学术中心三层（对照 04，计划 5.4 第 3 条）", "",
                  "04 的三层平面按 `frames.json` 的仿射变换到世界坐标后，与模型的 3F 轮廓比对"
                  "（双向最近距离）。", "",
                  "| 部位 | 中位 (m) | P95 (m) | 最大 (m) | IoU |",
                  "|---|---|---|---|---|"]
        for key, cn in (("plate", "外环"), ("courtyard", "内院")):
            st = threef[key]
            if st:
                lines.append(f"| {cn} | {st['median_m']} | {st['p95_m']} | {st['max_m']} | {st['iou']} |")
        lines += ["", f"> {threef['note']}"]

    if courts:
        lines += ["", "## 球场摆位（首层与场地，计划 5.4 第 2 条）", "",
                  "把球场单独一层做正交顶视（`model_courts_only.png`），在像素上重新检出矩形，",
                  "再与 `courts.json` 的坐标比对 —— 走的是「数据 → 几何 → 相机 → 像素」完整链路。", "",
                  "| 球场 | 数据坐标 (m) | 渲染检出 (m) | 偏移 (m) |",
                  "|---|---|---|---|"]
        for m in courts["matched"]:
            lines.append(f"| {m['id']} | ({m['expected'][0]}, {m['expected'][1]}) | "
                         f"({m['drawn'][0]}, {m['drawn'][1]}) | {m['offset_m']} |")
        lines += ["", f"共 {courts['count_expected']} 块，渲染检出 {courts['count_drawn']} 块；"
                      f"中位 {courts['median_offset_m']} m，最大 {courts['max_offset_m']} m，"
                      f"≤1 m 的 {courts['within_1m']}/{courts['count_expected']}。"]

    if section:
        lines += ["", "## 剖面竖向核对（05，P2/P3）", "",
                  f"- 标定：±0.00 在第 {section['y0_px']} 行，{section['px_per_m']} px/m", "",
                  "| 部位 | 标高表 (m) | 05 图上实测 (m) | 差 (m) |",
                  "|---|---|---|---|"]
        for m in section["matched"]:
            lines.append(f"| {m['name']} | {m['target_m']:.2f} | {m['drawn_m']:.2f} | "
                         f"{m['residual_m']:.2f} |")
        lines += ["",
                  f"- 命中 {section['matched_count']}/{section['target_count']}",
                  f"- **楼层线**：中位 {section['floor_median_m']} m，最大 {section['floor_max_m']} m"
                  f"（计划 5.4 要求 ≤ 0.3 m）",
                  f"- 屋面/女儿墙：中位 {section['roof_median_m']} m，最大 {section['roof_max_m']} m"
                  " —— 屋面楼板有厚度，图上同时有板底与板顶两条线，此列为「最近线」表观偏差"]

    if interior:
        lines += ["", "## 室内场馆定位（P4）", "",
                  "场馆矩形由 03 首层大厅轮廓居中摆放，因此与 03 的偏差只剩\"居中\"这一项。", "",
                  "| 场馆 | 03 大厅 (m) | 场馆 (m) | 余量 (m) | 朝向 | 是否放得下 |",
                  "|---|---|---|---|---|---|"]
        for k, v in interior.items():
            lines.append(f"| {k} | {v['hall_m'][0]} × {v['hall_m'][1]} | "
                         f"{v['venue_m'][0]} × {v['venue_m'][1]} | "
                         f"{v['margin_m'][0]} / {v['margin_m'][1]} | {v['rot_deg']}° | "
                         f"{'是' if v['fits'] else '否'} |")
    (REPORTS / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("写入 reports/align/metrics.json / metrics.md / metrics_overlay.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
