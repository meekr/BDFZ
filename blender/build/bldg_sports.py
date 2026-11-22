"""P2–P6 体育及艺术中心建模（含东南翼下坡屋面、浅灰屋面压顶、田径场西侧看台）。数据：data/bldg_sports.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_sports.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_sports.json')))
COLL = 'Bldg_SportsArt'
L = D['levels']

MATS = {
    'M_Sports_Wall': (0.70, 0.70, 0.68, 0.8),
    'M_Cloud_RoofPanel': (0.15, 0.18, 0.22, 0.48),       # wx_03/04/19/35：深蓝灰金属直立锁边坡屋面
    'M_Cloud_RoofRim': (0.68, 0.70, 0.72, 0.45),        # 屋面四周浅灰金属檐口压顶带
    'M_Paving': (0.62, 0.62, 0.60, 0.85),   # 混凝土阶梯看台
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
    r, g, b, rough = MATS[name]
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
    bsdf.inputs['Roughness'].default_value = rough
    if name in ('M_Cloud_RoofPanel', 'M_Cloud_RoofRim'):
        bsdf.inputs['Metallic'].default_value = 0.25
    m.diffuse_color = (r, g, b, 1)
    return m


def eave_z(x):
    x0, x1 = L.get('slope_x', [-148.0, -74.0])
    ew, ee = L.get('eave_west', L['eave']), L.get('eave_east', L['eave'])
    t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
    return ew + (ee - ew) * t


def link(name, me, material, c):
    me.materials.append(mat(material))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def walls(c):
    """外墙顶部紧贴斜坡檐口 eave_z(x)，东南翼向东平滑降低至 Z 3.5 m（wx_04、wx_19）。"""
    bm = bmesh.new()
    outer = D['outer']
    zb = L['ground']
    vb = [bm.verts.new((x, y, zb)) for x, y in outer]
    vt = [bm.verts.new((x, y, eave_z(x))) for x, y in outer]
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
    bm.faces.new(list(reversed(vb)))
    # 顶面用三角化补洞（防凹多边形遮挡）
    f_top = bm.faces.new(vt)
    bmesh.ops.triangulate(bm, faces=[f_top])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Mass'); bm.to_mesh(me); bm.free()
    return link('Bldg_SportsArt_Mass', me, 'M_Cloud_RoofPanel', c)


def roof(c):
    R = D['roof']
    me = bpy.data.meshes.new('Bldg_SportsArt_Roof')
    me.from_pydata([tuple(v) for v in R['verts']], [], [tuple(f) for f in R['faces']])
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(me); bm.free()
    o = link('Bldg_SportsArt_Roof', me, 'M_Cloud_RoofPanel', c)
    for p in me.polygons:
        p.use_smooth = True
    return o


def roof_rim(c):
    """屋面外沿浅灰金属檐口包边带（厚 1.4 m，外挑 0.9 m，wx_04/wx_19/wx_35 显著轮廓）。"""
    outer = D['outer']
    bm = bmesh.new()
    n = len(outer)
    # 计算每个顶点的外法向偏移
    out2 = []
    for i in range(n):
        a = Vector((outer[(i - 1) % n][0], outer[(i - 1) % n][1]))
        b = Vector((outer[i][0], outer[i][1]))
        d = Vector((outer[(i + 1) % n][0], outer[(i + 1) % n][1]))
        t1 = (b - a).normalized() if (b - a).length > 1e-4 else Vector((1, 0))
        t2 = (d - b).normalized() if (d - b).length > 1e-4 else t1
        n1 = Vector((t1.y, -t1.x))
        n2 = Vector((t2.y, -t2.x))
        nm = (n1 + n2)
        nm = nm.normalized() if nm.length > 1e-4 else n1
        out2.append((b.x + nm.x * 0.9, b.y + nm.y * 0.9))
    # 检查偏移方向是否确实向外（面积应增大）
    def area2(poly):
        return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    if abs(area2(out2)) < abs(area2(outer)):
        out2 = [(2 * outer[i][0] - out2[i][0], 2 * outer[i][1] - out2[i][1]) for i in range(n)]

    vi_t = [bm.verts.new((x, y, eave_z(x) + 0.12)) for x, y in outer]
    vo_t = [bm.verts.new((x, y, eave_z(x) + 0.12)) for x, y in out2]
    vo_b = [bm.verts.new((x, y, eave_z(x) - 1.35)) for x, y in out2]
    vi_b = [bm.verts.new((x, y, eave_z(x) - 1.35)) for x, y in outer]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vi_t[i], vi_t[j], vo_t[j], vo_t[i]))  # 顶边
        bm.faces.new((vo_t[i], vo_t[j], vo_b[j], vo_b[i]))  # 外立面檐口
        bm.faces.new((vo_b[i], vo_b[j], vi_b[j], vi_b[i]))  # 底面挑檐
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Rim'); bm.to_mesh(me); bm.free()
    return link('Bldg_SportsArt_Rim', me, 'M_Cloud_RoofRim', c)


def bleachers(c):
    """西翼东侧面向田径场的阶梯看台（wx_03、wx_04、wx_31、wx_36、08 长剖面证实）。
    沿西翼东缘 C9(-193,-117.6) → C10(-218,-47.4)，向操场（东偏北）阶梯状下降至 Z 0.0。"""
    p0 = Vector((-193.0, -115.0))
    p1 = Vector((-217.5, -48.5))
    ax = (p1 - p0).normalized()
    # 指向操场（+X 方向）的法向
    perp = Vector((-ax.y, ax.x))
    if perp.x < 0:
        perp = -perp
    bm = bmesh.new()
    steps = 9
    depth_tot = 9.0
    h_tot = 5.4
    for k in range(steps):
        d0 = depth_tot * (k / steps)
        d1 = depth_tot * ((k + 1) / steps)
        zt = h_tot * (1.0 - k / steps)
        zb = 0.0
        q0 = p0 + perp * d0; q1 = p1 + perp * d0
        q2 = p1 + perp * d1; q3 = p0 + perp * d1
        vs = [bm.verts.new((q0.x, q0.y, zb)), bm.verts.new((q1.x, q1.y, zb)),
              bm.verts.new((q2.x, q2.y, zb)), bm.verts.new((q3.x, q3.y, zb)),
              bm.verts.new((q0.x, q0.y, zt)), bm.verts.new((q1.x, q1.y, zt)),
              bm.verts.new((q2.x, q2.y, zt)), bm.verts.new((q3.x, q3.y, zt))]
        bm.faces.new(vs[0:4]); bm.faces.new(vs[4:8])
        for j in range(4):
            bm.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Bleachers'); bm.to_mesh(me); bm.free()
    return link('Bldg_SportsArt_Bleachers', me, 'M_Paving', c)


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    w = walls(c); roof(c); roof_rim(c); bleachers(c)
    exec(open(os.path.join(ROOT, 'blender', 'build', 'uvtools.py')).read(), globals())
    w.data.materials.clear()
    w.data.materials.append(mat('M_Cloud_RoofPanel'))
    m_gl = image_mat('M_Cloud_GlassGrid', os.path.join(ROOT, 'blender', 'textures', 'cloud_glass.png'), 0.08, 0.4, (0.30, 0.38, 0.45, 1))
    w.data.materials.append(m_gl)
    wall_uv(w, 1.5, 4.5, L['ground'], lambda p, n: 1)
    bpy.ops.wm.save_mainfile()
    print([(o.name, len(o.data.vertices), [round(v, 1) for v in o.dimensions]) for o in c.objects])


main()
