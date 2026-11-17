"""P2 宿舍综合楼体量。数据：data/bldg_dorm.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_dorm.py').read())
"""
import bpy, bmesh, json, os

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_dorm.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Bldg_Dorm'
LINK_X = 100.0     # 以西为与学术中心相连的低层连接体（wx_08 可见，较主体低）
LINK_TOP = 9.8     # 推定 2 层

MATS = {'M_Dorm_Roof': (0.80, 0.80, 0.78, 0.8), 'M_Dorm_Link': (0.66, 0.66, 0.64, 0.8),
        'M_Dorm_Base': (0.55, 0.54, 0.50, 0.9)}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        r, g, b, rough = MATS[name]
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1); bsdf.inputs['Roughness'].default_value = rough
        m.diffuse_color = (r, g, b, 1)
    return m


def prism(name, outer, holes, z0, z1, material, c, keep=None):
    """带洞多边形拉伸；keep=('x>'|'x<', 值) 时只保留半平面一侧。"""
    bm = bmesh.new(); edges = []
    for ring in [outer] + list(holes):
        vs = [bm.verts.new((x, y, 0.0)) for x, y in ring]
        edges += [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    if keep:
        side, v = keep
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(v, 0, 0),
                               plane_no=(1, 0, 0), clear_inner=(side == 'x>'), clear_outer=(side == 'x<'))
    bmesh.ops.dissolve_limit(bm, angle_limit=0.0005, verts=bm.verts[:], edges=bm.edges[:], delimit=set())
    r = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    top = {v for v in r['geom'] if isinstance(v, bmesh.types.BMVert)}
    for v in bm.verts:
        v.co.z = z1 if v in top else z0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat(material))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sh = D['shell'][0]; L = D['levels']
    z0 = L['ground']; roof = z0 + L['floors'] * L['floor_h']
    zb = SITE['campus_base_z']
    # 基座：宿舍台地 42.80 以下到校园地坪（东、南侧为 42.00/37.00 道路，P5 细化挡墙）
    prism('Bldg_Dorm_Base', sh['outer'], [], zb, z0, 'M_Dorm_Base', c)
    prism('Bldg_Dorm_Mass', sh['outer'], sh['holes'], z0, roof + L['parapet'], 'M_Dorm_Roof', c, keep=('x>', LINK_X))
    prism('Bldg_Dorm_Link', sh['outer'], sh['holes'], z0, LINK_TOP, 'M_Dorm_Link', c, keep=('x<', LINK_X))
    bpy.ops.wm.save_mainfile()
    print([(o.name, len(o.data.vertices), [round(v, 1) for v in o.dimensions]) for o in c.objects])


main()
