"""P2 学术中心体量。数据：data/bldg_cloud.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_cloud.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Bldg_Cloud'
L = D['levels']
Y_S, Y_N = L['ramp_y']          # 南端、北端过渡线

MATS = {
    'M_Cloud_Roof': (0.62, 0.62, 0.60, 0.8),
    'M_Cloud_Slab': (0.30, 0.31, 0.33, 0.5),
    'M_Cloud_Glass': (0.42, 0.52, 0.60, 0.15),
    'M_Cloud_Core': (0.85, 0.85, 0.83, 0.8),
    'M_Cloud_Column': (0.90, 0.90, 0.88, 0.7),
    'M_Cloud_Podium': (0.55, 0.54, 0.50, 0.9),
    'M_Cloud_LibraryRoof': (0.45, 0.30, 0.22, 0.8),
    'M_Cloud_RoofPanel': (0.17, 0.20, 0.24, 0.35),
    'M_Cloud_RoofRim': (0.72, 0.73, 0.72, 0.5),
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        r, g, b, rough = MATS[name]
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1); bsdf.inputs['Roughness'].default_value = rough
        m.diffuse_color = (r, g, b, 1)
    return m


def coll():
    c = bpy.data.collections.get(COLL)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def lerp_y(y, south, north):
    if y <= Y_S:
        return south
    if y >= Y_N:
        return north
    t = (y - Y_S) / (Y_N - Y_S)
    return south + t * (north - south)


def prism(name, outer, holes, base, top, material, c, cuts=()):
    """带洞多边形拉伸。base/top 为常数或 f(y)。cuts：在这些 y 处切开，使变高屋面分段为平面。"""
    bm = bmesh.new()
    edges = []
    for ring in [outer] + list(holes):
        vs = [bm.verts.new((x, y, 0.0)) for x, y in ring]
        edges += [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    for y in cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, y, 0), plane_no=(0, 1, 0))
    bmesh.ops.dissolve_limit(bm, angle_limit=0.0005, verts=bm.verts[:], edges=bm.edges[:], delimit=set())
    r = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    top_v = {v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)}
    for v in bm.verts:
        y = v.co.y
        f = top if v in top_v else base
        v.co.z = f(y) if callable(f) else f
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat(material))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def clip_y(ring, ymax):
    """多边形与半平面 y ≤ ymax 求交（Sutherland–Hodgman）。"""
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


P3 = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud_p3.json')))
LV = {k: tuple(v) for k, v in P3['levels'].items()}
SLAB_T = 0.8        # wx_10：楼板带约为层高的 1/6
COL_R = 0.45


def lv(name):
    s, n = LV[name]
    return lambda y: lerp_y(y, s, n)


def column_mesh():
    me = bpy.data.meshes.get('Bldg_Cloud_ColumnUnit')
    if me is None:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=COL_R, radius2=COL_R, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
        me = bpy.data.meshes.new('Bldg_Cloud_ColumnUnit'); bm.to_mesh(me); bm.free()
        me.materials.append(mat('M_Cloud_Column'))
    return me


def columns(c):
    me = column_mesh()
    fp, f1 = lv('pilotis'), lv('f1')
    for i, (x, y, nx, ny, kind) in enumerate(P3['columns']):
        if kind == 'slant':
            # 05 北翼剖面：斜柱下端在内、上端在楼板外缘
            a = Vector((x - 3.5 * nx, y - 3.5 * ny, 0)); b = Vector((x + 1.0 * nx, y + 1.0 * ny, 0))
        else:
            a = Vector((x, y, 0)); b = Vector((x, y, 0))
        a.z = fp(a.y); b.z = f1(b.y) - SLAB_T
        o = bpy.data.objects.new(f'Bldg_Cloud_Column_{i:03d}', me)
        d = b - a
        o.location = a
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        o.scale = (1, 1, d.length)
        c.objects.link(o)


BAY = 1.5            # 窗格宽度（wx_10 计数：约 1.5 m）
PANEL_CYCLE = (13.5, 4.5)   # 玻璃 / 白色实墙段长度（规则生成，P6 按照片逐段校正）
ROOF_FASCIA = 2.0


def glass_mat():
    m = bpy.data.materials.get('M_Cloud_GlassGrid')
    if m is None:
        m = bpy.data.materials.new('M_Cloud_GlassGrid'); m.use_nodes = True
        nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(os.path.join(ROOT, 'blender', 'textures', 'cloud_glass.png'), check_existing=True)
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.08; b.inputs['Metallic'].default_value = 0.4
        m.diffuse_color = (0.30, 0.38, 0.45, 1)
    return m


def facade_walls(c):
    """每层一圈立面墙：沿玻璃面轮廓，按 PANEL_CYCLE 分玻璃段与白墙段；UV 以 BAY × 层高 平铺。"""
    storeys = [('f1', 'f2'), ('f2', 'f3'), ('f3', 'roof')]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    rings = []
    for p in P3['facade']:
        rings += [p['outer']] + p['holes']
    cyc = sum(PANEL_CYCLE)
    for ring in rings:
        pts = [Vector((x, y, 0)) for x, y in ring]
        # 沿周长细分：每段 ≤ BAY*2，并在玻璃/白墙交界处断开
        seq = []; s = 0.0
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            L = (b - a).length
            cuts = {0.0, L}
            t = cyc * math.ceil(s / cyc)
            while t < s + L:
                for off in (0.0, PANEL_CYCLE[0]):
                    if s < t + off < s + L:
                        cuts.add(t + off - s)
                t += cyc
            n = max(1, int(math.ceil(L / (BAY * 2))))
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
                za0, zb0 = flo(a.y), flo(b.y); za1, zb1 = fhi(a.y) - SLAB_T, fhi(b.y) - SLAB_T
                if max(za1 - za0, zb1 - zb0) < 0.3:
                    continue
                v = [bm.verts.new((a.x, a.y, za0)), bm.verts.new((b.x, b.y, zb0)),
                     bm.verts.new((b.x, b.y, zb1)), bm.verts.new((a.x, a.y, za1))]
                f = bm.faces.new(v)
                white = ((s0 + s1) / 2) % cyc > PANEL_CYCLE[0]
                f.material_index = 1 if white else 0
                h = 4.5
                for lp, (uu, vv) in zip(f.loops, [(s0, za0), (s1, zb0), (s1, zb1), (s0, za1)]):
                    lp[uvl].uv = (uu / BAY, (vv - za0) / h if lp.vert in v[:2] else (vv - za0) / h)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    me = bpy.data.meshes.new('Bldg_Cloud_Facade'); bm.to_mesh(me); bm.free()
    me.materials.append(glass_mat()); me.materials.append(mat('M_Cloud_Core'))
    o = bpy.data.objects.new('Bldg_Cloud_Facade', me); c.objects.link(o)
    return o


def pitched_roof(c):
    """P6：坡屋面（data/bldg_cloud_roof.json，tools/p6_cloud_roof.py），坐在屋面板顶上、外缘内收一圈浅色檐口。"""
    from mathutils.kdtree import KDTree
    R = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud_roof.json')))
    edge_pts = []
    for p in R['edge']:
        for ring in [p['outer']] + p['holes']:
            for i in range(len(ring)):
                a, b = Vector(ring[i]), Vector(ring[(i + 1) % len(ring)])
                n = max(1, int((b - a).length / 0.25))
                edge_pts += [a.lerp(b, k / n) for k in range(n)]
    kd = KDTree(len(edge_pts))
    for i, q in enumerate(edge_pts):
        kd.insert((q.x, q.y, 0), i)
    kd.balance()
    bm = bmesh.new()
    edges = []
    for p in R['panel']:
        for ring in [p['outer']] + p['holes']:
            vs = [bm.verts.new((x, y, 0.0)) for x, y in ring]
            edges += [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    for _ in range(12):
        long = [e for e in bm.edges if e.calc_length() > 3.0]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=bm.edges[:])
    top = lv('roof')
    for v in bm.verts:
        d = kd.find((v.co.x, v.co.y, 0))[2]
        v.co.z = top(v.co.y) + 0.03 + R['slope'] * min(d, R['cap'])
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new('Bldg_Cloud_RoofSurface'); bm.to_mesh(me); bm.free()
    me.materials.append(mat('M_Cloud_RoofPanel'))
    o = bpy.data.objects.new('Bldg_Cloud_RoofSurface', me); c.objects.link(o)
    return o

def bevel(o, w, seg=3):
    m = o.modifiers.new('Bevel', 'BEVEL'); m.width = w; m.segments = seg
    m.limit_method = 'ANGLE'; m.angle_limit = math.radians(50); m.harden_normals = False
    return m

def main():
    c = coll()
    sh = D['shell'][0]
    court = max(sh['holes'], key=len)
    zb = SITE['campus_base_z']
    cuts = (Y_S, Y_N)
    ANX = json.load(open(os.path.join(ROOT, 'data', 'bldg_annex.json')))
    sunken = [b['outer'] for b in ANX['blocks'].values() if b.get('sunken')]
    prism('Bldg_Cloud_Podium', sh['outer'], sunken, zb, 0.0, 'M_Cloud_Podium', c)
    for k, p in enumerate(P3['core']):
        prism(f'Bldg_Cloud_GroundCore{k}', p['outer'], p['holes'], lv('pilotis'), lambda y: lv('f1')(y) - SLAB_T,
              'M_Cloud_Core', c, cuts=cuts)
    facade_walls(c)
    for name in ('f1', 'f2', 'f3', 'roof'):
        top = lv(name); th = ROOF_FASCIA if name == 'roof' else SLAB_T
        for k, p in enumerate(P3['slab']):
            o = prism(f'Bldg_Cloud_Slab_{name}', p['outer'], p['holes'], lambda y, t=top, th=th: t(y) - th, top,
                      'M_Cloud_RoofRim' if name == 'roof' else 'M_Cloud_Slab', c, cuts=cuts)
            bevel(o, 0.6 if name == 'roof' else 0.2)
    pitched_roof(c)
    columns(c)
    lib = clip_y(court, D['library']['clip_y_max'])
    z0, z1 = D['library']['z']
    prism('Bldg_Cloud_Library', lib, [], z0, z1, 'M_Cloud_LibraryRoof', c)
    bpy.ops.wm.save_mainfile()
    print('cloud objects', len(c.objects))


main()
exec(open(os.path.join(ROOT, 'blender', 'build', 'bldg_annex.py')).read())
