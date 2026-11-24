"""T1–T5 轻量化步行碰撞与瞬移导航网（Nav_Collision 集合 → 导出 web/public/nav_collision.glb）：
- Nav_Walkable_*：平滑连续可行走表面（所有阶梯转为顺滑斜坡面，确保 Capsule+Octree 无卡顿上阶与 Click-to-Teleport 精准落点）
- Nav_Blocker_*：泳池池口边界等防跌落隐形护栏
"""
import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ'
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
CY = json.load(open(os.path.join(ROOT, 'data', 'cloud_courtyard.json')))
RAMPS = json.load(open(os.path.join(ROOT, 'data', 'nav_ramps.json')))
COLL = 'Nav_Collision'


def ensure_coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def add_quad(bm, pts):
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.normal_update()
    if f.normal.z < 0:
        f.normal_flip()


def add_rect(bm, cx, cy, w, l, z, ang_deg=0.0):
    a = math.radians(ang_deg); ca, sa = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-w/2, -l/2), (w/2, -l/2), (w/2, l/2), (-w/2, l/2)):
        pts.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca, z))
    add_quad(bm, pts)


def add_poly(bm, poly, z):
    vs = [bm.verts.new((x, y, z)) for x, y in poly]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.z < 0:
        f.normal_flip()
    bmesh.ops.triangulate(bm, faces=[f])


def add_ramp(bm, p0, p1, width):
    v0, v1 = Vector(p0), Vector(p1)
    d = Vector((v1.x - v0.x, v1.y - v0.y, 0))
    L = d.length
    if L < 0.2:
        return
    n = Vector((-d.y / L * width * 0.5, d.x / L * width * 0.5, 0))
    add_quad(bm, [v0 - n, v0 + n, v1 + n, v1 - n])


def build_walkable(c):
    bm = bmesh.new()
    # 1. 室外自然地坪与北广场 (Z = -6.0)
    add_rect(bm, -45.0, -45.0, 520.0, 290.0, -5.98)
    # 2. 北入口主大台阶等效平滑步行坡道 (y=36 Z=-6 → y=10 Z=0, x=-34..+2)
    add_quad(bm, [(-34, 36, -5.98), (2, 36, -5.98), (2, 10, 0.04), (-34, 10, 0.04)])
    # 3. 学术中心地坪与星形庭院 (Z = 0.04)
    add_rect(bm, 0.0, -60.0, 145.0, 140.0, 0.08)
    # 4. 星形庭院扇形大台阶平滑斜坡 (y=-55 Z=0.04 → y=-69.5 Z=4.5)
    gs = CY['grand_stairs']
    b0, b1 = gs['bot_edge']; t0, t1 = gs['top_edge']
    add_quad(bm, [(b0[0], b0[1], 0.04), (b1[0], b1[1], 0.04), (t1[0], t1[1], 4.52), (t0[0], t0[1], 4.52)])
    # 5. 图书馆露台 (Z = 4.52) 与东露台 (Z = 3.82)
    add_poly(bm, CY['library_terrace']['polygon'], 4.52)
    add_poly(bm, CY['east_terrace']['polygon'], 3.82)
    # 6. 操场与球场抬高平台 (Z = 0.12)
    add_rect(bm, -195.0, -8.0, 195.0, 195.0, 0.12)
    # 看台前缘可走阶梯坡道
    add_ramp(bm, (-201.97, -78.62, 0.12), (-207.99, -80.78, 4.42), 68.0)
    # 7. 宿舍区平台与东北篮球场 (Z = -0.10)
    add_rect(bm, 150.0, -45.0, 110.0, 268.0, -0.10)
    # 8. 补齐的全部台地连接坡道 (data/nav_ramps.json)
    for r in RAMPS.get('ramps', []):
        add_ramp(bm, r['p0'], r['p1'], r['width'])

    # --- 室内可行走楼面 ---
    # 9. 体育中心：首层大厅 + 双篮球馆 + 泳池四周甲板 (Z = -5.92) + 大剧场阶梯坡面
    add_rect(bm, -180.0, -154.0, 42.0, 28.0, -5.92)                   # 门厅
    add_rect(bm, -235.5, -73.0, 31.0, 37.0, -5.90, 19.7)              # 双篮球馆
    # 泳池四周甲板（避开 20×48 m 水池池口！）
    for lx, ly, w, l in ((-11.75, 0, 3.2, 55.0), (11.75, 0, 3.2, 55.0), (0, -25.8, 26.0, 3.8), (0, 25.8, 26.0, 3.8)):
        a = math.radians(19.7); ca, sa = math.cos(a), math.sin(a)
        add_rect(bm, -214.0 + lx * ca - ly * sa, -133.0 + lx * sa + ly * ca, w, l, -5.90, 19.7)
    # 大剧场观众席斜坡 (Z=-5.75 → -2.05) + 舞台面 (Z=-4.92)
    a_t = math.radians(33.5); ct, st = math.cos(a_t), math.sin(a_t)
    def tp(lx, ly, lz): return (-131.0 + lx * ct - ly * st, -138.0 + lx * st + ly * ct, -5.92 + lz)
    add_quad(bm, [tp(-10, -5.5, 0.18), tp(10, -5.5, 0.18), tp(10, 15.0, 3.95), tp(-10, 15.0, 3.95)])
    add_quad(bm, [tp(-9.2, -16.2, 1.02), tp(9.2, -16.2, 1.02), tp(9.2, -8.5, 1.02), tp(-9.2, -8.5, 1.02)])

    # 10. 学术中心：图书馆(Z=0.06)、艺术馆展厅(Z=0.06)、3F 全北翼教室与外廊(Z=12.55)
    add_rect(bm, -22.0, -85.5, 35.0, 24.0, 0.08)                      # 图书馆
    add_rect(bm, -33.0, -50.2, 9.5, 15.0, 0.08)                       # 艺术馆展厅
    add_rect(bm, 2.0, -4.0, 67.0, 23.5, 12.55)                        # 3F 北翼外廊与 6 间示范教室

    # 11. 宿舍综合楼 2F 高中示范单元 (Z=3.46)
    add_rect(bm, 164.0, -52.5, 23.5, 10.5, 3.46, -9.0)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Nav_Walkable')
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new('Nav_Walkable', me)
    o['nav'] = 'walkable'
    c.objects.link(o)


def main():
    c = ensure_coll()
    build_walkable(c)
    bpy.ops.wm.save_mainfile()
    print('Nav_Collision built:', [o.name for o in c.objects])


main()
