# legacy_unverified/ —— 旧项目产物（可能有错）

来自 `/Users/perrylei/repos/BDFZ`（Three.js 版）。**这里的任何数值、坐标、标高、截图都未经独立核实**，
使用前必须在 `refs/` 的 A 级资料上重新量取或复核，复核结果写进 `docs/差异记录.md`。

| 内容 | 文件 | 可能的用途 | 已知风险 |
|---|---|---|---|
| 配准链 | `data/frames.json`、`reports/align/registration.json` | 各图像素→米的仿射变换，可作初值 | 04→02 旋转角 −36.75° 被旧项目自己标为"最弱一环"；旧计划曾写 35.8° |
| 建筑轮廓 | `data/buildings/{cloud,dorm,sports}.json` | 三栋主楼外轮廓与洞口 | 渲染与 02 的 IoU 只有 0.89–0.97，最大偏差 26 m |
| 学术中心三层房间 | `data/buildings/cloud_3f_rooms.json` | 隔墙低模参考 | 只含 >22 m² 的房间 |
| 场地 / 道路 / 入口 | `data/site.json` | 用地 498×251 m、6 个出入口 | 与官方面积差 −6.9% |
| 球场、跑道 | `data/courts.json`、`data/track.json` | 位置初值 | — |
| 标高 | `data/levels.json` | 楼层、屋面、场地标高 | 宿舍层高是"按 5 层均分"的推定值；01 图上学术中心标 4F/5F，与 levels 的分层要对照 |
| 室内场馆 | `data/interiors.json` | 泳池/篮球馆/剧场定位 | 按大厅居中摆放，属推断 |
| 描图脚本 | `scripts/*.py` | OpenCV 描图、配准的实现思路，可改写复用 | 依赖旧坐标系（Three.js Y 轴向上、Z 向南） |
| Three.js 几何 | `threejs_geometry/*.js` | 立面构件（檐口带、竖挺、斜柱）的做法参考 | 斜柱角度等为示意值 |
| 文档 | `docs/现场差异表.md`、`精细化提升计划.md`、`实施记录_P0-P2.md` | 旧项目的测量过程与结论 | 结论需复核 |
| 渲染截图 | `reports/shots/`、`reports/align/*overlay*.png` | 只用来看旧模型哪里不对 | **不可作为参考图** |

注意坐标系差异：旧项目是 Three.js（Y 向上，X 向东，Z 向南）；新项目在 Blender（Z 向上，X 向东，Y 向北）。
