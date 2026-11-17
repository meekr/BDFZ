"""P1 场地：用地、道路、广场、台地、田径场、球场。数据来自 data/site.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/site.py').read())
"""
import bpy, bmesh, json, math, os
from mathutils import Vector

ROOT = '/Users/perrylei/repos/BDFZ_V3'
S = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Site'

MATS = {
    'M_Ground': (0.36, 0.42, 0.26, 0.95),
    'M_Asphalt': (0.18, 0.18, 0.19, 0.9),
    'M_Paving': (0.62, 0.60, 0.56, 0.85),
    'M_TrackRed': (0.55, 0.16, 0.12, 0.9),
    'M_Turf': (0.16, 0.42, 0.14, 0.95),
    'M_CourtBlue': (0.15, 0.33, 0.55, 0.7),
    'M_CourtGreen': (0.20, 0.45, 0.35, 0.7),
    'M_LineWhite': (0.92, 0.92, 0.90, 0.6),
    'M_Terrace': (0.45, 0.47, 0.33, 0.95),
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


def obj(name, bm, material, c):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat(material))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def slab(name, poly, z, thick, material, c, holes=()):
    """多边形平板：顶面在 z，向下 thick。"""
    bm = bmesh.new()
    top = [bm.verts.new((x, y, z)) for x, y in poly]
    f = bm.faces.new(top)
    if thick > 0:
        r = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, vec=(0, 0, -thick), verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, bm, material, c)


def strip(name, line, width, z, material, c, thick=0.0):
    (x0, y0), (x1, y1) = line
    dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy); nx, ny = -dy / L * width / 2, dx / L * width / 2
    return slab(name, [(x0 + nx, y0 + ny), (x0 - nx, y0 - ny), (x1 - nx, y1 - ny), (x1 + nx, y1 + ny)], z, thick, material, c)


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


def build_track(c):
    T = S['track']; cx, cy = T['center']; ang = T['long_axis_deg_west_of_north']; z = T['z']
    straight = 84.39; r_kerb = 36.5; r_out = T['outer_bbox'][1] / 2
    out_, in_ = stadium_ring(r_kerb, r_out, straight)
    ring_mesh('Site_Track_Surface', place(out_, cx, cy, ang), place(in_, cx, cy, ang), z + 0.10, 'M_TrackRed', c)
    # 分道线：从突沿外 0.3 m 起每 1.22 m 一条，直到外缘
    r = r_kerb + 0.3; k = 0
    while r + 0.05 < r_out:
        o, i = stadium_ring(r - 0.025, r + 0.025, straight)
        ring_mesh(f'Site_Track_Lane{k}', place(o, cx, cy, ang), place(i, cx, cy, ang), z + 0.13, 'M_LineWhite', c)
        r += 1.22; k += 1
    # 内场：草坪（D 区一并为草）
    _, inner = stadium_ring(r_kerb, r_kerb, straight)
    slab('Site_Track_Infield', place(inner, cx, cy, ang), z + 0.10, 0, 'M_Turf', c)
    # 抬高台面外沿（推定 3 m 宽缓冲带）
    o3, _ = stadium_ring(r_out, r_out + 3.0, straight)
    _, i3 = stadium_ring(r_out, r_out, straight)
    ring_mesh('Site_Track_Deck', place(o3, cx, cy, ang), place(i3, cx, cy, ang), z + 0.06, 'M_Paving', c)


def build_courts(c):
    for k, v in S['courts'].items():
        cx, cy = v['center']; a = math.radians(v['long_axis_deg_from_E'])
        L, W = v['size']; pad = 3.5 if v['kind'] == 'tennis' else 2.0
        ca, sa = math.cos(a), math.sin(a)

        def P(x, y):
            return (cx + x * ca - y * sa, cy + x * sa + y * ca)
        hw, hh = L / 2 + pad, W / 2 + pad
        slab(f'Site_Court_{k}', [P(-hw, -hh), P(hw, -hh), P(hw, hh), P(-hw, hh)], v['z'] + 0.08, 0,
             'M_CourtGreen' if v['kind'] == 'tennis' else 'M_CourtBlue', c)
        # 外框线
        o = [P(-L / 2, -W / 2), P(L / 2, -W / 2), P(L / 2, W / 2), P(-L / 2, W / 2)]
        i = [P(-L / 2 + 0.05, -W / 2 + 0.05), P(L / 2 - 0.05, -W / 2 + 0.05), P(L / 2 - 0.05, W / 2 - 0.05), P(-L / 2 + 0.05, W / 2 - 0.05)]
        ring_mesh(f'Site_Court_{k}_Lines', o, i, v['z'] + 0.12, 'M_LineWhite', c)


def main():
    c = coll()
    b = S['boundary']['polygon']
    xs = [p[0] for p in b]; ys = [p[1] for p in b]
    # 外围大地（道路标高附近）
    X0, Y0, X1, Y1 = S['ground_extent']
    slab('Site_Ground_Outer', [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)], -6.2, 0, 'M_Ground', c)
    # 校园台面
    zb = S['campus_base_z']
    slab('Site_Campus', b, zb, 0.5, 'M_Ground', c)
    for zn in S['zones']:
        slab('Site_Zone_' + zn['name'], zn['polygon'], zn['z'] + 0.02, zn['z'] - zb + 0.02, 'M_Terrace', c)
    for p in S['plazas']:
        slab('Site_Plaza_' + p['name'], p['polygon'], p['z'], 1.0, 'M_Paving', c)
    for r in S['roads']:
        strip('Site_Road_' + r['name'], r['centerline'], r['width'], r['z'], 'M_Asphalt', c, thick=0.3)
    build_track(c)
    build_courts(c)
    bpy.ops.wm.save_mainfile()
    print('site objects', len(c.objects))


main()
