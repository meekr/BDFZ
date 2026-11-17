"""P2 学术中心体量。数据：data/bldg_cloud.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_cloud.py').read())
"""
import bpy, bmesh, json, os
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
SLAB_T = 0.6
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


def main():
    c = coll()
    sh = D['shell'][0]
    court = max(sh['holes'], key=len)
    zb = SITE['campus_base_z']
    cuts = (Y_S, Y_N)
    prism('Bldg_Cloud_Podium', sh['outer'], [], zb, 0.0, 'M_Cloud_Podium', c)
    for k, p in enumerate(P3['core']):
        prism(f'Bldg_Cloud_GroundCore{k}', p['outer'], p['holes'], lv('pilotis'), lambda y: lv('f1')(y) - SLAB_T,
              'M_Cloud_Core', c, cuts=cuts)
    fac_top = lambda y: lerp_y(y, LV['roof'][0], LV['f3'][1])
    for k, p in enumerate(P3['facade']):
        prism(f'Bldg_Cloud_Facade{k}', p['outer'], p['holes'], lv('f1'), fac_top, 'M_Cloud_Glass', c, cuts=cuts)
    for name in ('f1', 'f2', 'f3', 'roof'):
        top = lv(name)
        for k, p in enumerate(P3['slab']):
            prism(f'Bldg_Cloud_Slab_{name}', p['outer'], p['holes'], lambda y, t=top: t(y) - SLAB_T, top,
                  'M_Cloud_Slab', c, cuts=cuts)
    columns(c)
    lib = clip_y(court, D['library']['clip_y_max'])
    z0, z1 = D['library']['z']
    prism('Bldg_Cloud_Library', lib, [], z0, z1, 'M_Cloud_LibraryRoof', c)
    bpy.ops.wm.save_mainfile()
    print('cloud objects', len(c.objects))


main()
exec(open(os.path.join(ROOT, 'blender', 'build', 'bldg_annex.py')).read())
