"""P0 场景初始化：单位、集合、参考平面（卫星 + 01/02/03/04 图纸）。

在 Blender 中运行：exec(open('<repo>/blender/build/p0_scene.py').read())
参考平面按 data/frames.json 的「像素 → 世界米」相似变换铺设，四角直接取变换结果，无需手调。
"""
import bpy, json, os

ROOT = '/Users/perrylei/repos/BDFZ'
FR = json.load(open(os.path.join(ROOT, 'data', 'frames.json')))

REF_ITEMS = [
    # name, key, z, opacity
    ('REF_Satellite', 'sat', -0.30, 1.0),
    ('REF_01_color_site', '01', -0.20, 0.9),
    ('REF_02_roof_plan', '02', -0.10, 0.9),
    ('REF_03_line_site', '03', -0.05, 0.9),
    ('REF_04_cloud_3f', '04', 12.50, 0.9),
]

COLLECTIONS = ['REF_Drawings', 'REF_Cameras', 'Site', 'Bldg_Cloud', 'Bldg_Dorm', 'Bldg_SportsArt',
               'Bldg_Library', 'Bldg_Admin', 'Bldg_Tech', 'Bldg_Lab', 'Landscape']


def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for d in list(blk):
            if d.users == 0:
                blk.remove(d)


def setup_units():
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.scale_length = 1.0
    s.unit_settings.length_unit = 'METERS'
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.clip_end = 5000
                    sp.clip_start = 0.1


def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def ref_material(name, img, opacity, line_art=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Linear'
    emi = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(tex.outputs['Color'], emi.inputs['Color'])
    if line_art:
        # 白纸透明：只保留深色线条（亮度 < 0.55），浅灰填充与白纸都透明，线稿叠在卫星上仍可辨认
        bw = nt.nodes.new('ShaderNodeRGBToBW'); inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'GREATER_THAN'; mul.inputs[1].default_value = 0.45
        cl = nt.nodes.new('ShaderNodeClamp')
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Color'], bw.inputs[0]); nt.links.new(bw.outputs[0], inv.inputs[1])
        nt.links.new(inv.outputs[0], mul.inputs[0]); nt.links.new(mul.outputs[0], cl.inputs[0]); nt.links.new(cl.outputs[0], mix.inputs[0])
        emi.inputs['Color'].default_value = (0.9, 0.05, 0.05, 1); nt.links.remove(emi.inputs['Color'].links[0])
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(emi.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        m.surface_render_method = 'BLENDED'
    elif opacity < 1.0:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs[0].default_value = opacity
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(emi.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        m.surface_render_method = 'BLENDED'
    else:
        nt.links.new(emi.outputs[0], out.inputs['Surface'])
    return m


def ref_plane(name, key, z, opacity, coll):
    f = FR['sat'] if key == 'sat' else FR['frames'][key]
    path = os.path.join(ROOT, f['file'])
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    A = f['px_to_world']

    def P(px, py):
        return (A[0][0] * px + A[0][1] * py + A[0][2], A[1][0] * px + A[1][1] * py + A[1][2], z)
    me = bpy.data.meshes.new(name)
    me.from_pydata([P(0, h), P(w, h), P(w, 0), P(0, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = c
    me.materials.append(ref_material('M_' + name, img, opacity, line_art=key in ('02', '03', '04')))
    ob = bpy.data.objects.new(name, me)
    ob.hide_select = True
    ob['source'] = f['file']; ob['px_per_m'] = f['px_per_m']
    coll.objects.link(ob)
    return ob


def main():
    reset_scene()
    setup_units()
    for n in COLLECTIONS:
        collection(n)
    rc = bpy.data.collections['REF_Drawings']
    for name, key, z, op in REF_ITEMS:
        ob = ref_plane(name, key, z, op, rc)
        if key not in ('sat', '02'):
            ob.hide_set(True); ob.hide_render = True
    sc = bpy.context.scene
    sc['world_origin_latlon'] = FR['world']['origin_latlon']
    sc.render.engine = 'BLENDER_EEVEE'
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'blender', 'bdfz.blend'))
    print('ok', [o.name for o in rc.objects])



def refresh_refs():
    """只重建参考平面（frames.json 更新后用），不动其它集合。"""
    rc = bpy.data.collections['REF_Drawings']
    for o in list(rc.objects):
        m = o.data.materials[0] if o.data.materials else None
        bpy.data.objects.remove(o, do_unlink=True)
        if m and m.users == 0:
            bpy.data.materials.remove(m)
    for name, key, z, op in REF_ITEMS:
        ob = ref_plane(name, key, z, op, rc)
        ob.hide_render = True
        ob.hide_set(key != '02')
    bpy.ops.wm.save_mainfile()
    print('refs refreshed', [o.name for o in rc.objects])


# exec 前设 REFS_ONLY = True 则只刷新参考平面
if globals().get('REFS_ONLY'):
    refresh_refs()
else:
    main()
