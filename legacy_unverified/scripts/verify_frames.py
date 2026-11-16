"""用 frames.json 把 01/03/04 叠到 02 上，输出目视检查图。"""

import sys
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, REPORTS, load_sheet, read_json

def main():
    fr = read_json(DATA / "frames.json")
    g02 = load_sheet("02")
    H, W = g02.shape
    canvas = cv2.cvtColor(g02, cv2.COLOR_GRAY2BGR)
    colors = {"01": (0, 0, 220), "03": (0, 150, 0), "04": (200, 80, 0)}
    for key, col in colors.items():
        f = fr["frames"][key]
        a02 = np.array(fr["frames"]["02"]["affine"], dtype=np.float64)
        a = np.array(f["affine"], dtype=np.float64)
        # 该图 px -> 世界 -> 02 px
        world_to_02 = np.linalg.inv(a02)
        m = (world_to_02 @ a)[:2]
        g = load_sheet(key)
        warped = cv2.warpAffine(g, m.astype(np.float32), (W, H),
                                flags=cv2.INTER_LINEAR, borderValue=255)
        e = cv2.Canny(cv2.GaussianBlur(warped, (3, 3), 0), 55, 155)
        canvas[e > 0] = col
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = cv2.resize(canvas, None, fx=0.42, fy=0.42, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(REPORTS / "frames_overlay.png"), out)
    print("写入 reports/align/frames_overlay.png")

if __name__ == "__main__":
    main()
