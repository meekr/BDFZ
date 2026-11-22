"""P8 校园师生人物模型（独立 People 集合，7 套低模建筑配景人原型，通过 GPU Instancing 导出，支持网页一键隐藏）。
数据：data/people.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/people.py').read())
"""
import bpy, bmesh, json, os, math, random
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'people.json')))
COLL = 'People'


def people_mat():
    """单一调色板材质 M_People（8 格色板：肤色/深发/白校服/藏青裤/蓝球衣/红球衣/教师浅蓝衫/暗灰裤与书包）。"""
    m = bpy.data.materials.get('M_People')
    if m is None:
        m = bpy.data.materials.new('M_People')
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(ROOT, 'blender', 'textures', 'people_palette.png'), check_existing=True)
    img.reload()
    tex.image = img
    tex.interpolation = 'Closest'
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.78
    m.diffuse_color = (0.85, 0.85, 0.85, 1.0)
    return m


def add_part(bm, uvl, swatch_idx, shape, matrix):
    """添加带指定色板 UV 的低面数肢体构件。"""
    u = (swatch_idx + 0.5) / 8.0
    if shape == 'box':
        res = bmesh.ops.create_cube(bm, size=1.0, matrix=matrix)
        verts = set(res['verts'])
    elif shape == 'head':
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=matrix)
        verts = set(res['verts'])
    else:
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=1.0, radius2=0.85, depth=1.0, matrix=matrix)
        verts = set(res['verts'])
    for f in bm.faces:
        if all(v in verts for v in f.verts):
            f.smooth = (shape == 'head')
            for lp in f.loops:
                lp[uvl].uv = (u, 0.5)


def make_limb(bm, uvl, sw, p0, p1, r):
    va, vb = Vector(p0), Vector(p1)
    d = vb - va
    L = d.length
    if L < 1e-3:
        return
    q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    M = Matrix.Translation((va + vb) * 0.5) @ q @ Matrix.Diagonal((r, r, L, 1.0))
    add_part(bm, uvl, sw, 'cyl', M)


def build_prototype(name, shirt_sw, pants_sw, pose='stand', backpack=False, height_scale=1.0):
    """创建一套 ~180 三角面的低模建筑配景人物原型（面向 +Y，脚底在 Z=0）。"""
    old = bpy.data.meshes.get(name)
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')

    # 色板索引：0肤色 1深发/鞋 2白校服 3藏青裤 4蓝球衣 5红球衣 6教师浅蓝 7暗灰裤/书包
    if pose == 'sit':
        # 坐姿（臀部落在 Z=0.44 坐面上，大腿朝 +Y，小腿向下）
        add_part(bm, uvl, 0, 'head', Matrix.Translation((0, 0.02, 1.18)) @ Matrix.Diagonal((0.105, 0.115, 0.125, 1.0)))
        add_part(bm, uvl, 1, 'head', Matrix.Translation((0, -0.01, 1.24)) @ Matrix.Diagonal((0.108, 0.112, 0.085, 1.0)))
        # 躯干
        add_part(bm, uvl, shirt_sw, 'box', Matrix.Translation((0, 0.0, 0.78)) @ Matrix.Diagonal((0.36, 0.20, 0.52, 1.0)))
        # 臀与大腿（朝前 +Y）
        make_limb(bm, uvl, pants_sw, (-0.10, 0.02, 0.48), (-0.10, 0.44, 0.46), 0.075)
        make_limb(bm, uvl, pants_sw, (0.10, 0.02, 0.48), (0.10, 0.44, 0.46), 0.075)
        # 小腿（向下）
        make_limb(bm, uvl, 0, (-0.10, 0.44, 0.46), (-0.10, 0.46, 0.06), 0.055)
        make_limb(bm, uvl, 0, (0.10, 0.44, 0.46), (0.10, 0.46, 0.06), 0.055)
        # 鞋
        add_part(bm, uvl, 1, 'box', Matrix.Translation((-0.10, 0.50, 0.04)) @ Matrix.Diagonal((0.09, 0.20, 0.08, 1.0)))
        add_part(bm, uvl, 1, 'box', Matrix.Translation((0.10, 0.50, 0.04)) @ Matrix.Diagonal((0.09, 0.20, 0.08, 1.0)))
        # 双臂自然搭在膝上
        make_limb(bm, uvl, shirt_sw, (-0.22, 0.0, 0.98), (-0.23, 0.18, 0.74), 0.055)
        make_limb(bm, uvl, 0, (-0.23, 0.18, 0.74), (-0.16, 0.34, 0.58), 0.045)
        make_limb(bm, uvl, shirt_sw, (0.22, 0.0, 0.98), (0.23, 0.18, 0.74), 0.055)
        make_limb(bm, uvl, 0, (0.23, 0.18, 0.74), (0.16, 0.34, 0.58), 0.045)
    else:
        # 站姿 / 行走 / 奔跑 / 运动举臂
        add_part(bm, uvl, 0, 'head', Matrix.Translation((0, 0.0, 1.56)) @ Matrix.Diagonal((0.105, 0.115, 0.125, 1.0)))
        add_part(bm, uvl, 1, 'head', Matrix.Translation((0, -0.02, 1.62)) @ Matrix.Diagonal((0.108, 0.112, 0.085, 1.0)))
        # 躯干（上衣）
        add_part(bm, uvl, shirt_sw, 'box', Matrix.Translation((0, 0.0, 1.15)) @ Matrix.Diagonal((0.36, 0.20, 0.54, 1.0)))
        # 骨盆/裤腰
        add_part(bm, uvl, pants_sw, 'box', Matrix.Translation((0, 0.0, 0.84)) @ Matrix.Diagonal((0.33, 0.19, 0.14, 1.0)))

        if pose == 'walk':
            # 行走步态
            make_limb(bm, uvl, pants_sw, (-0.10, 0.0, 0.82), (-0.10, 0.18, 0.44), 0.068)
            make_limb(bm, uvl, pants_sw, (-0.10, 0.18, 0.44), (-0.10, 0.24, 0.05), 0.056)
            make_limb(bm, uvl, pants_sw, (0.10, 0.0, 0.82), (0.10, -0.15, 0.44), 0.068)
            make_limb(bm, uvl, pants_sw, (0.10, -0.15, 0.44), (0.10, -0.24, 0.05), 0.056)
            make_limb(bm, uvl, shirt_sw, (-0.22, 0.0, 1.36), (-0.24, -0.14, 1.08), 0.052)
            make_limb(bm, uvl, 0, (-0.24, -0.14, 1.08), (-0.24, -0.22, 0.86), 0.042)
            make_limb(bm, uvl, shirt_sw, (0.22, 0.0, 1.36), (0.24, 0.14, 1.08), 0.052)
            make_limb(bm, uvl, 0, (0.24, 0.14, 1.08), (0.24, 0.24, 0.88), 0.042)
        elif pose == 'run':
            # 动态奔跑（运动短裤 + 露小腿）
            make_limb(bm, uvl, pants_sw, (-0.10, 0.0, 0.82), (-0.10, 0.28, 0.48), 0.072)
            make_limb(bm, uvl, 0, (-0.10, 0.28, 0.48), (-0.10, 0.20, 0.08), 0.052)
            make_limb(bm, uvl, pants_sw, (0.10, 0.0, 0.82), (0.10, -0.22, 0.46), 0.072)
            make_limb(bm, uvl, 0, (0.10, -0.22, 0.46), (0.10, -0.40, 0.16), 0.052)
            make_limb(bm, uvl, shirt_sw, (-0.22, 0.0, 1.36), (-0.25, -0.20, 1.12), 0.052)
            make_limb(bm, uvl, 0, (-0.25, -0.20, 1.12), (-0.22, -0.05, 0.96), 0.042)
            make_limb(bm, uvl, shirt_sw, (0.22, 0.0, 1.36), (0.25, 0.22, 1.16), 0.052)
            make_limb(bm, uvl, 0, (0.25, 0.22, 1.16), (0.20, 0.36, 1.24), 0.042)
        elif pose == 'play':
            # 投篮/挥拍/传球动态举臂
            make_limb(bm, uvl, pants_sw, (-0.11, 0.0, 0.82), (-0.14, 0.14, 0.44), 0.070)
            make_limb(bm, uvl, 0, (-0.14, 0.14, 0.44), (-0.14, 0.12, 0.05), 0.052)
            make_limb(bm, uvl, pants_sw, (0.11, 0.0, 0.82), (0.14, -0.14, 0.44), 0.070)
            make_limb(bm, uvl, 0, (0.14, -0.14, 0.44), (0.14, -0.18, 0.05), 0.052)
            make_limb(bm, uvl, shirt_sw, (0.22, 0.0, 1.36), (0.26, 0.18, 1.56), 0.052)
            make_limb(bm, uvl, 0, (0.26, 0.18, 1.56), (0.18, 0.32, 1.78), 0.042)
            make_limb(bm, uvl, shirt_sw, (-0.22, 0.0, 1.36), (-0.26, 0.12, 1.12), 0.052)
            make_limb(bm, uvl, 0, (-0.26, 0.12, 1.12), (-0.18, 0.28, 1.06), 0.042)
        else:
            # 站立交谈 / 指导
            make_limb(bm, uvl, pants_sw, (-0.10, 0.0, 0.82), (-0.10, 0.02, 0.05), 0.064)
            make_limb(bm, uvl, pants_sw, (0.10, 0.0, 0.82), (0.10, -0.02, 0.05), 0.064)
            make_limb(bm, uvl, shirt_sw, (-0.22, 0.0, 1.36), (-0.24, 0.02, 1.08), 0.052)
            make_limb(bm, uvl, 0, (-0.24, 0.02, 1.08), (-0.22, 0.06, 0.82), 0.042)
            make_limb(bm, uvl, shirt_sw, (0.22, 0.0, 1.36), (0.24, 0.14, 1.12), 0.052)
            make_limb(bm, uvl, 0, (0.24, 0.14, 1.12), (0.16, 0.28, 1.18), 0.042)

        if backpack:
            add_part(bm, uvl, 7, 'box', Matrix.Translation((0.0, -0.17, 1.18)) @ Matrix.Diagonal((0.28, 0.14, 0.36, 1.0)))

    if height_scale != 1.0:
        bmesh.ops.scale(bm, vec=(height_scale, height_scale, height_scale), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(people_mat())
    return me


def ground_z(x, y, dg, sc):
    ok, loc, n, i, ob, _ = sc.ray_cast(dg, Vector((x, y, 40)), Vector((0, 0, -1)))
    return loc.z if ok else 0.0


def main():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    protos = {
        'Student_Walk':  build_prototype('People_Student_Walk',  2, 3, 'walk',  backpack=True,  height_scale=0.98),
        'Student_Stand': build_prototype('People_Student_Stand', 2, 3, 'stand', backpack=False, height_scale=0.97),
        'Student_Sit':   build_prototype('People_Student_Sit',   2, 3, 'sit',   backpack=False, height_scale=0.98),
        'Sport_Blue':    build_prototype('People_Sport_Blue',    4, 3, 'run',   backpack=False, height_scale=1.00),
        'Sport_Red':     build_prototype('People_Sport_Red',     5, 7, 'play',  backpack=False, height_scale=1.00),
        'Teacher_Stand': build_prototype('People_Teacher_Stand', 6, 7, 'stand', backpack=False, height_scale=1.04),
        'Teacher_Walk':  build_prototype('People_Teacher_Walk',  6, 7, 'walk',  backpack=False, height_scale=1.04),
    }

    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    random.seed(2026)

    for idx, p in enumerate(D['people']):
        k = p['kind']
        me = protos[k]
        z = p['z'] if 'z' in p else ground_z(p['x'], p['y'], dg, sc)
        o = bpy.data.objects.new(f'People_{k}_{idx:03d}', me)
        o.location = (p['x'], p['y'], z)
        o.rotation_euler = (0.0, 0.0, math.radians(p['yaw']))
        sc_j = random.uniform(0.95, 1.05)
        o.scale = (sc_j, sc_j, sc_j)
        c.objects.link(o)

    bpy.ops.wm.save_mainfile()
    print('people placed', len(c.objects), 'across', len(protos), 'instanced prototypes')


main()
