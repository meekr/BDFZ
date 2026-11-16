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


def main():
    c = coll()
    sh = D['shell'][0]
    court = max(sh['holes'], key=len)
    zb = SITE['campus_base_z']
    # 平台：外轮廓整体（含庭院），从校园地坪到庭院 ±0.00
    prism('Bldg_Cloud_Podium', sh['outer'], [], zb, 0.0, 'M_Cloud_Podium', c)
    s, n = L['south'], L['north']
    # 底层架空：内收核心（柱廊在 P3）
    for k, p in enumerate(D['ground_core']['parts']):
        prism(f'Bldg_Cloud_GroundCore{k}', p['outer'], p['holes'],
              lambda y: lerp_y(y, s[0], n[0]), lambda y: lerp_y(y, s[1], n[1]),
              'M_Cloud_Podium', c, cuts=(Y_S, Y_N))
    # 主体：二层楼面起，顶 = 北檐口 19 / 南屋面 23.5
    prism('Bldg_Cloud_Mass', sh['outer'], sh['holes'],
          lambda y: lerp_y(y, s[1], n[1]), lambda y: lerp_y(y, L['eave']['south'], L['eave']['north']),
          'M_Cloud_Roof', c, cuts=(Y_S, Y_N))
    # 图书馆：庭院南部单层
    lib = clip_y(court, D['library']['clip_y_max'])
    z0, z1 = D['library']['z']
    prism('Bldg_Cloud_Library', lib, [], z0, z1, 'M_Cloud_LibraryRoof', c)
    bpy.ops.wm.save_mainfile()
    print('cloud objects', [(o.name, len(o.data.vertices), [round(v, 1) for v in o.dimensions]) for o in c.objects])


main()
