"""P8/P10 程序化高精度贴图生成：
- blender/textures/sports_atlas.png      (2048x2048 四象限：柔和条纹足球草坪 / 网球红土 / 绿篮球场 / 蓝红篮球场；白线改由 site.py 3D 矢量几何生成，绝对锐利！)
- blender/textures/roof_seam.png         (512x512 深蓝灰直立锁边金属屋面)
- blender/textures/school_stone.png      (2048x768 北入口校名景石：细腻花岗岩纹理 + 居中留白深红大字)
- blender/textures/bleacher_slogan.png   (1024x192 看台前挡墙标语与五环)
- blender/textures/people_palette.png    (1024x64 16 格建筑配景人物统一色板)
- blender/textures/pool_water_normal.png (256x256 室内泳池无缝波纹法线贴图)
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
    """标准 11 人制足球场底纹（长 105 m 沿 Y，宽 68 m 沿 X），自然柔和 18 道草坪修剪条纹 + 细草丝肌理（白线由 3D 矢量几何承担）。"""
    pad_px = 14
    img[y0:y0 + size, x0:x0 + size] = (42, 112, 50)  # BGR
    stripes = 18
    x_l, x_r = x0 + pad_px, x0 + size - pad_px
    y_t, y_b = y0 + pad_px, y0 + size - pad_px
    ph = y_b - y_t
    for i in range(stripes):
        sy0 = y_t + int(round(ph * i / stripes))
        sy1 = y_t + int(round(ph * (i + 1) / stripes))
        # 更自然的草坪明暗交替（降低过硬斑马纹反差）
        col = (48, 124, 58) if i % 2 == 0 else (38, 106, 46)
        img[sy0:sy1, x_l:x_r] = col

    # 细腻双频草坪质感（低频自然斑块 + 高频微粒）
    rng = np.random.default_rng(42)
    low = cv2.resize(rng.normal(0, 3.2, (32, 32)).astype(np.float32), (size, size), interpolation=cv2.INTER_CUBIC)[..., None]
    hi = rng.normal(0, 3.8, (size, size, 1)).astype(np.float32)
    sub = img[y0:y0 + size, x0:x0 + size].astype(np.float32) + low + hi
    img[y0:y0 + size, x0:x0 + size] = np.clip(sub, 0, 255).astype(np.uint8)


def draw_tennis_quad(img, x0, y0, size):
    """标准网球场色彩分区（总 pad 30.77 x 17.97 m，内场 23.77 x 10.97 m）：深绿外框 + 红土内场（白线由 3D 矢量几何承担）。"""
    L_tot, W_tot = 30.77, 17.97
    L, W = 23.77, 10.97
    img[y0:y0 + size, x0:x0 + size] = (62, 88, 64)

    def pt(xm, ym):
        px = int(round(x0 + (xm + W_tot / 2.0) / W_tot * size))
        py = int(round(y0 + (L_tot / 2.0 - ym) / L_tot * size))
        return (px, py)

    cv2.rectangle(img, pt(-W / 2 - 0.10, L / 2 + 0.10), pt(W / 2 + 0.10, -L / 2 - 0.10), (96, 114, 168), -1)

    rng = np.random.default_rng(43)
    noise = rng.integers(-4, 5, (size, size, 1), dtype=np.int16)
    sub = img[y0:y0 + size, x0:x0 + size].astype(np.int16) + noise
    img[y0:y0 + size, x0:x0 + size] = np.clip(sub, 0, 255).astype(np.uint8)


def draw_basketball_quad(img, x0, y0, size, apron_bgr, court_bgr, key_bgr, seed=44):
    """标准 FIBA 篮球场色彩分区（总 pad 32 x 19 m，内场 28 x 15 m；白线由 3D 矢量几何承担）。"""
    L_tot, W_tot = 32.0, 19.0
    L, W = 28.0, 15.0
    img[y0:y0 + size, x0:x0 + size] = apron_bgr

    def pt(xm, ym):
        px = int(round(x0 + (xm + W_tot / 2.0) / W_tot * size))
        py = int(round(y0 + (L_tot / 2.0 - ym) / L_tot * size))
        return (px, py)

    cv2.rectangle(img, pt(-W / 2, L / 2), pt(W / 2, -L / 2), court_bgr, -1)
    for sgn in (1, -1):
        bl = sgn * L / 2.0
        y_ft = bl - sgn * 5.8
        cv2.rectangle(img, pt(-2.45, max(bl, y_ft)), pt(2.45, min(bl, y_ft)), key_bgr, -1)

    rng = np.random.default_rng(seed)
    noise = rng.integers(-4, 5, (size, size, 1), dtype=np.int16)
    sub = img[y0:y0 + size, x0:x0 + size].astype(np.int16) + noise
    img[y0:y0 + size, x0:x0 + size] = np.clip(sub, 0, 255).astype(np.uint8)


def make_sports_atlas():
    S = 2048
    H = S // 2
    img = np.zeros((S, S, 3), dtype=np.uint8)
    draw_football_quad(img, 0, 0, H)
    draw_tennis_quad(img, H, 0, H)
    draw_basketball_quad(img, 0, H, H,
                         apron_bgr=(152, 166, 174),
                         court_bgr=(84, 108, 86),
                         key_bgr=(148, 164, 174), seed=44)
    draw_basketball_quad(img, H, H, H,
                         apron_bgr=(92, 106, 190),
                         court_bgr=(196, 144, 88),
                         key_bgr=(98, 114, 194), seed=45)
    p = os.path.join(OUT, 'sports_atlas.png')
    cv2.imwrite(p, img)
    print('wrote', p)


def make_roof_seam():
    """深蓝灰直立锁边金属坡屋面纹理（带竖向锁边肋条与细微金属光泽肌理）。"""
    W, H = 512, 512
    im = np.full((H, W, 3), (62, 52, 44), dtype=np.uint8)
    step = W // 16
    for x in range(0, W, step):
        im[:, max(0, x - 1):min(W, x + 1)] = (42, 36, 30)
        if x + 2 < W:
            im[:, x + 1:x + 3] = (80, 68, 58)
    for y in (H // 2, H - 1):
        cv2.line(im, (0, y), (W, y), (46, 40, 34), 2)
    rng = np.random.default_rng(7)
    noise = rng.integers(-3, 4, (H, W, 1), dtype=np.int16)
    im = np.clip(im.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    p = os.path.join(OUT, 'roof_seam.png')
    cv2.imwrite(p, im)
    print('wrote', p)


def make_school_stone():
    """北入口校名景石 (2048x768)：细腻浅灰天然花岗岩纹理 + 官方“北京大学附属中学海口学校”书法字样。"""
    W, H = 2048, 768
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rng0 = np.random.default_rng(19)
    low = cv2.resize(rng0.normal(0, 1, (18, 48)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    mid = cv2.resize(rng0.normal(0, 1, (64, 160)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    fine = cv2.resize(rng0.normal(0, 1, (192, 512)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    wave = np.sin(yy * 0.028 + low * 2.0 + mid * 0.55) * 0.45 + low * 0.45 + fine * 0.18
    base = 166 + wave * 20
    rng = np.random.default_rng(11)
    grain = rng.normal(0, 5.5, (H, W))
    g = np.clip(base + grain, 90, 232).astype(np.uint8)
    arr = np.stack([g, g, np.clip(g.astype(int) + 2, 0, 255).astype(np.uint8)], axis=-1)
    pil = Image.fromarray(arr, mode='RGB')

    cal_path = os.path.join(ROOT, 'blender', 'textures', 'school_stone_calligraphy.png')
    if os.path.exists(cal_path):
        cal = Image.open(cal_path)
        cw, ch = cal.size
        tw = int(W * 0.75)
        th = int(ch * (tw / cw))
        cal_s = cal.resize((tw, th), Image.Resampling.LANCZOS)
        c_arr = np.array(cal_s)
        alpha = c_arr[:, :, 3].astype(np.float32) / 255.0
        
        crimson_rgb = (148, 22, 22)
        shadow_rgb = (60, 52, 52)
        t_arr = np.zeros((th, tw, 4), dtype=np.uint8)
        for i in range(3): t_arr[:, :, i] = crimson_rgb[i]
        t_arr[:, :, 3] = (alpha * 255).astype(np.uint8)
        text_layer = Image.fromarray(t_arr, 'RGBA')
        
        s_arr = np.zeros((th, tw, 4), dtype=np.uint8)
        for i in range(3): s_arr[:, :, i] = shadow_rgb[i]
        s_arr[:, :, 3] = (alpha * 210).astype(np.uint8)
        shadow_layer = Image.fromarray(s_arr, 'RGBA')
        
        tx = (W - tw) // 2
        ty = int(H * 0.46) - th // 2
        pil.paste(shadow_layer, (tx + 3, ty + 3), shadow_layer)
        pil.paste(text_layer, (tx, ty), text_layer)
    p = os.path.join(OUT, 'school_stone.png')
    pil.save(p)
    print('wrote', p, 'with authentic calligraphy')


def make_bleacher_slogan():
    """体育场看台前挡墙：浅灰混凝土 + 校训标语与五环装饰（official_19.jpg）。"""
    W, H = 1024, 192
    pil = Image.new('RGB', (W, H), (178, 179, 176))
    draw = ImageDraw.Draw(pil)
    for x in range(0, W, 128):
        draw.line([(x, 0), (x, H)], fill=(158, 159, 156), width=2)
    fp = find_cjk_font()
    font = ImageFont.truetype(fp, 42) if fp else ImageFont.load_default()
    text = '体育强则中国强    体育兴则中国兴'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, (H - th) // 2 - 4), text, font=font, fill=(72, 80, 88))
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
    """16 格建筑配景人物统一色板 (1024x64)：每格 64px 宽，单材质 UV 映射全员服饰与细节。
    0:  自然肤色(暖)   1:  自然肤色(浅)   2:  乌黑发色       3:  深棕发色
    4:  白校服上衣     5:  校服浅灰蓝领   6:  藏青校裤/短裤  7:  浅蓝教师衬衫
    8:  米白教师上衣   9:  深灰西裤       10: 活力蓝球衣     11: 活力红橙球衣
    12: 白色运动鞋     13: 深灰运动鞋     14: 藏青书包       15: 卡其/酒红书包
    """
    swatches = [
        (228, 188, 156),  # 0 warm skin
        (238, 204, 176),  # 1 light skin
        (36, 32, 32),     # 2 black hair
        (68, 48, 38),     # 3 dark brown hair
        (242, 245, 248),  # 4 white school uniform shirt
        (178, 194, 212),  # 5 collar / trim accent
        (36, 48, 76),     # 6 navy uniform pants / shorts
        (158, 188, 214),  # 7 teacher light blue shirt
        (230, 224, 210),  # 8 teacher cream shirt
        (62, 66, 74),     # 9 charcoal trousers
        (38, 108, 208),   # 10 blue sports jersey
        (216, 68, 52),    # 11 red/orange sports jersey
        (236, 238, 240),  # 12 white sneakers
        (72, 76, 82),     # 13 dark grey sneakers
        (46, 60, 92),     # 14 navy backpack
        (158, 72, 62),    # 15 burgundy/terracotta backpack
    ]
    W, H = 1024, 64
    sw = W // len(swatches)
    im = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(im)
    for i, col in enumerate(swatches):
        draw.rectangle([i * sw, 0, (i + 1) * sw - 1, H - 1], fill=col)
    p = os.path.join(OUT, 'people_palette.png')
    im.save(p)
    print('wrote', p)


def make_pool_water_normal():
    """生成 256x256 四方连续无缝水波法线贴图，赋予 50m 室内泳池细腻涟漪与高光反光。"""
    N = 256
    u = np.linspace(0, 2 * np.pi, N, endpoint=False)
    v = np.linspace(0, 2 * np.pi, N, endpoint=False)
    uu, vv = np.meshgrid(u, v)
    # 多方向周期正弦波叠加，确保四边严格无缝平铺
    h = (
        0.35 * np.sin(3 * uu + 2 * vv)
        + 0.25 * np.sin(5 * uu - 4 * vv + 1.1)
        + 0.20 * np.cos(7 * uu + 6 * vv + 2.3)
        + 0.12 * np.sin(11 * uu - 9 * vv + 0.7)
        + 0.08 * np.cos(13 * uu + 11 * vv)
    )
    dh_du = np.gradient(h, axis=1)
    dh_dv = np.gradient(h, axis=0)
    strength = 2.4
    nx = -dh_du * strength
    ny = -dh_dv * strength
    nz = np.ones_like(h)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= norm; ny /= norm; nz /= norm
    rgb = np.stack([(nx * 0.5 + 0.5), (ny * 0.5 + 0.5), (nz * 0.5 + 0.5)], axis=-1)
    bgr = (np.clip(rgb[..., ::-1], 0.0, 1.0) * 255).astype(np.uint8)
    p = os.path.join(OUT, 'pool_water_normal.png')
    cv2.imwrite(p, bgr)
    print('wrote', p)




def make_indoor_court_wood():
    """室内主篮球馆洁净枫木地板底纹 + 蓝三秒区 (1024x1024)，不再烘焙模糊旧白线（由 3D 矢量 Int_Sports_GymLines 承担，彻底消除双圈！）。"""
    W, H = 1024, 1024
    # 局部平面映射：x in [-15.0, 2.2] (宽 17.2 m), y in [-16.0, 16.0] (长 32.0 m)
    rng = np.random.default_rng(77)
    im = np.zeros((H, W, 3), dtype=np.uint8)
    # 浅暖枫木长条地板拼花（沿 Y 方向长木条）
    plank_w = 16
    plank_h = 96
    for x in range(0, W, plank_w):
        offset = int(rng.integers(0, plank_h))
        for y in range(-offset, H, plank_h):
            y0, y1 = max(0, y), min(H, y + plank_h)
            x1 = min(W, x + plank_w)
            tone = int(rng.integers(-11, 12))
            # BGR 暖浅枫木色
            col = np.clip(np.array([154 + tone, 194 + tone, 218 + tone]), 0, 255).astype(np.uint8)
            im[y0:y1, x:x1] = col
            if y0 > 0:
                im[y0:y0 + 1, x:x1] = (128, 164, 186)
        im[:, x:x + 1] = (132, 168, 190)
    noise = rng.integers(-4, 5, (H, W, 1), dtype=np.int16)
    im = np.clip(im.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # 主球场中心 x=-6.4 => u = (-6.4 - (-15.0)) / 17.2 = 0.500; 长 28 m 占 28/32 = 0.875
    def pt(lx, ly):
        u = (lx - (-15.0)) / 17.2
        v = (ly - (-16.0)) / 32.0
        px = int(round(u * W))
        py = int(round((1.0 - v) * H))
        return (px, py)
    # 南北浅蓝三秒区 (宽 4.9 m, 深 5.8 m)
    key_bgr = (196, 152, 108)
    for sgn in (1.0, -1.0):
        bl = sgn * 14.0
        yft = bl - sgn * 5.8
        cv2.rectangle(im, pt(-6.4 - 2.45, max(bl, yft)), pt(-6.4 + 2.45, min(bl, yft)), key_bgr, -1)
    p = os.path.join(OUT, 'indoor_court_wood.png')
    cv2.imwrite(p, im)
    print('wrote', p)


if __name__ == '__main__':
    make_sports_atlas()
    make_roof_seam()
    make_school_stone()
    make_bleacher_slogan()
    make_people_palette()
    make_pool_water_normal()
    make_indoor_court_wood()
