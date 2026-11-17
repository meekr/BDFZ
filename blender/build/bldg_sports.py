"""P2 体育及艺术中心体量。数据：data/bldg_sports.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_sports.py').read())
"""
import bpy, bmesh, json, os

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_sports.json')))
COLL = 'Bldg_SportsArt'
MATS = {'M_Sports_Wall': (0.70, 0.70, 0.68, 0.8), 'M_Sports_Roof': (0.38, 0.40, 0.43, 0.6)}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        r, g, b, rough = MATS[name]
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1); bsdf.inputs['Roughness'].default_value = rough
        m.diffuse_color = (r, g, b, 1)
    return m


def link(name, me, material, c):
    me.materials.append(mat(material))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def walls(c):
    L = D['levels']
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, L['ground'])) for x, y in D['outer']]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=(0, 0, L['eave'] - L['ground']), verts=[v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Mass'); bm.to_mesh(me); bm.free()
    return link('Bldg_SportsArt_Mass', me, 'M_Sports_Wall', c)


def roof(c):
    R = D['roof']
    me = bpy.data.meshes.new('Bldg_SportsArt_Roof')
    me.from_pydata([tuple(v) for v in R['verts']], [], [tuple(f) for f in R['faces']])
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(me); bm.free()
    o = link('Bldg_SportsArt_Roof', me, 'M_Sports_Roof', c)
    for p in me.polygons:
        p.use_smooth = False
    return o


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    w = walls(c); roof(c)
    exec(open(os.path.join(ROOT, 'blender', 'build', 'uvtools.py')).read(), globals())
    w.data.materials.clear()
    w.data.materials.append(mat('M_Sports_Roof'))     # 顶盖：补屋面三角网在凹角处的缺口
    w.data.materials.append(image_mat('M_Cloud_GlassGrid', os.path.join(ROOT, 'blender', 'textures', 'cloud_glass.png'), 0.08, 0.4, (0.30, 0.38, 0.45, 1)))
    wall_uv(w, 1.5, 4.5, D['levels']['ground'], lambda p, n: 1)
    bpy.ops.wm.save_mainfile()
    print([(o.name, len(o.data.vertices), [round(v, 1) for v in o.dimensions]) for o in c.objects])


main()
