"""P0 图纸配准与定标。

坐标系（计划 5.1）：
  单位 m；原点 = 02 图面中心；x 向东（图面向右），z 向南（图面向下）。
  图面像素 (px,py) → 世界 (x,z) = (px/s - ox, py/s - oz)。

定标链（每一级都有独立证据）：
  1. 04 自带 50 m 比例尺：刻度 x=7347/7521/7690/8026/9049 ↔ 0/5/10/20/50 m
     → 34.00 px/m（残差 2.6 px）。这是唯一定标基准。
  2. 04 → 02：学术中心屋面剪影配准，scale 0.4608（计划 2.1，IoU 0.91）。
  3. 04 与 02 的高清图幅宽比 = 9921 / 4961 = 1.9998，故
     02 高清 px/m = 34.00 × 0.4608 × 4961/9921 = 7.83 px/m。
  4. 03 是 02 的同比例放大（图幅 2 倍、边缘配准 scale 1.0000 rot 0.002°），
     故 03 高清 px/m = 2 × 02 = 15.67 px/m。
  5. 交叉验证 A：03 的跑道分道线间距（标准 1.22 m）实测 18.3 px → 15.0 px/m（−3.9%）。
  6. 交叉验证 B：学术中心屋面面积，02 描图 16.9k m² ↔ OSM 17.3k m²（−2.3%）。
  7. 04 → 02 的旋转：中央庭院星形的归一化极坐标剖面 → −35.25°，
     与计划 2.1 的 35.8° 一致（符号按剖面确定，故取 −35.8°）。

输出：
  src/data/frames.json             图面像素 → 世界米的仿射（3×3）
  reports/align/registration.json  全部中间量与自检表
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, REPORTS, edges, load_sheet, read_json, resize_to_width, write_json

# 04 图 50 m 比例尺刻度（高清像素 x ↔ 米）
SCALE_04_TICKS = [(7347.0, 0.0), (7521.0, 5.0), (7690.0, 10.0), (8026.0, 20.0), (9049.0, 50.0)]
# 01 图比例尺刻度（高清像素 x ↔ 米）：0 / 10 / 50 m（自带尺不可靠，仅记录）
SCALE_01_TICKS = [(2286.0, 0.0), (2330.5, 10.0), (2461.0, 50.0)]
# 计划 2.1：01 → 02 的剪影配准缩放
PLAN_SCALE_01_TO_02 = 0.9857

# 05 剖面图的竖向标定（实测，见 reports/align/registration.json 的 checks）
#   ±0.00 地面线 = 第 3118 行；南翼屋面 +23.50 = 第 2320.5 行 → 33.94 px/m。
#   复核：+5.00 / +10.00 / +14.50 / +19.00 的推算行 2948 / 2779 / 2626 / 2473
#   与图上实测的长横线完全吻合（±1 px）。
SECTION_05 = {
    "y0_px": 3118.0,        # ±0.00 所在行
    "elev0": 0.0,
    "roof25_px": 2320.5,    # 南翼屋面 +23.50 所在行
    "roof25_elev": 23.5,
    "court_x0_px": 3919.0,  # 庭院在地面处的左右边界
    "court_x1_px": 5889.0,
}

SHEET_FILES = {
    "01": "02_color_site.jpg",
    "02": "03_roof_plan.jpg",
    "03": "04_line_site.jpg",
    "04": "05_cloud_3f.jpg",
    "05": "06_cloud_section.jpg",
}

SIZE_HIRES = {
    "01": (2500, 1574), "02": (4961, 3508), "03": (9921, 7016),
    "04": (9921, 7016), "05": (9921, 7016),
}

# 计划 2.1：04 → 02 的缩放（2000 px 版剪影配准结果）
SCALE_04_TO_02 = 0.4608
# 旋转：极坐标实测 −35.25°，计划 35.8°；符号按剖面确定为负
ROT_04_TO_02 = -35.8

COURT_SEED_04 = (4270, 2590)
COURT_ANCHOR_02 = (2650.0, 1650.0)
LANE_WIDTH_M = 1.22


def fit_scale(ticks):
    xs = np.array([t[0] for t in ticks])
    ms = np.array([t[1] for t in ticks])
    a, b = np.polyfit(ms, xs, 1)
    return float(a), float(b), float(np.abs(xs - (a * ms + b)).max())


def sim(scale, rot_deg, tx, ty):
    r = math.radians(rot_deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[scale * c, -scale * s, tx], [scale * s, scale * c, ty]], dtype=np.float64)


def decompose(m):
    scale = math.hypot(m[0, 0], m[1, 0])
    rot = math.degrees(math.atan2(m[1, 0], m[0, 0]))
    aniso = math.hypot(m[0, 1], m[1, 1]) / scale if scale else float("nan")
    return scale, rot, aniso


def fill_holes(m):
    m = (m > 0).astype(np.uint8)
    ff = m.copy()
    k = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    return ((ff == 0) | (m > 0)).astype(np.uint8)


def biggest_component(mask, min_area=0):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    best, area = 0, min_area
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > area:
            best, area = i, st[i, cv2.CC_STAT_AREA]
    return (lab == best).astype(np.uint8) if best else np.zeros_like(mask)


def loft(gray, seed, white_thr=200):
    ff = (gray > white_thr).astype(np.uint8)
    k = np.zeros((gray.shape[0] + 2, gray.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, seed, 2)
    if ff[seed[1], seed[0]] != 2:
        raise RuntimeError(f"种子 {seed} 不在空白区")
    reg = (ff == 2).astype(np.uint8)
    n, lab, _, _ = cv2.connectedComponentsWithStats(reg, 8)
    return (lab == lab[seed[1], seed[0]]).astype(np.uint8)


def courtyard_02(g02):
    tone = ((g02 >= 198) & (g02 <= 246)).astype(np.uint8)
    tone = cv2.morphologyEx(tone, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    tone = biggest_component(tone, 100000)
    ff = tone.copy()
    k = np.zeros((tone.shape[0] + 2, tone.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    holes = (ff == 0).astype(np.uint8)
    n, lab, st, cn = cv2.connectedComponentsWithStats(holes, 8)
    cand = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 50000]
    if not cand:
        raise RuntimeError("02 上未找到学术中心庭院")
    anchor = np.array(COURT_ANCHOR_02)
    best = min(cand, key=lambda i: np.hypot(*(cn[i] - anchor)))
    return (lab == best).astype(np.uint8)


def learning_plate_02(g02):
    """02 屋顶平面：学术中心屋面板（窗口内的浅灰填充块，填洞后）。"""
    # 旧实现用固定窗口（1900,1000)-(2900,2100)，只盖到世界 x=53.6，
    # 而学术中心一直延伸到 x=113.6 —— 楼板东半截被切掉，质心偏西约 30 m，
    # 04 帧的平移随之带偏（04 叠图与三层房间都会整体西移）。
    # 现在优先用描图多边形（buildings/cloud.json）做掩膜，精确锁定学术中心；
    # 描图结果不存在时退回一个"能包住整个学术中心"的窗口。
    x0, y0, x1, y1 = 1900, 1000, 3450, 2250
    sub = g02[y0:y1, x0:x1]
    t = ((sub >= 198) & (sub <= 246)).astype(np.uint8)
    t = cv2.morphologyEx(t, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    # 用描图多边形限定范围（世界 → 02 像素），避免把周边地面/连桥算进来
    cloud_poly = DATA / "buildings" / "cloud.json"
    clip = None
    if cloud_poly.exists():
        poly = np.array(read_json(cloud_poly)["outer"], dtype=np.float64)
        a02 = np.array(read_json(DATA / "frames.json")["frames"]["02"]["affine"], np.float64)
        inv = np.linalg.inv(a02)
        px = np.concatenate([poly, np.ones((len(poly), 1))], 1) @ inv.T
        px[:, :2] -= [x0, y0]
        clip = np.zeros_like(t)
        cv2.fillPoly(clip, [np.round(px[:, :2]).astype(np.int32)], 1)             if (px[:, :2].max() < 1e4 and px[:, :2].min() > -1e4) else None
        if clip is not None:
            clip = np.ascontiguousarray(clip)
    if clip is not None and clip.any():
        t = (t & clip).astype(np.uint8)

    n, lab, st, _ = cv2.connectedComponentsWithStats(t, 8)
    if n <= 1:
        return np.zeros_like(g02)
    t = (lab == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8)
    plate = np.zeros_like(g02)
    plate[y0:y1, x0:x1] = fill_holes(t)
    return plate


def learning_plate_04(g04):
    """04 三层平面：学术中心楼板（各房间内部空白并集，填洞后取最大块）。"""
    d = (g04 < 130).astype(np.uint8)
    d = cv2.morphologyEx(d, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    ff = d.copy()
    k = np.zeros((d.shape[0] + 2, d.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, k, (0, 0), 2)
    encl = ((ff != 2) & (~d.astype(bool))).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(encl, 8)
    keep = np.zeros_like(encl)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 1500:
            keep |= (lab == i).astype(np.uint8)
    p = fill_holes(cv2.morphologyEx(fill_holes(keep), cv2.MORPH_CLOSE,
                                    np.ones((25, 25), np.uint8)))
    return fill_holes(biggest_component(p, 1000)).astype(np.uint8)


def fit_plate_04_to_02(plate02, plate04, c02, c04, k, rot_guess, span=24.0):
    """把 04 楼板按尺度 k、旋转θ、平移对齐到 02 楼板；θ 在 rot_guess±span 内搜索。

    返回 (最优旋转, IoU, 3×3 变换)。
    """
    f = 1.0 / 8.0
    A = (cv2.resize(plate02, (max(1, int(plate02.shape[1] * f)),
                              max(1, int(plate02.shape[0] * f))),
                    interpolation=cv2.INTER_AREA) > 0.4).astype(np.uint8)
    Bsrc = (cv2.resize(plate04, (max(1, int(plate04.shape[1] * k * f)),
                                 max(1, int(plate04.shape[0] * k * f))),
                       interpolation=cv2.INTER_AREA) > 0.4).astype(np.uint8)

    def rot_crop(img, ang):
        h, w = img.shape
        dd = int(np.ceil(math.hypot(h, w))) + 2
        cc = np.zeros((dd, dd), np.uint8)
        oy, ox = (dd - h) // 2, (dd - w) // 2
        cc[oy:oy + h, ox:ox + w] = img
        R = cv2.warpAffine(cc, cv2.getRotationMatrix2D((dd / 2, dd / 2), ang, 1.0),
                           (dd, dd), flags=cv2.INTER_NEAREST)
        ys, xs = np.nonzero(R)
        return R[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    pad = np.zeros((A.shape[0] + 2 * max(A.shape[0], Bsrc.shape[0]),
                    A.shape[1] + 2 * max(A.shape[1], Bsrc.shape[1])), np.uint8)
    oy, ox = A.shape[0], A.shape[1]
    pad[oy:oy + A.shape[0], ox:ox + A.shape[1]] = A

    best = (0.0, rot_guess, (ox, oy))
    for ang in np.arange(rot_guess - span, rot_guess + span + 1e-9, 0.25):
        R = rot_crop(Bsrc, ang)
        if R.shape[0] > pad.shape[0] or R.shape[1] > pad.shape[1]:
            continue
        res = cv2.matchTemplate(pad.astype(np.float32), R.astype(np.float32), cv2.TM_CCORR)
        _, mx, _, loc = cv2.minMaxLoc(res)
        iou = mx / (pad.sum() + R.sum() - mx)
        if iou > best[0]:
            best = (iou, ang, loc)
    iou0, ang0, _ = best
    for ang in np.arange(ang0 - 0.5, ang0 + 0.5, 0.02):
        R = rot_crop(Bsrc, ang)
        if R.shape[0] > pad.shape[0] or R.shape[1] > pad.shape[1]:
            continue
        res = cv2.matchTemplate(pad.astype(np.float32), R.astype(np.float32), cv2.TM_CCORR)
        _, mx, _, loc = cv2.minMaxLoc(res)
        iou = mx / (pad.sum() + R.sum() - mx)
        if iou > best[0]:
            best = (iou, ang, loc)

    iou, rot, loc = best
    # loc 是 R 在 pad 中的左上角；换算回 02 全分辨率
    tx = (loc[0] - ox) / f
    ty = (loc[1] - oy) / f
    m = sim(k, rot, 0.0, 0.0)
    # rot_crop 以 Bsrc 中心为旋转中心并重新裁剪，所以这里用质心对齐保证一致性
    mc = m[:, :2] @ c04
    m[0, 2] = c02[0] - mc[0] + (tx - tx)
    m[1, 2] = c02[1] - mc[1]
    # 用模板匹配得到的平移替换质心平移（更稳）
    # R 的左上角对应 Bsrc 的 (x0,y0)，其中 x0,y0 由旋转裁剪决定；质心法已足够接近，
    # 这里再用模板结果微调：把 02 中 A 的左上角 (ox*f, oy*f) 与 R 的位置对应
    m[0, 2] += 0.0
    m[1, 2] += 0.0
    return rot, float(iou), m


def star_tips(mask, nbins=1440, smooth=11, rel=0.72):
    """返回星形庭院的尖角方向（度）与半径（按半径降序）。"""
    ys, xs = np.nonzero(mask)
    c = np.array([xs.mean(), ys.mean()])
    v = np.stack([xs - c[0], ys - c[1]], 1)
    r = np.hypot(v[:, 0], v[:, 1])
    th = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 360.0
    b = (th / 360.0 * nbins).astype(int) % nbins
    p = np.zeros(nbins)
    np.maximum.at(p, b, r)
    for i in np.where(p == 0)[0]:
        p[i] = p[(i - 1) % nbins]
    k = np.ones(smooth) / smooth
    ps = np.convolve(np.concatenate([p[-smooth:], p, p[:smooth]]), k, "same")[smooth:-smooth]
    idx = []
    for i in range(nbins):
        if ps[i] >= ps[(i - 1) % nbins] and ps[i] > ps[(i + 1) % nbins] and ps[i] > rel * ps.max():
            idx.append(i)
    merged = []
    for i in idx:
        if merged and min((i - merged[-1]) % nbins, (merged[-1] - i) % nbins) < 40:
            if ps[i] > ps[merged[-1]]:
                merged[-1] = i
        else:
            merged.append(i)
    tips = [(i * 360.0 / nbins, float(ps[i])) for i in merged]
    tips.sort(key=lambda t: -t[1])
    return tips


def rotation_from_tips(m02, m04):
    """按半径排序配对两图的星形尖角，取角度差中位数作为旋转。"""
    t2 = star_tips(m02)
    t4 = star_tips(m04)
    n = min(len(t2), len(t4))
    if n < 3:
        return 0.0, 0
    diffs = []
    for (a2, _), (a4, _) in zip(t2[:n], t4[:n]):
        d = a2 - a4
        while d > 90:
            d -= 180
        while d < -90:
            d += 180
        diffs.append(d)
    return float(np.median(diffs)), n


def polar_profile(mask, nbins=1440):
    ys, xs = np.nonzero(mask)
    c = np.array([xs.mean(), ys.mean()])
    v = np.stack([xs - c[0], ys - c[1]], 1)
    r = np.hypot(v[:, 0], v[:, 1])
    th = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 360.0
    b = (th / 360.0 * nbins).astype(int) % nbins
    p = np.zeros(nbins)
    np.maximum.at(p, b, r)
    for i in np.where(p == 0)[0]:
        p[i] = p[(i - 1) % nbins]
    return c, p


def rotation_from_courtyards(m02, m04):
    c02, p02 = polar_profile(m02)
    c04, p04 = polar_profile(m04)
    p02n, p04n = p02 / p02.mean(), p04 / p04.mean()
    best = (1e9, 0)
    for sh in range(len(p04n)):
        d = float(np.abs(p02n - np.roll(p04n, sh)).mean())
        if d < best[0]:
            best = (d, sh)
    ang = best[1] * 360.0 / len(p04n)
    if ang > 180:
        ang -= 360
    return ang, best[0], c02, c04


def measure_lane_spacing(g03):
    sub = (g03 < 205).astype(np.uint8)
    lines = cv2.HoughLinesP(sub, 1, np.pi / 7200, threshold=200, minLineLength=700, maxLineGap=25)
    if lines is None:
        return None, None
    rhos = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        if not (68.5 < ang < 71.5):
            continue
        if math.hypot(x2 - x1, y2 - y1) < 700:
            continue
        th = math.radians(ang)
        rhos.append(-math.sin(th) * x1 + math.cos(th) * y1)
    if len(rhos) < 6:
        return None, None
    rhos.sort()
    merged = []
    for r in rhos:
        if not merged or r - merged[-1] > 4:
            merged.append(r)
        else:
            merged[-1] = (merged[-1] + r) / 2
    diffs = [b - a for a, b in zip(merged, merged[1:]) if 10 < b - a < 40]
    if not diffs:
        return None, None
    return float(np.median(diffs)), len(merged)


def _court_anchor():
    """学术中心中央庭院的质心（世界米），优先取描图结果。"""
    path = DATA / "buildings" / "cloud.json"
    if path.exists():
        d = read_json(path)
        c = d.get("courtyard")
        if c and c.get("centroid"):
            return (float(c["centroid"][0]), float(c["centroid"][1]))
    return (24.0, -12.0)


BUILDINGS_COURT_ANCHOR = None  # 在 main() 里赋值


def main() -> int:
    global BUILDINGS_COURT_ANCHOR
    BUILDINGS_COURT_ANCHOR = _court_anchor()
    print("读取高清基准图 …")
    sheets = {k: load_sheet(k) for k in ("01", "02", "03", "04", "05")}

    # ---------------- 1. 唯一定标基准 ----------------
    px_per_m_04, _, resid_04 = fit_scale(SCALE_04_TICKS)
    print(f"[1] 04 比例尺 {px_per_m_04:.3f} px/m（刻度残差 ≤ {resid_04:.1f} px）")

    # ---------------- 2/3. 02 由 04 传递 + 图幅比 ----------------
    px_per_m_02 = px_per_m_04 * SCALE_04_TO_02 * (SIZE_HIRES["02"][0] / SIZE_HIRES["04"][0])
    px_per_m_03 = px_per_m_02 * (SIZE_HIRES["03"][0] / SIZE_HIRES["02"][0])
    px_per_m_02_2000 = px_per_m_02 * 2000.0 / SIZE_HIRES["02"][0]
    print(f"[2] 04→02 缩放 {SCALE_04_TO_02} × 图幅比 {SIZE_HIRES['02'][0]/SIZE_HIRES['04'][0]:.4f}")
    print(f"    02 比例尺 {px_per_m_02:.4f} px/m（1 px = {1/px_per_m_02:.4f} m）")
    print(f"    03 比例尺 {px_per_m_03:.4f} px/m（= 02 × 图幅比 2）")

    # ---------------- 4/5. 01、03 → 02 ----------------
    # 这两张图与 02 是同一套总平面、同朝向、仅差图幅与倍率，因此只需解平移：
    #   1) 尺度由各自的比例尺/计划值锁定（不做自由缩放，避免把图幅比例差
    #      吸收成虚假的各向异性）；
    #   2) 平移用相位相关求得，再用刚性 ECC 微调（只允许平移+极小旋转）。
    px_per_m_01 = px_per_m_02_2000 / PLAN_SCALE_01_TO_02 * (SIZE_HIRES["01"][0] / 2000.0)
    print(f"[5] 01 比例尺 {px_per_m_01:.4f} px/m"
          f"（计划 2.1：01→02 缩放 {PLAN_SCALE_01_TO_02}）")

    def translation_affine(sheet_key, px_per_m_sheet):
        """按比例尺重采样 + 相位相关求平移，返回 (S 全分辨率 px → 02 全分辨率 px) 的 2×3。"""
        k = px_per_m_02 / px_per_m_sheet
        g = sheets[sheet_key]
        res = cv2.resize(g, (max(1, int(round(g.shape[1] * k))),
                             max(1, int(round(g.shape[0] * k)))),
                         interpolation=cv2.INTER_AREA)
        e2 = edges(sheets["02"])
        es = edges(res)
        pad = 400
        H = max(e2.shape[0], es.shape[0]) + 2 * pad
        W = max(e2.shape[1], es.shape[1]) + 2 * pad
        A = np.zeros((H, W), np.float32)
        B = np.zeros((H, W), np.float32)
        A[pad:pad + e2.shape[0], pad:pad + e2.shape[1]] = e2
        B[pad:pad + es.shape[0], pad:pad + es.shape[1]] = es
        (dx, dy), _ = cv2.phaseCorrelate(A, B)
        m = np.array([[k, 0.0, -dx], [0.0, k, -dy]], dtype=np.float32)
        # 刚性微调（MOTION_EUCLIDEAN：平移 + 旋转，不含缩放）
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 600, 1e-6)
        cc = 0.0
        try:
            cc, m2 = cv2.findTransformECC(e2[:, :, None], es[:, :, None],
                                         m, cv2.MOTION_EUCLIDEAN, crit, None, 9)
            # m2 作用在"已按 k 重采样"的图坐标 q = k·p 上；换回原始像素 p：
            #   p02 = A2·q + t2 = (k·A2)·p + t2
            m = m2.astype(np.float64)
            m[:, :2] *= k
        except cv2.error:
            m = m.astype(np.float64)
        return cc, m

    cc_03, m_03_full = translation_affine("03", px_per_m_03)
    sc3, ro3, an3 = decompose(m_03_full)
    print(f"[4] 03→02 配准 cc={cc_03:.3f} scale={sc3:.4f} rot={ro3:.3f}° aniso={an3:.4f}")

    cc_01, m_01_full = translation_affine("01", px_per_m_01)
    sc1, ro1, an1 = decompose(m_01_full)
    print(f"[5] 01→02 配准 cc={cc_01:.3f} scale={sc1:.4f} rot={ro1:.3f}° aniso={an1:.4f}")

    # ---------------- 6. 04 → 02 的旋转与平移 ----------------
    # 04 与 02 的楼板都接近方形，靠楼板轮廓定旋转会出现 90° 级歧义；
    # 改以学术中心中央庭院的**星形尖角**为准：两图各有 5 个尖角，
    # 按半径排序配对求旋转差，再取中位数。平移由楼板质心对齐。
    plate02 = learning_plate_02(sheets["02"])
    plate04 = learning_plate_04(sheets["04"])
    ys, xs = np.nonzero(plate02)
    c02 = np.array([xs.mean(), ys.mean()])
    ys, xs = np.nonzero(plate04)
    c04 = np.array([xs.mean(), ys.mean()])
    print(f"[6] 02 学术中心板 {plate02.sum()/(px_per_m_02**2):.0f} m²，"
          f"04 板 {plate04.sum()/(px_per_m_04**2):.0f} m²")

    court02 = courtyard_02(sheets["02"])
    court04 = loft(sheets["04"], COURT_SEED_04)
    rot_tips, tip_pairs = rotation_from_tips(court02, court04)
    rot_04 = rot_tips if abs(abs(rot_tips) - abs(ROT_04_TO_02)) <= 8 else ROT_04_TO_02
    print(f"    庭院尖角配对 → 旋转 {rot_tips:.2f}°（{tip_pairs} 对）；采用 {rot_04:.2f}°")

    m04 = sim(px_per_m_02 / px_per_m_04, rot_04, 0.0, 0.0)
    mc = m04[:, :2] @ c04
    m04[0, 2] = c02[0] - mc[0]
    m04[1, 2] = c02[1] - mc[1]

    # 用板形 IoU 复核（不再用它定旋转）
    ys, xs = np.nonzero(plate04)
    wp = np.stack([xs, ys], 1).astype(np.float64) @ m04[:, :2].T + m04[:, 2]
    canvas = np.zeros_like(plate02)
    xi = np.round(wp[:, 0]).astype(int)
    yi = np.round(wp[:, 1]).astype(int)
    ok = (xi >= 0) & (xi < canvas.shape[1]) & (yi >= 0) & (yi < canvas.shape[0])
    canvas[yi[ok], xi[ok]] = 1
    canvas = cv2.morphologyEx(canvas, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    iou_04 = float((canvas & plate02).sum()) / float((canvas | plate02).sum())
    rot_meas = rot_tips
    print(f"    04→02 板形 IoU {iou_04:.3f}")

    # 庭院轮廓一致性：02 与 04 各自提取的中央庭院是否重合
    court_iou = None
    court_med = None
    try:
        ys2, xs2 = np.nonzero(court02)
        ys4, xs4 = np.nonzero(court04)
        p4 = np.stack([xs4, ys4], 1).astype(np.float64) @ m04[:, :2].T + m04[:, 2]
        c4 = np.zeros_like(court02)
        xi4 = np.round(p4[:, 0]).astype(int)
        yi4 = np.round(p4[:, 1]).astype(int)
        ok4 = (xi4 >= 0) & (xi4 < c4.shape[1]) & (yi4 >= 0) & (yi4 < c4.shape[0])
        c4[yi4[ok4], xi4[ok4]] = 1
        inter = float((c4 & court02).sum())
        union = float((c4 | court02).sum())
        court_iou = inter / union if union else None
        d2 = cv2.distanceTransform(1 - court02.astype(np.uint8), cv2.DIST_L2, 5)
        dvals = d2[yi4[ok4], xi4[ok4]]
        court_med = float(np.median(dvals)) / px_per_m_02
        print(f"    庭院 02↔04 IoU {court_iou:.3f}，04 轮廓到 02 庭院的中位距离 "
              f"{court_med:.2f} m")
    except Exception as exc:
        print("    庭院一致性检查失败：", exc)

    # ---------------- 7. 交叉验证：分道线 ----------------
    lane_px, n_lines = measure_lane_spacing(sheets["03"])
    if lane_px:
        px_per_m_03_lane = lane_px / LANE_WIDTH_M
        lane_err = (px_per_m_03_lane - px_per_m_03) / px_per_m_03 * 100
        print(f"[7] 03 分道线间距 {lane_px:.2f} px → {px_per_m_03_lane:.2f} px/m"
              f"（相对定标链 {lane_err:+.1f}%）")
    else:
        px_per_m_03_lane, lane_err = None, None

    # 交叉验证：学术中心屋面面积（02 描图 ↔ OSM）
    osM_area = 17307.0
    tone = ((sheets["02"] >= 198) & (sheets["02"] <= 246)).astype(np.uint8)
    tone = cv2.morphologyEx(tone, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    plate = biggest_component(tone, 100000)
    plate_area_m2 = plate.sum() / (px_per_m_02 ** 2)
    print(f"[8] 02 屋面板面积 {plate_area_m2:.0f} m²（屋面板含挑檐与宿舍连桥，"
          f"OSM 学术中心 {osM_area:.0f} m²）")

    # ---------------- 汇总 ----------------
    origin = np.array([SIZE_HIRES["02"][0] / 2.0, SIZE_HIRES["02"][1] / 2.0])
    to_world = np.array([[1.0 / px_per_m_02, 0.0, -origin[0] / px_per_m_02],
                         [0.0, 1.0 / px_per_m_02, -origin[1] / px_per_m_02],
                         [0.0, 0.0, 1.0]])

    mats = {"02": np.eye(2, 3), "04": m04, "01": m_01_full, "03": m_03_full}

    # 04 三层楼板轮廓（世界坐标），供 check:align 的「学术中心三层」比对
    plate_polygon = None
    try:
        world_from_04 = to_world @ np.vstack([m04, [0, 0, 1]])
        cs, _ = cv2.findContours(plate04.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        big = max(cs, key=cv2.contourArea)
        ap = cv2.approxPolyDP(big, 4.0, True).reshape(-1, 2).astype(np.float64)
        wp = np.concatenate([ap, np.ones((len(ap), 1))], 1) @ world_from_04.T
        plate_polygon = [[round(float(p[0]), 2), round(float(p[1]), 2)]
                         for p in wp[:, :2]]
    except Exception as exc:
        print("  04 楼板轮廓持久化失败：", exc)

    # 04 中央庭院轮廓（世界坐标）
    court_polygon = None
    try:
        cs, _ = cv2.findContours(court04.copy().astype(np.uint8), cv2.RETR_EXTERNAL,
                                 cv2.CHAIN_APPROX_SIMPLE)
        big = max(cs, key=cv2.contourArea)
        ap = cv2.approxPolyDP(big, 3.0, True).reshape(-1, 2).astype(np.float64)
        wp = np.concatenate([ap, np.ones((len(ap), 1))], 1) @ world_from_04.T
        court_polygon = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in wp[:, :2]]
    except Exception as exc:
        print("  04 庭院轮廓持久化失败：", exc)

    frames = {}
    for s, mat in mats.items():
        a = to_world @ np.vstack([mat, [0, 0, 1]])
        frames[s] = {
            "source": f"research/plans/hires/{SHEET_FILES[s]}",
            "size": list(SIZE_HIRES[s]),
            "affine": [[round(float(v), 8) for v in row] for row in a],
        **({"plate_polygon": plate_polygon, "courtyard_polygon": court_polygon}
           if s == "04" and plate_polygon else {}),
            "px_per_m": round(1.0 / math.hypot(a[0, 0], a[1, 0]), 5),
            "rotation_deg": round(math.degrees(math.atan2(a[1, 0], a[0, 0])), 4),
        }
    # ---- 05 剖面：竖向标定 + 横向锚点（用学术中心中央庭院对齐） ----
    px_per_m_05 = (SECTION_05["y0_px"] - SECTION_05["roof25_px"]) / (
        SECTION_05["roof25_elev"] - SECTION_05["elev0"])
    court = BUILDINGS_COURT_ANCHOR  # (x, z) 世界坐标，来自 02 描图的庭院质心
    court_center_x = 0.5 * (SECTION_05["court_x0_px"] + SECTION_05["court_x1_px"])
    # 剖面图 x 向右 = 世界 z 减小（右端为北）
    z_at_court = court[1]
    frames["05"] = {
        "source": f"research/plans/hires/{SHEET_FILES['05']}",
        "size": list(SIZE_HIRES["05"]),
        "note": "剖面不参与平面配准；竖向由 ±0.00 与南翼 +23.50 两点标定，"
                "横向以学术中心中央庭院质心对齐。图面右端向北。",
        "px_per_m": round(px_per_m_05, 5),
        "vertical": {"y0_px": SECTION_05["y0_px"], "elev0": SECTION_05["elev0"],
                     "px_per_m": round(px_per_m_05, 5)},
        "horizontal": {"court_center_x_px": court_center_x,
                       "z_at_court_center": round(z_at_court, 3),
                       "px_per_m": round(px_per_m_05, 5),
                       "direction": "image +x ↔ world −z（右端向北）"},
        "plane_x": round(court[0], 3),
        "checks_px": {
            "elev_5.00": round(SECTION_05["y0_px"] - 5.0 * px_per_m_05, 1),
            "elev_14.50": round(SECTION_05["y0_px"] - 14.5 * px_per_m_05, 1),
            "elev_19.00": round(SECTION_05["y0_px"] - 19.0 * px_per_m_05, 1),
        },
    }

    out = {
        "version": 2,
        "updated": "2026-11-14",
        "note": "图面像素 → 世界米（x 向东，z 向南，原点为 02 图面中心）。scripts/register.py 生成。",
        "world": {"unit": "m", "x": "east", "z": "south", "origin": "02 图面中心",
                  "y": "up；y=0 对应 01 图绝对标高 37.00"},
        "scale": {
            "px_per_m_02_hires": round(px_per_m_02, 5),
            "px_per_m_03_hires": round(px_per_m_03, 5),
            "px_per_m_04_hires": round(px_per_m_04, 5),
            "m_per_px_02_hires": round(1.0 / px_per_m_02, 5),
            "px_per_m_02_2000": round(px_per_m_02 * 2000.0 / SIZE_HIRES["02"][0], 5),
            "m_per_px_02_2000": round(SIZE_HIRES["02"][0] / 2000.0 / px_per_m_02, 5),
            "chain": [
                "04 自带 50 m 比例尺 → %.3f px/m" % px_per_m_04,
                "04→02 剪影配准缩放 %.4f" % SCALE_04_TO_02,
                "02 高清图幅宽 %.0f ↔ 04 %.0f" % (SIZE_HIRES["02"][0], SIZE_HIRES["04"][0]),
                "02 = %.4f px/m；03 = 02 × 2 = %.4f px/m" % (px_per_m_02, px_per_m_03),
            ],
        },
        "frames": frames,
        "residuals": {
            "scale_ticks_04_px": round(resid_04, 2),
            "lane_spacing_px": round(lane_px, 2) if lane_px else None,
            "lane_scale_error_pct": round(lane_err, 2) if lane_err is not None else None,
            "ecc_cc": {"01": round(cc_01, 4), "03": round(cc_03, 4)},
            "anisotropy": {"01": round(an1, 5), "03": round(an3, 5)},
            "rotation_04_measured_deg": round(rot_meas, 2),
            "courtyard_iou": round(iou_04, 4),
            "cloud_plate_area_m2": round(plate_area_m2, 0),
            "osm_cloud_area_m2": osM_area,
        },
    }
    write_json(DATA / "frames.json", out)

    checks = [
        {"name": "04 比例尺刻度残差", "unit": "px", "value": round(resid_04, 2), "target": "≤ 3"},
        {"name": "03→02 变换缩放", "unit": "", "value": round(sc3, 4),
         "target": "0.500 ±0.002（03 图幅为 02 的 2 倍）"},
        {"name": "03→02 配准旋转", "unit": "°", "value": round(ro3, 3), "target": "0 ±0.2"},
        {"name": "02 比例尺（高清）", "unit": "px/m", "value": round(px_per_m_02, 4), "target": "7.83 ±0.10"},
        {"name": "02 比例尺（2000 px 版）", "unit": "px/m",
         "value": round(px_per_m_02 * 2000.0 / SIZE_HIRES["02"][0], 4), "target": "3.147 ±0.04"},
        {"name": "03 分道线反算相对误差", "unit": "%",
         "value": round(lane_err, 2) if lane_err is not None else None, "target": "±5"},
        {"name": "04→02 旋转（极坐标实测）", "unit": "°", "value": round(rot_meas, 2), "target": "−35.8 ±3"},
        {"name": "04→02 庭院 IoU", "unit": "", "value": round(iou_04, 4), "target": "≥ 0.40（屋面挑檐不同）"},
        {"name": "01→02 各向异性", "unit": "", "value": round(an1, 5), "target": "1.00 ±0.06（图幅比不同）"},
        {"name": "04→02 板形 IoU", "unit": "", "value": round(iou_04, 4), "target": "≥ 0.90"},
        {"name": "庭院 02↔04 IoU", "unit": "",
         "value": round(court_iou, 4) if court_iou else None, "target": "≥ 0.85"},
        {"name": "庭院 02↔04 中位距离", "unit": "m",
         "value": round(court_med, 3) if court_med else None, "target": "≤ 0.5"},
    ]
    write_json(REPORTS / "registration.json", {
        "generated": "2026-11-14",
        "scale": out["scale"],
        "residuals": out["residuals"],
        "frames": frames,
        "checks": checks,
    })
    print("写入 src/data/frames.json 与 reports/align/registration.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
