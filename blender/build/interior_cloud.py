"""T3 学术中心内部精建（独立 Interior_Cloud 集合，导出 web/public/interior_cloud.glb）：
1. 星形庭院底层图书馆（Z=0.04..4.15 m，通用 Crossboundaries 开放风格）：木地板、16 组实例化书架与书脊、8 张阅览长桌与 32 把椅子、阶梯木质读书角、服务台
2. 西侧艺术馆展厅（Z=0.04..3.1 m）：白墙展厅、6 组画框展板、3 座中央雕塑展台
3. 学术中心 3F 开放社交长廊与北翼 6 间示范教室（依据 05_cloud_3f.jpg，Z=12.5..16.2 m）：
   常规教室×2、圆桌研讨室×2、理科/创客实验室×1、教师办公室×1 + 走廊储物柜与卡座

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ/blender/build/interior_cloud.py').read())
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ'
TEX = os.path.join(ROOT, 'blender', 'textures')
COLL = 'Interior_Cloud'


def ensure_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def atlas_mat():
    m = bpy.data.materials.get('M_Int_Atlas')
    if m is None:
        m = bpy.data.materials.new('M_Int_Atlas')
        m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
        tex = nt.nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load(os.path.join(TEX, 'interior_atlas.png'), check_existing=True)
        img.reload(); tex.image = img; tex.interpolation = 'Closest'
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.72
    return m


def wood_mat():
    m = bpy.data.materials.get('M_Int_WoodFloor')
    if m is None:
        m = bpy.data.materials.new('M_Int_WoodFloor')
        m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
        tex = nt.nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load(os.path.join(TEX, 'wood_floor.png'), check_existing=True)
        img.reload(); tex.image = img
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.42
    return m


def glass_mat():
    return bpy.data.materials.get('M_SportsGlass') or atlas_mat()


def lamp_me():
    return bpy.data.meshes.get('Interior_LampUnit')


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


def make_proto(name, builder):
    old = bpy.data.meshes.get(name)
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    builder(bm, uvl)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    return me


def build_protos():
    def bookshelf(bm, uvl):
        # 双面原木书架 2.4m 宽 × 0.5m 深 × 2.1m 高，含彩色书脊条块
        add_uv_box(bm, uvl, 2, (-1.2, -0.25, 0.0), (-1.12, 0.25, 2.1))
        add_uv_box(bm, uvl, 2, (1.12, -0.25, 0.0), (1.2, 0.25, 2.1))
        add_uv_box(bm, uvl, 2, (-0.04, -0.25, 0.0), (0.04, 0.25, 2.1))
        colors = (11, 12, 13, 5, 4, 10)
        for s in range(5):
            zs = 0.14 + s * 0.40
            add_uv_box(bm, uvl, 2, (-1.14, -0.25, zs), (1.14, 0.25, zs + 0.04))
            for k in range(6):
                bx0 = -1.06 + k * 0.35
                add_uv_box(bm, uvl, colors[(s + k) % len(colors)],
                           (bx0, -0.18, zs + 0.04), (bx0 + 0.28, 0.18, zs + 0.31))

    def desk_set(bm, uvl):
        # 单人课桌 + 座椅组合（0.70 × 0.50 m）
        add_uv_box(bm, uvl, 6, (-0.33, -0.22, 0.0), (-0.29, -0.18, 0.72))
        add_uv_box(bm, uvl, 6, (0.29, -0.22, 0.0), (0.33, -0.18, 0.72))
        add_uv_box(bm, uvl, 6, (-0.33, 0.18, 0.0), (-0.29, 0.22, 0.72))
        add_uv_box(bm, uvl, 6, (0.29, 0.18, 0.0), (0.33, 0.22, 0.72))
        add_uv_box(bm, uvl, 2, (-0.36, -0.25, 0.72), (0.36, 0.25, 0.76))
        # 椅面与椅背
        add_uv_box(bm, uvl, 6, (-0.20, -0.62, 0.0), (-0.16, -0.34, 0.44))
        add_uv_box(bm, uvl, 6, (0.16, -0.62, 0.0), (0.20, -0.34, 0.44))
        add_uv_box(bm, uvl, 11, (-0.22, -0.64, 0.43), (0.22, -0.32, 0.48))
        add_uv_box(bm, uvl, 11, (-0.22, -0.66, 0.48), (0.22, -0.60, 0.84))

    def round_table(bm, uvl):
        # 研讨圆桌 + 4 把围坐椅
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.14, radius2=0.10, depth=0.72,
                              matrix=Matrix.Translation((0, 0, 0.36)))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.82, radius2=0.82, depth=0.05,
                              matrix=Matrix.Translation((0, 0, 0.74)))
        u_w = (2 + 0.5) / 16.0
        for f in bm.faces:
            for lp in f.loops:
                lp[uvl].uv = (u_w, 0.5)
        for a_deg in (0, 90, 180, 270):
            a = math.radians(a_deg); ca, sa = math.cos(a), math.sin(a)
            cx, cy = ca * 1.05, sa * 1.05
            add_uv_box(bm, uvl, 12, (cx - 0.20, cy - 0.20, 0.42), (cx + 0.20, cy + 0.20, 0.47))
            add_uv_box(bm, uvl, 6, (cx - 0.16, cy - 0.16, 0.0), (cx + 0.16, cy + 0.16, 0.42))

    def read_table(bm, uvl):
        # 图书馆 6 人原木阅览长桌 (2.6 × 1.1 m) + 6 把椅子
        add_uv_box(bm, uvl, 6, (-1.2, -0.45, 0.0), (-1.12, -0.38, 0.73))
        add_uv_box(bm, uvl, 6, (1.12, -0.45, 0.0), (1.2, -0.38, 0.73))
        add_uv_box(bm, uvl, 6, (-1.2, 0.38, 0.0), (-1.12, 0.45, 0.73))
        add_uv_box(bm, uvl, 6, (1.12, 0.38, 0.0), (1.2, 0.45, 0.73))
        add_uv_box(bm, uvl, 2, (-1.3, -0.55, 0.73), (1.3, 0.55, 0.78))
        for xi in (-0.85, 0.0, 0.85):
            for yi in (-0.78, 0.78):
                add_uv_box(bm, uvl, 10, (xi - 0.21, yi - 0.21, 0.43), (xi + 0.21, yi + 0.21, 0.48))
                add_uv_box(bm, uvl, 6, (xi - 0.17, yi - 0.17, 0.0), (xi + 0.17, yi + 0.17, 0.43))

    return {
        'shelf': make_proto('Int_Cloud_ShelfUnit', bookshelf),
        'desk':  make_proto('Int_Cloud_DeskUnit', desk_set),
        'round': make_proto('Int_Cloud_RoundTableUnit', round_table),
        'read':  make_proto('Int_Cloud_ReadTableUnit', read_table),
    }


def spawn(c, name, me, loc, rot_deg=0.0):
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    c.objects.link(o)


def build_library(c, protos, lm):
    """1. 星形庭院西南露台下图书馆（Z=0.04..4.15 m，x in [-40, -4], y in [-98, -73]）。"""
    z0, z1 = 0.10, 4.15
    # 原木地板
    bm_f = bmesh.new(); uvl_f = bm_f.loops.layers.uv.new('UVMap')
    vs = [bm_f.verts.new(p) for p in ((-40.0, -98.0, z0), (-4.0, -98.0, z0), (-4.0, -73.0, z0), (-40.0, -73.0, z0))]
    ff = bm_f.faces.new(vs)
    for lp, uv in zip(ff.loops, [(0, 0), (9, 0), (9, 6), (0, 6)]):
        lp[uvl_f].uv = uv
    me_f = bpy.data.meshes.new('Int_Cloud_LibFloor'); bm_f.to_mesh(me_f); bm_f.free()
    me_f.materials.append(wood_mat())
    c.objects.link(bpy.data.objects.new('Int_Cloud_LibFloor', me_f))

    # 结构内墙、服务台、阶梯木质读书角与浅色吸音吊顶
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    add_uv_box(bm, uvl, 0, (-40.0, -98.0, z1 - 0.12), (-4.0, -73.0, z1))  # 吊顶
    add_uv_box(bm, uvl, 0, (-40.0, -98.2, z0), (-4.0, -97.8, z1))        # 南背墙
    add_uv_box(bm, uvl, 0, (-4.2, -98.0, z0), (-3.8, -73.0, z1))         # 东隔墙
    # 借阅服务台（近北西入口）
    add_uv_box(bm, uvl, 2, (-27.0, -78.5, z0), (-21.0, -77.3, z0 + 1.05))
    add_uv_box(bm, uvl, 0, (-26.8, -78.6, z0 + 1.05), (-21.2, -77.2, z0 + 1.12))
    # 东南角 5 级木质阶梯读书角
    for k in range(5):
        add_uv_box(bm, uvl, 2, (-12.5, -97.5 + k * 0.85, z0), (-4.6, -97.5 + (k + 1) * 0.85, z0 + (5 - k) * 0.42))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Int_Cloud_LibShell'); bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    c.objects.link(bpy.data.objects.new('Int_Cloud_LibShell', me))

    # 12 组实例化原木双面书架（西侧藏书区）
    idx = 0
    for xi in (-36.5, -32.5, -28.5):
        for yi in (-82.0, -86.5, -91.0, -95.0):
            spawn(c, f'Int_Cloud_LibShelf_{idx:02d}', protos['shelf'], (xi, yi, z0), 0.0)
            idx += 1

    # 6 张实例化阅览长桌（中部阅览区）
    idx = 0
    for xi in (-20.0, -14.0):
        for yi in (-82.5, -87.5, -92.5):
            spawn(c, f'Int_Cloud_LibTable_{idx:02d}', protos['read'], (xi, yi, z0), 0.0)
            idx += 1

    if lm:
        idx = 0
        for xi in (-35.0, -27.0, -19.0, -11.0):
            for yi in (-78.0, -85.0, -92.0):
                spawn(c, f'Int_Cloud_LibLamp_{idx:02d}', lm, (xi, yi, z1 - 0.18), 0.0)
                idx += 1


def build_art_gallery(c, lm):
    """2. 星形庭院西侧艺术馆展厅（严格内嵌于 west_gallery_volume 梯形体块内部，封闭西南斜墙杜绝室外绿草坡穿模！）。"""
    z0, z1 = 0.10, 2.68
    # 严格内缩于 west_gallery_volume polygon [[-38.5,-42],[-31,-42],[-27.5,-54.5],[-37.5,-59]]
    trap = [(-38.0, -42.4), (-31.4, -42.4), (-28.1, -54.2), (-37.1, -58.3)]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')

    def add_poly_slab(poly, za, zb, sw):
        u = (sw + 0.5) / 16.0
        vb = [bm.verts.new((x, y, za)) for x, y in poly]
        vt = [bm.verts.new((x, y, zb)) for x, y in poly]
        fs = [bm.faces.new(list(reversed(vb))), bm.faces.new(vt)]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            fs.append(bm.faces.new((vb[i], vb[j], vt[j], vt[i])))
        for f in fs:
            for lp in f.loops:
                lp[uvl].uv = (u, 0.5)

    def add_wall(a, b, thick, za, zb, sw):
        va, vb = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
        d = (vb - va).normalized()
        n = Vector((-d.y, d.x, 0)) * (thick * 0.5)
        poly = [(va.x - n.x, va.y - n.y), (vb.x - n.x, vb.y - n.y), (vb.x + n.x, vb.y + n.y), (va.x + n.x, va.y + n.y)]
        add_poly_slab(poly, za, zb, sw)

    # 洁净浅灰展厅地面 + 白色吸音吊顶
    add_poly_slab(trap, z0 - 0.04, z0, 1)
    add_poly_slab(trap, z1 - 0.08, z1, 0)
    # 封闭北墙 (0->1)、南斜墙 (2->3，彻底遮蔽外部绿草坡!)、西主展墙 (3->0)
    add_wall(trap[0], trap[1], 0.30, z0, z1, 0)
    add_wall(trap[2], trap[3], 0.35, z0, z1, 0)
    add_wall(trap[3], trap[0], 0.35, z0, z1, 0)

    # 西主展墙 4 幅精致双层画框艺术画（外暗框 + 留白卡纸 + 双色现代几何构成画芯）
    pal = ((12, 5), (11, 10), (5, 13), (13, 12))
    for k, yi in enumerate((-54.2, -51.1, -48.0, -44.9)):
        # 按西墙斜线插值 X 贴紧墙面内侧
        t = (yi - (-58.3)) / ((-42.4) - (-58.3))
        wx = -37.1 + (-38.0 - (-37.1)) * t + 0.22
        add_uv_box(bm, uvl, 6, (wx, yi - 1.12, z0 + 0.98), (wx + 0.06, yi + 1.12, z0 + 2.34))
        add_uv_box(bm, uvl, 0, (wx + 0.04, yi - 1.04, z0 + 1.06), (wx + 0.09, yi + 1.04, z0 + 2.26))
        add_uv_box(bm, uvl, pal[k][0], (wx + 0.08, yi - 0.90, z0 + 1.18), (wx + 0.11, yi + 0.90, z0 + 2.14))
        add_uv_box(bm, uvl, pal[k][1], (wx + 0.10, yi - 0.45, z0 + 1.38), (wx + 0.13, yi + 0.55, z0 + 1.92))

    # 3 座中央白色雕塑展台 + 优雅圆润艺术雕塑（球体/环柱组合替代单调方块）
    u_pal = [(sw + 0.5) / 16.0 for sw in (11, 12, 13)]
    for k, yi in enumerate((-52.5, -49.0, -45.5)):
        add_uv_box(bm, uvl, 0, (-34.2, yi - 0.48, z0), (-33.2, yi + 0.48, z0 + 0.96))
        add_uv_box(bm, uvl, 6, (-34.24, yi - 0.52, z0), (-33.16, yi + 0.52, z0 + 0.06))
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.30,
                                         matrix=Matrix.Translation((-33.7, yi, z0 + 1.30)) @ Matrix.Diagonal((1.0, 0.85, 1.25, 1.0)))
        vset = set(res['verts'])
        for f in bm.faces:
            if all(v in vset for v in f.verts):
                f.smooth = True
                for lp in f.loops:
                    lp[uvl].uv = (u_pal[k], 0.5)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Int_Cloud_ArtGallery'); bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    c.objects.link(bpy.data.objects.new('Int_Cloud_ArtGallery', me))

    if lm:
        for k, yi in enumerate((-52.5, -49.0, -45.5)):
            spawn(c, f'Int_Cloud_ArtLamp_{k}', lm, (-33.5, yi, z1 - 0.14), 90.0)


def build_cloud_3f(c, protos, lm):
    """3. 学术中心 3F 北翼开放社交长廊与 6 间示范教室（依据 05_cloud_3f.jpg，Z=12.5..16.2 m）。"""
    z0, z1 = 12.54, 16.20
    # 地板（整个北翼 3F x in [-32, +36], y in [-16, +8]）
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    bm_gl = bmesh.new()
    # 浅灰水磨石教学楼面 + 白色吸音吊顶
    add_uv_box(bm, uvl, 1, (-32.0, -16.0, z0 - 0.08), (36.0, 8.0, z0))
    add_uv_box(bm, uvl, 0, (-32.0, -16.0, z1 - 0.12), (36.0, 8.0, z1))

    # 6 间示范教室分格（y in [-7.0, +7.6]，南侧沿 y=-7.0 设通透玻璃隔断与 1.8 m 敞开门洞！）
    room_xs = [-30.0, -19.0, -8.0, 4.0, 15.0, 26.0, 35.0]
    for i, xw in enumerate(room_xs):
        add_uv_box(bm, uvl, 0, (xw - 0.12, -7.0, z0), (xw + 0.12, 7.6, z1))
    # 各房间面向走廊的玻璃隔断与门洞
    for i in range(6):
        xa, xb = room_xs[i], room_xs[i + 1]
        door_x0, door_x1 = xa + 1.2, xa + 3.0
        # 门左实墙柱 + 门右玻璃隔断 + 门楣
        add_uv_box(bm, uvl, 0, (xa, -7.1, z0), (door_x0, -6.9, z1))
        add_uv_box(bm, uvl, 0, (door_x0, -7.1, z0 + 2.3), (door_x1, -6.9, z1))
        add_uv_box(bm, uvl, 0, (door_x1, -7.1, z0), (xb, -6.9, z0 + 0.95))
        bm_gl.faces.new([
            bm_gl.verts.new((door_x1, -7.0, z0 + 0.95)),
            bm_gl.verts.new((xb, -7.0, z0 + 0.95)),
            bm_gl.verts.new((xb, -7.0, z1 - 0.15)),
            bm_gl.verts.new((door_x1, -7.0, z1 - 0.15)),
        ])

    # 常规教室 1 ([-30,-19]) & 常规教室 2 ([+4,+15])：讲台 + 智慧绿板
    for xa in (-30.0, 4.0):
        add_uv_box(bm, uvl, 2, (xa + 0.4, -2.5, z0), (xa + 1.8, 2.5, z0 + 0.22))       # 讲台
        add_uv_box(bm, uvl, 2, (xa + 0.6, -0.7, z0 + 0.22), (xa + 1.4, 0.7, z0 + 1.15)) # 讲桌
        add_uv_box(bm, uvl, 7, (xa + 0.14, -2.6, z0 + 1.1), (xa + 0.22, 2.6, z0 + 2.4)) # 绿黑板

    # 研讨室 1 ([-19,-8]) & 研讨室 2 ([+15,+26])：可书写白板墙
    for xa in (-19.0, 15.0):
        add_uv_box(bm, uvl, 8, (xa + 0.14, -3.0, z0 + 1.0), (xa + 0.22, 3.0, z0 + 2.4))

    # 理科/创客实验室 ([-8, +4])：4 张暗灰防化实验长台 + 仪器柜
    for yi in (-4.2, -1.2, 1.8, 4.8):
        add_uv_box(bm, uvl, 0, (-6.2, yi - 0.45, z0), (2.2, yi + 0.45, z0 + 0.82))
        add_uv_box(bm, uvl, 6, (-6.25, yi - 0.48, z0 + 0.82), (2.25, yi + 0.48, z0 + 0.88))

    # 教师办公室 ([+26, +35])：办公桌组合
    for xi in (28.0, 32.5):
        for yi in (-3.5, 1.5):
            add_uv_box(bm, uvl, 2, (xi - 0.85, yi - 0.45, z0 + 0.72), (xi + 0.85, yi + 0.45, z0 + 0.77))
            add_uv_box(bm, uvl, 6, (xi - 0.80, yi - 0.40, z0), (xi - 0.74, yi + 0.40, z0 + 0.72))
            add_uv_box(bm, uvl, 6, (xi + 0.74, yi - 0.40, z0), (xi + 0.80, yi + 0.40, z0 + 0.72))

    # 开放社交走廊（y in [-15, -7]）：蓝色学生储物柜阵列 + 木质休闲长凳
    for xi in (-26.0, -14.0, -2.0, 10.0, 22.0):
        add_uv_box(bm, uvl, 5, (xi - 1.8, -7.65, z0), (xi + 1.8, -7.15, z0 + 1.85))
    for xi in (-20.0, -6.0, 8.0, 20.0):
        add_uv_box(bm, uvl, 2, (xi - 1.6, -13.5, z0), (xi + 1.6, -12.6, z0 + 0.46))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Int_Cloud_3FShell'); bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    c.objects.link(bpy.data.objects.new('Int_Cloud_3FShell', me))

    bmesh.ops.recalc_face_normals(bm_gl, faces=bm_gl.faces)
    me_gl = bpy.data.meshes.new('Int_Cloud_3FGlass'); bm_gl.to_mesh(me_gl); bm_gl.free()
    me_gl.materials.append(glass_mat())
    c.objects.link(bpy.data.objects.new('Int_Cloud_3FGlass', me_gl))

    # 实例化课桌椅（2 间常规教室各 15 套 = 30 套）
    d_idx = 0
    for xa in (-30.0, 4.0):
        for r in range(3):
            for col in range(5):
                spawn(c, f'Int_Cloud_Desk_{d_idx:02d}', protos['desk'],
                      (xa + 3.2 + r * 2.1, -4.4 + col * 2.1, z0), 90.0)
                d_idx += 1

    # 实例化圆桌研讨组（2 间研讨室各 4 组 = 8 组）
    r_idx = 0
    for xa in (-19.0, 15.0):
        for dx in (3.2, 7.6):
            for dy in (-3.2, 2.8):
                spawn(c, f'Int_Cloud_Round_{r_idx:02d}', protos['round'], (xa + dx, dy, z0), 0.0)
                r_idx += 1

    # 教室与走廊顶灯（实例化）
    if lm:
        l_idx = 0
        for xi in range(-26, 35, 8):
            for yi in (-11.0, -3.0, 3.0):
                spawn(c, f'Int_Cloud_3FLamp_{l_idx:02d}', lm, (xi, yi, z1 - 0.18), 0.0)
                l_idx += 1


def main():
    c = ensure_coll(COLL)
    protos = build_protos()
    lm = lamp_me()
    build_library(c, protos, lm)
    build_art_gallery(c, lm)
    build_cloud_3f(c, protos, lm)
    bpy.ops.wm.save_mainfile()
    print('Interior_Cloud objects:', len(c.objects))


main()
