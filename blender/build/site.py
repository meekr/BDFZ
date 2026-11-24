"""P1 + P8 + P10 场地：用地、道路与标线、石材铺装广场、台地、田径场（柔和条纹草坪、纯 3D 矢量锐利足球场白线、
3D 足球门、跳远沙坑、升旗台、高杆照明灯塔）、网球场与篮球场（纯 3D 矢量 FIBA/ITF 白线、3D 球网与篮架、围网、休憩亭）。
数据来自 data/site.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ/blender/build/site.py').read())
"""
import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ'
S = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Site'

MATS = {
    'M_Ground': (0.32, 0.39, 0.23, 0.95),
    'M_Asphalt': (0.17, 0.17, 0.19, 0.88),
    'M_Paving': (0.66, 0.65, 0.62, 0.84),
    'M_TrackRed': (0.55, 0.16, 0.12, 0.88),
    'M_Turf': (0.15, 0.38, 0.14, 0.95),
    'M_LineWhite': (0.96, 0.97, 0.96, 0.55),
    'M_Cloud_Slab': (0.22, 0.24, 0.27, 0.45),
    'M_Cloud_Skylight': (0.22, 0.30, 0.38, 0.12),
    'M_AccentRed': (0.76, 0.16, 0.10, 0.50),
    'M_FenceMesh': (0.14, 0.26, 0.18, 0.65),
}


def fresh_mesh(name):
    old = bpy.data.meshes.get(name)
    if old is not None:
        bpy.data.meshes.remove(old, do_unlink=True)
    return bpy.data.meshes.new(name)


def paving_mat():
    m = bpy.data.materials.get('M_Paving')
    if m is None:
        m = bpy.data.materials.new('M_Paving')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    ap = os.path.join(ROOT, 'blender', 'textures', 'paving_albedo.png')
    np_ = os.path.join(ROOT, 'blender', 'textures', 'paving_normal.png')
    if os.path.exists(ap):
        ta = nt.nodes.new('ShaderNodeTexImage')
        ia = bpy.data.images.load(ap, check_existing=True); ia.reload()
        ta.image = ia
        nt.links.new(ta.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.66, 0.65, 0.62, 1.0)
    if os.path.exists(np_):
        tn = nt.nodes.new('ShaderNodeTexImage')
        in_ = bpy.data.images.load(np_, check_existing=True); in_.reload()
        in_.colorspace_settings.name = 'Non-Color'
        tn.image = in_
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = 0.25
        nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.84
    m.diffuse_color = (0.66, 0.65, 0.62, 1.0)
    return m


def mat(name):
    if name == 'M_Paving':
        return paving_mat()
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
    """单一图集材质覆盖足球场、网球场、西篮球场、东北篮球场底色与草坪条纹（锐利白线由 3D 矢量网格承担）。"""
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
    bsdf.inputs['Roughness'].default_value = 0.88
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
    me = fresh_mesh(name)
    bm.to_mesh(me)
    bm.free()
    m = material if isinstance(material, bpy.types.Material) else mat(material)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def slab(name, poly, z, thick, material, c):
    """多边形平板：顶面在 z，向下 thick；自动三角化并赋世界平面 UV。"""
    bm = bmesh.new()
    top = [bm.verts.new((x, y, z)) for x, y in poly]
    f = bm.faces.new(top)
    if thick > 0:
        r = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, vec=(0, 0, -thick),
                            verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('UVMap')
    for ff in bm.faces:
        for lp in ff.loops:
            lp[uvl].uv = (lp.vert.co.x / 6.0, lp.vert.co.y / 6.0)
    return obj(name, bm, material, c)


def uv_quad(name, corners_xy, z, uvs, material, c):
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


# ---------- 3D 矢量球场白线几何工具（单 Draw Call 绝对锐利，杜绝贴图模糊） ----------

def add_vec_seg(bm, p0, p1, w, z, extend=0.0):
    """在水平面 z 处添加从 p0 到 p1、宽 w 的扁平矢量线段。"""
    x0, y0 = p0; x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 1e-4:
        return
    ux, uy = dx / L, dy / L
    nx, ny = -uy * (w * 0.5), ux * (w * 0.5)
    if extend > 0.0:
        x0 -= ux * extend; y0 -= uy * extend
        x1 += ux * extend; y1 += uy * extend
    vs = [
        bm.verts.new((x0 + nx, y0 + ny, z)),
        bm.verts.new((x0 - nx, y0 - ny, z)),
        bm.verts.new((x1 - nx, y1 - ny, z)),
        bm.verts.new((x1 + nx, y1 + ny, z)),
    ]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.z < 0:
        f.normal_flip()


def add_vec_rect(bm, P, x0, y0, x1, y1, w, z):
    hw = w * 0.5
    add_vec_seg(bm, P(x0, y0), P(x1, y0), w, z, extend=hw)
    add_vec_seg(bm, P(x1, y0), P(x1, y1), w, z, extend=hw)
    add_vec_seg(bm, P(x1, y1), P(x0, y1), w, z, extend=hw)
    add_vec_seg(bm, P(x0, y1), P(x0, y0), w, z, extend=hw)


def add_vec_arc(bm, P, cx, cy, r, a0_rad, a1_rad, w, z, segs=48):
    r_in = max(0.01, r - w * 0.5)
    r_out = r + w * 0.5
    pts_in = []
    pts_out = []
    for i in range(segs + 1):
        a = a0_rad + (a1_rad - a0_rad) * (i / segs)
        ca, sa = math.cos(a), math.sin(a)
        pts_in.append(bm.verts.new((*P(cx + r_in * ca, cy + r_in * sa), z)))
        pts_out.append(bm.verts.new((*P(cx + r_out * ca, cy + r_out * sa), z)))
    for i in range(segs):
        f = bm.faces.new((pts_out[i], pts_out[i + 1], pts_in[i + 1], pts_in[i]))
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()


def add_vec_disk(bm, P, cx, cy, r, z, segs=16):
    vs = [bm.verts.new((*P(cx + r * math.cos(2 * math.pi * i / segs),
                           cy + r * math.sin(2 * math.pi * i / segs)), z)) for i in range(segs)]
    f = bm.faces.new(vs)
    f.normal_update()
    if f.normal.z < 0:
        f.normal_flip()
    bmesh.ops.triangulate(bm, faces=[f])


def add_football_vector_lines(bm, P, z):
    """FIFA 标准 105 × 68 m 足球场纯 3D 矢量白线（线宽 0.15 m，任意近中远距均绝对清晰）。"""
    L, W = 105.0, 68.0
    lw = 0.15
    # 外框 + 中线 + 中圈 + 中点
    add_vec_rect(bm, P, -W / 2, -L / 2, W / 2, L / 2, lw, z)
    add_vec_seg(bm, P(-W / 2, 0.0), P(W / 2, 0.0), lw, z)
    add_vec_arc(bm, P, 0.0, 0.0, 9.15, 0.0, 2 * math.pi, lw, z, segs=64)
    add_vec_disk(bm, P, 0.0, 0.0, 0.34, z, segs=16)

    # 南北大小禁区、点球点、罚球弧
    ang_pen = math.acos(5.5 / 9.15)  # ~0.926 rad
    for sgn in (1.0, -1.0):
        gl = sgn * L / 2.0
        y_pen = gl - sgn * 16.5
        y_goal = gl - sgn * 5.5
        y_spot = gl - sgn * 11.0
        add_vec_rect(bm, P, -20.16, min(gl, y_pen), 20.16, max(gl, y_pen), lw, z)
        add_vec_rect(bm, P, -9.16, min(gl, y_goal), 9.16, max(gl, y_goal), lw, z)
        add_vec_disk(bm, P, 0.0, y_spot, 0.28, z, segs=14)
        if sgn > 0:
            # 北侧罚球弧朝 -Y（即 -pi/2 ± ang_pen）
            add_vec_arc(bm, P, 0.0, y_spot, 9.15, -math.pi / 2 - ang_pen, -math.pi / 2 + ang_pen, lw, z, segs=28)
        else:
            # 南侧罚球弧朝 +Y（即 +pi/2 ± ang_pen）
            add_vec_arc(bm, P, 0.0, y_spot, 9.15, math.pi / 2 - ang_pen, math.pi / 2 + ang_pen, lw, z, segs=28)

    # 四角角球弧 (R = 1.25 m)
    add_vec_arc(bm, P, -W / 2, -L / 2, 1.25, 0.0, math.pi / 2, lw, z, segs=10)
    add_vec_arc(bm, P, W / 2, -L / 2, 1.25, math.pi / 2, math.pi, lw, z, segs=10)
    add_vec_arc(bm, P, W / 2, L / 2, 1.25, math.pi, 1.5 * math.pi, lw, z, segs=10)
    add_vec_arc(bm, P, -W / 2, L / 2, 1.25, 1.5 * math.pi, 2 * math.pi, lw, z, segs=10)


def add_basketball_vector_lines(bm, P, z):
    """FIBA 标准 28 × 15 m 室外篮球场纯 3D 矢量白线（局部 +X 为长轴 28 m，+Y 为宽轴 15 m）。"""
    L, W = 28.0, 15.0
    lw = 0.08
    add_vec_rect(bm, P, -L / 2, -W / 2, L / 2, W / 2, lw, z)
    add_vec_seg(bm, P(0.0, -W / 2), P(0.0, W / 2), lw, z)
    add_vec_arc(bm, P, 0.0, 0.0, 1.80, 0.0, 2 * math.pi, lw, z, segs=36)

    dy_corner = math.sqrt(6.75 ** 2 - 6.6 ** 2)
    ang_3 = math.asin(6.6 / 6.75)  # ~1.359 rad (~77.9 deg from +X/-X axis)
    for sgn in (1.0, -1.0):
        bl = sgn * L / 2.0
        x_ft = bl - sgn * 5.8
        x_hoop = bl - sgn * 1.575
        add_vec_rect(bm, P, min(bl, x_ft), -2.45, max(bl, x_ft), 2.45, lw, z)
        add_vec_arc(bm, P, x_ft, 0.0, 1.80, 0.0, 2 * math.pi, lw, z, segs=32)
        # 三分底角直线 + 三分弧
        x_join = x_hoop - sgn * dy_corner
        add_vec_seg(bm, P(bl, -6.6), P(x_join, -6.6), lw, z, extend=lw * 0.5)
        add_vec_seg(bm, P(bl, 6.6), P(x_join, 6.6), lw, z, extend=lw * 0.5)
        if sgn > 0:
            # +X 端篮筐，弧朝 -X（pi ± ang_3）
            add_vec_arc(bm, P, x_hoop, 0.0, 6.75, math.pi - ang_3, math.pi + ang_3, lw, z, segs=36)
        else:
            # -X 端篮筐，弧朝 +X（-ang_3 .. +ang_3）
            add_vec_arc(bm, P, x_hoop, 0.0, 6.75, -ang_3, ang_3, lw, z, segs=36)


def add_tennis_vector_lines(bm, P, z):
    """ITF 标准 23.77 × 10.97 m 网球场纯 3D 矢量白线（局部 +X 为长轴 23.77 m，+Y 为宽轴 10.97 m）。"""
    L, W = 23.77, 10.97
    Ws = 8.23
    L_srv = 6.40
    lw = 0.075
    add_vec_rect(bm, P, -L / 2, -W / 2, L / 2, W / 2, lw, z)
    add_vec_seg(bm, P(-L / 2, -Ws / 2), P(L / 2, -Ws / 2), lw, z)
    add_vec_seg(bm, P(-L / 2, Ws / 2), P(L / 2, Ws / 2), lw, z)
    add_vec_seg(bm, P(-L_srv, -Ws / 2), P(-L_srv, Ws / 2), lw, z)
    add_vec_seg(bm, P(L_srv, -Ws / 2), P(L_srv, Ws / 2), lw, z)
    add_vec_seg(bm, P(-L_srv, 0.0), P(L_srv, 0.0), lw, z)
    add_vec_seg(bm, P(-L / 2, 0.0), P(-L / 2 + 0.35, 0.0), lw, z)
    add_vec_seg(bm, P(L / 2, 0.0), P(L / 2 - 0.35, 0.0), lw, z)


def stadium_ring(r_in, r_out, straight, seg=56):
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


def add_ring_to_bm(bm, outer, inner, z):
    vo = [bm.verts.new((x, y, z)) for x, y in outer]
    vi = [bm.verts.new((x, y, z)) for x, y in inner]
    n = len(vo)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((vo[i], vo[j], vi[j], vi[i]))
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()


def ring_mesh(name, outer, inner, z, material, c):
    bm = bmesh.new()
    add_ring_to_bm(bm, outer, inner, z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 6.0, lp.vert.co.y / 6.0)
    return obj(name, bm, material, c)


def football_goal_mesh():
    bm = bmesh.new()
    hw, h, dt, db = 3.66, 2.44, 0.85, 2.0
    add_cyl(bm, (-hw, 0, 0), (-hw, 0, h), 0.08, 10, 0)
    add_cyl(bm, (hw, 0, 0), (hw, 0, h), 0.08, 10, 0)
    add_cyl(bm, (-hw - 0.05, 0, h), (hw + 0.05, 0, h), 0.08, 10, 0)
    add_cyl(bm, (-hw, 0, h), (-hw, dt, h), 0.045, 6, 0)
    add_cyl(bm, (hw, 0, h), (hw, dt, h), 0.045, 6, 0)
    add_cyl(bm, (-hw, dt, h), (hw, dt, h), 0.045, 6, 0)
    add_cyl(bm, (-hw, dt, h), (-hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (hw, dt, h), (hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (-hw, 0, 0.04), (-hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (hw, 0, 0.04), (hw, db, 0.04), 0.045, 6, 0)
    add_cyl(bm, (-hw, db, 0.04), (hw, db, 0.04), 0.045, 6, 0)
    v_fl0 = bm.verts.new((-hw, 0.04, 0.04))
    v_fr0 = bm.verts.new((hw, 0.04, 0.04))
    v_fl1 = bm.verts.new((-hw, 0.04, h - 0.04))
    v_fr1 = bm.verts.new((hw, 0.04, h - 0.04))
    v_btl = bm.verts.new((-hw, dt, h - 0.04))
    v_btr = bm.verts.new((hw, dt, h - 0.04))
    v_bbl = bm.verts.new((-hw, db, 0.04))
    v_bbr = bm.verts.new((hw, db, 0.04))
    for verts in (
        (v_fl1, v_fr1, v_btr, v_btl),
        (v_btl, v_btr, v_bbr, v_bbl),
        (v_fl0, v_fl1, v_btl, v_bbl),
        (v_fr0, v_bbr, v_btr, v_fr1),
    ):
        f = bm.faces.new(verts)
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh('Site_FootballGoalUnit')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_LineWhite'))
    me.materials.append(mat('M_FenceMesh'))
    return me


def floodlight_mesh():
    bm = bmesh.new()
    add_box(bm, (-0.35, -0.35, 0), (0.35, 0.35, 0.5), 1)
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.22, radius2=0.11, depth=18.5,
                                matrix=Matrix.Translation((0, 0, 9.5)))
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 0
    add_box(bm, (-1.6, -0.2, 18.4), (1.6, 0.25, 19.7), 1)
    add_box(bm, (-1.45, 0.25, 18.55), (1.45, 0.38, 19.55), 0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh('Site_FloodlightUnit')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_LineWhite'))
    me.materials.append(mat('M_Cloud_Slab'))
    return me


def basket_hoop_mesh():
    bm = bmesh.new()
    add_box(bm, (-0.55, -1.65, 0.0), (0.55, -0.45, 0.72), 0)
    add_cyl(bm, (0, -1.05, 0.7), (0, -0.95, 3.35), 0.09, 8, 0)
    add_cyl(bm, (0, -0.95, 3.32), (0, 0.28, 3.32), 0.08, 8, 0)
    add_cyl(bm, (0, -0.98, 2.55), (0, 0.15, 3.30), 0.05, 6, 0)
    add_box(bm, (-0.90, 0.33, 2.90), (0.90, 0.38, 3.95), 1)
    for p0, p1 in (
        ((-0.91, 0.38, 2.90), (0.91, 0.40, 2.95)),
        ((-0.91, 0.38, 3.90), (0.91, 0.40, 3.95)),
        ((-0.91, 0.38, 2.90), (-0.86, 0.40, 3.95)),
        ((0.86, 0.38, 2.90), (0.91, 0.40, 3.95)),
    ):
        add_box(bm, p0, p1, 2)
    nseg = 12
    rc = 0.23
    cy_rim = 0.72
    pts = [(rc * math.cos(2 * math.pi * i / nseg), cy_rim + rc * math.sin(2 * math.pi * i / nseg), 3.05) for i in range(nseg)]
    for i in range(nseg):
        add_cyl(bm, pts[i], pts[(i + 1) % nseg], 0.022, 6, 3)
    add_box(bm, (-0.08, 0.38, 3.00), (0.08, 0.50, 3.08), 3)
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=0.14, radius2=0.22, depth=0.42,
                                matrix=Matrix.Translation((0, cy_rim, 2.83)))
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh('Site_BasketHoopUnit')
    bm.to_mesh(me)
    bm.free()
    for mn in ('M_Cloud_Slab', 'M_Cloud_Skylight', 'M_LineWhite', 'M_AccentRed'):
        me.materials.append(mat(mn))
    return me


def build_track(c, bm_vec):
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

    # 1. 跑道塑胶面 + 合并为单网格的 7 条白色分道线（加宽至 7.5 cm 减轻远距莫尔纹）
    out_, in_ = stadium_ring(r_kerb, r_out, straight)
    ring_mesh('Site_Track_Surface', place(out_, cx, cy, ang), place(in_, cx, cy, ang), z + 0.10, 'M_TrackRed', c)
    bm_lanes = bmesh.new()
    r = r_kerb + 0.3
    while r + 0.05 < r_out:
        o, i = stadium_ring(r - 0.0375, r + 0.0375, straight)
        add_ring_to_bm(bm_lanes, place(o, cx, cy, ang), place(i, cx, cy, ang), z + 0.135)
        r += 1.22
    bmesh.ops.recalc_face_normals(bm_lanes, faces=bm_lanes.faces)
    obj('Site_Track_Lanes', bm_lanes, 'M_LineWhite', c)

    # 2. 内场 D 区底草坪 + 105×68 m 条纹足球场底纹 + 纯 3D 矢量锐利足球场白线
    _, inner = stadium_ring(r_kerb, r_kerb, straight)
    slab('Site_Track_Infield', place(inner, cx, cy, ang), z + 0.09, 0, 'M_Turf', c)

    scale_pad = 1024.0 / (1024.0 - 28.0)
    hw_p = 34.0 * scale_pad
    hl_p = 52.5 * scale_pad
    pitch_xy = [P(-hw_p, -hl_p), P(hw_p, -hl_p), P(hw_p, hl_p), P(-hw_p, hl_p)]
    pitch_uv = [(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)]
    uv_quad('Site_Track_Pitch', pitch_xy, z + 0.125, pitch_uv, sports_atlas_mat(), c)
    add_football_vector_lines(bm_vec, P, z + 0.145)

    # 3. 两端 3D 足球门框 + 球网
    goal_me = football_goal_mesh()
    for name, yl, rot_extra in (('Site_FootballGoal_N', 52.5, 0.0), ('Site_FootballGoal_S', -52.5, math.pi)):
        gx, gy = P(0.0, yl)
        go = bpy.data.objects.new(name, goal_me)
        go.location = (gx, gy, z + 0.125)
        go.rotation_euler = (0.0, 0.0, ang_rad + rot_extra)
        c.objects.link(go)

    # 4. 北侧 D 区：跳远助跑道 + 双白色沙坑
    lj_runway = [P(-16.0, 58.2), P(16.0, 58.2), P(16.0, 60.0), P(-16.0, 60.0)]
    slab('Site_Track_LongJumpRunway', lj_runway, z + 0.125, 0.0, 'M_Paving', c)
    for tag, x0, x1 in (('W', -21.5, -14.5), ('E', 14.5, 21.5)):
        pit = [P(x0, 57.5), P(x1, 57.5), P(x1, 60.8), P(x0, 60.8)]
        slab(f'Site_Track_SandPit_{tag}', pit, z + 0.135, 0.0, 'M_LineWhite', c)

    # 5. 南侧 D 区：升旗石质方台 + 3 根旗杆与微褶飘扬红旗
    fp_poly = [P(-3.2, -68.0), P(3.2, -68.0), P(3.2, -62.0), P(-3.2, -62.0)]
    slab('Site_Track_FlagPodium', fp_poly, z + 0.38, 0.30, 'M_Paving', c)
    bm_fl = bmesh.new()
    for dx_f, h_f in ((-1.8, 10.5), (0.0, 12.2), (1.8, 10.5)):
        fx, fy = P(dx_f, -65.0)
        add_cyl(bm_fl, (fx, fy, z + 0.38), (fx, fy, z + 0.38 + h_f), 0.06, 8, 0)
        # 4 段微波动飘扬旗面（代替生硬平板）
        z_bot_f = z + 0.38 + h_f - 1.25
        z_top_f = z + 0.38 + h_f - 0.10
        cols_b, cols_t = [], []
        for s_i in range(5):
            t = s_i / 4.0
            wav = 0.10 * math.sin(t * math.pi * 2.0) * t
            qx, qy = P(dx_f + 1.85 * t, -65.0 + wav)
            cols_b.append(bm_fl.verts.new((qx, qy, z_bot_f - 0.04 * t)))
            cols_t.append(bm_fl.verts.new((qx, qy, z_top_f - 0.04 * t)))
        for s_i in range(4):
            f = bm_fl.faces.new((cols_b[s_i], cols_b[s_i + 1], cols_t[s_i + 1], cols_t[s_i]))
            f.material_index = 1
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm_fl, faces=bm_fl.faces)
    me_fl = fresh_mesh('Site_Track_Flagpoles')
    bm_fl.to_mesh(me_fl)
    bm_fl.free()
    me_fl.materials.append(mat('M_LineWhite'))
    me_fl.materials.append(mat('M_AccentRed'))
    c.objects.link(bpy.data.objects.new('Site_Track_Flagpoles', me_fl))

    # 6. 4 座高杆照明灯塔
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
    bm = bmesh.new()
    n = len(corners_xy)
    for i in range(n):
        if i in skip_edges:
            continue
        (x0, y0), (x1, y1) = corners_xy[i], corners_xy[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        for hz in (0.12, height * 0.5, height):
            add_cyl(bm, (x0, y0, z0 + hz), (x1, y1, z0 + hz), 0.04, 6, 0)
        nsegs = max(2, int(round(L / 3.5)))
        for s in range(nsegs + 1):
            t = s / nsegs
            px = x0 + (x1 - x0) * t
            py = y0 + (y1 - y0) * t
            add_cyl(bm, (px, py, z0), (px, py, z0 + height), 0.045, 6, 0)
        vs = [
            bm.verts.new((x0, y0, z0 + 0.12)),
            bm.verts.new((x1, y1, z0 + 0.12)),
            bm.verts.new((x1, y1, z0 + height)),
            bm.verts.new((x0, y0, z0 + height)),
        ]
        f = bm.faces.new(vs)
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Cloud_Slab'))
    me.materials.append(mat('M_FenceMesh'))
    c.objects.link(bpy.data.objects.new(name, me))


def build_courts(c, bm_vec):
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

        if v['kind'] == 'tennis':
            u0, u1, v0, v1 = 0.5, 1.0, 0.5, 1.0
            add_tennis_vector_lines(bm_vec, P, z + 0.138)
        elif k == 'basket_W':
            u0, u1, v0, v1 = 0.0, 0.5, 0.0, 0.5
            add_basketball_vector_lines(bm_vec, P, z + 0.138)
        else:
            u0, u1, v0, v1 = 0.5, 1.0, 0.0, 0.5
            add_basketball_vector_lines(bm_vec, P, z + 0.138)

        uvs = [(u1, v0), (u1, v1), (u0, v1), (u0, v0)]
        uv_quad(f'Site_Court_{k}', corners, z + 0.12, uvs, atlas, c)
        slab(f'Site_Court_{k}_Base', corners, z + 0.10, 0.25, 'M_Paving', c)

        if v['kind'] == 'tennis':
            bm_net = bmesh.new()
            nhw = W / 2.0 + 0.91
            p_l = P(0.0, -nhw)
            p_r = P(0.0, nhw)
            add_cyl(bm_net, (p_l[0], p_l[1], z + 0.12), (p_l[0], p_l[1], z + 1.19), 0.055, 8, 0)
            add_cyl(bm_net, (p_r[0], p_r[1], z + 0.12), (p_r[0], p_r[1], z + 1.19), 0.055, 8, 0)
            add_cyl(bm_net, (p_l[0], p_l[1], z + 1.15), (p_r[0], p_r[1], z + 1.15), 0.032, 6, 1)
            vs = [
                bm_net.verts.new((p_l[0], p_l[1], z + 0.14)),
                bm_net.verts.new((p_r[0], p_r[1], z + 0.14)),
                bm_net.verts.new((p_r[0], p_r[1], z + 1.12)),
                bm_net.verts.new((p_l[0], p_l[1], z + 1.12)),
            ]
            f = bm_net.faces.new(vs)
            f.material_index = 2
            bmesh.ops.recalc_face_normals(bm_net, faces=bm_net.faces)
            me_n = fresh_mesh(f'Site_Court_{k}_Net')
            bm_net.to_mesh(me_n)
            bm_net.free()
            me_n.materials.append(mat('M_Cloud_Slab'))
            me_n.materials.append(mat('M_LineWhite'))
            me_n.materials.append(mat('M_FenceMesh'))
            c.objects.link(bpy.data.objects.new(f'Site_Court_{k}_Net', me_n))
            build_fence(f'Site_Court_{k}_Fence', corners, z + 0.12, 4.0, c)

        else:
            for tag, xl, rot_h in (('S', -(L / 2.0 + 0.85), a - math.pi / 2), ('N', L / 2.0 + 0.85, a + math.pi / 2)):
                hx, hy = P(xl, 0.0)
                ho = bpy.data.objects.new(f'Site_Court_{k}_Hoop_{tag}', hoop_me)
                ho.location = (hx, hy, z + 0.12)
                ho.rotation_euler = (0.0, 0.0, rot_h)
                c.objects.link(ho)

            if k == 'basket_W':
                build_fence('Site_Court_basket_W_Fence', corners, z + 0.12, 4.0, c)
                shed = [P(-hl - 5.5, hw - 1.5), P(-hl - 0.5, hw - 1.5), P(-hl - 0.5, hw + 5.0), P(-hl - 5.5, hw + 5.0)]
                slab('Site_Court_basket_W_Shed', shed, z + 3.4, 3.4, 'M_LineWhite', c)
            else:
                bm_acc = bmesh.new()
                for xl in (-9.5, 0.0, 9.5):
                    lx, ly = P(xl, hw + 0.6)
                    # 灯杆底座法兰盘 + 灯杆
                    add_cyl(bm_acc, (lx, ly, z + 0.10), (lx, ly, z + 0.24), 0.18, 10, 0)
                    add_cyl(bm_acc, (lx, ly, z + 0.12), (lx, ly, z + 7.2), 0.09, 8, 0)
                    px0, py0 = P(xl - 0.65, hw + 0.45)
                    px1, py1 = P(xl + 0.65, hw + 0.45)
                    add_cyl(bm_acc, (px0, py0, z + 7.2), (px1, py1, z + 7.2), 0.06, 6, 0)
                for xl in (-5.0, 5.0):
                    bx0, by0 = P(xl - 1.4, hw + 0.4)
                    bx1, by1 = P(xl + 1.4, hw + 0.4)
                    add_cyl(bm_acc, (bx0, by0, z + 0.48), (bx1, by1, z + 0.48), 0.14, 6, 0)
                bmesh.ops.recalc_face_normals(bm_acc, faces=bm_acc.faces)
                me_a = fresh_mesh('Site_Court_basket_NE_Poles')
                bm_acc.to_mesh(me_a)
                bm_acc.free()
                me_a.materials.append(mat('M_Cloud_Slab'))
                c.objects.link(bpy.data.objects.new('Site_Court_basket_NE_Poles', me_a))

    # 网球场东侧休憩遮阳亭
    tn, ts = S['courts']['tennis_N'], S['courts']['tennis_S']
    px = (tn['center'][0] + ts['center'][0]) * 0.5
    py = (tn['center'][1] + ts['center'][1]) * 0.5
    ang_t = math.radians(tn['long_axis_deg_from_E'])
    ct, st = math.cos(ang_t), math.sin(ang_t)
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

    # 体育及艺术中心西侧室外训练区
    wplaza = [(-290.0, -172.0), (-248.0, -172.0), (-268.0, -68.0), (-290.0, -68.0)]
    slab('Site_SportsWest_Plaza', wplaza, -5.92, 0.2, 'M_Paving', c)
    for idx, (hx, hy) in enumerate(((-272.0, -108.0), (-268.0, -128.0), (-264.0, -148.0))):
        ho = bpy.data.objects.new(f'Site_SportsWest_Hoop_{idx}', hoop_me)
        ho.location = (hx, hy, -5.92)
        ho.rotation_euler = (0.0, 0.0, math.radians(-108.0))
        c.objects.link(ho)


def build_road_markings(c):
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


def build_nav_ramps(c):
    rp_path = os.path.join(ROOT, 'data', 'nav_ramps.json')
    if not os.path.exists(rp_path):
        return
    R = json.load(open(rp_path))
    bm = bmesh.new()
    for item in R.get('ramps', []):
        p0 = Vector(item['p0'])
        p1 = Vector(item['p1'])
        w = float(item.get('width', 5.0))
        d = Vector((p1.x - p0.x, p1.y - p0.y, 0.0))
        L = d.length
        if L < 0.5:
            continue
        nx, ny = -d.y / L * (w * 0.5), d.x / L * (w * 0.5)
        n_off = Vector((nx, ny, 0.0))
        dz = Vector((0.0, 0.0, -0.45))
        v0 = bm.verts.new(p0 - n_off); v1 = bm.verts.new(p0 + n_off)
        v2 = bm.verts.new(p1 + n_off); v3 = bm.verts.new(p1 - n_off)
        b0 = bm.verts.new(p0 - n_off + dz); b1 = bm.verts.new(p0 + n_off + dz)
        b2 = bm.verts.new(p1 + n_off + dz); b3 = bm.verts.new(p1 - n_off + dz)
        for q in ((v0, v1, v2, v3), (b3, b2, b1, b0), (v0, b0, b1, v1),
                  (v1, b1, b2, v2), (v2, b2, b3, v3), (v3, b3, b0, v0)):
            bm.faces.new(q).material_index = 0
        for sgn in (-1.0, 1.0):
            ra = p0 + n_off * sgn
            rb = p1 + n_off * sgn
            add_cyl(bm, ra + Vector((0, 0, 0.98)), rb + Vector((0, 0, 0.98)), 0.04, 6, 1)
            for k in range(5):
                t = k / 4.0
                rp = ra.lerp(rb, t)
                add_cyl(bm, rp, rp + Vector((0, 0, 0.98)), 0.035, 6, 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 6.0, lp.vert.co.y / 6.0)
    me = fresh_mesh('Site_NavRamps')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Paving'))
    me.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new('Site_NavRamps', me))


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
    bm_vec = bmesh.new()
    build_track(c, bm_vec)
    build_courts(c, bm_vec)
    bmesh.ops.recalc_face_normals(bm_vec, faces=bm_vec.faces)
    obj('Site_Sports_VectorLines', bm_vec, 'M_LineWhite', c)
    build_nav_ramps(c)
    bpy.ops.wm.save_mainfile()
    print('site objects', len(c.objects))


main()
