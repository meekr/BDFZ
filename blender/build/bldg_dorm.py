"""P2–P8 宿舍综合楼建模：
- 屋顶外沿与 4 大庭院内沿镂空钢格栅挑檐构架（wx_26/27/33/34）
- 17 处小庭院带立柱轻薄采光顶棚
- 4 处大庭院内部几何石材步道、嵌入式草坪、标志性弧角白色种植池+深灰石材坐凳、4 层室外折跑钢楼梯（wx_26/33）
- 西北连接体直立锁边金属坡屋面与西侧入口雨棚/台阶
数据：data/bldg_dorm.json。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_dorm.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_dorm.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Bldg_Dorm'
LINK_X = 100.0

MATS = {
    'M_Dorm_Roof': (0.60, 0.61, 0.59, 0.85),
    'M_Cloud_Core': (0.91, 0.91, 0.89, 0.72),
    'M_Paving': (0.66, 0.66, 0.64, 0.86),
    'M_Cloud_RoofRim': (0.62, 0.64, 0.66, 0.45),
    'M_Cloud_Slab': (0.22, 0.24, 0.27, 0.45),
    'M_Dorm_Canopy': (0.80, 0.84, 0.86, 0.35),
    'M_Turf': (0.18, 0.39, 0.13, 0.92),
    'M_Cloud_Skylight': (0.18, 0.26, 0.34, 0.14),
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
                bsdf.inputs['Metallic'].default_value = 0.28
        m.diffuse_color = (r, g, b, 1)
    return m


def poly_area(ring):
    return abs(sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
                   for i in range(len(ring)))) * 0.5


def offset_ring(ring, d):
    n = len(ring)
    out = []
    for i in range(n):
        a = Vector(ring[(i - 1) % n])
        b = Vector(ring[i])
        c = Vector(ring[(i + 1) % n])
        t1 = (b - a).normalized() if (b - a).length > 1e-4 else Vector((1, 0))
        t2 = (c - b).normalized() if (c - b).length > 1e-4 else t1
        nm = Vector((t1.y, -t1.x)) + Vector((t2.y, -t2.x))
        nm = nm.normalized() if nm.length > 1e-4 else Vector((t1.y, -t1.x))
        out.append((b.x + nm.x * d, b.y + nm.y * d))
    if (d > 0 and poly_area(out) < poly_area(ring)) or (d < 0 and poly_area(out) > poly_area(ring)):
        out = [(2 * ring[i][0] - out[i][0], 2 * ring[i][1] - out[i][1]) for i in range(n)]
    return out


def add_beam(bm, a, b, w=0.22, h=0.35, mat_idx=0):
    """两点间水平/斜向矩形钢梁。"""
    va, vb = Vector(a), Vector(b)
    d = vb - va
    L = d.length
    if L < 0.05:
        return
    horiz = Vector((d.x, d.y, 0))
    if horiz.length < 1e-4:
        nx, ny = 1.0, 0.0
    else:
        hn = horiz.normalized()
        nx, ny = -hn.y, hn.x
    hw, hh = w * 0.5, h * 0.5
    off = Vector((nx * hw, ny * hw, 0))
    dz = Vector((0, 0, hh))
    vs = [
        bm.verts.new(va - off - dz), bm.verts.new(va + off - dz),
        bm.verts.new(va + off + dz), bm.verts.new(va - off + dz),
        bm.verts.new(vb - off - dz), bm.verts.new(vb + off - dz),
        bm.verts.new(vb + off + dz), bm.verts.new(vb - off + dz),
    ]
    for q in (
        (vs[0], vs[1], vs[5], vs[4]), (vs[1], vs[2], vs[6], vs[5]),
        (vs[2], vs[3], vs[7], vs[6]), (vs[3], vs[0], vs[4], vs[7]),
        (vs[0], vs[3], vs[2], vs[1]), (vs[4], vs[5], vs[6], vs[7]),
    ):
        f = bm.faces.new(q)
        f.material_index = mat_idx


def add_box(bm, p0, p1, mat_idx=0):
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    vs = [bm.verts.new(p) for p in (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )]
    for q in (
        (vs[0], vs[3], vs[2], vs[1]), (vs[4], vs[5], vs[6], vs[7]),
        (vs[0], vs[1], vs[5], vs[4]), (vs[1], vs[2], vs[6], vs[5]),
        (vs[2], vs[3], vs[7], vs[6]), (vs[3], vs[0], vs[4], vs[7]),
    ):
        f = bm.faces.new(q)
        f.material_index = mat_idx


def prism(name, outer, holes, z0, z1, material, c, keep=None, top_mat=None):
    bm = bmesh.new()
    edges = []
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
        f = z1 if v in top else z0
        v.co.z = f(v.co.x, v.co.y) if callable(f) else f
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        if top_mat:
            f.material_index = 1 if f.normal.z > 0.7 else 0
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 10.0, lp.vert.co.y / 10.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(material))
    if top_mat:
        m_top = bpy.data.materials.get(top_mat) or mat(top_mat)
        me.materials.append(m_top)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def open_roof_pergola(name, outer_ring, big_holes, z_roof, c):
    """P8 升级：镂空钢格栅挑檐构架（外沿纵梁 + 内沿纵梁 + 每 3.4 m 一道横向钢椽 + 支柱），
    同时覆盖外墙顶缘与 4 座大庭院内挑格栅（wx_26、wx_27、wx_33、wx_34）。"""
    bm = bmesh.new()
    z_mid = z_roof + 0.75

    def add_trellis_ring(ring, w_out, w_in, filter_x=None):
        r_out = offset_ring(ring, w_out)
        r_in = offset_ring(ring, -w_in)
        r_mid = offset_ring(ring, (w_out - w_in) * 0.5)
        n = len(ring)
        for i in range(n):
            j = (i + 1) % n
            if filter_x is not None and max(r_out[i][0], r_out[j][0]) < filter_x:
                continue
            # 外/中/内三道纵梁
            add_beam(bm, (r_out[i][0], r_out[i][1], z_mid), (r_out[j][0], r_out[j][1], z_mid), 0.24, 0.34, 0)
            add_beam(bm, (r_mid[i][0], r_mid[i][1], z_mid), (r_mid[j][0], r_mid[j][1], z_mid), 0.16, 0.24, 0)
            add_beam(bm, (r_in[i][0], r_in[i][1], z_mid), (r_in[j][0], r_in[j][1], z_mid), 0.24, 0.34, 0)
            # 横向格栅椽条（每 3.4 m 一根）
            L = math.hypot(r_out[j][0] - r_out[i][0], r_out[j][1] - r_out[i][1])
            nr = max(1, int(round(L / 3.4)))
            for k in range(nr):
                t = k / nr
                ax = r_out[i][0] + (r_out[j][0] - r_out[i][0]) * t
                ay = r_out[i][1] + (r_out[j][1] - r_out[i][1]) * t
                bx = r_in[i][0] + (r_in[j][0] - r_in[i][0]) * t
                by = r_in[i][1] + (r_in[j][1] - r_in[i][1]) * t
                add_beam(bm, (ax, ay, z_mid), (bx, by, z_mid), 0.14, 0.26, 0)
                if k % 3 == 0:
                    # 立柱撑起构架（落在女儿墙位置）
                    px = ring[i][0] + (ring[j][0] - ring[i][0]) * t
                    py = ring[i][1] + (ring[j][1] - ring[i][1]) * t
                    add_box(bm, (px - 0.11, py - 0.11, z_roof - 0.1), (px + 0.11, py + 0.11, z_mid), 0)

    add_trellis_ring(outer_ring, 2.3, 1.8, filter_x=LINK_X - 1.0)
    for h in big_holes:
        # 大庭院顶部的内挑钢格栅（上传图 #1/#2 顶部透光钢架！）
        add_trellis_ring(h, 0.0, 1.35, filter_x=None)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Cloud_RoofRim'))
    c.objects.link(bpy.data.objects.new(name, me))


def courtyards_and_canopies(holes, z0, z_roof, c):
    """17 处小庭院带立柱采光顶棚 + 4 处大庭院详细内部（步道/草坪/白色弧角坐凳花池/室外折跑钢楼梯）。"""
    bm_can = bmesh.new()
    bm_det = bmesh.new()  # 0=M_Turf, 1=M_Cloud_Core(花池白墙), 2=M_Cloud_Slab(深灰石材坐凳/钢梯), 3=M_Paving

    for h in holes:
        a = poly_area(h)
        if a < 150.0:
            # 17 处小庭院：轻薄采光顶板 + 4 根金属支撑柱（wx_08/wx_31）
            r = offset_ring(h, 0.75)
            z_top = z_roof + 1.45
            vs = [bm_can.verts.new((x, y, z_top)) for x, y in r]
            f = bm_can.faces.new(vs)
            res = bmesh.ops.extrude_face_region(bm_can, geom=[f])
            bmesh.ops.translate(bm_can, vec=(0, 0, 0.22),
                                verts=[v for v in res['geom'] if isinstance(v, bmesh.types.BMVert)])
            for x, y in h[::max(1, len(h) // 4)][:4]:
                add_box(bm_can, (x - 0.10, y - 0.10, z_roof - 0.1), (x + 0.10, y + 0.10, z_top), 1)
        else:
            # 4 处大庭院内部精细重构（wx_26、wx_33）
            xs = [p[0] for p in h]
            ys = [p[1] for p in h]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            # 1) 庭院草坪底（内收 1.6 m 留外廊边通道）
            r_gr = offset_ring(h, -1.6)
            vs = [bm_det.verts.new((x, y, z0 + 0.06)) for x, y in r_gr]
            f = bm_det.faces.new(vs)
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
            f.material_index = 0
            bmesh.ops.triangulate(bm_det, faces=[f])

            # 2) 中央十字几何浅灰石材步道（略高于草坪 0.04 m）
            sx = (max(xs) - min(xs)) * 0.42
            sy = (max(ys) - min(ys)) * 0.42
            add_box(bm_det, (cx - 1.8, cy - sy, z0 + 0.04), (cx + 1.8, cy + sy, z0 + 0.11), 3)
            add_box(bm_det, (cx - sx, cy - 1.6, z0 + 0.04), (cx + sx, cy + 1.6, z0 + 0.11), 3)

            # 3) 标志性对称白色花池 + 深灰悬挑石材坐凳（上传图 #1/#2）
            for dx in (-4.8, 4.8):
                for dy in (-4.2, 4.2):
                    px, py = cx + dx, cy + dy
                    # 白墙种植池框 (宽 2.8 × 深 2.4 × 高 0.85 m)
                    add_box(bm_det, (px - 1.4, py - 1.2, z0 + 0.05), (px + 1.4, py + 1.2, z0 + 0.88), 1)
                    # 种植池内草土
                    add_box(bm_det, (px - 1.15, py - 0.95, z0 + 0.82), (px + 1.15, py + 0.95, z0 + 0.90), 0)
                    # 外侧深灰悬挑石材坐凳（宽 0.55 m，高 0.45 m）
                    sx0 = px - 1.95 if dx < 0 else px + 1.40
                    sx1 = px - 1.40 if dx < 0 else px + 1.95
                    add_box(bm_det, (sx0, py - 1.15, z0 + 0.36), (sx1, py + 1.15, z0 + 0.46), 2)

            # 4) 室外 4 层折跑钢楼梯（靠西侧墙内缘，还原上传图 #2 左侧标志特征）
            st_x = min(xs) + 1.8
            st_y = cy - 4.0
            fh = D['levels']['floor_h']
            for fl in range(4):
                zb = z0 + fl * fh
                zm = zb + fh * 0.5
                zt = zb + fh
                # 下半跑 (南→北)
                add_beam(bm_det, (st_x, st_y, zb + 0.1), (st_x, st_y + 4.2, zm), 1.35, 0.22, 2)
                # 休息平台
                add_box(bm_det, (st_x - 0.7, st_y + 4.2, zm - 0.12), (st_x + 2.1, st_y + 5.6, zm + 0.08), 2)
                # 上半跑 (北→南)
                add_beam(bm_det, (st_x + 1.4, st_y + 4.2, zm), (st_x + 1.4, st_y, zt), 1.35, 0.22, 2)

    bmesh.ops.recalc_face_normals(bm_can, faces=bm_can.faces)
    me_c = bpy.data.meshes.new('Bldg_Dorm_Canopies')
    bm_can.to_mesh(me_c)
    bm_can.free()
    me_c.materials.append(mat('M_Dorm_Canopy'))
    me_c.materials.append(mat('M_Cloud_Slab'))
    c.objects.link(bpy.data.objects.new('Bldg_Dorm_Canopies', me_c))

    bmesh.ops.recalc_face_normals(bm_det, faces=bm_det.faces)
    me_g = bpy.data.meshes.new('Bldg_Dorm_CourtDetails')
    bm_det.to_mesh(me_g)
    bm_det.free()
    for mn in ('M_Turf', 'M_Cloud_Core', 'M_Cloud_Slab', 'M_Paving'):
        me_g.materials.append(mat(mn))
    c.objects.link(bpy.data.objects.new('Bldg_Dorm_CourtDetails', me_g))


def entrance_canopies(c, z0):
    """宿舍东侧入口玻璃雨棚与石阶（还原上传图 #4 wx_27）。"""
    bm = bmesh.new()
    # 东立面沿 x ≈ 186..196 的几个主要入口点
    for ex, ey in ((190.5, -122.0), (183.5, -72.0), (176.5, -22.0), (168.0, 20.0)):
        # 玻璃雨棚
        add_box(bm, (ex, ey - 2.6, z0 + 3.2), (ex + 2.4, ey + 2.6, z0 + 3.35), 0)
        # 入口台阶
        for s in range(5):
            add_box(bm, (ex + 0.35 * s, ey - 2.0, z0 - 0.8 + 0.16 * s),
                    (ex + 2.2, ey + 2.0, z0 - 0.64 + 0.16 * s), 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Bldg_Dorm_Entrances')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('M_Cloud_Skylight'))
    me.materials.append(mat('M_Paving'))
    c.objects.link(bpy.data.objects.new('Bldg_Dorm_Entrances', me))


exec(open(os.path.join(ROOT, 'blender', 'build', 'uvtools.py')).read())
TEX = os.path.join(ROOT, 'blender', 'textures')


def reload_image_mat(name, path, rough=0.6, metal=0.0, fallback=(0.8, 0.8, 0.8, 1)):
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
    img = bpy.data.images.load(path, check_existing=True)
    img.reload()
    tex.image = img
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = fallback
    return m


def facades(c, z0):
    holes = D['shell'][0]['holes']
    win = reload_image_mat('M_Dorm_Window', os.path.join(TEX, 'dorm_window.png'), 0.65, 0.0, (0.90, 0.90, 0.89, 1))
    gal = reload_image_mat('M_Dorm_Gallery', os.path.join(TEX, 'dorm_gallery.png'), 0.70, 0.0, (0.80, 0.80, 0.78, 1))

    for name in ('Bldg_Dorm_Mass', 'Bldg_Dorm_Link'):
        o = bpy.data.objects[name]
        win_idx = len(o.data.materials)
        o.data.materials.append(win)
        gal_idx = len(o.data.materials)
        o.data.materials.append(gal)

        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            if abs(f.normal.z) > 0.35:
                continue
            q = f.calc_center_median() + f.normal * 1.0
            is_court = any(point_in(h, q.x, q.y) for h in holes)
            f.material_index = gal_idx if is_court else win_idx
            u_span = 4.5 if is_court else 14.4
            t = Vector((-f.normal.y, f.normal.x, 0.0)).normalized()
            for lp in f.loops:
                p = lp.vert.co
                lp[uvl].uv = ((p.x * t.x + p.y * t.y) / u_span, (p.z - z0) / D['levels']['floor_h'])
        bm.to_mesh(o.data)
        bm.free()


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sh = D['shell'][0]
    L = D['levels']
    z0 = L['ground']
    z_body = z0 + L['floors'] * L['floor_h'] + 0.4
    zb = SITE['campus_base_z']

    prism('Bldg_Dorm_Base', sh['outer'], [], zb, z0, 'M_Paving', c)
    prism('Bldg_Dorm_Mass', sh['outer'], sh['holes'], z0, z_body, 'M_Dorm_Roof', c, keep=('x>', LINK_X))
    link_roof_z = lambda x, y: 7.5 + max(0.0, min(1.0, (x - 80.0) / 20.0)) * 6.3
    prism('Bldg_Dorm_Link', sh['outer'], sh['holes'], z0, link_roof_z, 'M_Cloud_Core', c,
          keep=('x<', LINK_X), top_mat='M_Cloud_RoofPanel')
    facades(c, z0)
    big_holes = [h for h in sh['holes'] if poly_area(h) >= 150.0]
    open_roof_pergola('Bldg_Dorm_Pergola', sh['outer'], big_holes, z_body, c)
    courtyards_and_canopies(sh['holes'], z0, z_body, c)
    entrance_canopies(c, z0)
    bpy.ops.wm.save_mainfile()
    print('dorm objects', [(o.name, len(o.data.vertices)) for o in c.objects])


main()
