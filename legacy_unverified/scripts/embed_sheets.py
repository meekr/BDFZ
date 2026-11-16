"""把 02 屋顶平面与 05 剖面压成可内嵌的 base64 JPEG（供页面里的叠图使用）。

为什么单独做：
  - 01/03/04 已经有内嵌底图（plan_b64 / plan_line_b64 / plan_3f_b64）；
  - 02 与 05 是这次新增的叠图对象，需要等比例、按 frames.json 摆放；
  - 线稿/剖面在页面里用 MultiplyBlending 叠（白底自动透明），
    所以这里保留白底、不要做成透明 PNG。

输出：src/data/sheet_02_b64.json、src/data/sheet_05_b64.json
用法：python3 scripts/embed_sheets.py
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.imagekit import DATA, HIRES, write_json

TARGETS = {
    "02": {"file": "03_roof_plan.jpg", "width": 2000, "quality": 82},
    "05": {"file": "06_cloud_section.jpg", "width": 1800, "quality": 82},
}


def main() -> int:
    for sheet, spec in TARGETS.items():
        src = HIRES / spec["file"]
        im = Image.open(src).convert("RGB")
        w, h = im.size
        scale = spec["width"] / w
        im = im.resize((spec["width"], max(1, int(round(h * scale)))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=spec["quality"], optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        out = DATA / f"sheet_{sheet}_b64.json"
        write_json(out, {
            "sheet": sheet,
            "source": f"research/plans/hires/{spec['file']}",
            "size": [im.size[0], im.size[1]],
            "data": "data:image/jpeg;base64," + b64,
        })
        print(f"{sheet}: {im.size[0]}×{im.size[1]} → {out.name} "
              f"({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
