"""P1 + P8 场地：用地、道路与标线、广场、台地、田径场（条纹草坪、11人制场地线、3D足球门、跳远沙坑、升旗台、高杆照明灯塔）、
网球场（红土/墨绿双色地坪、标准划线、3D球网、高围网、东侧休憩亭）、篮球场（绿/蓝真实双色地坪、FIBA划线、3D玻璃篮板篮架、围网/灯杆/长椅）。
数据来自 data/site.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/site.py').read())
"""
import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
S = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Site'

MATS = {
    'M_Ground': (0.32, 0.39, 0.23, 0.95),
    'M_Asphalt': (0.17, 0.17, 0.19, 0.88),
    'M_Paving': (0.64, 0.63, 0.60, 0.85),
    'M_TrackRed': (0.55, 0.16, 0.12, 0.88),
    'M_Turf': (0.15, 0.38, 0.14, 0.95),
    'M_LineWhite': (0.93, 0.94, 0.92, 0.55),
    'M_Cloud_Slab': (0.22, 0.24, 0.27, 0.45),
    'M_Cloud_Skylight': (0.22, 0.30, 0.38, 0.12),
    'M_AccentRed': (0.76, 0.16, 0.10, 0.50),
    'M_FenceMesh': (0.14, 0.26, 0.18, 0.65),
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    if name in MATS:
        r, g, b, rough = MATS[name]
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
            bsdf.inputs['Roughness'].default_value = rough
            if name == 'M_FenceMesh':
                bsdf.inputs['Alpha'].default_value = 0.22
                m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else m.blend_method
            elif name == 'M_Cloud_Skylight':
                bsdf.inputs['Metallic'].default_value = 0.35
        m.diffuse_color = (r, g, b, 0.25 if name == 'M_FenceMesh' else 1.0)
    return m


def sports_atlas_mat():
    """单一图集材质覆盖足球场、网球场、西篮球场、东北篮球场，节省材质与 draw call。"""
    name = 'M_SportsCourts'
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img_path = os.path.join(ROOT, 'blender', 'textures', 'sports_atlas.png')
    img = bpy.data.images.load(img_path, check_existing=True)
    img.reload()
    tex.image = img
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.86
    m.diffuse_color = (0.22, 0.45, 0.28, 1.0)
    return m


def coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def obj(name, bm, material, c):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    m = material if isinstance(material, bpy.types.Material) else mat(material)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def slab(name, poly, z, thick, material, c):
    """多边形平板：顶面在 z，向下 thick。"""
    bm = bmesh.new()
    top = [bm.verts.new((x, y, z)) for x, y in poly]
    f = bm.faces.new(top)
    if thick > 0:
        r = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, vec=(0, 0, -thick),
                            verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, bm, material, c)


def uv_quad(name, corners_xy, z, uvs, material, c):
    """创建带精确 UV 的水平四边形面（用于球场与足球场图集映射）。"""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    vs = [bm.verts.new((x, y, z)) for x, y in corners_xy]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.z < 0:
        f.normal_flip()
    for lp, uv in zip(f.loops, uvs):
        lp[uvl].uv = uv
    return obj(name, bm, material, c)


def strip(name, line, width, z, material, c, thick=0.0):
    (x0, y0), (x1, y1) = line
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * width / 2, dx / L * width / 2
    return slab(name, [(x0 + nx, y0 + ny), (x0 - nx, y0 - ny), (x1 - nx, y1 - ny), (x1 + nx, y1 + ny)], z, thick, material, c)


def add_box(bm, p0, p1, mat_idx=0):
    """轴对齐长方体（局部坐标）。"""
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    vs = [bm.verts.new(p) for p in (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )]
    faces = [
        bm.faces.new((vs[0], vs[3], vs[2], vs[1])),
        bm.faces.new((vs[4], vs[5], vs[6], vs[7])),
        bm.faces.new((vs[0], vs[1], vs[5], vs[4])),
        bm.faces.new((vs[1], vs[2], vs[6], vs[5])),
        bm.faces.new((vs[2], vs[3], vs[7], vs[6])),
        bm.faces.new((vs[3], vs[0], vs[4], vs[7])),
    ]
    for f in faces:
        f.material_index = mat_idx


def add_cyl(bm, a, b, r, seg=8, mat_idx=0):
    """任意两点间的圆柱杆件。"""
    va, vb = Vector(a), Vector(b)
    d = vb - va
    L = d.length
    if L < 1e-4:
        return
    q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    mid = (va + vb) * 0.5
    M = Matrix.Translation(mid) @ q
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=L, matrix=M)
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = mat_idx


def stadium_ring(r_in, r_out, straight, seg=48):
    """跑道环：返回 (外环点, 内环点)，局部坐标，长轴 = +Y。"""
    def loop(r):
        pts = []
        for i in range(seg + 1):
            t = math.pi * i / seg
            pts.append((r * math.cos(t), straight / 2 + r * math.sin(t)))
        for i in range(seg + 1):
            t = math.pi + math.pi * i / seg
            pts.append((r * math.cos(t), -straight / 2 + r * math.sin(t)))
        return pts
    return loop(r_out), loop(r_in)


def place(pts, cx, cy, ang_deg_west_of_north):
    a = math.radians(ang_deg_west_of_north)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def ring_mesh(name, outer, inner, z, material, c):
    bm = bmesh.new()
    vo = [bm.verts.new((x, y, z)) for x, y in outer]
    vi = [bm.verts.new((x, y, z)) for x, y in inner]
    n = len(vo)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vo[i], vo[j], vi[j], vi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, bm, material, c)


def football_goal_mesh():
    """标准 11 人制足球门框（宽 7.32 m × 高 2.44 m × 底深 2.0 m，开口朝 -Y）。"""
    old = bpy.data.meshes.get('Site_FootballGoalUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new()
    hw, h, dt, db = 3.66, 2.44, 0.85, 2.0
    # 0 = M_LineWhite（白漆门框与后撑），1 = M_FenceMesh（半透明球网）
    add_cyl(bm, (-hw, 0, 0), (-hw, 0, h), 0.075, 8, 0)
    add_cyl(bm, (hw, 0, 0), (hw, 0, h), 0.075, 8, 0)
    add_cyl(bm, (-hw - 0.05, 0, h), (hw + 0.05, 0, h), 0.075, 8, 0)
    # 顶部后撑与底框
    add_cyl(bm, (-hw, 0, h), (-hw, dt, h), 0.045, 6, 0)
    add_cyl(bm, (hw, 0, h), (hw, dt, h), 0.045, 6, 0)
    add_cyl(bm, (-hw, dt, h), (hw, dt, h), 0.045, 6, 0)
    add_cyl(bm, (-hw, dt, h), (-hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (hw, dt, h), (hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (-hw, 0, 0.04), (-hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (hw, 0, 0.04), (hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (-hw, db, 0.04), (hw, db, 0.04), 0.045, 6, 0)
    # 球网（顶面、背面、两侧面）
    v_fl0 = bm.verts.new((-hw, 0.04, 0.04))
    v_fr0 = bm.verts.new((hw, 0.04, 0.04))
    v_fl1 = bm.verts.new((-hw, 0.04, h - 0.04))
    v_fr1 = bm.verts.new((hw, 0.04, h - 0.04))
    v_btl = bm.verts.new((-hw, dt, h - 0.04))
    v_btr = bm.verts.new((hw, dt, h - 0.04))
    v_bbl = bm.verts.new((-hw, db, 0.04))
    v_bbr = bm.verts.new((hw, db, 0.04))
    for verts in (
        (v_fl1, v_fr1, v_btr, v_btl),  # 顶网
        (v_btl, v_btr, v_bbr, v_bbl),  # 后网
        (v_fl0, v_fl1, v_btl, v_bbl),  # 左网
        (v_fr0, v_bbr, v_btr, v_fr1),  # 右网
    ):
        f = bm.faces.new(verts)
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Site_FootballGoalUnit')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_LineWhite'))
    me.materials.append(mat('M_FenceMesh'))
    return me


def floodlight_mesh():
    """田径场 18 m 高杆照明灯塔（实例化）。"""
    old = bpy.data.meshes.get('Site_FloodlightUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new()
    # 底座 + 锥形灯杆 (0 = M_LineWhite, 1 = M_Cloud_Slab)
    add_box(bm, (-0.35, -0.35, 0), (0.35, 0.35, 0.5), 1)
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.22, radius2=0.11, depth=18.5,
                                matrix=Matrix.Translation((0, 0, 9.5)))
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 0
    # 顶部投光灯架（朝 +Y）
    add_box(bm, (-1.6, -0.2, 18.4), (1.6, 0.25, 19.7), 1)
    add_box(bm, (-1.45, 0.25, 18.55), (1.45, 0.38, 19.55), 0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Site_FloodlightUnit')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_LineWhite'))
    me.materials.append(mat('M_Cloud_Slab'))
    return me


def basket_hoop_mesh():
    """标准室外玻璃篮板篮球架（悬臂朝 +Y，篮筐高 3.05 m，实例化）。"""
    old = bpy.data.meshes.get('Site_BasketHoopUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new()
    # 0 = M_Cloud_Slab（深色底座与立柱）, 1 = M_Cloud_Skylight（玻璃篮板）, 2 = M_LineWhite（白框与篮网）, 3 = M_AccentRed（橙红篮筐）
    add_box(bm, (-0.55, -1.65, 0.0), (0.55, -0.45, 0.72), 0)       # 配重箱
    add_cyl(bm, (0, -1.05, 0.7), (0, -0.95, 3.35), 0.09, 8, 0)     # 主立柱
    add_cyl(bm, (0, -0.95, 3.32), (0, 0.28, 3.32), 0.08, 8, 0)     # 悬臂伸臂
    add_cyl(bm, (0, -0.98, 2.55), (0, 0.15, 3.30), 0.05, 6, 0)     # 斜撑
    # 篮板 (宽 1.80 m × 高 1.05 m，底高 2.90 m，位于 y = 0.35 m)
    add_box(bm, (-0.90, 0.33, 2.90), (0.90, 0.38, 3.95), 1)
    # 篮板白色边框
    for p0, p1 in (
        ((-0.91, 0.38, 2.90), (0.91, 0.40, 2.95)),
        ((-0.91, 0.38, 3.90), (0.91, 0.40, 3.95)),
        ((-0.91, 0.38, 2.90), (-0.86, 0.40, 3.95)),
        ((0.86, 0.38, 2.90), (0.91, 0.40, 3.95)),
    ):
        add_box(bm, p0, p1, 2)
    # 橙红篮筐 (直径 0.45 m，圆心 y = 0.73 m, z = 3.05 m)
    nseg = 12
    rc = 0.23
    cy_rim = 0.72
    pts = [(rc * math.cos(2 * math.pi * i / nseg), cy_rim + rc * math.sin(2 * math.pi * i / nseg), 3.05) for i in range(nseg)]
    for i in range(nseg):
        add_cyl(bm, pts[i], pts[(i + 1) % nseg], 0.022, 6, 3)
    add_box(bm, (-0.08, 0.38, 3.00), (0.08, 0.50, 3.08), 3)
    # 篮网（白锥筒）
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=0.14, radius2=0.22, depth=0.42,
                                matrix=Matrix.Translation((0, cy_rim, 2.83)))
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Site_BasketHoopUnit')
    bm.to_mesh(me)
    bm.free()
    for mn in ('M_Cloud_Slab', 'M_Cloud_Skylight', 'M_LineWhite', 'M_AccentRed'):
        me.materials.append(mat(mn))
    return me


def build_track(c):
    T = S['track']
    cx, cy = T['center']
    ang = T['long_axis_deg_west_of_north']
    z = T['z']
    straight = 84.39
    r_kerb = 36.5
    r_out = T['outer_bbox'][1] / 2
    ang_rad = math.radians(ang)
    ca, sa = math.cos(ang_rad), math.sin(ang_rad)

    def P(x, y):
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)

    # 1. 跑道塑胶面与 6 条白色分道线
    out_, in_ = stadium_ring(r_kerb, r_out, straight)
    ring_mesh('Site_Track_Surface', place(out_, cx, cy, ang), place(in_, cx, cy, ang), z + 0.10, 'M_TrackRed', c)
    r = r_kerb + 0.3
    k = 0
    while r + 0.05 < r_out:
        o, i = stadium_ring(r - 0.025, r + 0.025, straight)
        ring_mesh(f'Site_Track_Lane{k}', place(o, cx, cy, ang), place(i, cx, cy, ang), z + 0.13, 'M_LineWhite', c)
        r += 1.22
        k += 1

    # 2. 内场 D 区底草坪 + 105×68 m 条纹足球场与完整白线（图集左上象限 u:0..0.5, v:0.5..1.0）
    _, inner = stadium_ring(r_kerb, r_kerb, straight)
    slab('Site_Track_Infield', place(inner, cx, cy, ang), z + 0.09, 0, 'M_Turf', c)

    # 纹理四周留有 14/1024 边距，放大网格 1024/(1024-28) 使白线精确落在 105×68 m
    scale_pad = 1024.0 / (1024.0 - 28.0)
    hw_p = 34.0 * scale_pad
    hl_p = 52.5 * scale_pad
    pitch_xy = [P(-hw_p, -hl_p), P(hw_p, -hl_p), P(hw_p, hl_p), P(-hw_p, hl_p)]
    pitch_uv = [(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)]
    uv_quad('Site_Track_Pitch', pitch_xy, z + 0.125, pitch_uv, sports_atlas_mat(), c)

    # 3. 两端 3D 足球门框 + 球网（精确位于 y_local = ±52.5 m）
    goal_me = football_goal_mesh()
    for name, yl, rot_extra in (('Site_FootballGoal_N', 52.5, 0.0), ('Site_FootballGoal_S', -52.5, math.pi)):
        gx, gy = P(0.0, yl)
        go = bpy.data.objects.new(name, goal_me)
        go.location = (gx, gy, z + 0.125)
        go.rotation_euler = (0.0, 0.0, ang_rad + rot_extra)
        c.objects.link(go)

    # 4. 北侧 D 区：跳远助跑道 + 双白色沙坑（卫星图清晰可见，位于 y_local ≈ +59 m）
    lj_runway = [P(-16.0, 58.2), P(16.0, 58.2), P(16.0, 60.0), P(-16.0, 60.0)]
    slab('Site_Track_LongJumpRunway', lj_runway, z + 0.125, 0.0, 'M_Paving', c)
    for tag, x0, x1 in (('W', -21.5, -14.5), ('E', 14.5, 21.5)):
        pit = [P(x0, 57.5), P(x1, 57.5), P(x1, 60.8), P(x0, 60.8)]
        slab(f'Site_Track_SandPit_{tag}', pit, z + 0.135, 0.0, 'M_LineWhite', c)

    # 5. 南侧 D 区：升旗石质方台 + 3 根旗杆与旗帜（wx_35.jpg 可见，位于 y_local ≈ -65 m）
    fp_poly = [P(-3.2, -68.0), P(3.2, -68.0), P(3.2, -62.0), P(-3.2, -62.0)]
    slab('Site_Track_FlagPodium', fp_poly, z + 0.38, 0.30, 'M_Paving', c)
    bm_fl = bmesh.new()
    for dx_f, h_f in ((-1.8, 10.5), (0.0, 12.2), (1.8, 10.5)):
        fx, fy = P(dx_f, -65.0)
        add_cyl(bm_fl, (fx, fy, z + 0.38), (fx, fy, z + 0.38 + h_f), 0.06, 8, 0)
        # 飘扬红旗面（略偏东）
        fx2, fy2 = P(dx_f + 1.8, -65.0)
        vs = [
            bm_fl.verts.new((fx, fy, z + 0.38 + h_f - 1.25)),
            bm_fl.verts.new((fx2, fy2, z + 0.38 + h_f - 1.25)),
            bm_fl.verts.new((fx2, fy2, z + 0.38 + h_f - 0.10)),
            bm_fl.verts.new((fx, fy, z + 0.38 + h_f - 0.10)),
        ]
        f = bm_fl.faces.new(vs)
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm_fl, faces=bm_fl.faces)
    me_fl = bpy.data.meshes.new('Site_Track_Flagpoles')
    bm_fl.to_mesh(me_fl)
    bm_fl.free()
    me_fl.materials.append(mat('M_LineWhite'))
    me_fl.materials.append(mat('M_AccentRed'))
    c.objects.link(bpy.data.objects.new('Site_Track_Flagpoles', me_fl))

    # 6. 4 座高杆照明灯塔（实例化，分布于跑道东西两侧）
    fl_me = floodlight_mesh()
    masts = [
        ('NW', -47.0, 38.0, -math.pi / 2),
        ('SW', -47.0, -40.0, -math.pi / 2),
        ('NE', 48.0, 42.0, math.pi / 2),
        ('SE', 48.0, -32.0, math.pi / 2),
    ]
    for tag, lx, ly, rot_f in masts:
        mx, my = P(lx, ly)
        mo = bpy.data.objects.new(f'Site_Track_Floodlight_{tag}', fl_me)
        mo.location = (mx, my, z + 0.05)
        mo.rotation_euler = (0.0, 0.0, ang_rad + rot_f)
        c.objects.link(mo)

    # 7. 抬高台面外沿缓冲带
    o3, _ = stadium_ring(r_out, r_out + 3.0, straight)
    _, i3 = stadium_ring(r_out, r_out, straight)
    ring_mesh('Site_Track_Deck', place(o3, cx, cy, ang), place(i3, cx, cy, ang), z + 0.06, 'M_Paving', c)


def build_fence(name, corners_xy, z0, height, c, skip_edges=()):
    """球场高围网（立柱 + 上下横梁 + 低面数半透明网面）。"""
    bm = bmesh.new()
    n = len(corners_xy)
    for i in range(n):
        if i in skip_edges:
            continue
        (x0, y0), (x1, y1) = corners_xy[i], corners_xy[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        # 上、中、下横梁（mat 0 = M_Cloud_Slab）
        for hz in (0.12, height * 0.5, height):
            add_cyl(bm, (x0, y0, z0 + hz), (x1, y1, z0 + hz), 0.04, 6, 0)
        # 每约 3.5 m 一根立柱
        nsegs = max(2, int(round(L / 3.5)))
        for s in range(nsegs + 1):
            t = s / nsegs
            px = x0 + (x1 - x0) * t
            py = y0 + (y1 - y0) * t
            add_cyl(bm, (px, py, z0), (px, py, z0 + height), 0.045, 6, 0)
        # 半透明围网面（mat 1 = M_FenceMesh）
        vs = [
            bm.verts.new((x0, y0, z0 + 0.12)),
            bm.verts.new((x1, y1, z0 + 0.12)),
            bm.verts.new((x1, y1, z0 + height)),
            bm.verts.new((x0, y0, z0 + height)),
        ]
        f = bm.faces.new(vs)
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Cloud_Slab'))
    me.materials.append(mat('M_FenceMesh'))
    c.objects.link(bpy.data.objects.new(name, me))


def build_courts(c):
    atlas = sports_atlas_mat()
    hoop_me = basket_hoop_mesh()

    for k, v in S['courts'].items():
        cx, cy = v['center']
        a = math.radians(v['long_axis_deg_from_E'])
        L, W = v['size']
        pad = 3.5 if v['kind'] == 'tennis' else 2.0
        z = v['z']
        ca, sa = math.cos(a), math.sin(a)

        def P(x, y):
            return (cx + x * ca - y * sa, cy + x * sa + y * ca)

        hl, hw = L / 2.0 + pad, W / 2.0 + pad
        corners = [P(-hl, -hw), P(hl, -hw), P(hl, hw), P(-hl, hw)]

        # 根据球场类型选择图集象限
        if v['kind'] == 'tennis':
            u0, u1, v0, v1 = 0.5, 1.0, 0.5, 1.0
        elif k == 'basket_W':
            u0, u1, v0, v1 = 0.0, 0.5, 0.0, 0.5
        else:
            u0, u1, v0, v1 = 0.5, 1.0, 0.0, 0.5

        uvs = [(u1, v0), (u1, v1), (u0, v1), (u0, v0)]
        uv_quad(f'Site_Court_{k}', corners, z + 0.12, uvs, atlas, c)
        # 球场微抬边缘路缘底座（防与地面 Z-fighting）
        slab(f'Site_Court_{k}_Base', corners, z + 0.10, 0.25, 'M_Paving', c)

        if v['kind'] == 'tennis':
            # 3D 网球网 + 两侧网柱
            bm_net = bmesh.new()
            nhw = W / 2.0 + 0.91
            p_l = P(0.0, -nhw)
            p_r = P(0.0, nhw)
            add_cyl(bm_net, (p_l[0], p_l[1], z + 0.12), (p_l[0], p_l[1], z + 1.19), 0.055, 8, 0)
            add_cyl(bm_net, (p_r[0], p_r[1], z + 0.12), (p_r[0], p_r[1], z + 1.19), 0.055, 8, 0)
            # 白色网顶带
            add_cyl(bm_net, (p_l[0], p_l[1], z + 1.15), (p_r[0], p_r[1], z + 1.15), 0.032, 6, 1)
            # 黑色/深绿球网面
            vs = [
                bm_net.verts.new((p_l[0], p_l[1], z + 0.14)),
                bm_net.verts.new((p_r[0], p_r[1], z + 0.14)),
                bm_net.verts.new((p_r[0], p_r[1], z + 1.12)),
                bm_net.verts.new((p_l[0], p_l[1], z + 1.12)),
            ]
            f = bm_net.faces.new(vs)
            f.material_index = 2
            bmesh.ops.recalc_face_normals(bm_net, faces=bm_net.faces)
            me_n = bpy.data.meshes.new(f'Site_Court_{k}_Net')
            bm_net.to_mesh(me_n)
            bm_net.free()
            me_n.materials.append(mat('M_Cloud_Slab'))
            me_n.materials.append(mat('M_LineWhite'))
            me_n.materials.append(mat('M_FenceMesh'))
            c.objects.link(bpy.data.objects.new(f'Site_Court_{k}_Net', me_n))

            # 4 m 高围网（两片网球场共用中间边界，外围完整围合）
            build_fence(f'Site_Court_{k}_Fence', corners, z + 0.12, 4.0, c)

        else:
            # 篮球架（2 套，分别位于 ±(L/2 + 0.85) 端线外，面向球场中心）
            # 在 P 局部系中：+X 为 long_axis 方向；basket_hoop_mesh 悬臂朝局部 +Y
            # 所以放于 -L/2 时悬臂需朝 +X_court (rot = a - pi/2)；放于 +L/2 时悬臂朝 -X_court (rot = a + pi/2)
            for tag, xl, rot_h in (('S', -(L / 2.0 + 0.85), a - math.pi / 2), ('N', L / 2.0 + 0.85, a + math.pi / 2)):
                hx, hy = P(xl, 0.0)
                ho = bpy.data.objects.new(f'Site_Court_{k}_Hoop_{tag}', hoop_me)
                ho.location = (hx, hy, z + 0.12)
                ho.rotation_euler = (0.0, 0.0, rot_h)
                c.objects.link(ho)

            if k == 'basket_W':
                # 西篮球场外围 4 m 高围网 + 南侧白色小型器材房（卫星图清晰可见）
                build_fence('Site_Court_basket_W_Fence', corners, z + 0.12, 4.0, c)
                shed = [P(-hl - 5.5, hw - 1.5), P(-hl - 0.5, hw - 1.5), P(-hl - 0.5, hw + 5.0), P(-hl - 5.5, hw + 5.0)]
                slab('Site_Court_basket_W_Shed', shed, z + 3.4, 3.4, 'M_LineWhite', c)
            else:
                # 东北篮球场（上传图 #5/#6）：西侧 3 根球场双头灯杆 + 场边长椅
                bm_acc = bmesh.new()
                for xl in (-9.5, 0.0, 9.5):
                    lx, ly = P(xl, hw + 0.6)
                    add_cyl(bm_acc, (lx, ly, z + 0.12), (lx, ly, z + 7.2), 0.09, 8, 0)
                    px0, py0 = P(xl - 0.65, hw + 0.45)
                    px1, py1 = P(xl + 0.65, hw + 0.45)
                    add_cyl(bm_acc, (px0, py0, z + 7.2), (px1, py1, z + 7.2), 0.06, 6, 0)
                # 场边长凳 2 张
                for xl in (-5.0, 5.0):
                    bx0, by0 = P(xl - 1.4, hw + 0.4)
                    bx1, by1 = P(xl + 1.4, hw + 0.4)
                    add_cyl(bm_acc, (bx0, by0, z + 0.48), (bx1, by1, z + 0.48), 0.14, 6, 0)
                bmesh.ops.recalc_face_normals(bm_acc, faces=bm_acc.faces)
                me_a = bpy.data.meshes.new('Site_Court_basket_NE_Poles')
                bm_acc.to_mesh(me_a)
                bm_acc.free()
                me_a.materials.append(mat('M_Cloud_Slab'))
                c.objects.link(bpy.data.objects.new('Site_Court_basket_NE_Poles', me_a))

    # 网球场东侧休憩遮阳亭/小看台（wx_35.jpg 与卫星图紧贴 tennis_N/S 东缘可见）
    tn, ts = S['courts']['tennis_N'], S['courts']['tennis_S']
    px = (tn['center'][0] + ts['center'][0]) * 0.5
    py = (tn['center'][1] + ts['center'][1]) * 0.5
    ang_t = math.radians(tn['long_axis_deg_from_E'])
    ct, st = math.cos(ang_t), math.sin(ang_t)
    # 东侧偏移为局部 -y 方向
    def PT(x, y):
        return (px + x * ct - y * st, py + x * st + y * ct)
    pav_base = [PT(-11.0, -9.2), PT(11.0, -9.2), PT(11.0, -13.2), PT(-11.0, -13.2)]
    slab('Site_Tennis_Pavilion_Deck', pav_base, 0.35, 0.45, 'M_Paving', c)
    slab('Site_Tennis_Pavilion_Roof', pav_base, 3.45, 0.25, 'M_Cloud_Slab', c)
    bm_p = bmesh.new()
    for xl in (-9.8, -3.2, 3.2, 9.8):
        for yl in (-9.6, -12.8):
            x0, y0 = PT(xl, yl)
            add_cyl(bm_p, (x0, y0, 0.35), (x0, y0, 3.20), 0.10, 8, 0)
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    obj('Site_Tennis_Pavilion_Cols', bm_p, 'M_Cloud_Slab', c)

    # 体育及艺术中心西侧室外混凝土地坪与 3 组训练篮架（wx_35.jpg 右下角实景可见）
    wplaza = [(-290.0, -172.0), (-248.0, -172.0), (-268.0, -68.0), (-290.0, -68.0)]
    slab('Site_SportsWest_Plaza', wplaza, -5.92, 0.2, 'M_Paving', c)
    for idx, (hx, hy) in enumerate(((-272.0, -108.0), (-268.0, -128.0), (-264.0, -148.0))):
        ho = bpy.data.objects.new(f'Site_SportsWest_Hoop_{idx}', hoop_me)
        ho.location = (hx, hy, -5.92)
        ho.rotation_euler = (0.0, 0.0, math.radians(-108.0))
        c.objects.link(ho)


def build_road_markings(c):
    """市政道路白色虚线与人行横道（合并为单一网格，仅 1 draw call）。"""
    bm = bmesh.new()
    for r in S['roads']:
        if r['width'] < 6.0:
            continue
        (x0, y0), (x1, y1) = r['centerline']
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        z = r['z'] + 0.04
        # 中心虚线（长 6 m，空 9 m，宽 0.18 m）
        s = 8.0
        while s + 6.0 < L - 8.0:
            ax, ay = x0 + ux * s, y0 + uy * s
            bx, by = x0 + ux * (s + 6.0), y0 + uy * (s + 6.0)
            hw = 0.09
            vs = [
                bm.verts.new((ax + nx * hw, ay + ny * hw, z)),
                bm.verts.new((ax - nx * hw, ay - ny * hw, z)),
                bm.verts.new((bx - nx * hw, by - ny * hw, z)),
                bm.verts.new((bx + nx * hw, by + ny * hw, z)),
            ]
            bm.faces.new(vs)
            s += 15.0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj('Site_Road_Markings', bm, 'M_LineWhite', c)


def main():
    c = coll()
    b = S['boundary']['polygon']
    X0, Y0, X1, Y1 = S['ground_extent']
    slab('Site_Ground_Outer', [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)], -6.2, 0, 'M_Ground', c)
    zb = S['campus_base_z']
    slab('Site_Campus', b, zb, 0.5, 'M_Ground', c)
    for zn in S['zones']:
        slab('Site_Zone_' + zn['name'], zn['polygon'], zn['z'] + 0.02, zn['z'] - zb + 0.02, 'M_Ground', c)
    for p in S['plazas']:
        slab('Site_Plaza_' + p['name'], p['polygon'], p['z'], 1.0, 'M_Paving', c)
    for r in S['roads']:
        strip('Site_Road_' + r['name'], r['centerline'], r['width'], r['z'], 'M_Asphalt', c, thick=0.3)
    build_road_markings(c)
    build_track(c)
    build_courts(c)
    bpy.ops.wm.save_mainfile()
    print('site objects', len(c.objects))


main()
