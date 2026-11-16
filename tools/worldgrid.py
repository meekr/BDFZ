"""把任一参考图（卫星或图纸）按 data/frames.json 重采样到统一的世界网格。

世界网格：+X 东、+Y 北；像素 (i, j) 中心 = (X0 + (j + 0.5) * res, Y1 - (i + 0.5) * res)。
"""
import os, json
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FR = json.load(open(os.path.join(ROOT, 'data', 'frames.json')))
EXTENT = (-330.0, -220.0, 330.0, 220.0)   # X0, Y0, X1, Y1


def frame(key):
    f = FR['sat'] if key == 'sat' else FR['frames'][key]
    return f, np.vstack([np.array(f['px_to_world']), [0, 0, 1]])


def world_to_grid(res, extent=EXTENT):
    X0, Y0, X1, Y1 = extent
    return np.array([[1 / res, 0, -X0 / res], [0, -1 / res, Y1 / res], [0, 0, 1]])


def grid_to_world(res, extent=EXTENT):
    return np.linalg.inv(world_to_grid(res, extent))


def warp(key, res=0.25, extent=EXTENT, img=None, interp=cv2.INTER_LINEAR, border=255):
    f, P2W = frame(key)
    if img is None:
        img = cv2.imread(os.path.join(ROOT, f['file']), cv2.IMREAD_UNCHANGED)
    M = world_to_grid(res, extent) @ P2W
    X0, Y0, X1, Y1 = extent
    W, H = int(round((X1 - X0) / res)), int(round((Y1 - Y0) / res))
    return cv2.warpAffine(img, M[:2], (W, H), flags=interp, borderValue=border if img.ndim == 2 else (border,) * 3)


def to_world(pts_px, res=0.25, extent=EXTENT):
    G = grid_to_world(res, extent)
    p = np.c_[np.asarray(pts_px, float), np.ones(len(pts_px))]
    return (p @ G.T)[:, :2]


def to_px(pts_w, res=0.25, extent=EXTENT):
    G = world_to_grid(res, extent)
    p = np.c_[np.asarray(pts_w, float), np.ones(len(pts_w))]
    return (p @ G.T)[:, :2]
