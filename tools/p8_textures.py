"""P8 程序化高精度贴图生成：
- blender/textures/sports_atlas.png  (2048x2048 四象限：足球场 / 网球场 / 绿篮球场 / 蓝篮球场)
- blender/textures/roof_seam.png     (512x512 深蓝灰直立锁边金属屋面)
- blender/textures/school_stone.png  (1024x384 北入口校名景石：北京大学附属中学海口学校)
- blender/textures/bleacher_slogan.png (1024x192 看台前挡墙标语与五环)
- blender/textures/people_palette.png (512x64 建筑配景人物统一色板)
"""
import os, math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'blender', 'textures')
os.makedirs(OUT, exist_ok=True)


def find_cjk_font():
    candidates = [
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def draw_football_quad(img, x0, y0, size):
    """标准 11 人制足球场（长 105 m 沿 Y，宽 68 m 沿 X），带 18 道草坪条纹与完整白线。"""
    # 象限区域：x in [x0, x0+size), y in [y0, y0+size)
    # 留 1.5% 边距防止纹理采样渗色
    pad_px = 14
    L, W = 105.0, 68.0
    # 铺底深绿草
    img[y0:y0 + size, x0:x0 + size] = (34, 96, 40)  # BGR
    # 18 道交替横向草坪条纹（沿长度方向 Y）
    stripes = 18
    x_l, x_r = x0 + pad_px, x0 + size - pad_px
    y_t, y_b = y0 + pad_px, y0 + size - pad_px
    pw = x_r - x_l
    ph = y_b - y_t
    for i in range(stripes):
        sy0 = y_t + int(round(ph * i / stripes))
        sy1 = y_t + int(round(ph * (i + 1) / stripes))
        col = (44, 126, 56) if i % 2 == 0 else (30, 92, 38)  # 浅绿 / 深绿 BGR
        img[sy0:sy1, x_l:x_r] = col

    # 微弱草坪颗粒噪点（保持自然但不杂乱）
    rng = np.random.default_rng(42)
    noise = rng.integers(-6, 7, (size, size, 1), dtype=np.int16)
    sub = img[y0:y0 + size, x0:x0 + size].astype(np.int16) + noise
    img[y0:y0 + size, x0:x0 + size] = np.clip(sub, 0, 255).astype(np.uint8)

    # 坐标映射：球场局部 (xm in [-W/2, W/2], ym in [-L/2, L/2]) -> 像素
    def pt(xm, ym):
        px = int(round(x_l + (xm + W / 2.0) / W * pw))
        py = int(round(y_b - (ym + L / 2.0) / L * ph))
        return (px, py)

    def rx(m):
        return max(1, int(round(m / W * pw)))

    def ry(m):
        return max(1, int(round(m / L * ph)))

    white = (242, 245, 242)
    lw = 4

    # 外边线与底线
    cv2.rectangle(img, pt(-W / 2, L / 2), pt(W / 2, -L / 2), white, lw, cv2.LINE_AA)
    # 中线
    cv2.line(img, pt(-W / 2, 0), pt(W / 2, 0), white, lw, cv2.LINE_AA)
    # 中圈 (R = 9.15 m) 与中点
    cv2.ellipse(img, pt(0, 0), (rx(9.15), ry(9.15)), 0, 0, 360, white, lw, cv2.LINE_AA)
    cv2.circle(img, pt(0, 0), 5, white, -1, cv2.LINE_AA)

    # 南北禁区、球门区、点球点、罚球弧
    for sgn in (1, -1):
        gl = sgn * L / 2.0
        # 大禁区 40.32 x 16.5 m
        y_pen = gl - sgn * 16.5
        cv2.rectangle(img, pt(-20.16, max(gl, y_pen)), pt(20.16, min(gl, y_pen)), white, lw, cv2.LINE_AA)
        # 小禁区（球门区）18.32 x 5.5 m
        y_goal = gl - sgn * 5.5
        cv2.rectangle(img, pt(-9.16, max(gl, y_goal)), pt(9.16, min(gl, y_goal)), white, lw, cv2.LINE_AA)
        # 点球点 (11 m)
        y_spot = gl - sgn * 11.0
        cv2.circle(img, pt(0, y_spot), 4, white, -1, cv2.LINE_AA)
        # 罚球弧 (R = 9.15 m，只露在大禁区外)
        # cos(theta) = 5.5 / 9.15 => theta = 53.05 deg
        ang = math.degrees(math.acos(5.5 / 9.15))
        if sgn == 1:
            # 北端，弧朝下 (屏幕 +Y，即角度 90 ± ang)
            cv2.ellipse(img, pt(0, y_spot), (rx(9.15), ry(9.15)), 0, 90 - ang, 90 + ang, white, lw, cv2.LINE_AA)
        else:
            # 南端，弧朝上 (屏幕 -Y，即角度 270 ± ang)
            cv2.ellipse(img, pt(0, y_spot), (rx(9.15), ry(9.15)), 0, 270 - ang, 270 + ang, white, lw, cv2.LINE_AA)

    # 四角角球弧 (R = 1.2 m 便于清晰可见)
    cv2.ellipse(img, pt(-W / 2, L / 2), (rx(1.5), ry(1.5)), 0, 0, 90, white, lw, cv2.LINE_AA)
    cv2.ellipse(img, pt(W / 2, L / 2), (rx(1.5), ry(1.5)), 0, 90, 180, white, lw, cv2.LINE_AA)
    cv2.ellipse(img, pt(W / 2, -L / 2), (rx(1.5), ry(1.5)), 0, 180, 270, white, lw, cv2.LINE_AA)
    cv2.ellipse(img, pt(-W / 2, -L / 2), (rx(1.5), ry(1.5)), 0, 270, 360, white, lw, cv2.LINE_AA)


def draw_tennis_quad(img, x0, y0, size):
    """标准网球场（总 pad 30.77 x 17.97 m，内场 23.77 x 10.97 m）：深绿外框 + 红褐红土内场 + 标准白线。"""
    L_tot, W_tot = 30.77, 17.97
    L, W = 23.77, 10.97
    Ws = 8.23
    L_srv = 6.40
    # 外圈深绿缓冲区 (卫星图 & wx_35)
    img[y0:y0 + size, x0:x0 + size] = (62, 86, 62)  # 深墨绿 BGR

    def pt(xm, ym):
        px = int(round(x0 + (xm + W_tot / 2.0) / W_tot * size))
        py = int(round(y0 + (L_tot / 2.0 - ym) / L_tot * size))
        return (px, py)

    # 红褐/砖红比赛区（略外扩 0.25 m 与实景一致）
    cv2.rectangle(img, pt(-W / 2 - 0.15, L / 2 + 0.15), pt(W / 2 + 0.15, -L / 2 - 0.15), (96, 114, 168), -1)

    rng = np.random.default_rng(43)
    noise = rng.integers(-5, 6, (size, size, 1), dtype=np.int16)
    sub = img[y0:y0 + size, x0:x0 + size].astype(np.int16) + noise
    img[y0:y0 + size, x0:x0 + size] = np.clip(sub, 0, 255).astype(np.uint8)

    white = (244, 246, 244)
    lw = 4
    # 双打外框
    cv2.rectangle(img, pt(-W / 2, L / 2), pt(W / 2, -L / 2), white, lw, cv2.LINE_AA)
    # 单打边线
    cv2.line(img, pt(-Ws / 2, L / 2), pt(-Ws / 2, -L / 2), white, lw, cv2.LINE_AA)
    cv2.line(img, pt(Ws / 2, L / 2), pt(Ws / 2, -L / 2), white, lw, cv2.LINE_AA)
    # 发球线
    cv2.line(img, pt(-Ws / 2, L_srv), pt(Ws / 2, L_srv), white, lw, cv2.LINE_AA)
    cv2.line(img, pt(-Ws / 2, -L_srv), pt(Ws / 2, -L_srv), white, lw, cv2.LINE_AA)
    # 中发球线
    cv2.line(img, pt(0, L_srv), pt(0, -L_srv), white, lw, cv2.LINE_AA)
    # 球网参考淡线
    cv2.line(img, pt(-W / 2 - 0.9, 0), pt(W / 2 + 0.9, 0), (200, 200, 200), 2, cv2.LINE_AA)
    # 端线中心标记
    cv2.line(img, pt(0, L / 2), pt(0, L / 2 - 0.4), white, lw, cv2.LINE_AA)
    cv2.line(img, pt(0, -L / 2), pt(0, -L / 2 + 0.4), white, lw, cv2.LINE_AA)


def draw_basketball_quad(img, x0, y0, size, apron_bgr, court_bgr, key_bgr, seed=44):
    """标准 FIBA 篮球场（总 pad 32 x 19 m，内场 28 x 15 m）。"""
    L_tot, W_tot = 32.0, 19.0
    L, W = 28.0, 15.0
    img[y0:y0 + size, x0:x0 + size] = apron_bgr

    def pt(xm, ym):
        px = int(round(x0 + (xm + W_tot / 2.0) / W_tot * size))
        py = int(round(y0 + (L_tot / 2.0 - ym) / L_tot * size))
        return (px, py)

    def rx(m):
        return max(1, int(round(m / W_tot * size)))

    def ry(m):
        return max(1, int(round(m / L_tot * size)))

    # 主赛区色
    cv2.rectangle(img, pt(-W / 2, L / 2), pt(W / 2, -L / 2), court_bgr, -1)
    # 南北三秒区涂色 (宽 4.9 m, 深 5.8 m)
    for sgn in (1, -1):
        bl = sgn * L / 2.0
        y_ft = bl - sgn * 5.8
        cv2.rectangle(img, pt(-2.45, max(bl, y_ft)), pt(2.45, min(bl, y_ft)), key_bgr, -1)

    rng = np.random.default_rng(seed)
    noise = rng.integers(-4, 5, (size, size, 1), dtype=np.int16)
    sub = img[y0:y0 + size, x0:x0 + size].astype(np.int16) + noise
    img[y0:y0 + size, x0:x0 + size] = np.clip(sub, 0, 255).astype(np.uint8)

    white = (246, 247, 246)
    lw = 4
    # 边线与端线
    cv2.rectangle(img, pt(-W / 2, L / 2), pt(W / 2, -L / 2), white, lw, cv2.LINE_AA)
    # 中线与中圈 (R = 1.8 m)
    cv2.line(img, pt(-W / 2, 0), pt(W / 2, 0), white, lw, cv2.LINE_AA)
    cv2.ellipse(img, pt(0, 0), (rx(1.8), ry(1.8)), 0, 0, 360, white, lw, cv2.LINE_AA)

    for sgn in (1, -1):
        bl = sgn * L / 2.0
        y_ft = bl - sgn * 5.8
        y_hoop = bl - sgn * 1.575
        # 三秒区框
        cv2.rectangle(img, pt(-2.45, max(bl, y_ft)), pt(2.45, min(bl, y_ft)), white, lw, cv2.LINE_AA)
        # 罚球圆 (R = 1.8 m)
        cv2.ellipse(img, pt(0, y_ft), (rx(1.8), ry(1.8)), 0, 0, 360, white, lw, cv2.LINE_AA)
        # 三分线：底角直线 x = ±6.6 m，弧半径 R = 6.75 m 以篮筐为中心
        dy_corner = math.sqrt(6.75 ** 2 - 6.6 ** 2)  # ~1.41 m
        y_arc_join = y_hoop - sgn * dy_corner
        cv2.line(img, pt(-6.6, bl), pt(-6.6, y_arc_join), white, lw, cv2.LINE_AA)
        cv2.line(img, pt(6.6, bl), pt(6.6, y_arc_join), white, lw, cv2.LINE_AA)
        ang = math.degrees(math.acos(6.6 / 6.75))  # ~12.1 deg
        if sgn == 1:
            # 北侧篮筐，三分弧朝下 (屏幕 +Y，即 12..168 deg)
            cv2.ellipse(img, pt(0, y_hoop), (rx(6.75), ry(6.75)), 0, ang, 180 - ang, white, lw, cv2.LINE_AA)
        else:
            # 南侧篮筐，三分弧朝上 (屏幕 -Y，即 192..348 deg)
            cv2.ellipse(img, pt(0, y_hoop), (rx(6.75), ry(6.75)), 0, 180 + ang, 360 - ang, white, lw, cv2.LINE_AA)


def make_sports_atlas():
    S = 2048
    H = S // 2
    img = np.zeros((S, S, 3), dtype=np.uint8)
    # 象限布置（Blender UV: v=0 在底部, v=1 在顶部）
    # 图像顶部 y=0..H => UV v=0.5..1.0
    draw_football_quad(img, 0, 0, H)
    draw_tennis_quad(img, H, 0, H)
    # 图像底部 y=H..S => UV v=0.0..0.5
    # basket_W (卫星图：深绿主赛区 + 米黄三秒区与外圈)
    draw_basketball_quad(img, 0, H, H,
                         apron_bgr=(152, 166, 174),
                         court_bgr=(84, 108, 86),
                         key_bgr=(148, 164, 174), seed=44)
    # basket_NE (上传照片 #5/#6：天蓝主赛区 + 砖红缓冲与三秒区)
    draw_basketball_quad(img, H, H, H,
                         apron_bgr=(92, 106, 190),
                         court_bgr=(196, 144, 88),
                         key_bgr=(98, 114, 194), seed=45)
    p = os.path.join(OUT, 'sports_atlas.png')
    cv2.imwrite(p, img)
    print('wrote', p)


def make_roof_seam():
    """深蓝灰直立锁边金属坡屋面纹理（带竖向锁边肋条与细微光伏分区肌理）。"""
    W, H = 512, 512
    im = np.full((H, W, 3), (62, 52, 44), dtype=np.uint8)  # 深蓝灰 BGR
    # 16 条锁边纵肋
    step = W // 16
    for x in range(0, W, step):
        im[:, max(0, x - 1):min(W, x + 1)] = (42, 36, 30)
        if x + 2 < W:
            im[:, x + 1:x + 3] = (80, 68, 58)
    # 横向金属板接缝
    for y in (H // 2, H - 1):
        cv2.line(im, (0, y), (W, y), (46, 40, 34), 2)
    rng = np.random.default_rng(7)
    noise = rng.integers(-3, 4, (H, W, 1), dtype=np.int16)
    im = np.clip(im.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    p = os.path.join(OUT, 'roof_seam.png')
    cv2.imwrite(p, im)
    print('wrote', p)


def make_school_stone():
    """北入口校名景石：灰白纹理天然景石 + 深红书法字样“北京大学附属中学海口学校”。"""
    W, H = 1024, 384
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # 多频自然花岗岩纹理
    rng0 = np.random.default_rng(19)
    low = cv2.resize(rng0.normal(0, 1, (16, 42)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    mid = cv2.resize(rng0.normal(0, 1, (48, 128)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    wave = np.sin(yy * 0.065 + low * 2.2 + mid * 0.7) * 0.6 + low * 0.5
    base = 148 + wave * 26
    rng = np.random.default_rng(11)
    grain = rng.normal(0, 8, (H, W))
    g = np.clip(base + grain, 60, 220).astype(np.uint8)
    arr = np.stack([g, g, np.clip(g.astype(int) + 3, 0, 255).astype(np.uint8)], axis=-1)
    pil = Image.fromarray(arr, mode='RGB')
    draw = ImageDraw.Draw(pil)
    fp = find_cjk_font()
    text = '北京大学附属中学海口学校'
    font = ImageFont.truetype(fp, 74) if fp else ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = (W - tw) // 2, (H - th) // 2 - 8
    # 浅刻影 + 深红字
    draw.text((tx + 2, ty + 2), text, font=font, fill=(65, 55, 55))
    draw.text((tx, ty), text, font=font, fill=(138, 26, 26))
    p = os.path.join(OUT, 'school_stone.png')
    pil.save(p)
    print('wrote', p)


def make_bleacher_slogan():
    """体育场看台前挡墙：浅灰混凝土 + 校训标语与五环装饰（official_19.jpg）。"""
    W, H = 1024, 192
    pil = Image.new('RGB', (W, H), (178, 179, 176))
    draw = ImageDraw.Draw(pil)
    # 混凝土模板分缝
    for x in range(0, W, 128):
        draw.line([(x, 0), (x, H)], fill=(158, 159, 156), width=2)
    fp = find_cjk_font()
    font = ImageFont.truetype(fp, 42) if fp else ImageFont.load_default()
    text = '体育强则中国强    体育兴则中国兴'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, (H - th) // 2 - 4), text, font=font, fill=(72, 80, 88))
    # 两侧奥运五环小装饰（不与文字重叠）
    colors = [(0, 120, 200), (240, 175, 0), (35, 35, 35), (0, 150, 70), (215, 38, 46)]
    for cx0 in (52, W - 118):
        offs = [(0, 0), (14, 14), (28, 0), (42, 14), (56, 0)]
        for (dx, dy), col in zip(offs, colors):
            r = 12
            draw.ellipse([cx0 + dx - r, H // 2 - 6 + dy - r, cx0 + dx + r, H // 2 - 6 + dy + r], outline=col, width=3)
    p = os.path.join(OUT, 'bleacher_slogan.png')
    pil.save(p)
    print('wrote', p)


def make_people_palette():
    """8 格建筑配景人物统一色板 (512x64)：每格 64px 宽，单材质 UV 映射全员着装。
    0: 肤色, 1: 深发, 2: 白校服, 3: 藏青校裤, 4: 蓝球衣, 5: 红橙球衣, 6: 教师浅蓝衬衫, 7: 暗灰长裤/书包
    """
    swatches = [
        (228, 190, 158),  # 0 skin
        (42, 36, 34),     # 1 dark hair / shoes
        (242, 244, 246),  # 2 white school uniform
        (36, 48, 76),     # 3 navy shorts / pants
        (40, 108, 206),   # 4 blue sports jersey
        (214, 72, 52),    # 5 red/orange sports jersey
        (178, 198, 214),  # 6 teacher light blue shirt
        (68, 72, 78),     # 7 charcoal pants / backpack
    ]
    W, H = 512, 64
    sw = W // len(swatches)
    im = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(im)
    for i, col in enumerate(swatches):
        draw.rectangle([i * sw, 0, (i + 1) * sw - 1, H - 1], fill=col)
    p = os.path.join(OUT, 'people_palette.png')
    im.save(p)
    print('wrote', p)


if __name__ == '__main__':
    make_sports_atlas()
    make_roof_seam()
    make_school_stone()
    make_bleacher_slogan()
    make_people_palette()
