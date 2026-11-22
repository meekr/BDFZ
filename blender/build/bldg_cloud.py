"""P2–P8 学术中心建模（含星形庭院三维重构、退进式开敞外廊与3D廊柱/栏杆、北翼第三条天窗、直立锁边金属坡屋面）。
数据：data/bldg_cloud.json、bldg_cloud_p3.json、bldg_cloud_roof.json、cloud_courtyard.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_cloud.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud.json')))
P3 = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud_p3.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
CY = json.load(open(os.path.join(ROOT, 'data', 'cloud_courtyard.json')))
COLL = 'Bldg_Cloud'

RAMP_ANG = math.radians(P3.get('ramp_axis_deg', -10.0))
U_S, U_N = P3.get('ramp_u', P3['ramp_y'])
LV = {k: tuple(v) for k, v in P3['levels'].items()}
SLAB_T = 0.8
COL_R = 0.45
BAY = 1.5
COURT_BAY = 4.2
PANEL_CYCLE = (13.5, 4.5)
ROOF_FASCIA = 2.0

MATS = {
    'M_Cloud_Slab': (0.22, 0.24, 0.27, 0.45),        # 深灰金属板楼板带与檐口立面
    'M_Cloud_Core': (0.91, 0.91, 0.89, 0.72),        # 白色柱身与实墙
    'M_Paving': (0.68, 0.68, 0.66, 0.86),            # wx_02/15/23：明快浅灰石材铺装
    'M_Turf': (0.18, 0.39, 0.13, 0.92),              # 庭院鲜绿草坪与草坡
    'M_Cloud_RoofRim': (0.70, 0.72, 0.73, 0.45),     # 屋面顶缘浅灰金属压顶
    'M_Cloud_Skylight': (0.18, 0.26, 0.34, 0.12),    # 采光井玻璃天窗
    'M_TreeCrown': (0.14, 0.31, 0.11, 0.88),         # 灌木球冠复用
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
            if name in ('M_Cloud_Slab', 'M_Cloud_RoofRim'):
                bsdf.inputs['Metallic'].default_value = 0.25
            elif name == 'M_Cloud_Skylight':
                bsdf.inputs['Metallic'].default_value = 0.45
        m.diffuse_color = (r, g, b, 1)
    return m


def img_mat(name, fname, rough=0.15, metal=0.2, fallback=(0.5, 0.5, 0.5, 1)):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img_path = os.path.join(ROOT, 'blender', 'textures', fname)
    img = bpy.data.images.load(img_path, check_existing=True)
    img.reload()
    tex.image = img
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = fallback
    return m


def coll():
    c = bpy.data.collections.get(COLL)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def ramp_u(x, y):
    return y * math.cos(RAMP_ANG) + x * math.sin(RAMP_ANG)


def lerp_xy(x, y, south, north):
    u = ramp_u(x, y)
    if u <= U_S:
        return south
    if u >= U_N:
        return north
    t = (u - U_S) / (U_N - U_S)
    return south + t * (north - south)


def lv(name):
    s, n = LV[name]
    return lambda x, y: lerp_xy(x, y, s, n)


def poly_area_signed(ring):
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring))) * 0.5


def offset_ring(ring, d):
    """平面多边形等距偏移（d > 0 扩大面积，d < 0 缩小面积）。"""
    n = len(ring)
    out = []
    for i in range(n):
        a = Vector(ring[(i - 1) % n])
        b = Vector(ring[i])
        c = Vector(ring[(i + 1) % n])
        t1 = (b - a).normalized() if (b - a).length > 1e-4 else Vector((1, 0))
        t2 = (c - b).normalized() if (c - b).length > 1e-4 else t1
        nm = Vector((t1.y, -t1.x)) + Vector((t2.y, -t2.x))
        L = nm.length
        if L > 1e-4:
            # 防止尖角过度放大
            scale = min(1.5, 1.0 / max(0.4, (L * 0.5)))
            nm = nm.normalized() * scale
        else:
            nm = Vector((t1.y, -t1.x))
        out.append((b.x + nm.x * d, b.y + nm.y * d))
    a0 = abs(poly_area_signed(ring))
    a1 = abs(poly_area_signed(out))
    if (d > 0 and a1 < a0) or (d < 0 and a1 > a0):
        out = [(2 * ring[i][0] - out[i][0], 2 * ring[i][1] - out[i][1]) for i in range(n)]
    return out


def prism(name, outer, holes, base, top, material, c, cuts=(), top_mat=None):
    """带洞多边形拉伸。base/top 为常数或 f(x, y)。cuts 为沿过渡轴 u 的切割值。"""
    bm = bmesh.new()
    edges = []
    for ring in [outer] + list(holes):
        vs = [bm.verts.new((x, y, 0.0)) for x, y in ring]
        edges += [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    nx, ny = math.sin(RAMP_ANG), math.cos(RAMP_ANG)
    for u in cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(u * nx, u * ny, 0), plane_no=(nx, ny, 0))
    bmesh.ops.dissolve_limit(bm, angle_limit=0.0005, verts=bm.verts[:], edges=bm.edges[:], delimit=set())
    r = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    top_v = {v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)}
    for v in bm.verts:
        f = top if v in top_v else base
        v.co.z = f(v.co.x, v.co.y) if callable(f) else f
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if top_mat:
        for f in bm.faces:
            f.material_index = 1 if f.normal.z > 0.7 else 0
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(material))
    if top_mat:
        me.materials.append(mat(top_mat))
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def column_mesh(name='Bldg_Cloud_ColumnUnit', radius=COL_R):
    me = bpy.data.meshes.get(name)
    if me is None:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=radius, radius2=radius, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat('M_Cloud_Core'))
    return me


def columns(c):
    me = column_mesh('Bldg_Cloud_ColumnUnit', COL_R)
    fp, f1 = lv('pilotis'), lv('f1')
    for i, (x, y, nx, ny, kind) in enumerate(P3['columns']):
        if kind == 'slant':
            a = Vector((x - 3.5 * nx, y - 3.5 * ny, 0))
            b = Vector((x + 1.0 * nx, y + 1.0 * ny, 0))
        else:
            a = Vector((x, y, 0))
            b = Vector((x, y, 0))
        a.z = fp(a.x, a.y)
        b.z = f1(b.x, b.y) - SLAB_T
        o = bpy.data.objects.new(f'Bldg_Cloud_Column_{i:03d}', me)
        d = b - a
        o.location = a
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        o.scale = (1, 1, d.length)
        c.objects.link(o)


def add_rail_segment(bm, a, b, z0a, z0b, h=1.08, post_step=1.6):
    """两点间生成精致的 3D 金属护栏（顶扶手、中横杆、等距竖杆）。"""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 0.15:
        return
    # 顶扶手带
    for za_off, zb_off, thick in ((h - 0.08, h, 0.08), (0.08, 0.15, 0.07)):
        vs = [
            bm.verts.new((a[0], a[1], z0a + za_off)),
            bm.verts.new((b[0], b[1], z0b + za_off)),
            bm.verts.new((b[0], b[1], z0b + zb_off)),
            bm.verts.new((a[0], a[1], z0a + zb_off)),
        ]
        bm.faces.new(vs)
    # 竖向栏杆
    n = max(1, int(round(L / post_step)))
    pw = 0.055 / L
    for k in range(n + 1):
        t0 = max(0.0, k / n - pw * 0.5)
        t1 = min(1.0, k / n + pw * 0.5)
        if t1 - t0 < 1e-4:
            continue
        x0 = a[0] + (b[0] - a[0]) * t0
        y0 = a[1] + (b[1] - a[1]) * t0
        z0 = z0a + (z0b - z0a) * t0
        x1 = a[0] + (b[0] - a[0]) * t1
        y1 = a[1] + (b[1] - a[1]) * t1
        z1 = z0a + (z0b - z0a) * t1
        bm.faces.new([
            bm.verts.new((x0, y0, z0)),
            bm.verts.new((x1, y1, z1)),
            bm.verts.new((x1, y1, z1 + h)),
            bm.verts.new((x0, y0, z0 + h)),
        ])


def facade_and_galleries(c):
    """外立面：蓝灰玻璃带 + 白色实墙段；
    内院立面（P8 升级）：真实退进 2.4 m 的教室立面 + 前沿 3D 实例化白圆廊柱 + 连续金属栏杆 + 室外折跑连廊楼梯。"""
    storeys = [('f1', 'f2'), ('f2', 'f3'), ('f3', 'roof')]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    cyc = sum(PANEL_CYCLE)
    ring_specs = []
    court_edge_ring = None

    for p in P3['facade']:
        ring_specs.append((p['outer'], 'outer'))
        if p['holes']:
            big_h = max(p['holes'], key=len)
            court_edge_ring = big_h
            for h in p['holes']:
                if h is big_h:
                    # 内院教室退进 2.4 m（向洞口外侧扩出，即退入楼板内部）形成真实三维开敞外廊！
                    recessed = offset_ring(h, +2.4)
                    ring_specs.append((recessed, 'courtyard'))
                else:
                    ring_specs.append((h, 'skylight'))

    for ring, kind in ring_specs:
        pts = [Vector((x, y, 0)) for x, y in ring]
        seq = []
        s = 0.0
        step_len = COURT_BAY if kind == 'courtyard' else BAY * 2
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            L = (b - a).length
            cuts = {0.0, L}
            if kind == 'outer':
                t = cyc * math.ceil(s / cyc)
                while t < s + L:
                    for off in (0.0, PANEL_CYCLE[0]):
                        if s < t + off < s + L:
                            cuts.add(t + off - s)
                    t += cyc
            n = max(1, int(math.ceil(L / step_len)))
            cuts |= {L * k / n for k in range(n)}
            cs = sorted(cuts)
            for u0, u1 in zip(cs[:-1], cs[1:]):
                if u1 - u0 < 1e-3:
                    continue
                seq.append((a.lerp(b, u0 / L), a.lerp(b, u1 / L), s + u0, s + u1))
            s += L
        for lo, hi in storeys:
            flo, fhi = lv(lo), lv(hi)
            for a, b, s0, s1 in seq:
                za0, zb0 = flo(a.x, a.y), flo(b.x, b.y)
                za1, zb1 = fhi(a.x, a.y) - SLAB_T, fhi(b.x, b.y) - SLAB_T
                if max(za1 - za0, zb1 - zb0) < 0.3:
                    continue
                v = [bm.verts.new((a.x, a.y, za0)), bm.verts.new((b.x, b.y, zb0)),
                     bm.verts.new((b.x, b.y, zb1)), bm.verts.new((a.x, a.y, za1))]
                f = bm.faces.new(v)
                is_3f_north = (lo == 'f3' and -33.0 <= (a.x + b.x) * 0.5 <= 37.0 and (a.y + b.y) * 0.5 >= -22.0)
                if is_3f_north:
                    f.material_index = 3
                    uv_bay = BAY
                elif kind == 'courtyard':
                    f.material_index = 2
                    uv_bay = COURT_BAY
                elif kind == 'skylight':
                    f.material_index = 0
                    uv_bay = BAY
                else:
                    white = ((s0 + s1) / 2) % cyc > PANEL_CYCLE[0]
                    f.material_index = 1 if white else 0
                    uv_bay = BAY
                h = 4.5
                for lp, (uu, vv) in zip(f.loops, [(s0, za0), (s1, zb0), (s1, zb1), (s0, za1)]):
                    lp[uvl].uv = (uu / uv_bay, (vv - za0) / h)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    me = bpy.data.meshes.new('Bldg_Cloud_Facade')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(img_mat('M_Cloud_GlassGrid', 'cloud_glass.png', 0.08, 0.4, (0.30, 0.38, 0.45, 1)))
    me.materials.append(mat('M_Cloud_Core'))
    me.materials.append(img_mat('M_Cloud_Courtyard', 'cloud_courtyard.png', 0.55, 0.05, (0.82, 0.82, 0.80, 1)))
    me.materials.append(bpy.data.materials.get('M_SportsGlass') or mat('M_Cloud_Skylight'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_Facade', me))

    # 3D 开敞外廊前沿白色圆形廊柱（实例化）+ 连续金属栏杆（wx_15/wx_23/wx_32）
    if court_edge_ring:
        rail_ring = offset_ring(court_edge_ring, -0.15)
        col_ring = offset_ring(court_edge_ring, +0.25)
        bm_r = bmesh.new()
        n = len(rail_ring)
        for lo, hi in storeys:
            flo = lv(lo)
            for i in range(n):
                a, b = rail_ring[i], rail_ring[(i + 1) % n]
                add_rail_segment(bm_r, a, b, flo(a[0], a[1]), flo(b[0], b[1]), h=1.08, post_step=1.6)
        me_r = bpy.data.meshes.new('Bldg_Cloud_GalleryRails')
        bm_r.to_mesh(me_r)
        bm_r.free()
        me_r.materials.append(mat('M_Cloud_Slab'))
        c.objects.link(bpy.data.objects.new('Bldg_Cloud_GalleryRails', me_r))

        # 沿外廊每 ~5.0 m 一根白色圆廊柱（共 3 层，共用 1 份柱体网格 → 1 draw call）
        gcol_me = column_mesh('Bldg_Cloud_GalleryColUnit', 0.21)
        pts_c = [Vector((x, y)) for x, y in col_ring]
        col_xy = []
        acc = 0.0
        spacing = 5.2
        for i in range(len(pts_c)):
            a, b = pts_c[i], pts_c[(i + 1) % len(pts_c)]
            L = (b - a).length
            while acc < L:
                p = a.lerp(b, acc / max(L, 1e-4))
                col_xy.append((p.x, p.y))
                acc += spacing
            acc -= L
        idx = 0
        for lo, hi in storeys:
            flo, fhi = lv(lo), lv(hi)
            for (x, y) in col_xy:
                z0 = flo(x, y)
                z1 = fhi(x, y) - SLAB_T
                if z1 - z0 < 1.0:
                    continue
                co = bpy.data.objects.new(f'Bldg_Cloud_GalleryCol_{idx:03d}', gcol_me)
                co.location = (x, y, z0)
                co.scale = (1.0, 1.0, z1 - z0)
                c.objects.link(co)
                idx += 1


def pitched_roof(c):
    """P6 + P8：直立锁边纹理金属坡屋面 + 东西北三处条形玻璃天窗。"""
    R = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud_roof.json')))
    M = R['mesh']
    me = bpy.data.meshes.new('Bldg_Cloud_RoofSurface')
    me.from_pydata([tuple(v) for v in M['verts']], [], [tuple(f) for f in M['faces']])
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    b_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if b_edges:
        r_ext = bmesh.ops.extrude_edge_only(bm, edges=b_edges)
        bmesh.ops.translate(bm, vec=(0, 0, -0.28),
                            verts=[v for v in r_ext['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 10.0, lp.vert.co.y / 10.0)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(img_mat('M_Cloud_RoofPanel', 'roof_seam.png', 0.45, 0.28, (0.16, 0.19, 0.23, 1)))
    o = bpy.data.objects.new('Bldg_Cloud_RoofSurface', me)
    c.objects.link(o)

    # 东西两处 + 北翼第 3 处条形采光玻璃天窗（wx_02、wx_23）
    top = lv('roof')
    bm = bmesh.new()
    all_sky = list(R.get('skylights', []))
    if 'north_skylight' in CY:
        all_sky.append(CY['north_skylight'])
    for ring in all_sky:
        vs = [bm.verts.new((x, y, top(x, y) + 0.55)) for x, y in ring]
        if len(vs) >= 3:
            f = bm.faces.new(vs)
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me_s = bpy.data.meshes.new('Bldg_Cloud_Skylights')
    bm.to_mesh(me_s)
    bm.free()
    me_s.materials.append(mat('M_Cloud_Skylight'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_Skylights', me_s))
    return o


def lamp_mesh():
    """星形庭院细长深灰 T 形高杆庭院灯（wx_15 实景可见，实例化）。"""
    old = bpy.data.meshes.get('Bldg_Cloud_CourtLampUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.06, radius2=0.045, depth=3.4,
                          matrix=Matrix.Translation((0, 0, 1.7)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, 3.45)) @ Matrix.Diagonal((0.85, 0.14, 0.08, 1.0)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_Cloud_CourtLampUnit')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Cloud_Slab'))
    return me


def build_curbed_lawn(name, poly, z0, c, curb_w=0.28, curb_h=0.14):
    """带浅色石材路缘石的几何草坪岛（wx_02、wx_15、wx_23）。"""
    outer = offset_ring(poly, curb_w)
    bm = bmesh.new()
    vo_b = [bm.verts.new((x, y, z0)) for x, y in outer]
    vo_t = [bm.verts.new((x, y, z0 + curb_h)) for x, y in outer]
    vi_t = [bm.verts.new((x, y, z0 + curb_h)) for x, y in poly]
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        f1 = bm.faces.new((vo_b[i], vo_b[j], vo_t[j], vo_t[i]))
        f2 = bm.faces.new((vo_t[i], vo_t[j], vi_t[j], vi_t[i]))
        f1.material_index = 0
        f2.material_index = 0
    f_in = bm.faces.new(vi_t)
    f_in.material_index = 1
    bmesh.ops.triangulate(bm, faces=[f_in])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Cloud_Core'))
    me.materials.append(mat('M_Turf'))
    c.objects.link(bpy.data.objects.new(name, me))


def build_slope_turf(name, top_pts, bot_pts, z_top, z_bot, c):
    """连接抬高露台与 Z=0 庭院地面的三角形/折面陡草坡（wx_15/wx_23 标志特征）。"""
    bm = bmesh.new()
    vt = [bm.verts.new((x, y, z_top)) for x, y in top_pts]
    vb = [bm.verts.new((x, y, z_bot)) for x, y in bot_pts]
    for i in range(len(top_pts) - 1):
        f = bm.faces.new((vt[i], vt[i + 1], vb[i + 1], vb[i]))
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    # 两侧封口白石斜缘
    bm.faces.new((vt[0], vb[0], bm.verts.new((top_pts[0][0], top_pts[0][1], z_bot))))
    bm.faces.new((vt[-1], bm.verts.new((top_pts[-1][0], top_pts[-1][1], z_bot)), vb[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Turf'))
    c.objects.link(bpy.data.objects.new(name, me))


def courtyard_interior(c, court):
    """P8 星形庭院内部三维重构（数据来自 data/cloud_courtyard.json）：
    - 干净浅灰石材庭院地坪（屏蔽模糊 landcover 糊斑）
    - 西南图书馆斜向抬高露台 + 3 处路缘草坪岛 + 15 级扇形/梯形条纹大台阶
    - 东侧抬高露台 + 护栏 + 西向陡绿草坡
    - 西侧艺术馆展厅低层体块 + 护栏 + 南侧陡绿草坡
    - Z=0 五处带路缘石几何绿化岛 + 规整球状灌木群 + 12 盏高杆庭院灯
    """
    # 1. 干净浅灰石材庭院底板（覆盖整个庭院洞口投影，高出 Podium 0.04 m 彻底消除糊绿斑）
    court_floor_ring = offset_ring(court, +4.0)
    prism('Bldg_Cloud_CourtFloor', court_floor_ring, [], -0.02, 0.04, 'M_Paving', c)

    # 2. 西南图书馆抬高露台（Z=0..4.5 m，暗灰侧壁 + 浅灰铺装顶面）
    LT = CY['library_terrace']
    z0, z1 = LT['z_base'], LT['z_top']
    # T3 破壳：图书馆顶部仍保留完整露台屋面板 (Z=4.15..4.5) 供行走与俯视，下方变为通透玻璃幕墙+门洞，支持直接从星形庭院步入图书馆室内！
    prism('Bldg_Cloud_Library', LT['polygon'], [], z1 - 0.35, z1, 'M_Cloud_Slab', c, top_mat='M_Paving')
    bm_lw = bmesh.new()
    lp_pts = LT['polygon']
    for i in range(len(lp_pts)):
        a, b = lp_pts[i], lp_pts[(i + 1) % len(lp_pts)]
        mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
        # 北侧大台阶后方与西北入口处留空门洞，其余做半透玻璃围护
        if i == 4 or (-38.0 <= mx <= -16.0 and -80.0 <= my <= -68.0):
            continue
        vs = [bm_lw.verts.new((a[0], a[1], z0)), bm_lw.verts.new((b[0], b[1], z0)),
              bm_lw.verts.new((b[0], b[1], z1 - 0.35)), bm_lw.verts.new((a[0], a[1], z1 - 0.35))]
        bm_lw.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm_lw, faces=bm_lw.faces)
    me_lw = bpy.data.meshes.new('Bldg_Cloud_LibraryGlass'); bm_lw.to_mesh(me_lw); bm_lw.free()
    me_lw.materials.append(bpy.data.materials.get('M_SportsGlass') or mat('M_Cloud_Skylight'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_LibraryGlass', me_lw))
    # 露台顶面 3 处路缘草坪岛
    for k, poly in enumerate(LT['lawns']):
        build_curbed_lawn(f'Bldg_Cloud_CourtLawn_{k}', poly, z1 + 0.01, c)
    # 露台临空边护栏（西斜边与东斜边）
    bm_lr = bmesh.new()
    lp = LT['polygon']
    for i0, i1 in ((5, 0), (4, 3)):
        add_rail_segment(bm_lr, lp[i0], lp[i1], z1, z1, h=1.08, post_step=1.8)
    me_lr = bpy.data.meshes.new('Bldg_Cloud_LibraryRails')
    bm_lr.to_mesh(me_lr)
    bm_lr.free()
    me_lr.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_LibraryRails', me_lr))

    # 3. 扇形/梯形条纹大台阶（下口宽 6.5 m @ y=-55 → 上口宽 33 m @ y=-69.5，15 级深浅交替）
    GS = CY['grand_stairs']
    b0, b1 = Vector(GS['bot_edge'][0]), Vector(GS['bot_edge'][1])
    t0_pt, t1_pt = Vector(GS['top_edge'][0]), Vector(GS['top_edge'][1])
    steps = GS['steps']
    bm_st = bmesh.new()
    for i in range(steps):
        f0, f1 = i / steps, (i + 1) / steps
        pa0 = b0.lerp(t0_pt, f0)
        pb0 = b1.lerp(t1_pt, f0)
        pa1 = b0.lerp(t0_pt, f1)
        pb1 = b1.lerp(t1_pt, f1)
        zt = GS['z0'] + (GS['z1'] - GS['z0']) * f1
        zb = GS['z0']
        vs = [
            bm_st.verts.new((pa0.x, pa0.y, zb)), bm_st.verts.new((pb0.x, pb0.y, zb)),
            bm_st.verts.new((pb1.x, pb1.y, zb)), bm_st.verts.new((pa1.x, pa1.y, zb)),
            bm_st.verts.new((pa0.x, pa0.y, zt)), bm_st.verts.new((pb0.x, pb0.y, zt)),
            bm_st.verts.new((pb1.x, pb1.y, zt)), bm_st.verts.new((pa1.x, pa1.y, zt)),
        ]
        f_top = bm_st.faces.new(vs[4:8])
        f_top.material_index = 0  # 浅灰踏面
        bm_st.faces.new(vs[0:4]).material_index = 0
        for j in range(4):
            ff = bm_st.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4]))
            # 前立面（踢面）用深灰形成 wx_23/wx_02 标志性黑白条纹阶梯视觉
            ff.material_index = 1 if j == 0 else 0
    bmesh.ops.recalc_face_normals(bm_st, faces=bm_st.faces)
    me_st = bpy.data.meshes.new('Bldg_Cloud_CourtSteps')
    bm_st.to_mesh(me_st)
    bm_st.free()
    me_st.materials.append(mat('M_Paving'))
    me_st.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_CourtSteps', me_st))

    # 4. 东侧抬高露台（wx_15 右前景）+ 护栏 + 西向陡草坡
    ET = CY['east_terrace']
    prism('Bldg_Cloud_EastTerrace', ET['polygon'], [], ET['z_base'], ET['z_top'], 'M_Cloud_Slab', c, top_mat='M_Paving')
    build_slope_turf('Bldg_Cloud_EastSlope', ET['slope_top'], ET['slope_bot'], ET['z_top'], 0.04, c)
    bm_er = bmesh.new()
    ep = ET['polygon']
    for i0, i1 in ET['rail_edges']:
        add_rail_segment(bm_er, ep[i0], ep[i1], ET['z_top'], ET['z_top'], h=1.08, post_step=1.6)
    me_er = bpy.data.meshes.new('Bldg_Cloud_EastRails')
    bm_er.to_mesh(me_er)
    bm_er.free()
    me_er.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_EastRails', me_er))

    # 5. 西侧艺术馆展厅低层体块（wx_15 左中景）+ 玻璃立面 + 护栏 + 陡草坡
    WG = CY['west_gallery_volume']
    # T3 破壳：艺术馆展厅改为中空顶板 + 面向庭院敞开入口，支持自由步入展厅！
    bm_ag = bmesh.new()
    wgp = WG['polygon']
    for i in range(len(wgp)):
        if i == 1:  # 东向面对庭院中央的入口面留空门洞
            continue
        a, b = wgp[i], wgp[(i + 1) % len(wgp)]
        bm_ag.faces.new([bm_ag.verts.new((a[0], a[1], WG['z_base'])), bm_ag.verts.new((b[0], b[1], WG['z_base'])),
                         bm_ag.verts.new((b[0], b[1], WG['z_top'] - 0.8)), bm_ag.verts.new((a[0], a[1], WG['z_top'] - 0.8))])
    bmesh.ops.recalc_face_normals(bm_ag, faces=bm_ag.faces)
    me_ag = bpy.data.meshes.new('Bldg_Cloud_ArtGallery'); bm_ag.to_mesh(me_ag); bm_ag.free()
    me_ag.materials.append(bpy.data.materials.get('M_SportsGlass') or mat('M_Cloud_Skylight'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_ArtGallery', me_ag))
    prism('Bldg_Cloud_ArtGallery_Fascia', WG['polygon'], [], WG['z_top'] - 0.8, WG['z_top'], 'M_Cloud_Slab', c, top_mat='M_Paving')
    build_slope_turf('Bldg_Cloud_WestSlope', WG['slope_top'], WG['slope_bot'], WG['z_top'], 0.04, c)
    bm_wr = bmesh.new()
    wp = WG['polygon']
    for i0, i1 in ((1, 2), (2, 3)):
        add_rail_segment(bm_wr, wp[i0], wp[i1], WG['z_top'], WG['z_top'], h=1.05, post_step=1.5)
    me_wr = bpy.data.meshes.new('Bldg_Cloud_WestRails')
    bm_wr.to_mesh(me_wr)
    bm_wr.free()
    me_wr.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_WestRails', me_wr))

    # 6. Z=0 五处带路缘石几何花坛岛 + 规整低矮灌木球（合并为单网格）
    bm_sh = bmesh.new()
    for isl in CY['ground_islands']:
        build_curbed_lawn(f"Bldg_Cloud_Island_{isl['name']}", isl['poly'], 0.04, c)
        for sx, sy in isl.get('shrubs', []):
            bmesh.ops.create_icosphere(bm_sh, subdivisions=2, radius=0.82,
                                       matrix=Matrix.Translation((sx, sy, 0.58)) @ Matrix.Diagonal((1.0, 1.0, 0.65, 1.0)))
    for f in bm_sh.faces:
        f.smooth = True
    bmesh.ops.recalc_face_normals(bm_sh, faces=bm_sh.faces)
    me_sh = bpy.data.meshes.new('Bldg_Cloud_CourtShrubs')
    bm_sh.to_mesh(me_sh)
    bm_sh.free()
    me_sh.materials.append(mat('M_TreeCrown'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_CourtShrubs', me_sh))

    # 7. 12 盏高杆庭院灯（实例化，1 draw call）
    lm = lamp_mesh()
    for idx, (lx, ly, lz) in enumerate(CY.get('lamps', [])):
        lo = bpy.data.objects.new(f'Bldg_Cloud_CourtLamp_{idx:02d}', lm)
        lo.location = (lx, ly, lz + 0.04)
        c.objects.link(lo)


def bevel(o, w, seg=3):
    m = o.modifiers.new('Bevel', 'BEVEL')
    m.width = w
    m.segments = seg
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(50)
    m.harden_normals = False
    return m


def main():
    c = coll()
    sh = D['shell'][0]
    court = max(sh['holes'], key=len)
    zb = SITE['campus_base_z']
    cuts = (U_S, U_N)
    ANX = json.load(open(os.path.join(ROOT, 'data', 'bldg_annex.json')))
    sunken = [b['outer'] for b in ANX['blocks'].values() if b.get('sunken')]
    prism('Bldg_Cloud_Podium', sh['outer'], sunken, zb, 0.0, 'M_Paving', c)
    for k, p in enumerate(P3['core']):
        prism(f'Bldg_Cloud_GroundCore{k}', p['outer'], p['holes'], lv('pilotis'), lambda x, y: lv('f1')(x, y) - SLAB_T,
              'M_Cloud_Core', c, cuts=cuts)
    facade_and_galleries(c)
    for name in ('f1', 'f2', 'f3', 'roof'):
        top = lv(name)
        th = ROOF_FASCIA if name == 'roof' else SLAB_T
        for k, p in enumerate(P3['slab']):
            o = prism(f'Bldg_Cloud_Slab_{name}', p['outer'], p['holes'],
                      lambda x, y, t=top, th=th: t(x, y) - th, top,
                      'M_Cloud_Slab', c, cuts=cuts,
                      top_mat='M_Cloud_RoofRim' if name == 'roof' else None)
            bevel(o, 0.55 if name == 'roof' else 0.2)
    pitched_roof(c)
    columns(c)
    courtyard_interior(c, court)
    bpy.ops.wm.save_mainfile()
    print('cloud objects', len(c.objects))


main()
exec(open(os.path.join(ROOT, 'blender', 'build', 'bldg_annex.py')).read())
