"""P4 立面贴图：
- cloud_glass.png: 学术中心外立面玻璃窗格（wx_10/wx_14：1.5 m × 4.5 m，三排蓝灰玻璃）
- cloud_courtyard.png: 学术中心星形庭院内侧开敞外廊（wx_15/wx_23/wx_32：栏杆 + 白色圆廊柱 + 退进教室立面）
- dorm_window.png: 宿舍外墙（wx_27/wx_31/wx_34：白墙竖向窄窗 + 窗下深灰百叶 + 周期性开敞楼梯间/阳台栏杆）
- dorm_gallery.png: 宿舍大庭院内侧外廊（wx_26/wx_33：明快白色梁板柱 + 深灰竖杆栏杆 + 浅灰退进墙面）
输出 blender/textures/*.png。"""
import os, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'blender', 'textures'); os.makedirs(OUT, exist_ok=True)


def cloud_glass():
    W, H = 128, 384                      # 1.5 m × 4.5 m
    im = np.zeros((H, W, 3), np.uint8); im[:] = (118, 100, 80)      # BGR 蓝灰玻璃
    g = np.linspace(0, 1, H)[:, None, None]
    im = (im * (0.78 + 0.38 * g)).clip(0, 255).astype(np.uint8)
    frame = (52, 50, 48)
    cv2.rectangle(im, (0, 0), (W - 1, H - 1), frame, 6)
    for y in (int(H * 0.34), int(H * 0.68)):                          # 三排窗格
        cv2.line(im, (0, y), (W, y), frame, 4)
    cv2.imwrite(os.path.join(OUT, 'cloud_glass.png'), im)


def cloud_courtyard():
    """学术中心庭院内侧开敞外廊（wx_15、wx_23、wx_32）：1 跨 4.2 m × 1 层 4.5 m。"""
    W, H = 256, 288
    im = np.full((H, W, 3), (218, 218, 216), np.uint8)               # 浅灰白内退教室墙
    # 上部走廊阴影顶棚（深度感）
    im[0:int(H * 0.24), :] = (105, 108, 112)
    # 中部教室玻璃门窗（退进暗色）
    cv2.rectangle(im, (int(W * 0.14), int(H * 0.24)), (int(W * 0.72), int(H * 0.78)), (75, 72, 66), -1)
    for x in np.linspace(int(W * 0.14), int(W * 0.72), 4).astype(int):
        cv2.line(im, (x, int(H * 0.24)), (x, int(H * 0.78)), (48, 48, 48), 3)
    # 下部走廊楼面阴影
    im[int(H * 0.78):H, :] = (128, 130, 132)
    # 前景金属栏杆（离底 0..1.1 m = 约 28% 层高）
    rt = H - int(H * 0.30)
    cv2.line(im, (0, rt), (W, rt), (58, 60, 62), 4)
    for x in range(0, W, 6):
        cv2.line(im, (x, rt), (x, H), (72, 74, 76), 1)
    # 白色廊柱（每跨一根，靠近左缘）
    cv2.rectangle(im, (0, 0), (int(W * 0.09), H), (238, 238, 236), -1)
    cv2.line(im, (int(W * 0.09), 0), (int(W * 0.09), H), (195, 195, 193), 2)
    cv2.imwrite(os.path.join(OUT, 'cloud_courtyard.png'), im)


PX = 64   # 每米像素


def dorm_window():
    """宿舍外墙（wx_27、wx_31、wx_34）：1 单元 14.4 m（4 跨）× 1 层 3.6 m。
    包含 3 组竖向窄窗（窗下带深灰百叶）+ 1 组开敞楼梯间/阳台（深色凹进 + 竖杆栏杆）。"""
    W, H = int(14.4 * PX), int(3.6 * PX)
    im = np.full((H, W, 3), (242, 243, 244), np.uint8)               # 洁白外墙
    # 3 组竖向窄窗（分布在 x = 0..10.2 m，每 1.7 m 一扇 0.85 m 宽的竖窗）
    for cx_m in (1.0, 2.7, 4.4, 6.4, 8.1, 9.8):
        x0, x1 = int((cx_m - 0.42) * PX), int((cx_m + 0.42) * PX)
        yt = int(0.65 * PX)
        ym = int(2.15 * PX)      # 窗玻璃底
        yb = int(2.75 * PX)      # 百叶底
        im[yt:ym, x0:x1] = (108, 96, 84)                             # 蓝灰窗玻璃
        cv2.rectangle(im, (x0, yt), (x1, ym), (48, 48, 48), 3)
        im[ym:yb, x0:x1] = (72, 72, 74)                              # 窗下空调百叶
        for x in range(x0 + 4, x1, 6):
            cv2.line(im, (x, ym), (x, yb), (110, 110, 112), 2)
    # 右侧 1 组开敞楼梯间/共享阳台（x = 10.8..14.0 m，深色凹进 + 金属栏杆）
    bx0, bx1 = int(10.8 * PX), int(14.0 * PX)
    by0, by1 = int(0.45 * PX), int(3.35 * PX)
    im[by0:by1, bx0:bx1] = (52, 54, 56)
    rt = by1 - int(1.05 * PX)
    cv2.line(im, (bx0, rt), (bx1, rt), (90, 92, 95), 4)
    for x in range(bx0, bx1, 7):
        cv2.line(im, (x, rt), (x, by1), (115, 118, 120), 2)
    # 细微层间缝线
    cv2.line(im, (0, 0), (W, 0), (222, 223, 224), 2)
    cv2.imwrite(os.path.join(OUT, 'dorm_window.png'), im)


def dorm_gallery():
    """宿舍大庭院外廊（wx_26、wx_33）：明快白色框架梁柱 + 浅暖灰退进外廊 + 深灰金属栏杆。"""
    W, H = int(4.5 * PX), int(3.6 * PX)
    im = np.full((H, W, 3), (242, 243, 242), np.uint8)               # 白色结构梁柱
    # 退进走廊区域：浅灰白内墙 + 深色玻璃门，不再一片漆黑
    t_beam = int(0.55 * PX)
    w_col = int(0.42 * PX)
    im[t_beam:H, 0:W - w_col] = (178, 178, 174)                      # 走廊退进墙面（浅暖灰）
    im[t_beam:t_beam + int(0.42 * PX), 0:W - w_col] = (118, 118, 116)# 走廊顶棚阴影
    # 走廊内侧玻璃门窗
    gx0, gx1 = int(0.35 * PX), int(2.6 * PX)
    im[t_beam + int(0.35 * PX):H - int(0.3 * PX), gx0:gx1] = (86, 84, 78)
    for x in np.linspace(gx0, gx1, 4).astype(int):
        cv2.line(im, (x, t_beam + int(0.35 * PX)), (x, H - int(0.3 * PX)), (52, 52, 50), 3)
    # 栏杆（离底 1.05 m）
    rt = H - int(1.05 * PX)
    cv2.line(im, (0, rt), (W - w_col, rt), (58, 60, 62), 4)
    for x in range(0, W - w_col, 7):
        cv2.line(im, (x, rt), (x, H), (75, 77, 80), 2)
    cv2.imwrite(os.path.join(OUT, 'dorm_gallery.png'), im)


if __name__ == '__main__':
    cloud_glass(); cloud_courtyard(); dorm_window(); dorm_gallery(); print('ok')
