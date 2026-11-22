"""P2–P6 学术中心南侧低层附楼（wx_03/wx_04/wx_09/wx_14/wx_16/wx_18 校正）。数据：data/bldg_annex.json。"""
import bpy, bmesh, json, os

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_annex.json')))
COLL = 'Bldg_Cloud'

MATS = {
    'M_Paving': (0.64, 0.64, 0.62, 0.88),     # 浅灰混凝土屋面露台（wx_14/wx_16）
    'M_Cloud_Slab': (0.24, 0.26, 0.29, 0.50),   # 暗灰金属女儿墙檐口带（wx_09/14/16）
    'M_Cloud_Core': (0.86, 0.86, 0.84, 0.80),     # 一层白墙
    'M_Cloud_Slab': (0.20, 0.22, 0.25, 0.45),     # 屋面深灰金属栏杆
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
    r, g, b, rough = MATS[name]
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
    bsdf.inputs['Roughness'].default_value = rough
    m.diffuse_color = (r, g, b, 1)
    return m


def top_fn(b):
    if 'top_ramp' in b:
        r = b['top_ramp']
        yn, zn, ys, zs = r['y_north'], r['z_north'], r['y_south'], r['z_south']
        def fn(x, y):
            t = max(0.0, min(1.0, (y - ys) / (yn - ys)))
            return zs + t * (zn - zs)
        return fn
    z = float(b['top'])
    return lambda x, y: z


def build_block(k, b, c):
    zbase = float(D['base_z'])
    ft = top_fn(b)
    outer = b['outer']
    holes = [b['courtyard_hole']] if 'courtyard_hole' in b else []

    # 1. 主体（白墙至顶下 1.4 m）+ 顶部暗灰檐口带（厚 1.4 m）+ 混凝土屋面顶面
    def make_prism(suffix, z0_f, z1_f, side_m, top_m):
        bm = bmesh.new(); edges = []
        for ring in [outer] + holes:
            vs = [bm.verts.new((x, y, 0.0)) for x, y in ring]
            edges += [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
        bmesh.ops.dissolve_limit(bm, angle_limit=0.0005, verts=bm.verts[:], edges=bm.edges[:], delimit=set())
        r = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        top_v = {v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)}
        for v in bm.verts:
            f = z1_f if v in top_v else z0_f
            v.co.z = f(v.co.x, v.co.y) if callable(f) else f
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for f in bm.faces:
            f.material_index = 1 if f.normal.z > 0.7 else 0
        me = bpy.data.meshes.new(f'Bldg_Cloud_Annex_{k}{suffix}'); bm.to_mesh(me); bm.free()
        me.materials.append(mat(side_m)); me.materials.append(mat(top_m))
        c.objects.link(bpy.data.objects.new(me.name, me))

    make_prism('', zbase, lambda x, y: ft(x, y) - 1.4, 'M_Cloud_Core', 'M_Paving')
    make_prism('_Fascia', lambda x, y: ft(x, y) - 1.4, ft, 'M_Cloud_Slab', 'M_Paving')

    # 2. 屋面周边暗灰护栏（高 1.1 m，顶扶手框，wx_09/14/16/18 特征）
    bm = bmesh.new()
    for ring in [outer] + holes:
        n = len(ring)
        for i in range(n):
            (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
            za, zb = ft(x0, y0), ft(x1, y1)
            # 顶扶手细带（离屋面 0.95..1.10 m）
            vs = [bm.verts.new((x0, y0, za + 0.95)), bm.verts.new((x1, y1, zb + 0.95)),
                  bm.verts.new((x1, y1, zb + 1.10)), bm.verts.new((x0, y0, za + 1.10))]
            bm.faces.new(vs)
            # 竖向栏杆每隔 3 m 一个立柱
            import math
            L = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, int(L / 3.0))
            for s in range(steps):
                t0 = s / steps
                t1 = min(1.0, t0 + 0.08 / max(L, 0.1))
                px0, py0 = x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0
                px1, py1 = x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1
                zp = ft(px0, py0)
                bm.faces.new([bm.verts.new((px0, py0, zp)), bm.verts.new((px1, py1, zp)),
                              bm.verts.new((px1, py1, zp + 1.05)), bm.verts.new((px0, py0, zp + 1.05))])
    me_r = bpy.data.meshes.new(f'Bldg_Cloud_Annex_{k}_Rail'); bm.to_mesh(me_r); bm.free()
    me_r.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new(me_r.name, me_r))


def main():
    c = bpy.data.collections[COLL]
    for o in [o for o in c.objects if o.name.startswith('Bldg_Cloud_Annex')]:
        bpy.data.objects.remove(o, do_unlink=True)
    for k, b in D['blocks'].items():
        if b.get('sunken'):
            continue
        build_block(k, b, c)
    bpy.ops.wm.save_mainfile()
    print('annex', [k for k, b in D['blocks'].items() if not b.get('sunken')])


main()
