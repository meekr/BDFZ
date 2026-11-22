"""P2–P6 学术中心建模。数据：data/bldg_cloud.json、bldg_cloud_p3.json、bldg_cloud_roof.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_cloud.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud.json')))
P3 = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud_p3.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
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
    'M_Cloud_Roof': (0.62, 0.62, 0.60, 0.8),
    'M_Cloud_Slab': (0.22, 0.24, 0.27, 0.45),        # wx_09/10/14/18：深灰金属板楼板带与檐口立面
    'M_Cloud_Glass': (0.42, 0.52, 0.60, 0.15),
    'M_Cloud_Core': (0.88, 0.88, 0.86, 0.8),
    'M_Cloud_Core': (0.91, 0.91, 0.89, 0.7),
    'M_Paving': (0.58, 0.58, 0.56, 0.88),
    'M_Paving': (0.64, 0.64, 0.62, 0.88), # wx_02/23：浅灰石材铺装露台
    'M_Turf': (0.20, 0.38, 0.14, 0.92),  # wx_02/15/23：庭院草坪
    'M_Cloud_RoofPanel': (0.14, 0.17, 0.21, 0.50),   # 深蓝灰直立锁边金属坡屋面
    'M_Cloud_RoofRim': (0.70, 0.72, 0.73, 0.45),     # 屋面顶缘浅灰金属压顶
    'M_Cloud_Skylight': (0.18, 0.26, 0.34, 0.12),    # 采光井玻璃天窗
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
    r, g, b, rough = MATS[name]
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
    bsdf.inputs['Roughness'].default_value = rough
    if name in ('M_Cloud_Slab', 'M_Cloud_RoofPanel', 'M_Cloud_RoofRim'):
        bsdf.inputs['Metallic'].default_value = 0.25
    elif name == 'M_Cloud_Skylight':
        bsdf.inputs['Metallic'].default_value = 0.45
    m.diffuse_color = (r, g, b, 1)
    return m


def img_mat(name, fname, rough=0.15, metal=0.2, fallback=(0.5, 0.5, 0.5, 1)):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
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
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat(material))
    if top_mat:
        me.materials.append(mat(top_mat))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def clip_y(ring, ymax):
    out = []
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        ia, ib = a[1] <= ymax, b[1] <= ymax
        if ia:
            out.append(a)
        if ia != ib:
            t = (ymax - a[1]) / (b[1] - a[1])
            out.append([a[0] + t * (b[0] - a[0]), ymax])
    return out


def column_mesh():
    me = bpy.data.meshes.get('Bldg_Cloud_ColumnUnit')
    if me is None:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=COL_R, radius2=COL_R, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
        me = bpy.data.meshes.new('Bldg_Cloud_ColumnUnit'); bm.to_mesh(me); bm.free()
        me.materials.append(mat('M_Cloud_Core'))
    return me


def columns(c):
    me = column_mesh()
    fp, f1 = lv('pilotis'), lv('f1')
    for i, (x, y, nx, ny, kind) in enumerate(P3['columns']):
        if kind == 'slant':
            a = Vector((x - 3.5 * nx, y - 3.5 * ny, 0)); b = Vector((x + 1.0 * nx, y + 1.0 * ny, 0))
        else:
            a = Vector((x, y, 0)); b = Vector((x, y, 0))
        a.z = fp(a.x, a.y); b.z = f1(b.x, b.y) - SLAB_T
        o = bpy.data.objects.new(f'Bldg_Cloud_Column_{i:03d}', me)
        d = b - a
        o.location = a
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        o.scale = (1, 1, d.length)
        c.objects.link(o)


def facade_walls(c):
    """外立面：蓝灰玻璃带 + 白色实墙段；内院立面（最大洞口）：开敞外廊（wx_15/wx_23/wx_32）。"""
    storeys = [('f1', 'f2'), ('f2', 'f3'), ('f3', 'roof')]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    cyc = sum(PANEL_CYCLE)
    ring_specs = []
    for p in P3['facade']:
        ring_specs.append((p['outer'], 'outer'))
        if p['holes']:
            big_h = max(p['holes'], key=len)
            for h in p['holes']:
                ring_specs.append((h, 'courtyard' if h is big_h else 'skylight'))
    for ring, kind in ring_specs:
        pts = [Vector((x, y, 0)) for x, y in ring]
        seq = []; s = 0.0
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
                if kind == 'courtyard':
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
    me = bpy.data.meshes.new('Bldg_Cloud_Facade'); bm.to_mesh(me); bm.free()
    me.materials.append(img_mat('M_Cloud_GlassGrid', 'cloud_glass.png', 0.08, 0.4, (0.30, 0.38, 0.45, 1)))
    me.materials.append(mat('M_Cloud_Core'))
    me.materials.append(img_mat('M_Cloud_Courtyard', 'cloud_courtyard.png', 0.45, 0.05, (0.72, 0.72, 0.70, 1)))
    o = bpy.data.objects.new('Bldg_Cloud_Facade', me); c.objects.link(o)
    return o


def pitched_roof(c):
    """P6：干净 Delaunay 坡屋面（data/bldg_cloud_roof.json）+ 东西两处条形玻璃天窗。"""
    R = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud_roof.json')))
    M = R['mesh']
    me = bpy.data.meshes.new('Bldg_Cloud_RoofSurface')
    me.from_pydata([tuple(v) for v in M['verts']], [], [tuple(f) for f in M['faces']])
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    # 外缘向下延展 0.28 m 形成干净收边，杜绝与屋面板接缝漏光或穿插
    b_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if b_edges:
        r_ext = bmesh.ops.extrude_edge_only(bm, edges=b_edges)
        bmesh.ops.translate(bm, vec=(0, 0, -0.28),
                            verts=[v for v in r_ext['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat('M_Cloud_RoofPanel'))
    o = bpy.data.objects.new('Bldg_Cloud_RoofSurface', me); c.objects.link(o)

    # 东西两处采光井玻璃天窗（wx_02、wx_23）
    top = lv('roof')
    bm = bmesh.new()
    for ring in R.get('skylights', []):
        vs = [bm.verts.new((x, y, top(x, y) + 0.30)) for x, y in ring]
        if len(vs) >= 3:
            f = bm.faces.new(vs)
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me_s = bpy.data.meshes.new('Bldg_Cloud_Skylights'); bm.to_mesh(me_s); bm.free()
    me_s.materials.append(mat('M_Cloud_Skylight'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_Skylights', me_s))
    return o


def courtyard_terrace(c, court):
    """星形庭院南部抬高图书馆露台（wx_02、wx_15、wx_23）：浅灰石材铺装顶面、暗灰立面挡墙、草坪岛与东北侧大台阶。"""
    lib = clip_y(court, D['library']['clip_y_max'])
    z0, z1 = D['library']['z']
    # 主体露台（侧壁暗灰，顶面浅灰铺装）
    prism('Bldg_Cloud_Library', lib, [], z0, z1, 'M_Cloud_Slab', c, top_mat='M_Paving')
    # 露台上的草坪岛（wx_02/wx_23 可见三块几何草坪）
    lawns = [
        [(-25.0, -76.0), (-8.0, -76.0), (-14.0, -90.0), (-26.0, -86.0)],
        [(-3.0, -78.0), (14.0, -78.0), (10.0, -96.0), (-5.0, -92.0)],
        [(-35.0, -88.0), (-18.0, -93.0), (-24.0, -104.0), (-38.0, -99.0)],
    ]
    for k, poly in enumerate(lawns):
        prism(f'Bldg_Cloud_CourtLawn_{k}', poly, [], z1, z1 + 0.12, 'M_Turf', c)
    # 中央庭院低区（Z 0）草坪岛（wx_02/wx_15/wx_23）
    low_lawns = [
        [(-18.0, -34.0), (-4.0, -34.0), (-9.0, -48.0), (-17.0, -44.0)],
        [(6.0, -48.0), (20.0, -52.0), (14.0, -64.0), (4.0, -58.0)],
        [(-42.0, -56.0), (-30.0, -52.0), (-32.0, -68.0), (-44.0, -64.0)],
    ]
    for k, poly in enumerate(low_lawns):
        prism(f'Bldg_Cloud_LowLawn_{k}', poly, [], 0.0, 0.15, 'M_Turf', c)
    # 东北侧大台阶（从 Z 0.0 拾级而上至 Z 5.0 图书馆露台，wx_02/wx_23 显著特征）
    bm = bmesh.new()
    steps = 12
    x0, x1 = -16.0, 12.0
    y_bot, y_top = -60.0, -70.0
    for i in range(steps):
        t0, t1 = i / steps, (i + 1) / steps
        ya = y_bot + (y_top - y_bot) * t0
        yb = y_bot + (y_top - y_bot) * t1
        zt = z0 + (z1 - z0) * t1
        vs = [bm.verts.new((x0, ya, z0)), bm.verts.new((x1, ya, z0)), bm.verts.new((x1, yb, z0)), bm.verts.new((x0, yb, z0)),
              bm.verts.new((x0, ya, zt)), bm.verts.new((x1, ya, zt)), bm.verts.new((x1, yb, zt)), bm.verts.new((x0, yb, zt))]
        bm.faces.new(vs[0:4]); bm.faces.new(vs[4:8])
        for j in range(4):
            bm.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_Cloud_CourtSteps'); bm.to_mesh(me); bm.free()
    me.materials.append(mat('M_Paving'))
    c.objects.link(bpy.data.objects.new('Bldg_Cloud_CourtSteps', me))


def bevel(o, w, seg=3):
    m = o.modifiers.new('Bevel', 'BEVEL'); m.width = w; m.segments = seg
    m.limit_method = 'ANGLE'; m.angle_limit = math.radians(50); m.harden_normals = False
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
    facade_walls(c)
    for name in ('f1', 'f2', 'f3', 'roof'):
        top = lv(name); th = ROOF_FASCIA if name == 'roof' else SLAB_T
        for k, p in enumerate(P3['slab']):
            o = prism(f'Bldg_Cloud_Slab_{name}', p['outer'], p['holes'],
                      lambda x, y, t=top, th=th: t(x, y) - th, top,
                      'M_Cloud_Slab', c, cuts=cuts,
                      top_mat='M_Cloud_RoofRim' if name == 'roof' else None)
            bevel(o, 0.55 if name == 'roof' else 0.2)
    pitched_roof(c)
    columns(c)
    courtyard_terrace(c, court)
    bpy.ops.wm.save_mainfile()
    print('cloud objects', len(c.objects))


main()
exec(open(os.path.join(ROOT, 'blender', 'build', 'bldg_annex.py')).read())
