"""P2–P6 宿舍综合楼建模（含屋顶挑檐钢构架、17 处小庭院遮阳顶棚、4 处大庭院草坪、斜坡金属屋面连接体）。
数据：data/bldg_dorm.json。实景依据：wx_03、wx_08、wx_11、wx_26、wx_27、wx_31、wx_33、wx_34。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/bldg_dorm.py').read())
"""
import bpy, bmesh, json, os, math
from mathutils import Vector

ROOT = '/Users/perrylei/repos/BDFZ_V3'
D = json.load(open(os.path.join(ROOT, 'data', 'bldg_dorm.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
COLL = 'Bldg_Dorm'
LINK_X = 100.0

MATS = {
    'M_Dorm_Roof': (0.58, 0.59, 0.57, 0.85),          # 屋面浅灰防水面层（wx_03/08/31）
    'M_Cloud_Core': (0.86, 0.86, 0.84, 0.80),          # 连接体白色立面
    'M_Cloud_RoofPanel': (0.16, 0.19, 0.24, 0.48),      # wx_03/08/31：连接体深蓝灰金属坡屋面
    'M_Paving': (0.55, 0.54, 0.50, 0.90),
    'M_Cloud_RoofRim': (0.60, 0.62, 0.64, 0.45),       # wx_03/08/27/34：屋顶浅灰金属挑檐构架
    'M_Dorm_Canopy': (0.78, 0.80, 0.78, 0.60),        # wx_03/08/31：17 处小庭院架高遮阳棚
    'M_Turf': (0.20, 0.38, 0.14, 0.92),         # wx_26/33：大庭院草坪
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


def poly_area(ring):
    return abs(sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
                   for i in range(len(ring)))) * 0.5


def offset_ring(ring, d):
    n = len(ring)
    out = []
    for i in range(n):
        a = Vector(ring[(i - 1) % n]); b = Vector(ring[i]); c = Vector(ring[(i + 1) % n])
        t1 = (b - a).normalized() if (b - a).length > 1e-4 else Vector((1, 0))
        t2 = (c - b).normalized() if (c - b).length > 1e-4 else t1
        nm = Vector((t1.y, -t1.x)) + Vector((t2.y, -t2.x))
        nm = nm.normalized() if nm.length > 1e-4 else Vector((t1.y, -t1.x))
        out.append((b.x + nm.x * d, b.y + nm.y * d))
    if (d > 0 and poly_area(out) < poly_area(ring)) or (d < 0 and poly_area(out) > poly_area(ring)):
        out = [(2 * ring[i][0] - out[i][0], 2 * ring[i][1] - out[i][1]) for i in range(n)]
    return out


def prism(name, outer, holes, z0, z1, material, c, keep=None, top_mat=None):
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
        f = z1 if v in top else z0
        v.co.z = f(v.co.x, v.co.y) if callable(f) else f
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if top_mat:
        for f in bm.faces:
            f.material_index = 1 if f.normal.z > 0.7 else 0
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat(material))
    if top_mat:
        me.materials.append(mat(top_mat))
    o = bpy.data.objects.new(name, me); c.objects.link(o)
    return o


def roof_canopy_band(name, ring, width_out, width_in, z_bot, z_top, c):
    """沿轮廓生成悬挑屋顶遮阳挑檐环带（wx_03/wx_08/wx_27/wx_31/wx_34）。"""
    r_out = offset_ring(ring, width_out)
    r_in = offset_ring(ring, -width_in)
    bm = bmesh.new()
    n = len(ring)
    vo_b = [bm.verts.new((x, y, z_bot)) for x, y in r_out]
    vo_t = [bm.verts.new((x, y, z_top)) for x, y in r_out]
    vi_b = [bm.verts.new((x, y, z_bot)) for x, y in r_in]
    vi_t = [bm.verts.new((x, y, z_top)) for x, y in r_in]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vo_t[i], vo_t[j], vi_t[j], vi_t[i]))
        bm.faces.new((vi_b[i], vi_b[j], vo_b[j], vo_b[i]))
        bm.faces.new((vo_b[i], vo_b[j], vo_t[j], vo_t[i]))
        bm.faces.new((vi_t[i], vi_t[j], vi_b[j], vi_b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # 只保留主体侧 x > LINK_X - 1
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(LINK_X - 1.0, 0, 0),
                           plane_no=(1, 0, 0), clear_inner=True, clear_outer=False)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat('M_Cloud_RoofRim'))
    c.objects.link(bpy.data.objects.new(name, me))


def small_canopies_and_lawns(holes, z0, z_roof, c):
    """小庭院（<150 m²）：屋顶上方架高遮阳顶棚（wx_03/wx_08/wx_31）；
    大庭院（≥150 m²）：底部绿色草坪 + 屋顶内沿挑檐（wx_26/wx_33）。"""
    bm_can = bmesh.new()
    bm_gr = bmesh.new()
    for h in holes:
        a = poly_area(h)
        if a < 150.0:
            # 略外扩 0.8 m 覆盖小庭院采光井上方，高出屋面 1.4 m
            r = offset_ring(h, 0.8)
            vs = [bm_can.verts.new((x, y, z_roof + 1.35)) for x, y in r]
            f = bm_can.faces.new(vs)
            res = bmesh.ops.extrude_face_region(bm_can, geom=[f])
            bmesh.ops.translate(bm_can, vec=(0, 0, 0.35),
                                verts=[v for v in res['geom'] if isinstance(v, bmesh.types.BMVert)])
        else:
            # 大庭院底部铺草坪（内收 1.5 m 留走道）
            r = offset_ring(h, -1.5)
            vs = [bm_gr.verts.new((x, y, z0 + 0.08)) for x, y in r]
            f = bm_gr.faces.new(vs)
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
    bmesh.ops.recalc_face_normals(bm_can, faces=bm_can.faces)
    me_c = bpy.data.meshes.new('Bldg_Dorm_Canopies'); bm_can.to_mesh(me_c); bm_can.free()
    me_c.materials.append(mat('M_Dorm_Canopy'))
    c.objects.link(bpy.data.objects.new('Bldg_Dorm_Canopies', me_c))

    bmesh.ops.triangulate(bm_gr, faces=bm_gr.faces[:])
    me_g = bpy.data.meshes.new('Bldg_Dorm_CourtGrass'); bm_gr.to_mesh(me_g); bm_gr.free()
    me_g.materials.append(mat('M_Turf'))
    c.objects.link(bpy.data.objects.new('Bldg_Dorm_CourtGrass', me_g))


exec(open(os.path.join(ROOT, 'blender', 'build', 'uvtools.py')).read())
TEX = os.path.join(ROOT, 'blender', 'textures')


def reload_image_mat(name, path, rough=0.6, metal=0.0, fallback=(0.8, 0.8, 0.8, 1)):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
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
        # 保留现有材质（0 = 屋面/墙，可能 1 = 连接体屋面），附加 win / gal
        win_idx = len(o.data.materials); o.data.materials.append(win)
        gal_idx = len(o.data.materials); o.data.materials.append(gal)

        bm = bmesh.new(); bm.from_mesh(o.data)
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
        bm.to_mesh(o.data); bm.free()


def main():
    c = bpy.data.collections[COLL]
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sh = D['shell'][0]; L = D['levels']
    z0 = L['ground']
    z_body = z0 + L['floors'] * L['floor_h'] + 0.4    # 女儿墙顶 ≈ Z 18.2 m
    zb = SITE['campus_base_z']

    prism('Bldg_Dorm_Base', sh['outer'], [], zb, z0, 'M_Paving', c)
    prism('Bldg_Dorm_Mass', sh['outer'], sh['holes'], z0, z_body, 'M_Dorm_Roof', c, keep=('x>', LINK_X))
    # 西北连接体：深蓝灰金属坡屋面，由东侧 x=100 的 Z 13.8 缓坡降至西侧 x=80 的 Z 7.5（wx_03/08/11/31）
    link_roof_z = lambda x, y: 7.5 + max(0.0, min(1.0, (x - 80.0) / 20.0)) * 6.3
    prism('Bldg_Dorm_Link', sh['outer'], sh['holes'], z0, link_roof_z, 'M_Cloud_Core', c,
          keep=('x<', LINK_X), top_mat='M_Cloud_RoofPanel')
    facades(c, z0)
    # 屋顶外沿悬挑钢构架（底 Z 18.6，顶 Z 19.0，外挑 2.2 m，wx_03/08/27/31/34）
    roof_canopy_band('Bldg_Dorm_Pergola', sh['outer'], 2.2, 2.5, z_body + 0.4, z_body + 0.85, c)
    small_canopies_and_lawns(sh['holes'], z0, z_body, c)
    bpy.ops.wm.save_mainfile()
    print([(o.name, len(o.data.vertices), [round(v, 1) for v in o.dimensions]) for o in c.objects])


main()
