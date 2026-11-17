"""P5 景观：地表分类贴图（顶面平面 UV）、实例化树、日光与天空。
在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/landscape.py').read())
"""
import bpy, bmesh, json, os, math, random

ROOT = '/Users/perrylei/repos/BDFZ_V3'
TR = json.load(open(os.path.join(ROOT, 'data', 'trees.json')))
X0, Y0, X1, Y1 = TR['extent']
COLL = 'Landscape'
TOP_SURFACES = ['Site_Campus', 'Site_Zone_操场平台周边', 'Site_Plaza_北入口台阶广场', 'Bldg_Cloud_Podium', 'Bldg_Dorm_Base']


def landcover_mat():
    m = bpy.data.materials.get('M_Landcover')
    if m is None:
        m = bpy.data.materials.new('M_Landcover'); m.use_nodes = True
        nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(os.path.join(ROOT, 'blender', 'textures', 'landcover.png'), check_existing=True)
        t.extension = 'EXTEND'
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.9
        m.diffuse_color = (0.45, 0.5, 0.4, 1)
    return m


def apply_landcover():
    lm = landcover_mat()
    for n in TOP_SURFACES:
        o = bpy.data.objects.get(n)
        if o is None:
            continue
        me = o.data
        if lm.name not in me.materials:
            me.materials.append(lm)
        slot = list(me.materials).index(me.materials[lm.name])
        bm = bmesh.new(); bm.from_mesh(me)
        uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            if f.normal.z > 0.5:
                f.material_index = slot
                for lp in f.loops:
                    lp[uvl].uv = ((lp.vert.co.x - X0) / (X1 - X0), (lp.vert.co.y - Y0) / (Y1 - Y0))
        bm.to_mesh(me); bm.free()


def tree_mesh():
    me = bpy.data.meshes.get('Landscape_TreeUnit')
    if me:
        return me
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.08, radius2=0.06, depth=0.55,
                          matrix=__import__('mathutils').Matrix.Translation((0, 0, 0.275)))
    r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in r['verts']:
        v.co.z = v.co.z * 0.6 + 0.85
    me = bpy.data.meshes.new('Landscape_TreeUnit'); bm.to_mesh(me); bm.free()
    for nm, col in (('M_TreeTrunk', (0.30, 0.22, 0.15, 1)), ('M_TreeCrown', (0.16, 0.32, 0.12, 1))):
        m = bpy.data.materials.get(nm) or bpy.data.materials.new(nm)
        m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = col
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9; m.diffuse_color = col
        me.materials.append(m)
    for p in me.polygons:
        p.material_index = 1 if p.center.z > 0.5 else 0
    return me


def ground_z(x, y, dg, sc):
    from mathutils import Vector
    ok, loc, n, i, ob, _ = sc.ray_cast(dg, Vector((x, y, 80)), Vector((0, 0, -1)))
    return (loc.z, ob.name) if ok else (-6.0, '')


def trees():
    c = bpy.data.collections[COLL]
    for o in [o for o in c.objects if o.name.startswith('Landscape_Tree')]:
        bpy.data.objects.remove(o, do_unlink=True)
    me = tree_mesh(); random.seed(7)
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for x, y, r in TR['trees']:
        z, hit = ground_z(x, y, dg, sc)
        if hit.startswith(('Bldg_Cloud_Slab', 'Bldg_Dorm_Mass', 'Bldg_SportsArt', 'Site_Track')):
            continue
        h = max(4.0, r * 2.2) * random.uniform(0.85, 1.15)
        o = bpy.data.objects.new(f'Landscape_Tree_{n:04d}', me)
        o.location = (x, y, z); o.scale = (r, r, h); o.rotation_euler = (0, 0, random.uniform(0, 6.28))
        c.objects.link(o); n += 1
    return n


def sky():
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w
    w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground'); sk = nt.nodes.new('ShaderNodeTexSky')
    try:
        sk.sky_type = 'NISHITA'
    except TypeError:
        pass
    # 海口 20°N，冬季午后：太阳高度 40°、方位西南
    for attr, v in (('sun_elevation', math.radians(40)), ('sun_rotation', math.radians(215)), ('altitude', 30.0)):
        if hasattr(sk, attr):
            setattr(sk, attr, v)
    bg.inputs['Strength'].default_value = 0.35
    nt.links.new(sk.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.objects.get('Sun')
    if sun is None:
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); bpy.data.collections[COLL].objects.link(sun)
    sun.data.energy = 3.0; sun.data.angle = math.radians(0.6)
    sun.rotation_euler = (math.radians(50), 0, math.radians(215 - 90 + 180))
    sc.view_settings.exposure = -0.8
    sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'


def box(name, x0, y0, x1, y1, z0, z1, matname, c):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
    bm.faces.new(vs[0:4]); bm.faces.new(vs[4:8])
    for i in range(4):
        bm.faces.new((vs[i], vs[(i + 1) % 4], vs[(i + 1) % 4 + 4], vs[i + 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    m = bpy.data.materials.get(matname) or bpy.data.materials.new(matname)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def north_entrance(c):
    """北入口大台阶：y 117（顶，庭院 43.00 = Z 0）到 y 80（底，道路 37.00 = Z −6），12 级；门房两座。"""
    W0, W1, YT, YB, ZT, ZB, N = -80.0, 10.0, 117.0, 80.0, 0.0, -6.0, 12
    for i in range(N):
        z1 = ZT + (ZB - ZT) * i / N
        y0 = YT + (YB - YT) * i / N; y1 = YT + (YB - YT) * (i + 1) / N
        box(f'Landscape_NorthStep_{i:02d}', W0, y0, W1, y1, ZB, z1, 'M_Paving', c)
    box('Landscape_Gatehouse_W', -90, 66, -55, 79, -6, -1.5, 'M_Cloud_Core', c)
    box('Landscape_Gatehouse_E', 0, 66, 32, 79, -6, -1.5, 'M_Cloud_Core', c)


def main():
    apply_landcover()
    north_entrance(bpy.data.collections[COLL])
    n = trees()
    sky()
    bpy.ops.wm.save_mainfile()
    print('trees placed', n)


main()
