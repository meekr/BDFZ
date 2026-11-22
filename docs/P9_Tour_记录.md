# P9 记录：第一人称视角校园 Tour（室外场地 + 建筑外围 + 6 大核心室内）

日期：2026-11-22　状态：**完成，全链路验收通过**

## 一、核心交付成果

1. **分包流式 GLB 架构（[export_chunks.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/export_chunks.py)）**：
   - 室外主包 `web/public/bdfz.glb`：**0.788 MB**（1,303 对象，48 ms 首屏加载）
   - 体育及艺术中心室内包 `web/public/interior_sports.glb`：**0.105 MB**（275 对象，按需懒加载）
   - 学术中心室内包 `web/public/interior_cloud.glb`：**0.033 MB**（105 对象，按需懒加载）
   - 宿舍示范单元包 `web/public/interior_dorm.glb`：**0.011 MB**（21 对象，按需懒加载）
   - 轻量化步行碰撞导航包 `web/public/nav_collision.glb`：**0.002 MB**（[nav_collision.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/nav_collision.py)）
   - 5 个分包合计仅 **0.94 MB**（远低于 25 MB 预算），所有家具/座椅/灯具/篮架均走 `EXT_mesh_gpu_instancing`。

2. **室外步行连通与外壳破壳**：
   - 按 [nav_ramps.json](file:///Users/perrylei/repos/BDFZ_V3/data/nav_ramps.json) 在 [site.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/site.py) 补建 5 处高低差衔接坡道/台阶与护栏，打通全园连续步行流线；
   - 体育及艺术中心（[bldg_sports.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/bldg_sports.py)）与学术中心图书馆/展厅/3F 北翼（[bldg_cloud.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/bldg_cloud.py)）升级为半透明玻璃幕墙 + 可步行门洞，内外视野通透。

3. **6 大核心室内建模**：
   - **体育及艺术中心（[interior_sports.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/interior_sports.py)）**：双室内篮球馆（原木主赛场 + 浅蓝训练场 + 空间钢网架屋顶 + 20 盏高棚灯 + 4 篮架 + 伸缩看台）、50 m 8 道恒温游泳馆（碧蓝池水 + 泳道线 + 16 出发台 + 观赛看台）、艺术中心大剧场（216 张实例化暗红绒面座椅 + 12 级坡地 + 深木舞台 + 三联发光大屏）、首层门厅；
   - **学术中心（[interior_cloud.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/interior_cloud.py)）**：星形庭院底层开放图书馆（12 组书架 + 6 阅览桌 + 阶梯读书角）、西侧艺术馆展厅（4 挂画墙 + 3 雕塑展台）、3F 开放社交走廊与 6 间示范教室（2 常规教室 + 2 圆桌研讨室 + 1 理科实验室 + 1 教师办公室，依据 `05_cloud_3f.jpg` V3 标定坐标）；
   - **宿舍综合楼（[interior_dorm.py](file:///Users/perrylei/repos/BDFZ_V3/blender/build/interior_dorm.py)）**：依据 `09_高中宿舍 1` 轴测图还原 2F 高中示范单元（4 间 2 人寝室含 8 套实例化上床下桌 + 木格栅门 + 8 人共享休闲厅 + 干湿分离公共卫浴 + 庭院外廊）。

4. **双模网页漫游交互（`web/src/tour/` + [main.js](file:///Users/perrylei/repos/BDFZ_V3/web/src/main.js)）**：
   - 顶部一键切换 **`鸟瞰浏览`** | **`第一人称漫游`**（支持 `?mode=fps&stop=<id>` 直达）；
   - 支持 **WASD/方向键步行 + 拖拽转视角 + 地面点击光环平滑瞬移 + 移动端虚拟摇杆**；
   - 配套 **实时迷你小地图**（标示位置与视野扇形、点击彩点直跳）、**12 站底部导览条**（含自动巡游）、以及 **实景照片对照弹窗**（`web/public/photos/*.webp`）。

## 二、实机浏览器验收数据

| 场景 / 视点 | 帧率 | Draw Calls（≤ 300） | 三角面数 | 说明 |
|---|---|---|---|---|
| 鸟瞰浏览 | 119–120 fps | 288 | 478k | 首屏 `bdfz.glb` 仅 48 ms |
| 北门校名石（一人称） | 77–120 fps | 239 | 473k | 室外人视校名石与主台阶 |
| 双室内篮球馆（室内） | 120 fps | 165 | 401k | 懒加载 `interior_sports.glb` (200) |
| 50 m 恒温游泳馆（室内） | 120 fps | 185 | 404k | 8 泳道碧蓝水面 + 室外树景穿透 |
| 艺术中心大剧场（室内） | 120 fps | 144 | 449k | 216 座实例座椅 + 三联大屏 |
| 图书馆（室内） | 120 fps | 166 | 463k | 懒加载 `interior_cloud.glb` (200) |
| 学术中心 3F 教室与外廊 | 120 fps | 179 | 471k | 社交走廊储物柜 + 研讨室 |
| 高中示范宿舍单元（室内） | 120 fps | 137 | 397k | 懒加载 `interior_dorm.glb` (200) |

- 控制台报错：**0**；生产构建 `cd web && npm run build` 零错误通过。
