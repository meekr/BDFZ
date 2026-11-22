"""T4 宿舍综合楼高中示范单元（独立 Interior_Dorm 集合，导出 web/public/interior_dorm.glb）：
依据 09_dorm_plan.jpg 与 09_高中宿舍 1（单元轴测剖切），在第 2 座大庭院北侧 2F (cx=164, cy=-52.5, Z=3.4..6.9 m, ang=-9°) 完整还原：
- 4 间 2 人寝室（木格栅半透推拉门 + 8 套实例化上床下桌/衣柜模块）
- 8 人共享休闲自习厅（面向大庭院的落地窗 + 长木学习桌 + 模块坐凳）
- 干湿分离公共卫浴间（长洗手台镜面 + 4 间独立淋浴/厕位隔间）
- 半开放式庭院外廊衔接室外折跑钢楼梯

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/interior_dorm.py').read())
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
TEX = os.path.join(ROOT, 'blender', 'textures')
COLL = 'Interior_Dorm'


def ensure_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def atlas_mat():
    return bpy.data.materials.get('M_Int_Atlas')


def wood_mat():
    return bpy.data.materials.get('M_Int_WoodFloor') or atlas_mat()


def glass_mat():
    return bpy.data.materials.get('M_SportsGlass') or atlas_mat()


def add_uv_box(bm, uvl, sw, p0, p1, mat_idx=0):
    u = (sw + 0.5) / 16.0
    x0, y0, z0 = p0; x1, y1, z1 = p1
    vs = [bm.verts.new(p) for p in (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )]
    for q in (
        (vs[0], vs[3], vs[2], vs[1]), (vs[4], vs[5], vs[6], vs[7]),
        (vs[0], vs[1], vs[5], vs[4]), (vs[1], vs[2], vs[6], vs[5]),
        (vs[2], vs[3], vs[7], vs[6]), (vs[3], vs[0], vs[4], vs[7]),
    ):
        f = bm.faces.new(q)
        f.material_index = mat_idx
        for lp in f.loops:
            lp[uvl].uv = (u, 0.5)


def loft_bed_mesh():
    """宿舍组合式上床下桌+衣柜原型（2.0 m 长 × 0.95 m 宽 × 2.15 m 高，实例化）。"""
    old = bpy.data.meshes.get('Int_Dorm_LoftBedUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 四根木立柱 + 上铺床板与护栏 + 米色床垫与枕头
    for px in (-0.98, 0.92):
        for py in (-0.46, 0.40):
            add_uv_box(bm, uvl, 2, (px, py, 0.0), (px + 0.06, py + 0.06, 2.15))
    add_uv_box(bm, uvl, 2, (-0.98, -0.46, 1.55), (0.98, 0.46, 1.62))      # 床板
    add_uv_box(bm, uvl, 10, (-0.94, -0.42, 1.62), (0.94, 0.42, 1.78))     # 柔和米色床垫
    add_uv_box(bm, uvl, 0, (-0.88, -0.32, 1.78), (-0.48, 0.32, 1.90))     # 白色枕头
    add_uv_box(bm, uvl, 2, (-0.98, -0.46, 1.78), (0.98, -0.42, 2.08))     # 上铺安全护栏
    # 下方书桌 + 书架 + 右侧衣柜
    add_uv_box(bm, uvl, 2, (-0.96, -0.42, 0.72), (0.35, 0.42, 0.77))      # 书桌面
    add_uv_box(bm, uvl, 2, (0.35, -0.44, 0.0), (0.96, 0.44, 1.55))        # 整体衣柜
    add_uv_box(bm, uvl, 11, (-0.50, -0.68, 0.42), (-0.08, -0.26, 0.47))   # 椅子面
    add_uv_box(bm, uvl, 6, (-0.46, -0.64, 0.0), (-0.12, -0.30, 0.42))     # 椅腿
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Int_Dorm_LoftBedUnit')
    bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    return me


def main():
    c = ensure_coll(COLL)
    cx, cy, z0, ang = 163.0, -49.5, 3.45, -9.0
    H = 3.35
    a = math.radians(ang); ca, sa = math.cos(a), math.sin(a)
    def wloc(lx, ly, lz=0.0):
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, z0 + lz)

    # 1. 示范单元整体地板、隔墙、木格栅门、共享厅家具与干湿分离卫浴
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 主体浅灰/木地板 + 白色吊顶（24×11 m）
    add_uv_box(bm, uvl, 1, (-12.0, -5.5, -0.12), (12.0, 5.5, 0.0))
    add_uv_box(bm, uvl, 0, (-12.0, -5.5, H - 0.12), (12.0, 5.5, H))
    # 北侧外墙 & 东西端墙
    add_uv_box(bm, uvl, 0, (-12.0, 5.2, 0.0), (12.0, 5.5, H))
    add_uv_box(bm, uvl, 0, (-12.0, -5.5, 0.0), (-11.7, 5.5, H))
    add_uv_box(bm, uvl, 0, (11.7, -5.5, 0.0), (12.0, 5.5, H))
    # 4 间 2 人寝室隔墙（x in [-11.5, +4.5]，每间宽 4.0 m × 深 4.4 m，y in [0.8, 5.2]）
    for xi in (-11.5, -7.5, -3.5, 0.5, 4.5):
        add_uv_box(bm, uvl, 0, (xi - 0.09, 0.8, 0.0), (xi + 0.09, 5.2, H))
    # 每间寝室面向共享厅的木格栅推拉门框（左侧留 1.5 m 敞开门洞便于走入！）
    for i in range(4):
        xa = -11.5 + i * 4.0
        add_uv_box(bm, uvl, 2, (xa + 1.6, 0.72, 0.0), (xa + 3.9, 0.88, H))  # 暖木格栅隔断
        add_uv_box(bm, uvl, 2, (xa, 0.72, 2.25), (xa + 1.6, 0.88, H))       # 门头过梁

    # 8 人共享休闲自习厅（x in [-11.5, +4.5], y in [-2.6, +0.8]）：木长桌 + 休闲方凳（还原 09_高中宿舍 1 轴测图）
    add_uv_box(bm, uvl, 2, (-8.5, -1.6, 0.72), (-1.5, -0.5, 0.78))
    add_uv_box(bm, uvl, 6, (-8.2, -1.5, 0.0), (-8.1, -0.6, 0.72))
    add_uv_box(bm, uvl, 6, (-1.9, -1.5, 0.0), (-1.8, -0.6, 0.72))
    for xi in (-7.5, -5.8, -4.1, -2.4):
        add_uv_box(bm, uvl, 10, (xi - 0.25, -2.05, 0.0), (xi + 0.25, -1.65, 0.45))
        add_uv_box(bm, uvl, 10, (xi - 0.25, -0.45, 0.0), (xi + 0.25, -0.05, 0.45))
    # 共享厅东侧软装模块坐凳
    for bx, by in ((1.2, -1.2), (2.4, -1.6), (3.1, -0.5)):
        add_uv_box(bm, uvl, 11, (bx - 0.35, by - 0.35, 0.0), (bx + 0.35, by + 0.35, 0.44))

    # 干湿分离公共卫浴间（x in [+4.8, +11.6], y in [-2.4, +5.2]）：洗手台 + 4 间独立隔间
    add_uv_box(bm, uvl, 0, (4.7, -2.4, 0.0), (4.9, 1.0, H))
    add_uv_box(bm, uvl, 0, (5.1, -2.1, 0.0), (11.2, -1.4, 0.85))        # 白色长洗手台
    add_uv_box(bm, uvl, 15, (5.2, -2.25, 1.0), (11.0, -2.18, 2.15))     # 长镜面
    for s in range(4):
        sx = 5.4 + s * 1.55
        add_uv_box(bm, uvl, 1, (sx - 0.05, 1.8, 0.0), (sx + 0.05, 5.1, 2.2))

    # 面向大庭院的半开放外廊栏杆 (y = -5.3)
    add_uv_box(bm, uvl, 6, (-11.8, -5.4, 0.98), (11.8, -5.25, 1.08))
    for xi in range(-11, 12, 2):
        add_uv_box(bm, uvl, 6, (xi - 0.04, -5.38, 0.0), (xi + 0.04, -5.28, 1.05))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Int_Dorm_UnitShell'); bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    o = bpy.data.objects.new('Int_Dorm_UnitShell', me)
    o.location = (cx, cy, z0); o.rotation_euler = (0.0, 0.0, a)
    c.objects.link(o)

    # 8 套实例化上床下桌组合（4 间 2 人寝室，每间左右各 1 套）
    bed_me = loft_bed_mesh()
    idx = 0
    for i in range(4):
        xa = -11.5 + i * 4.0
        for dx, rdeg in ((0.65, 90.0), (3.35, -90.0)):
            bo = bpy.data.objects.new(f'Int_Dorm_Bed_{idx:02d}', bed_me)
            bo.location = wloc(xa + dx, 3.0, 0.0)
            bo.rotation_euler = (0.0, 0.0, math.radians(ang + rdeg))
            c.objects.link(bo); idx += 1

    # 室内照明灯具（实例化）
    lm = bpy.data.meshes.get('Interior_LampUnit')
    if lm:
        l_idx = 0
        for xi in (-9.5, -5.5, -1.5, 2.5, 8.0):
            for yi in (-1.0, 3.0):
                lo = bpy.data.objects.new(f'Int_Dorm_Lamp_{l_idx:02d}', lm)
                lo.location = wloc(xi, yi, H - 0.16)
                lo.rotation_euler = (0.0, 0.0, a)
                c.objects.link(lo); l_idx += 1

    bpy.ops.wm.save_mainfile()
    print('Interior_Dorm objects:', len(c.objects))


main()
