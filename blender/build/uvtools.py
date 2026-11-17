"""立面 UV 工具：竖直面按 (水平位置 / tile_w, (z - z0) / tile_h) 平铺；可按法向把面分到不同材质槽。"""
import bpy, bmesh
from mathutils import Vector


def image_mat(name, path, rough=0.6, metal=0.0, fallback=(0.8, 0.8, 0.8, 1)):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(path, check_existing=True)
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
        m.diffuse_color = fallback
    return m


def point_in(poly, x, y):
    ins = False; n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            ins = not ins
    return ins


def wall_uv(o, tile_w, tile_h, z0, classify=None):
    """classify(face_center, normal) -> 材质槽号；None 时不改材质。"""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        if abs(f.normal.z) > 0.3:
            continue
        d = Vector((-f.normal.y, f.normal.x, 0)).normalized()
        for lp in f.loops:
            co = lp.vert.co
            lp[uvl].uv = ((co.x * d.x + co.y * d.y) / tile_w, (co.z - z0) / tile_h)
        if classify:
            f.material_index = classify(f.calc_center_median(), f.normal)
    bm.to_mesh(me); bm.free()
