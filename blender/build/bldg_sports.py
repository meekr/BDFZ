"""P2–T2 体育及艺术中心建模（外壳破壳透明玻璃幕墙 + 入口门洞 + 直立锁边金属坡屋面 + 细化看台 + 西南底层柱廊）。
数据：data/bldg_sports.json。
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
    if name == 'M_Paving' and m.node_tree and any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes):
        return m
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


def sports_glass_mat():
    """半透明建筑玻璃幕墙：外看通透反光，内看可望见校园操场与蓝天。"""
    m = bpy.data.materials.get('M_SportsGlass')
    if m is None:
        m = bpy.data.materials.new('M_SportsGlass')
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    b.inputs['Base Color'].default_value = (0.24, 0.38, 0.52, 1.0)
    b.inputs['Roughness'].default_value = 0.05
    b.inputs['Metallic'].default_value = 0.25
    b.inputs['Alpha'].default_value = 0.42
    if hasattr(m, 'blend_method'):
        m.blend_method = 'BLEND'
    m.diffuse_color = (0.36, 0.50, 0.62, 0.34)
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


def walls_hollow(c):
    """T2 破壳外墙：半透明玻璃幕墙 + 暗灰竖梃框架，西南主入口与西侧入口留出高 4.2 m 敞开门洞供第一人称自由进出！"""
    bm_gl = bmesh.new()
    bm_fr = bmesh.new()
    outer = D['outer']
    zb = L['ground']
    n = len(outer)

    # 入口开门区域（不封底段玻璃，允许自由步行进入体育中心大厅）
    def is_doorway(x, y):
        # 1) 西南底层柱廊主入口 (x in [-196, -176], y < -174)
        if -196.0 <= x <= -176.0 and y < -174.0:
            return True
        # 2) 东北看台衔接口 (x in [-195, -182], y in [-132, -120])
        if -195.0 <= x <= -180.0 and -132.0 <= y <= -118.0:
            return True
        return False

    for i in range(n):
        j = (i + 1) % n
        x0, y0 = outer[i]
        x1, y1 = outer[j]
        mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        zt0, zt1 = eave_z(x0), eave_z(x1)
        z_bot = zb + 4.4 if is_doorway(mx, my) else zb
        # 玻璃面片
        vs = [
            bm_gl.verts.new((x0, y0, z_bot)),
            bm_gl.verts.new((x1, y1, z_bot)),
            bm_gl.verts.new((x1, y1, zt1)),
            bm_gl.verts.new((x0, y0, zt0)),
        ]
        bm_gl.faces.new(vs)

        # 每隔 3 个顶点加一根暗灰立面竖梃 + 水平横梁（保持外部立面视觉分格）
        if i % 3 == 0:
            dx, dy = x1 - x0, y1 - y0
            Lseg = max(0.05, math.hypot(dx, dy))
            ux, uy = dx / Lseg * 0.14, dy / Lseg * 0.14
            bm_fr.faces.new([
                bm_fr.verts.new((x0, y0, z_bot)),
                bm_fr.verts.new((x0 + ux, y0 + uy, z_bot)),
                bm_fr.verts.new((x0 + ux, y0 + uy, zt0)),
                bm_fr.verts.new((x0, y0, zt0)),
            ])
        # 中间层水平腰梁 (Z = 0.0 处)
        if zt0 > 1.5 and zt1 > 1.5:
            bm_fr.faces.new([
                bm_fr.verts.new((x0, y0, -0.25)),
                bm_fr.verts.new((x1, y1, -0.25)),
                bm_fr.verts.new((x1, y1, 0.25)),
                bm_fr.verts.new((x0, y0, 0.25)),
            ])

    bmesh.ops.recalc_face_normals(bm_gl, faces=bm_gl.faces)
    me_gl = bpy.data.meshes.new('Bldg_SportsArt_Mass')
    bm_gl.to_mesh(me_gl)
    bm_gl.free()
    o_gl = link('Bldg_SportsArt_Mass', me_gl, sports_glass_mat(), c)

    bmesh.ops.recalc_face_normals(bm_fr, faces=bm_fr.faces)
    me_fr = bpy.data.meshes.new('Bldg_SportsArt_Mullions')
    bm_fr.to_mesh(me_fr)
    bm_fr.free()
    link('Bldg_SportsArt_Mullions', me_fr, 'M_Cloud_Slab', c)
    return o_gl


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
    # 按法线夹角拆分脊线/折线硬边，消除 L 形坡屋面对角阴影折痕
    sharp_edges = [
        e for e in bm.edges
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(14.0)
    ]
    if sharp_edges:
        bmesh.ops.split_edges(bm, edges=sharp_edges)
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
    """P10 精确对齐跑道局部坐标系的 8 级混凝土看台：
    严格退让至 track_local x in [-52.10, -45.70]（距红跑道外缘 -44.745 m 留出 0.95 m 安全通道，绝不占用跑道！）。"""
    S = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
    T = S['track']
    tcx, tcy = T['center']
    tang = math.radians(T['long_axis_deg_west_of_north'])
    ca, sa = math.cos(tang), math.sin(tang)

    def to_w(lx, ly):
        return Vector((tcx + lx * ca - ly * sa, tcy + lx * sa + ly * ca))

    x_back = -52.10
    depth_tot = 6.40   # 前缘落在 x_local = -45.70（距跑道外缘 -44.745 净距 0.955 m）
    y_s, y_n = -88.0, -18.5
    p0 = to_w(x_back, y_s)
    p1 = to_w(x_back, y_n)
    ax = (p1 - p0).normalized()
    L_tot = (p1 - p0).length
    perp = Vector((ca, sa))  # 跑道局部 +X（正东偏北，严格垂直于跑道直道！）

    bm = bmesh.new()
    steps = 7
    h_front = 1.12
    h_tot = 4.62
    for k in range(steps):
        d0 = depth_tot * (k / steps)
        d1 = depth_tot * ((k + 1) / steps)
        zt = h_front + (h_tot - h_front) * (1.0 - k / (steps - 1))
        zb = 0.0
        q0 = p0 + perp * d0; q1 = p1 + perp * d0
        q2 = p1 + perp * d1; q3 = p0 + perp * d1
        vs = [bm.verts.new((q0.x, q0.y, zb)), bm.verts.new((q1.x, q1.y, zb)),
              bm.verts.new((q2.x, q2.y, zb)), bm.verts.new((q3.x, q3.y, zb)),
              bm.verts.new((q0.x, q0.y, zt)), bm.verts.new((q1.x, q1.y, zt)),
              bm.verts.new((q2.x, q2.y, zt)), bm.verts.new((q3.x, q3.y, zt))]
        bm.faces.new(vs[0:4]).material_index = 0
        bm.faces.new(vs[4:8]).material_index = 0
        for j in range(4):
            bm.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4])).material_index = 0

    for frac in (0.22, 0.50, 0.78):
        s_mid = L_tot * frac
        for k in range(steps):
            d0 = depth_tot * (k / steps)
            d1 = depth_tot * ((k + 1) / steps)
            zt = h_front + (h_tot - h_front) * (1.0 - k / (steps - 1)) + 0.025
            c0 = p0 + ax * (s_mid - 1.05) + perp * d0
            c1 = p0 + ax * (s_mid + 1.05) + perp * d0
            c2 = p0 + ax * (s_mid + 1.05) + perp * d1
            c3 = p0 + ax * (s_mid - 1.05) + perp * d1
            bm.faces.new([bm.verts.new((c0.x, c0.y, zt)), bm.verts.new((c1.x, c1.y, zt)),
                          bm.verts.new((c2.x, c2.y, zt)), bm.verts.new((c3.x, c3.y, zt))]).material_index = 2

    r0 = p0 + perp * 0.22; r1 = p1 + perp * 0.22
    bm.faces.new([
        bm.verts.new((r0.x, r0.y, h_tot + 0.96)), bm.verts.new((r1.x, r1.y, h_tot + 0.96)),
        bm.verts.new((r1.x, r1.y, h_tot + 1.08)), bm.verts.new((r0.x, r0.y, h_tot + 1.08)),
    ]).material_index = 1
    for i in range(25):
        t = i / 24.0
        qa = r0.lerp(r1, t); qb = qa + ax * 0.08
        bm.faces.new([
            bm.verts.new((qa.x, qa.y, h_tot)), bm.verts.new((qb.x, qb.y, h_tot)),
            bm.verts.new((qb.x, qb.y, h_tot + 1.05)), bm.verts.new((qa.x, qa.y, h_tot + 1.05)),
        ]).material_index = 1

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    old_m = bpy.data.meshes.get('Bldg_SportsArt_Bleachers')
    if old_m: bpy.data.meshes.remove(old_m, do_unlink=True)
    me = bpy.data.meshes.new('Bldg_SportsArt_Bleachers')
    bm.to_mesh(me); bm.free()
    me.materials.append(mat('M_Paving'))
    me.materials.append(mat('M_Cloud_Slab'))
    me.materials.append(mat('M_Cloud_Core'))
    c.objects.link(bpy.data.objects.new('Bldg_SportsArt_Bleachers', me))

    # 前挡墙校训标语（紧贴看台最前立面外 0.04 m，位于 x_local = -45.66，离红跑道外缘仍有 0.91 m 净距）
    bm_w = bmesh.new()
    uvl = bm_w.loops.layers.uv.new('UVMap')
    w0 = p0 + ax * 18.0 + perp * (depth_tot + 0.04)
    w1 = p0 + ax * (L_tot - 18.0) + perp * (depth_tot + 0.04)
    vs = [bm_w.verts.new((w0.x, w0.y, 0.08)), bm_w.verts.new((w1.x, w1.y, 0.08)),
          bm_w.verts.new((w1.x, w1.y, 1.12)), bm_w.verts.new((w0.x, w0.y, 1.12))]
    fw = bm_w.faces.new(vs)
    for lp, uv in zip(fw.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        lp[uvl].uv = uv
    old_w = bpy.data.meshes.get('Bldg_SportsArt_SloganWall')
    if old_w: bpy.data.meshes.remove(old_w, do_unlink=True)
    me_w = bpy.data.meshes.new('Bldg_SportsArt_SloganWall')
    bm_w.to_mesh(me_w); bm_w.free()
    me_w.materials.append(img_mat('M_BleacherSlogan', 'bleacher_slogan.png', 0.80, 0.0, (0.70, 0.70, 0.68, 1)))
    c.objects.link(bpy.data.objects.new('Bldg_SportsArt_SloganWall', me_w))


def sw_colonnade(c):
    col_me = bpy.data.meshes.get('Bldg_Cloud_ColumnUnit')
    if col_me is None:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.45, radius2=0.45, depth=1.0)
        bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)
        col_me = bpy.data.meshes.new('Bldg_Cloud_ColumnUnit')
        bm.to_mesh(col_me); bm.free()
        col_me.materials.append(mat('M_Cloud_Core'))
    outer = D['outer']; zb = L['ground']; idx = 0
    for i in range(len(outer)):
        x, y = outer[i]
        if x < -190.0 and y < -145.0:
            co = bpy.data.objects.new(f'Bldg_SportsArt_Col_{idx:02d}', col_me)
            co.location = (x, y, zb); co.scale = (1.0, 1.0, 5.2)
            c.objects.link(co); idx += 1


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    walls_hollow(c)
    roof(c)
    roof_rim(c)
    bleachers(c)
    sw_colonnade(c)
    bpy.ops.wm.save_mainfile()
    print('sports hollow shell objects', len(c.objects))


main()
