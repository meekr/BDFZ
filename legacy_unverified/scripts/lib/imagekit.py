"""图像读取、缩放与边缘提取工具（P0 配准与描图共用）。"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HIRES = ROOT / "research" / "plans" / "hires"
DATA = ROOT / "src" / "data"
REPORTS = ROOT / "reports" / "align"

# 1.1 五张基准图（高清版）
SHEETS = {
    "01": "02_color_site.jpg",
    "02": "03_roof_plan.jpg",
    "03": "04_line_site.jpg",
    "04": "05_cloud_3f.jpg",
    "05": "06_cloud_section.jpg",
}


def load_sheet(key: str, gray: bool = True) -> np.ndarray:
    path = HIRES / SHEETS[key]
    flag = cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR
    img = cv2.imread(str(path), flag)
    if img is None:
        raise FileNotFoundError(path)
    return img


def resize_to_width(img: np.ndarray, width: int) -> np.ndarray:
    h, w = img.shape[:2]
    height = int(round(h * width / w))
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def edges(img: np.ndarray, low: int = 40, high: int = 110, blur: float = 1.2) -> np.ndarray:
    g = cv2.GaussianBlur(img, (5, 5), blur)
    e = cv2.Canny(g, low, high)
    return cv2.dilate(e, np.ones((3, 3), np.uint8)).astype(np.float32) / 255.0


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
