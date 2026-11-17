"""P2 学术中心南侧低层体量（金属屋面，wx_01）。数据：data/bldg_annex.json。"""
import bpy, bmesh, json, os

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_annex.json')))
COLL = 'Bldg_Cloud'


def mat():
    m = bpy.data.materials.get('M_Annex_Roof')
    if m is None:
        m = bpy.data.materials.new('M_Annex_Roof'); m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        b.inputs['Base Color'].default_value = (0.50, 0.52, 0.55, 1); b.inputs['Roughness'].default_value = 0.5
        m.diffuse_color = (0.50, 0.52, 0.55, 1)
    return m


def main():
    c = bpy.data.collections[COLL]
    for o in [o for o in c.objects if o.name.startswith('Bldg_Cloud_Annex')]:
        bpy.data.objects.remove(o, do_unlink=True)
    for k, b in D['blocks'].items():
        bm = bmesh.new()
        f = bm.faces.new([bm.verts.new((x, y, D['base_z'])) for x, y in b['outer']])
        r = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, vec=(0, 0, b['top'] - D['base_z']), verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new('Bldg_Cloud_Annex_' + k); bm.to_mesh(me); bm.free()
        me.materials.append(mat())
        c.objects.link(bpy.data.objects.new(me.name, me))
    bpy.ops.wm.save_mainfile()
    print('annex', list(D['blocks']))


main()
