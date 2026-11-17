"""P4 立面贴图：学术中心玻璃窗格（1 跨 = 1.5 m 宽 × 1 层高）、宿舍窗。输出 blender/textures/*.png。"""
import os, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'blender', 'textures'); os.makedirs(OUT, exist_ok=True)


def cloud_glass():
    W, H = 128, 384                      # 1.5 m × 4.5 m
    im = np.zeros((H, W, 3), np.uint8); im[:] = (120, 104, 84)      # BGR 蓝灰玻璃
    g = np.linspace(0, 1, H)[:, None, None]
    im = (im * (0.8 + 0.35 * g)).clip(0, 255).astype(np.uint8)       # 上暗下亮的天空反射
    frame = (60, 58, 56)
    cv2.rectangle(im, (0, 0), (W - 1, H - 1), frame, 6)              # 竖梃 + 上下框
    for y in (int(H * 0.36), int(H * 0.70)):                          # 横档（wx_10：三排窗格）
        cv2.line(im, (0, y), (W, y), frame, 4)
    cv2.imwrite(os.path.join(OUT, 'cloud_glass.png'), im)


PX = 64   # 每米像素


def dorm_window():
    """宿舍外墙（wx_11）：白墙 + 深色窗，1 跨 3.6 m × 1 层 3.6 m；窗 2.6 × 2.0 m，离地 1.2 m。"""
    W = H = int(3.6 * PX)
    im = np.full((H, W, 3), 236, np.uint8)
    x0, x1 = int(0.5 * PX), int(3.1 * PX); yb, yt = H - int(1.2 * PX), H - int(3.2 * PX)
    im[yt:yb, x0:x1] = (70, 62, 55)
    im[yt:yt + int(0.5 * PX), x0:x1] = (150, 150, 148)          # 上部灰色窗槛板
    for x in np.linspace(x0, x1, 5).astype(int):
        cv2.line(im, (x, yt), (x, yb), (40, 40, 40), 3)
    cv2.imwrite(os.path.join(OUT, 'dorm_window.png'), im)


def dorm_gallery():
    """宿舍庭院侧（wx_33）：外廊。上部深色凹进，0–1.1 m 栏杆，顶部 0.5 m 白色楼板边。"""
    W = H = int(3.6 * PX)
    im = np.full((H, W, 3), 240, np.uint8)
    im[int(0.5 * PX):H, :] = (95, 92, 88)
    rt = H - int(1.1 * PX)
    cv2.line(im, (0, rt), (W, rt), (45, 45, 45), 4)
    for x in range(0, W, int(0.12 * PX)):
        cv2.line(im, (x, rt), (x, H), (55, 55, 55), 1)
    cv2.rectangle(im, (W - int(0.4 * PX), int(0.5 * PX)), (W, H), (232, 232, 230), -1)   # 柱
    cv2.imwrite(os.path.join(OUT, 'dorm_gallery.png'), im)


if __name__ == '__main__':
    cloud_glass(); dorm_window(); dorm_gallery(); print('ok')
