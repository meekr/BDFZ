"""P5–P6 景观：地表分类贴图、实例化树（修复树冠下半部误赋树干材质 Bug）、北入口门房与大台阶、日光与天空。
在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/landscape.py').read())
"""
import bpy, bmesh, json, os, math, random
from mathutils import Matrix, Vector

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
    """重建干净的实例化树木网格（所有 565 棵树共用 1 份网格，保持 1 次 GPU 实例化绘制）。
    修复旧版 p.center.z > 0.5 导致树冠下半部被误赋棕色树干材质的问题。"""
    old = bpy.data.meshes.get('Landscape_TreeUnit')
    if old is not None:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new()
    # 树干（material_index = 0）
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.09, radius2=0.055, depth=0.55,
                          matrix=Matrix.Translation((0, 0, 0.275)))
    trunk_faces = set(bm.faces[:])
    for f in trunk_faces:
        f.material_index = 0
    # 树冠（subdivisions=2 柔和球冠，material_index = 1）
    r = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    crown_verts = set(r['verts'])
    for v in crown_verts:
        v.co.z = v.co.z * 0.58 + 0.90
        # 轻微自然起伏，避免生硬正球
        k = 1.0 + 0.08 * math.sin(v.co.x * 3.1 + v.co.y * 2.7)
        v.co.x *= k; v.co.y *= k
    for f in bm.faces:
        if f not in trunk_faces:
            f.material_index = 1
            f.smooth = True
    me = bpy.data.meshes.new('Landscape_TreeUnit'); bm.to_mesh(me); bm.free()
    for nm, col in (('M_TreeTrunk', (0.28, 0.20, 0.14, 1)), ('M_TreeCrown', (0.14, 0.31, 0.11, 1))):
        m = bpy.data.materials.get(nm) or bpy.data.materials.new(nm)
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = col
        b.inputs['Roughness'].default_value = 0.88
        m.diffuse_color = col
        me.materials.append(m)
    return me


def ground_z(x, y, dg, sc):
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
        if hit.startswith(('Bldg_Cloud_Slab', 'Bldg_Cloud_Roof', 'Bldg_Dorm_Mass', 'Bldg_Dorm_Pergola',
                           'Bldg_Dorm_Canopies', 'Bldg_SportsArt', 'Site_Track', 'Landscape_NorthSteps')):
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
    for attr, v in (('sun_elevation', math.radians(40)), ('sun_rotation', math.radians(215)), ('altitude', 30.0)):
        if hasattr(sk, attr):
            setattr(sk, attr, v)
    if hasattr(sk, 'sun_disc'):
        sk.sun_disc = False
    bg.inputs['Strength'].default_value = 0.25
    nt.links.new(sk.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.objects.get('Sun')
    if sun is None:
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); bpy.data.collections[COLL].objects.link(sun)
    sun.data.energy = 3.5; sun.data.angle = math.radians(0.6)
    sun.rotation_euler = (math.radians(50), 0, math.radians(215 - 90 + 180))
    sc.view_settings.exposure = 0.0
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    far = bpy.data.objects.get('Landscape_FarGround')
    if far is None:
        far = box('Landscape_FarGround', -4000, -4000, 4000, 4000, -6.6, -6.4, 'M_FarGround', bpy.data.collections[COLL])
        m = far.data.materials[0]; m.use_nodes = True
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.20, 0.26, 0.15, 1)
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0; m.diffuse_color = (0.20, 0.26, 0.15, 1)


def simple_mat(name, col, rough=0.7, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = col
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = col
    return m


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


def gatehouse(name, x0, y0, x1, y1, z0, z1, c):
    """北入口门房（wx_11 右前景、wx_01、wx_08）：深色玻璃幕墙体 + 顶部深灰檐口框 + 浅灰平屋面。"""
    m_gl = simple_mat('M_Cloud_Skylight', (0.12, 0.16, 0.20, 1), rough=0.12, metal=0.35)
    m_fa = simple_mat('M_Cloud_Slab', (0.22, 0.24, 0.27, 1), rough=0.45, metal=0.25)
    m_rf = simple_mat('M_Cloud_RoofRim', (0.76, 0.77, 0.76, 1), rough=0.80, metal=0.0)
    # 玻璃墙身（内收 0.5 m）
    o1 = box(name, x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5, z0, z1 - 0.9, 'M_Cloud_Skylight', c)
    # 屋顶挑檐框（顶部浅灰，四周暗灰）
    o2 = box(name + '_Roof', x0, y0, x1, y1, z1 - 0.9, z1, 'M_Cloud_Slab', c)
    o2.data.materials.append(m_rf)
    for p in o2.data.polygons:
        if p.normal.z > 0.7:
            p.material_index = 1
    return o1


def north_entrance(c):
    """北入口门房两座 + 主入口大台阶（连接北入口广场 Z -6 与学术中心北侧庭院平台 Z 0，wx_01/08/11、06 剖面 ⑥）。"""
    for o in [o for o in c.objects if o.name.startswith(('Landscape_NorthStep', 'Landscape_Gatehouse'))]:
        bpy.data.objects.remove(o, do_unlink=True)
    gatehouse('Landscape_Gatehouse_W', -90, 66, -55, 79, -6.0, -1.5, c)
    gatehouse('Landscape_Gatehouse_E', 0, 66, 32, 79, -6.0, -1.5, c)

    # 主入口宽大台阶：位于北广场以南、学术中心北翼以北（y=36 Z=-6 → y=10 Z=0，x=-36..+4）
    m_step = simple_mat('M_Paving', (0.66, 0.66, 0.64, 1), rough=0.85)
    bm = bmesh.new()
    steps = 16
    x0, x1 = -36.0, 4.0
    y_bot, y_top = 36.0, 10.0
    z_bot, z_top = -6.0, 0.0
    for i in range(steps):
        t0, t1 = i / steps, (i + 1) / steps
        ya = y_bot + (y_top - y_bot) * t0
        yb = y_bot + (y_top - y_bot) * t1
        zt = z_bot + (z_top - z_bot) * t1
        vs = [bm.verts.new((x0, ya, z_bot)), bm.verts.new((x1, ya, z_bot)),
              bm.verts.new((x1, yb, z_bot)), bm.verts.new((x0, yb, z_bot)),
              bm.verts.new((x0, ya, zt)), bm.verts.new((x1, ya, zt)),
              bm.verts.new((x1, yb, zt)), bm.verts.new((x0, yb, zt))]
        bm.faces.new(vs[0:4]); bm.faces.new(vs[4:8])
        for j in range(4):
            bm.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Landscape_NorthSteps'); bm.to_mesh(me); bm.free()
    me.materials.append(m_step)
    c.objects.link(bpy.data.objects.new('Landscape_NorthSteps', me))


def main():
    apply_landcover()
    north_entrance(bpy.data.collections[COLL])
    n = trees()
    sky()
    bpy.ops.wm.save_mainfile()
    print('trees placed', n)


main()
