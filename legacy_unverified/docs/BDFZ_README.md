# 北京大学附属中学海口学校 · 3D 校园模型

以 **Crossboundaries 2024 建成版官方图纸 01–05 号** 为建模基准复原的参数化 3D 校园漫游展示。
卫星影像、OSM 与实景照片只用于复核比例、补充材质与立面；与图纸冲突时按图纸建模。

## 建模数据链（可复现）

```
04 号图 50 m 比例尺 → 34.00 px/m
        ↓ 04↔02 学术中心板形配准（缩放 0.4608 / 旋转 −36.75°）
02 号图 7.83 px/m  ← 03 号图跑道分道线间距（1.22 m 标准道宽）独立复核，偏差 −4%
        ├── scripts/trace.py        粗轮廓描图（容差 0.2 m）
        │     src/data/buildings/*.json   三栋外轮廓 + 庭院/天井洞口
        ├── scripts/trace_rooms.py  04 三层平面 → buildings/cloud_3f_rooms.json
        ├── scripts/trace_interior.py 03 首层大厅 → interiors.json（泳池/篮球馆/剧场定位）
        ├── scripts/trace_site.py   03 道路内缘 → site.json（用地 498×251、道路、6 处出入口）
        └── scripts/trace_courts.py 03 图场矩形 → courts.json（5 斜向小球场 + 3 标准场）
        ↓ 05 号剖面读数（±0.00 与 +23.50 两点标定 33.94 px/m）
src/data/levels.json        楼层与屋面标高
```

- `src/data/frames.json`：各图「图面像素 → 世界米」的仿射变换与残差
- `src/data/buildings/`：学术中心、宿舍、体育及艺术中心的平面轮廓与洞口
- `src/data/track.json`、`src/data/levels.json`：跑道参数与竖向标高
- `src/data/site.json`、`src/data/courts.json`：用地红线、道路、出入口与球场（均从图纸描出）
- `src/data/interiors.json`：室内泳池 / 篮球馆 / 剧场观众厅在 03 大厅内的定位
- `reports/align/`：叠图检查图、平面偏差与剖面标高统计（`metrics.md`）

页面里可以直接调出五张图纸做对照（顶栏「图纸叠加」循环切换）：

| 叠图 | 摆放方式 |
|---|---|
| 01 彩色总平面 | 按 `frames.json` 等比例铺在地面，白底压暗模型 |
| 03 总平面线稿 | 同上，`MultiplyBlending` 让白底透明 |
| **02 屋顶平面** | 铺在屋脊以上 1.5 m，屋顶轮廓与模型屋面重合 |
| **05 剖面**（顶栏「剖面 05」） | 竖直立在学术中心南北向剖切线上，楼层线与模型对齐 |
| 04 三层平面（顶栏「分层平面」） | 悬浮在 +12.50 m 楼板高度 |

![校园全貌](reports/shots/overview.png)

![01 彩色总平面按配准叠在模型上](reports/shots/plan-overlay.png)

实施细节与验收数据见 [`research/plans/实施记录_P0-P2.md`](research/plans/实施记录_P0-P2.md)，
图纸与其它资料的每一处不一致都记在 [`research/plans/现场差异表.md`](research/plans/现场差异表.md)，
`reports/` 里每份产物的用途与提交策略见 [`reports/README.md`](reports/README.md)。

## 技术栈与升级

- **构建工具**: [Vite](https://vitejs.dev/) 8.x（秒级开发服务器热更新与现代打包）
- **渲染引擎**: [Three.js](https://threejs.org/) 0.187.0（从旧版 r128 升级为现代 ES Modules）
- **单文件分发**: 集成 `vite-plugin-singlefile`，构建产物可作为独立离线单文件在任何浏览器中双击直接运行。

### Three.js 升级主要改动

1. **模块化重构**：全面采用 ES Module 规范，通过 `import * as THREE from 'three'` 及 `import { OrbitControls } from 'three/addons/controls/OrbitControls.js'` 管理依赖。
2. **色彩空间适配**：废弃 `outputEncoding = THREE.sRGBEncoding`，升级为 `outputColorSpace = THREE.SRGBColorSpace`。
3. **阴影映射优化**：将已移除的 `THREE.PCFSoftShadowMap` 升级为 `THREE.PCFShadowMap`。
4. **材质与贴图色彩空间**：图纸贴图加载流程统一配置 `colorSpace = THREE.SRGBColorSpace`，确保色彩还原精确无失真。

---

## 快速上手

### 1. 安装依赖
```bash
npm install
```

### 2. 启动本地开发服务器
```bash
npm run dev
```
打开浏览器访问控制台提示的地址（如 `http://localhost:5173`）即可享受即时热更新开发体验。

### 3. 构建发布
```bash
npm run build
```
构建命令会通过 Vite 进行生产打包，生成：
- `dist/index.html`（内嵌资源的高性能独立单文件 HTML，支持直接双击离线打开）

### 4. 预览构建产物
```bash
npm run preview
```

### 5. 图纸管线与对齐验收

```bash
npm run register        # 配准 01–05 → src/data/frames.json
npm run trace:all       # 场地/道路/球场/三栋建筑/三层房间 全部重描
npm run trace           # 只重描三栋建筑 → src/data/buildings/*.json
npm run verify:frames   # 01/03/04 叠回 02 的目视检查图
npm run check:align     # 建筑平面（↔02）＋ 剖面标高（↔05）＋ 球场摆位（渲染回检）→ reports/align/
npm run check:console   # 打开构建产物跑一遍交互，有运行期报错即失败
npm run shots           # 文档/README 用展示截图 → reports/shots/
python3 scripts/embed_sheets.py   # 生成 02/05 的内嵌叠图
python3 scripts/trace_rooms.py    # 从 04 提取三层房间低模
```

管线依赖 Python 3 + `opencv-python` + `numpy`；`check:align` 直接通过 CDP 驱动本机 Chrome
（不额外引入 Playwright/Puppeteer，可用 `CHROME_PATH` 指定其它浏览器路径）。

### 性能

场景做了静态几何合批（`src/geometry/batch.js`）：同材质的檐口带、竖挺、屋面格栅、
房间隔墙烘进 InstancedMesh，并用实例矩阵保留位置/旋转/尺寸；屋面构件合成一批后
仍统一参与剖切。draw call 由 **9,465 降到 217**，三角面由 84k 降到 31k。

### 调试接口

页面暴露 `window.__app`：`scene`、`camera`、`TARGETS`、`focus(id)`、
`setOrthoTop(bounds)`、`setLayers(ids)`、`setPlanOverlay(n, opacity)`、
`setFloorOverlay(on)`、`setSectionOverlay(on)`、`setCutaway(on)`、`setFlatRender(on)`，
供自动化与回归使用。

