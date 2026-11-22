"""P2–P8 体育及艺术中心建模（直立锁边金属坡屋面、浅灰屋面压顶、细化阶梯看台含 3 过道/护栏/标语前墙、西南底层柱廊）。
数据：data/bldg_sports.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_sports.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_sports.json')))
COLL = 'Bldg_SportsArt'
L = D['levels']

MATS = {
    'M_Cloud_RoofRim': (0.68, 0.70, 0.72, 0.45),
    'M_Cloud_Slab': (0.22, 0.24, 0.27, 0.45),
    'M_Cloud_Core': (0.91, 0.91, 0.89, 0.72),
    'M_Paving': (0.66, 0.66, 0.64, 0.86),
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    if name in MATS:
        r, g, b, rough = MATS[name]
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
            bsdf.inputs['Roughness'].default_value = rough
            if name in ('M_Cloud_RoofRim', 'M_Cloud_Slab'):
                bsdf.inputs['Metallic'].default_value = 0.25
        m.diffuse_color = (r, g, b, 1)
    return m


def img_mat(name, fname, rough=0.65, metal=0.0, fallback=(0.6, 0.6, 0.6, 1)):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(ROOT, 'blender', 'textures', fname), check_existing=True)
    img.reload()
    tex.image = img
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = fallback
    return m


def eave_z(x):
    x0, x1 = L.get('slope_x', [-148.0, -74.0])
    ew, ee = L.get('eave_west', L['eave']), L.get('eave_east', L['eave'])
    t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
    return ew + (ee - ew) * t


def link(name, me, material, c):
    m = material if isinstance(material, bpy.types.Material) else (bpy.data.materials.get(material) or mat(material))
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def walls(c):
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
    f_top = bm.faces.new(vt)
    bmesh.ops.triangulate(bm, faces=[f_top])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Mass')
    bm.to_mesh(me)
    bm.free()
    return link('Bldg_SportsArt_Mass', me, 'M_Cloud_RoofPanel', c)


def roof(c):
    R = D['roof']
    me = bpy.data.meshes.new('Bldg_SportsArt_Roof')
    me.from_pydata([tuple(v) for v in R['verts']], [], [tuple(f) for f in R['faces']])
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 10.0, lp.vert.co.y / 10.0)
    bm.to_mesh(me)
    bm.free()
    o = link('Bldg_SportsArt_Roof', me, 'M_Cloud_RoofPanel', c)
    for p in me.polygons:
        p.use_smooth = True
    return o


def roof_rim(c):
    outer = D['outer']
    bm = bmesh.new()
    n = len(outer)
    out2 = []
    for i in range(n):
        a = Vector((outer[(i - 1) % n][0], outer[(i - 1) % n][1]))
        b = Vector((outer[i][0], outer[i][1]))
        d = Vector((outer[(i + 1) % n][0], outer[(i + 1) % n][1]))
        t1 = (b - a).normalized() if (b - a).length > 1e-4 else Vector((1, 0))
        t2 = (d - b).normalized() if (d - b).length > 1e-4 else t1
        nm = Vector((t1.y, -t1.x)) + Vector((t2.y, -t2.x))
        nm = nm.normalized() if nm.length > 1e-4 else Vector((t1.y, -t1.x))
        out2.append((b.x + nm.x * 0.9, b.y + nm.y * 0.9))

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
        bm.faces.new((vi_t[i], vi_t[j], vo_t[j], vo_t[i]))
        bm.faces.new((vo_t[i], vo_t[j], vo_b[j], vo_b[i]))
        bm.faces.new((vo_b[i], vo_b[j], vi_b[j], vi_b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Rim')
    bm.to_mesh(me)
    bm.free()
    return link('Bldg_SportsArt_Rim', me, 'M_Cloud_RoofRim', c)


def bleachers(c):
    """P8 升级：西翼东侧面向田径场的 9 级混凝土看台（含 3 条纵向阶梯过道、顶部及两侧栏杆、前挡墙标语贴图，official_19.jpg）。"""
    p0 = Vector((-193.0, -115.0))
    p1 = Vector((-217.5, -48.5))
    ax = (p1 - p0).normalized()
    L_tot = (p1 - p0).length
    perp = Vector((-ax.y, ax.x))
    if perp.x < 0:
        perp = -perp

    bm = bmesh.new()
    steps = 9
    depth_tot = 9.0
    h_tot = 5.4
    # 0 = M_Paving（看台混凝土）, 1 = M_Cloud_Slab（栏杆）, 2 = M_Cloud_Core（踏步过道浅灰条）
    for k in range(steps):
        d0 = depth_tot * (k / steps)
        d1 = depth_tot * ((k + 1) / steps)
        zt = h_tot * (1.0 - k / steps)
        zb = 0.0
        q0 = p0 + perp * d0
        q1 = p1 + perp * d0
        q2 = p1 + perp * d1
        q3 = p0 + perp * d1
        vs = [bm.verts.new((q0.x, q0.y, zb)), bm.verts.new((q1.x, q1.y, zb)),
              bm.verts.new((q2.x, q2.y, zb)), bm.verts.new((q3.x, q3.y, zb)),
              bm.verts.new((q0.x, q0.y, zt)), bm.verts.new((q1.x, q1.y, zt)),
              bm.verts.new((q2.x, q2.y, zt)), bm.verts.new((q3.x, q3.y, zt))]
        bm.faces.new(vs[0:4]).material_index = 0
        bm.faces.new(vs[4:8]).material_index = 0
        for j in range(4):
            bm.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4])).material_index = 0

    # 3 条纵向踏步过道（official_19.jpg 可见 3 处浅色踏步楼梯分隔看台）
    for frac in (0.22, 0.50, 0.78):
        s_mid = L_tot * frac
        for k in range(steps):
            d0 = depth_tot * (k / steps)
            d1 = depth_tot * ((k + 1) / steps)
            zt = h_tot * (1.0 - k / steps) + 0.03
            c0 = p0 + ax * (s_mid - 1.1) + perp * d0
            c1 = p0 + ax * (s_mid + 1.1) + perp * d0
            c2 = p0 + ax * (s_mid + 1.1) + perp * d1
            c3 = p0 + ax * (s_mid - 1.1) + perp * d1
            f = bm.faces.new([bm.verts.new((c0.x, c0.y, zt)), bm.verts.new((c1.x, c1.y, zt)),
                              bm.verts.new((c2.x, c2.y, zt)), bm.verts.new((c3.x, c3.y, zt))])
            f.material_index = 2

    # 顶部护栏（高 1.05 m）
    r0 = p0 + perp * 0.25
    r1 = p1 + perp * 0.25
    bm.faces.new([
        bm.verts.new((r0.x, r0.y, h_tot + 0.96)), bm.verts.new((r1.x, r1.y, h_tot + 0.96)),
        bm.verts.new((r1.x, r1.y, h_tot + 1.08)), bm.verts.new((r0.x, r0.y, h_tot + 1.08)),
    ]).material_index = 1
    for i in range(25):
        t = i / 24.0
        qa = r0.lerp(r1, t)
        qb = qa + ax * 0.08
        bm.faces.new([
            bm.verts.new((qa.x, qa.y, h_tot)), bm.verts.new((qb.x, qb.y, h_tot)),
            bm.verts.new((qb.x, qb.y, h_tot + 1.05)), bm.verts.new((qa.x, qa.y, h_tot + 1.05)),
        ]).material_index = 1

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_SportsArt_Bleachers')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Paving'))
    me.materials.append(mat('M_Cloud_Slab'))
    me.materials.append(mat('M_Cloud_Core'))
    c.objects.link(bpy.data.objects.new('Bldg_SportsArt_Bleachers', me))

    # 看台前缘校训标语挡墙（official_19.jpg：“体育强则中国强 体育兴则中国兴” + 奥运五环）
    bm_w = bmesh.new()
    uvl = bm_w.loops.layers.uv.new('UVMap')
    w0 = p0 + ax * 14.0 + perp * (depth_tot + 0.06)
    w1 = p0 + ax * (L_tot - 14.0) + perp * (depth_tot + 0.06)
    vs = [
        bm_w.verts.new((w0.x, w0.y, 0.05)),
        bm_w.verts.new((w1.x, w1.y, 0.05)),
        bm_w.verts.new((w1.x, w1.y, 2.35)),
        bm_w.verts.new((w0.x, w0.y, 2.35)),
    ]
    fw = bm_w.faces.new(vs)
    for lp, uv in zip(fw.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        lp[uvl].uv = uv
    me_w = bpy.data.meshes.new('Bldg_SportsArt_SloganWall')
    bm_w.to_mesh(me_w)
    bm_w.free()
    me_w.materials.append(img_mat('M_BleacherSlogan', 'bleacher_slogan.png', 0.80, 0.0, (0.70, 0.70, 0.68, 1)))
    c.objects.link(bpy.data.objects.new('Bldg_SportsArt_SloganWall', me_w))


def sw_colonnade(c):
    """西南角一层外围柱廊（wx_04 左下角可见白色外廊圆柱列）。"""
    col_me = bpy.data.meshes.get('Bldg_Cloud_ColumnUnit')
    if col_me is None:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.45, radius2=0.45, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
        col_me = bpy.data.meshes.new('Bldg_Cloud_ColumnUnit')
        bm.to_mesh(col_me)
        bm.free()
        col_me.materials.append(mat('M_Cloud_Core'))
    outer = D['outer']
    zb = L['ground']
    idx = 0
    for i in range(len(outer)):
        x, y = outer[i]
        # 西南弯角区域 (x < -190, y < -145)
        if x < -190.0 and y < -145.0:
            co = bpy.data.objects.new(f'Bldg_SportsArt_Col_{idx:02d}', col_me)
            co.location = (x, y, zb)
            co.scale = (1.0, 1.0, 5.2)
            c.objects.link(co)
            idx += 1


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    w = walls(c)
    roof(c)
    roof_rim(c)
    bleachers(c)
    sw_colonnade(c)
    exec(open(os.path.join(ROOT, 'blender', 'build', 'uvtools.py')).read(), globals())
    w.data.materials.clear()
    w.data.materials.append(bpy.data.materials.get('M_Cloud_RoofPanel') or mat('M_Cloud_RoofRim'))
    m_gl = image_mat('M_Cloud_GlassGrid', os.path.join(ROOT, 'blender', 'textures', 'cloud_glass.png'), 0.08, 0.4, (0.30, 0.38, 0.45, 1))
    w.data.materials.append(m_gl)
    wall_uv(w, 1.5, 4.5, L['ground'], lambda p, n: 1)
    bpy.ops.wm.save_mainfile()
    print('sports objects', [(o.name, len(o.data.vertices)) for o in c.objects])


main()
