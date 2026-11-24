"""T2 体育及艺术中心室内精建（独立 Interior_Sports 集合，按需分包导出 web/public/interior_sports.glb）：
1. 双室内篮球馆（official_04.jpg）：原木主球场 + 浅蓝训练场、大跨度灰色空间钢网架屋顶、24 盏高棚 LED 灯、4 套蓝色室内玻璃篮架、可伸缩看台
2. 50 m 室内恒温游泳馆（official_11.jpg）：50×21 m 8 泳道池体、瓷砖泳道底线、半透明碧蓝水面、7 条浮标泳道线、16 座出发台、侧向观赛看台与吸音吊顶
3. 艺术中心大剧场（official_27.jpg）：12 排阶梯坡地 + 216 张实例化暗红绒面礼堂座椅、原木吸音条纹侧墙、深木色舞台与讲台、三联发光大屏、舞台面光灯桥
4. 首层公共大厅（衔接三大场馆与西南柱廊主入口）

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/interior_sports.py').read())
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

ROOT = '/Users/perrylei/repos/BDFZ_V3'
TEX = os.path.join(ROOT, 'blender', 'textures')
COLL = 'Interior_Sports'


def ensure_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


def atlas_mat():
    """统一室内色板材质（16 色格，所有墙体/家具/座椅/钢网架共用，极致省 draw call）。"""
    m = bpy.data.materials.get('M_Int_Atlas')
    if m is None:
        m = bpy.data.materials.new('M_Int_Atlas')
        m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(TEX, 'interior_atlas.png'), check_existing=True)
    img.reload(); tex.image = img; tex.interpolation = 'Closest'
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.72
    m.diffuse_color = (0.8, 0.78, 0.74, 1)
    return m


def emissive_mat(name, col, strength=2.2):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    b.inputs['Base Color'].default_value = col
    b.inputs['Roughness'].default_value = 0.2
    if 'Emission Color' in b.inputs:
        b.inputs['Emission Color'].default_value = col
        b.inputs['Emission Strength'].default_value = strength
    m.diffuse_color = col
    return m


def img_mat(name, fname, rough=0.35, metal=0.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(TEX, fname), check_existing=True)
    img.reload(); tex.image = img
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def water_mat():
    m = bpy.data.materials.get('M_Int_PoolWater')
    if m is None:
        m = bpy.data.materials.new('M_Int_PoolWater')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    b.inputs['Base Color'].default_value = (0.12, 0.68, 0.86, 1.0)
    b.inputs['Roughness'].default_value = 0.05
    b.inputs['Metallic'].default_value = 0.08
    b.inputs['Alpha'].default_value = 0.56
    wn_path = os.path.join(TEX, 'pool_water_normal.png')
    if os.path.exists(wn_path):
        tn = nt.nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load(wn_path, check_existing=True); img.reload()
        img.colorspace_settings.name = 'Non-Color'
        tn.image = img
        nmap = nt.nodes.new('ShaderNodeNormalMap')
        nmap.inputs['Strength'].default_value = 0.42
        nt.links.new(tn.outputs['Color'], nmap.inputs['Color'])
        nt.links.new(nmap.outputs['Normal'], b.inputs['Normal'])
    if hasattr(m, 'blend_method'):
        m.blend_method = 'BLEND'
    m.diffuse_color = (0.12, 0.68, 0.86, 0.56)
    return m


def add_uv_box(bm, uvl, sw, p0, p1, mat_idx=0):
    """在局部空间添加盒子并赋色板 UV (sw in 0..15)。"""
    u = (sw + 0.5) / 16.0
    x0, y0, z0 = p0; x1, y1, z1 = p1
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
        for lp in f.loops:
            lp[uvl].uv = (u, 0.5)


def add_uv_cyl(bm, uvl, sw, a, b, r, seg=6, mat_idx=0):
    va, vb = Vector(a), Vector(b)
    d = vb - va; L = d.length
    if L < 1e-4:
        return
    u = (sw + 0.5) / 16.0
    M = Matrix.Translation((va + vb) * 0.5) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=L, matrix=M)
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = mat_idx
            for lp in f.loops:
                lp[uvl].uv = (u, 0.5)


def link_local(name, bm, mats, cx, cy, z0, ang_deg, c):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    o.location = (cx, cy, z0)
    o.rotation_euler = (0.0, 0.0, math.radians(ang_deg))
    c.objects.link(o)
    return o


def local_to_world(cx, cy, z0, ang_deg, lx, ly, lz):
    a = math.radians(ang_deg); ca, sa = math.cos(a), math.sin(a)
    return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, z0 + lz)


def theater_seat_mesh():
    """暗红绒面礼堂座椅原型（面向 +Y，~120 三角面，全剧场 216 座仅 1 draw call）。"""
    old = bpy.data.meshes.get('Interior_TheaterSeatUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 金属支腿 (6), 暗红坐垫与靠背 (4), 扶手 (3)
    add_uv_box(bm, uvl, 6, (-0.24, -0.05, 0.0), (-0.20, 0.05, 0.42))
    add_uv_box(bm, uvl, 6, (0.20, -0.05, 0.0), (0.24, 0.05, 0.42))
    add_uv_box(bm, uvl, 4, (-0.23, -0.18, 0.39), (0.23, 0.24, 0.49))
    # 微仰角人体工学软包靠背 + 头枕收口
    add_uv_box(bm, uvl, 4, (-0.23, -0.20, 0.47), (0.23, -0.11, 0.74))
    add_uv_box(bm, uvl, 4, (-0.22, -0.24, 0.72), (0.22, -0.15, 0.98))
    add_uv_box(bm, uvl, 3, (-0.27, -0.16, 0.56), (-0.22, 0.22, 0.62))
    add_uv_box(bm, uvl, 3, (0.22, -0.16, 0.56), (0.27, 0.22, 0.62))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Interior_TheaterSeatUnit')
    bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    return me


def lamp_panel_mesh():
    """室内 LED 高棚/条形灯具原型（实例化）。"""
    old = bpy.data.meshes.get('Interior_LampUnit')
    if old:
        bpy.data.meshes.remove(old, do_unlink=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    add_uv_box(bm, uvl, 6, (-0.6, -0.25, 0.04), (0.6, 0.25, 0.14), 0)
    add_uv_box(bm, uvl, 14, (-0.54, -0.20, 0.0), (0.54, 0.20, 0.05), 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Interior_LampUnit')
    bm.to_mesh(me); bm.free()
    me.materials.append(atlas_mat())
    me.materials.append(emissive_mat('M_Int_LED', (1.0, 0.98, 0.92, 1.0), 22.0))
    return me


def build_basketball_hall(c, lamp_me):
    """1. 双室内篮球馆（official_04.jpg）：(-235.5, -73.0), 32×38 m, ang=19.7°, Z=-5.92..+7.5 m。"""
    cx, cy, z0, ang = -235.5, -73.0, -5.92, 19.7
    W, L, H = 32.0, 38.0, 12.5
    m_atl = atlas_mat()
    m_wood = img_mat('M_Int_GymWood', 'indoor_court_wood.png', rough=0.28)
    m_led = emissive_mat('M_Int_LED', (1.0, 0.98, 0.92, 1.0), 22.0)

    # 主结构（地坪 + 东西北墙，南端留宽门洞通大厅，西墙留高大采光窗，钢网架屋顶）
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 整体浅灰水磨石衬底地坪
    add_uv_box(bm, uvl, 1, (-W/2, -L/2, -0.15), (W/2, L/2, 0.0))
    # 东侧副球场（浅蓝塑胶地胶，official_04.jpg 左下）
    add_uv_box(bm, uvl, 9, (2.5, -14.0, 0.0), (14.5, 14.0, 0.02))
    # 东墙 & 北墙（浅暖灰吸音墙面，带立柱）
    add_uv_box(bm, uvl, 0, (W/2 - 0.3, -L/2, 0.0), (W/2, L/2, H))
    add_uv_box(bm, uvl, 0, (-W/2, L/2 - 0.3, 0.0), (W/2, L/2, H))
    # 西墙矮窗台（上部透明落地玻璃直接借用外部幕墙透光！）
    add_uv_box(bm, uvl, 0, (-W/2, -L/2, 0.0), (-W/2 + 0.3, L/2, 1.4))
    # 南侧隔墙（中段留宽 10 m × 高 4.5 m 大门洞连通游泳馆与主大厅）
    add_uv_box(bm, uvl, 0, (-W/2, -L/2, 0.0), (-5.0, -L/2 + 0.35, H))
    add_uv_box(bm, uvl, 0, (5.0, -L/2, 0.0), (W/2, -L/2 + 0.35, H))
    add_uv_box(bm, uvl, 0, (-5.0, -L/2, 4.5), (5.0, -L/2 + 0.35, H))
    # 东侧可伸缩暗红看台（official_04.jpg 右下背景）
    for k in range(5):
        add_uv_box(bm, uvl, 4, (W/2 - 0.4 - (5 - k) * 0.62, -11.0, k * 0.42),
                   (W/2 - 0.4 - (4 - k) * 0.62, 11.0, (k + 1) * 0.42))
    # 大跨度空间钢网架屋顶（6 榀主桁架 + 纵向檩条，official_04.jpg 最显著建筑特征！）
    for yi in range(-16, 18, 6):
        add_uv_box(bm, uvl, 6, (-W/2 + 0.2, yi - 0.14, H - 1.5), (W/2 - 0.2, yi + 0.14, H - 1.25))
        add_uv_box(bm, uvl, 6, (-W/2 + 0.2, yi - 0.14, H - 0.25), (W/2 - 0.2, yi + 0.14, H))
        for xi in range(-14, 15, 4):
            add_uv_cyl(bm, uvl, 6, (xi, yi, H - 1.4), (xi + 2.0, yi, H - 0.12), 0.06, 5)
            add_uv_cyl(bm, uvl, 6, (xi + 2.0, yi, H - 0.12), (xi + 4.0, yi, H - 1.4), 0.06, 5)
    for xi in range(-14, 15, 5):
        add_uv_box(bm, uvl, 6, (xi - 0.1, -L/2 + 0.3, H - 1.45), (xi + 0.1, L/2 - 0.3, H - 1.28))
    # 暗灰屋面底衬板
    add_uv_box(bm, uvl, 6, (-W/2, -L/2, H), (W/2, L/2, H + 0.25))
    link_local('Int_Sports_GymShell', bm, [m_atl], cx, cy, z0, ang, c)

    # 西侧原木主篮球场（精确 UV 贴图 indoor_court_wood.png，18×32 m）
    bm_c = bmesh.new(); uvl_c = bm_c.loops.layers.uv.new('UVMap')
    vs = [bm_c.verts.new(p) for p in ((-15.0, -16.0, 0.025), (2.2, -16.0, 0.025), (2.2, 16.0, 0.025), (-15.0, 16.0, 0.025))]
    fc = bm_c.faces.new(vs)
    for lp, uv in zip(fc.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        lp[uvl_c].uv = uv
    link_local('Int_Sports_GymWoodCourt', bm_c, [m_wood], cx, cy, z0, ang, c)

    # 室内篮球馆纯 3D 矢量锐利球场白线（主原木场 15×28 m + 东侧副场 11×24 m）
    bm_gl = bmesh.new()
    def _seg(a0, a1, w, z):
        dx, dy = a1[0] - a0[0], a1[1] - a0[1]
        L_ = math.hypot(dx, dy)
        if L_ < 1e-4: return
        nx, ny = -dy / L_ * (w * 0.5), dx / L_ * (w * 0.5)
        bm_gl.faces.new([bm_gl.verts.new((a0[0]+nx, a0[1]+ny, z)), bm_gl.verts.new((a0[0]-nx, a0[1]-ny, z)),
                         bm_gl.verts.new((a1[0]-nx, a1[1]-ny, z)), bm_gl.verts.new((a1[0]+nx, a1[1]+ny, z))])
    def _rect(x0, y0, x1, y1, w, z):
        _seg((x0, y0), (x1, y0), w, z); _seg((x1, y0), (x1, y1), w, z)
        _seg((x1, y1), (x0, y1), w, z); _seg((x0, y1), (x0, y0), w, z)
    def _arc(ox, oy, r, a0, a1, w, z, segs=32):
        ri, ro = r - w * 0.5, r + w * 0.5
        vi = [bm_gl.verts.new((ox + ri * math.cos(a0 + (a1-a0)*i/segs), oy + ri * math.sin(a0 + (a1-a0)*i/segs), z)) for i in range(segs+1)]
        vo = [bm_gl.verts.new((ox + ro * math.cos(a0 + (a1-a0)*i/segs), oy + ro * math.sin(a0 + (a1-a0)*i/segs), z)) for i in range(segs+1)]
        for i in range(segs):
            bm_gl.faces.new((vo[i], vo[i+1], vi[i+1], vi[i]))
    # 主原木球场中心 (-6.4, 0.0), 宽 15 m × 长 28 m
    mcx, cw, cl, zlw, lw = -6.4, 15.0, 28.0, 0.036, 0.07
    _rect(mcx - cw/2, -cl/2, mcx + cw/2, cl/2, lw, zlw)
    _seg((mcx - cw/2, 0.0), (mcx + cw/2, 0.0), lw, zlw)
    _arc(mcx, 0.0, 1.8, 0.0, 2*math.pi, lw, zlw, 36)
    ang3 = math.asin(6.6 / 6.75)
    dy3 = math.sqrt(6.75**2 - 6.6**2)
    for sgn in (1.0, -1.0):
        bl = sgn * cl / 2.0; yft = bl - sgn * 5.8; yh = bl - sgn * 1.575
        _rect(mcx - 2.45, min(bl, yft), mcx + 2.45, max(bl, yft), lw, zlw)
        _arc(mcx, yft, 1.8, 0.0, 2*math.pi, lw, zlw, 28)
        yj = yh - sgn * dy3
        _seg((mcx - 6.6, bl), (mcx - 6.6, yj), lw, zlw)
        _seg((mcx + 6.6, bl), (mcx + 6.6, yj), lw, zlw)
        if sgn > 0:
            _arc(mcx, yh, 6.75, -math.pi/2 - ang3, -math.pi/2 + ang3, lw, zlw, 32)
        else:
            _arc(mcx, yh, 6.75, math.pi/2 - ang3, math.pi/2 + ang3, lw, zlw, 32)
    # 东侧蓝色训练场中心 (8.5, 0.0), 宽 11 m × 长 26 m
    _rect(3.0, -13.0, 14.0, 13.0, 0.065, 0.032)
    _seg((3.0, 0.0), (14.0, 0.0), 0.065, 0.032)
    _arc(8.5, 0.0, 1.5, 0.0, 2*math.pi, 0.065, 0.032, 28)
    m_wl = bpy.data.materials.get('M_LineWhite') or m_atl
    link_local('Int_Sports_GymLines', bm_gl, [m_wl], cx, cy, z0, ang, c)

    # 4 套室内篮球架（复用已实例化 Site_BasketHoopUnit！）
    hoop_me = bpy.data.meshes.get('Site_BasketHoopUnit')
    if hoop_me:
        for idx, (lx, ly, rdeg) in enumerate((
            (-6.4, -14.8, 0.0), (-6.4, 14.8, 180.0),
            (8.5, -13.5, 0.0), (8.5, 13.5, 180.0),
        )):
            ho = bpy.data.objects.new(f'Int_Sports_GymHoop_{idx}', hoop_me)
            ho.location = local_to_world(cx, cy, z0, ang, lx, ly, 0.02)
            ho.rotation_euler = (0.0, 0.0, math.radians(ang + rdeg))
            c.objects.link(ho)

    # 20 盏高棚 LED 灯具（实例化）
    idx = 0
    for xi in (-10.0, -3.5, 3.5, 10.0):
        for yi in (-14.0, -7.0, 0.0, 7.0, 14.0):
            lo = bpy.data.objects.new(f'Int_Sports_GymLamp_{idx:02d}', lamp_me)
            lo.location = local_to_world(cx, cy, z0, ang, xi, yi, H - 1.55)
            lo.rotation_euler = (0.0, 0.0, math.radians(ang))
            c.objects.link(lo); idx += 1


def build_swimming_pool(c, lamp_me):
    """2. 50 m 室内恒温游泳馆（official_11.jpg）：(-214.0, -133.0), 27×56 m, ang=19.7°, Z=-5.92..+5.8 m。"""
    cx, cy, z0, ang = -214.0, -133.0, -5.65, 19.7
    W, L, H = 27.0, 56.0, 11.2
    pw, pl = 20.0, 48.0  # 8 泳道标准池体净尺寸
    m_atl = atlas_mat()
    m_pool = img_mat('M_Int_PoolTile', 'pool_tile.png', rough=0.25)
    m_wat = water_mat()

    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 泳池四周宽敞防滑步道甲板（围合 20×48 m 池口）
    add_uv_box(bm, uvl, 1, (-W/2, -L/2, -0.2), (-pw/2, L/2, 0.0))      # 西甲板
    add_uv_box(bm, uvl, 1, (pw/2, -L/2, -0.2), (W/2, L/2, 0.0))        # 东甲板
    add_uv_box(bm, uvl, 1, (-pw/2, -L/2, -0.2), (pw/2, -pl/2, 0.0))    # 南甲板
    add_uv_box(bm, uvl, 1, (-pw/2, pl/2, -0.2), (pw/2, L/2, 0.0))      # 北甲板
    # 池壁（浅蓝池砖感，下沉 1.7 m）
    add_uv_box(bm, uvl, 9, (-pw/2 - 0.15, -pl/2, -0.32), (-pw/2, pl/2, 0.0))
    add_uv_box(bm, uvl, 9, (pw/2, -pl/2, -0.32), (pw/2 + 0.15, pl/2, 0.0))
    add_uv_box(bm, uvl, 9, (-pw/2, -pl/2 - 0.15, -0.32), (pw/2, -pl/2, 0.0))
    add_uv_box(bm, uvl, 9, (-pw/2, pl/2, -0.32), (pw/2, pl/2 + 0.15, 0.0))
    # 东墙（白墙 + 4 级观赛台阶，official_11.jpg 背景特征）
    add_uv_box(bm, uvl, 0, (W/2 - 0.3, -L/2, 0.0), (W/2, L/2, H))
    for k in range(3):
        add_uv_box(bm, uvl, 11, (W/2 - 0.35 - (3 - k) * 0.55, -20.0, k * 0.42),
                   (W/2 - 0.35 - (2 - k) * 0.55, 20.0, (k + 1) * 0.42))
    # 南/北墙（南北端各留 8 m 宽敞门洞连通大厅与篮球馆）
    for sy in (-L/2, L/2 - 0.3):
        add_uv_box(bm, uvl, 0, (-W/2, sy, 0.0), (-4.0, sy + 0.3, H))
        add_uv_box(bm, uvl, 0, (4.0, sy, 0.0), (W/2, sy + 0.3, H))
        add_uv_box(bm, uvl, 0, (-4.0, sy, 4.2), (4.0, sy + 0.3, H))
    # 白色冲孔吸音吊顶（带横向肋梁）
    add_uv_box(bm, uvl, 0, (-W/2, -L/2, H), (W/2, L/2, H + 0.3))
    for yi in range(-24, 25, 8):
        add_uv_box(bm, uvl, 15, (-W/2, yi - 0.25, H - 0.45), (W/2, yi + 0.25, H))
    # 7 条浮标分道线（红/蓝/白交替）+ 两端 16 座出发台
    lane_w = pw / 8.0
    for i in range(1, 8):
        lx = -pw/2 + i * lane_w
        add_uv_cyl(bm, uvl, 5 if i % 2 == 0 else 4, (lx, -pl/2 + 0.2, -0.07), (lx, pl/2 - 0.2, -0.07), 0.06, 6)
    for i in range(8):
        lx = -pw/2 + (i + 0.5) * lane_w
        for sy in (-pl/2 - 0.45, pl/2 + 0.45):
            add_uv_box(bm, uvl, 15, (lx - 0.26, sy - 0.26, 0.0), (lx + 0.26, sy + 0.26, 0.52))
            add_uv_box(bm, uvl, 5, (lx - 0.28, sy - 0.28, 0.52), (lx + 0.28, sy + 0.28, 0.62))
    link_local('Int_Sports_PoolShell', bm, [m_atl], cx, cy, z0, ang, c)

    # 泳池 8 泳道瓷砖池底
    bm_f = bmesh.new(); uvl_f = bm_f.loops.layers.uv.new('UVMap')
    vs = [bm_f.verts.new(p) for p in ((-pw/2, -pl/2, -0.27), (pw/2, -pl/2, -0.27), (pw/2, pl/2, -0.27), (-pw/2, pl/2, -0.27))]
    ff = bm_f.faces.new(vs)
    for lp, uv in zip(ff.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        lp[uvl_f].uv = uv
    link_local('Int_Sports_PoolFloor', bm_f, [m_pool], cx, cy, z0, ang, c)

    # 半透明碧蓝泳池水面（平铺水波法线 UV 10x24，呈现真实涟漪高光）
    bm_w = bmesh.new(); uvl_w = bm_w.loops.layers.uv.new('UVMap')
    fw = bm_w.faces.new([bm_w.verts.new(p) for p in ((-pw/2, -pl/2, -0.10), (pw/2, -pl/2, -0.10), (pw/2, pl/2, -0.10), (-pw/2, pl/2, -0.10))])
    for lp, uv in zip(fw.loops, [(0, 0), (10, 0), (10, 24), (0, 24)]):
        lp[uvl_w].uv = uv
    link_local('Int_Sports_PoolWater', bm_w, [m_wat], cx, cy, z0, ang, c)

    # 18 盏泳池顶灯（实例化）
    idx = 0
    for xi in (-7.5, 0.0, 7.5):
        for yi in (-20.0, -12.0, -4.0, 4.0, 12.0, 20.0):
            lo = bpy.data.objects.new(f'Int_Sports_PoolLamp_{idx:02d}', lamp_me)
            lo.location = local_to_world(cx, cy, z0, ang, xi, yi, H - 0.52)
            lo.rotation_euler = (0.0, 0.0, math.radians(ang))
            c.objects.link(lo); idx += 1


def build_auditorium(c, seat_me, lamp_me):
    """3. 艺术中心大剧场（official_27.jpg）：(-131.0, -138.0), 22×34 m, ang=33.5°, 舞台在 -Y(东南), 阶梯观众席在 +Y(西北)。"""
    cx, cy, z0, ang = -131.0, -138.0, -5.92, 33.5
    W, L, H = 22.0, 34.0, 9.6
    m_atl = atlas_mat()
    m_scr = emissive_mat('M_Int_StageScreen', (0.86, 0.92, 0.98, 1.0), 1.6)

    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 基础地坪与舞台前区
    add_uv_box(bm, uvl, 3, (-W/2, -L/2, -0.15), (W/2, L/2, 0.0))
    # 深胡桃木抬高主舞台（位于 y in [-16.5, -8.5], 高 1.0 m，official_27.jpg）
    add_uv_box(bm, uvl, 3, (-9.5, -16.5, 0.0), (9.5, -8.5, 1.0))
    # 舞台前三级台阶 + 演讲台
    for k in range(3):
        add_uv_box(bm, uvl, 3, (-6.5, -8.5, 0.0), (6.5, -8.5 + (3 - k) * 0.45, (k + 1) * 0.33))
    add_uv_box(bm, uvl, 4, (-3.6, -10.2, 1.0), (-2.6, -9.4, 2.15))  # 红色演讲台
    # 舞台黑色深背景幕墙 + 顶部舞台黑框
    add_uv_box(bm, uvl, 6, (-W/2, -L/2, 0.0), (W/2, -L/2 + 0.5, H))
    add_uv_box(bm, uvl, 6, (-W/2, -9.2, 6.2), (W/2, -8.7, H))
    # 东西两侧暖木吸音条纹墙 + 后墙（留入场门洞）
    add_uv_box(bm, uvl, 2, (-W/2, -L/2, 0.0), (-W/2 + 0.4, L/2, H))
    add_uv_box(bm, uvl, 2, (W/2 - 0.4, -L/2, 0.0), (W/2, L/2, H))
    add_uv_box(bm, uvl, 2, (-W/2, L/2 - 0.4, 0.0), (-4.0, L/2, H))
    add_uv_box(bm, uvl, 2, (4.0, L/2 - 0.4, 0.0), (W/2, L/2, H))
    add_uv_box(bm, uvl, 2, (-4.0, L/2 - 0.4, 4.2), (4.0, L/2, H))
    # 黑色剧场吊顶 + 2 道舞台面光灯桥
    add_uv_box(bm, uvl, 6, (-W/2, -L/2, H), (W/2, L/2, H + 0.3))
    for ly in (-5.0, 2.0, 9.0):
        add_uv_box(bm, uvl, 6, (-9.8, ly - 0.25, H - 0.9), (9.8, ly + 0.25, H - 0.5))

    # 12 级阶梯观众席台地（y = -5.5 → +14.5，Z 从 0.15 线性升至 3.85 m）
    rows = 12
    for r in range(rows):
        y0 = -5.5 + r * 1.55
        y1 = y0 + 1.55
        zt = 0.15 + r * 0.32
        add_uv_box(bm, uvl, 1, (-W/2 + 0.4, y0, 0.0), (W/2 - 0.4, y1, zt))
    link_local('Int_Sports_TheaterShell', bm, [m_atl], cx, cy, z0, ang, c)

    # 三联发光屏幕：主舞台 LED 大屏 + 左右副投影幕（official_27.jpg 标志特征）
    bm_sc = bmesh.new(); uvl_sc = bm_sc.loops.layers.uv.new('UVMap')
    add_uv_box(bm_sc, uvl_sc, 8, (-5.4, -15.8, 1.5), (5.4, -15.65, 5.8))      # 主屏
    add_uv_box(bm_sc, uvl_sc, 8, (-10.2, -9.8, 3.0), (-7.2, -9.65, 5.2))      # 左副屏
    add_uv_box(bm_sc, uvl_sc, 8, (7.2, -9.8, 3.0), (10.2, -9.65, 5.2))        # 右副屏
    link_local('Int_Sports_TheaterScreens', bm_sc, [m_scr], cx, cy, z0, ang, c)

    # 216 张实例化暗红绒面礼堂座椅（12 排 × 18 座，中间留 2 条通道，面向舞台 -Y）
    idx = 0
    for r in range(rows):
        ly = -4.7 + r * 1.55
        lz = 0.15 + r * 0.32
        for c_i in range(-9, 10):
            if c_i in (-4, 4):  # 两条观众过道
                continue
            lx = c_i * 0.88
            so = bpy.data.objects.new(f'Int_Sports_Seat_{idx:03d}', seat_me)
            so.location = local_to_world(cx, cy, z0, ang, lx, ly, lz)
            so.rotation_euler = (0.0, 0.0, math.radians(ang + 180.0))  # 面向 -Y 舞台
            c.objects.link(so); idx += 1

    # 12 盏剧场顶灯
    l_idx = 0
    for xi in (-6.0, 0.0, 6.0):
        for yi in (-5.0, 2.0, 9.0, 14.0):
            lo = bpy.data.objects.new(f'Int_Sports_TheaterLamp_{l_idx:02d}', lamp_me)
            lo.location = local_to_world(cx, cy, z0, ang, xi, yi, H - 0.95)
            lo.rotation_euler = (0.0, 0.0, math.radians(ang))
            c.objects.link(lo); l_idx += 1


def build_foyer(c, lamp_me):
    """4. 首层公共入口门厅（(-180.0, -154.0), 34×24 m, Z=-5.92..+5.5 m）：无缝串联西南柱廊、泳池、篮球馆与大剧场。"""
    cx, cy, z0 = -180.0, -154.0, -5.92
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    # 明亮水磨石大厅地板 + 浅色吊顶
    add_uv_box(bm, uvl, 1, (-18.0, -15.0, -0.15), (22.0, 14.0, 0.0))
    add_uv_box(bm, uvl, 0, (-18.0, -15.0, 6.2), (22.0, 14.0, 6.5))
    # 接待服务台 + 休闲木长椅
    add_uv_box(bm, uvl, 2, (-4.0, 2.0, 0.0), (4.0, 3.2, 1.05))
    add_uv_box(bm, uvl, 0, (-3.8, 1.9, 1.05), (3.8, 3.3, 1.12))
    for bx in (-10.0, 10.0):
        add_uv_box(bm, uvl, 2, (bx - 2.0, -4.0, 0.0), (bx + 2.0, -3.2, 0.45))
    link_local('Int_Sports_Foyer', bm, [atlas_mat()], cx, cy, z0, 0.0, c)

    idx = 0
    for xi in (-10.0, 0.0, 10.0):
        for yi in (-6.0, 4.0):
            lo = bpy.data.objects.new(f'Int_Sports_FoyerLamp_{idx:02d}', lamp_me)
            lo.location = (cx + xi, cy + yi, z0 + 6.1)
            c.objects.link(lo); idx += 1


def main():
    c = ensure_coll(COLL)
    seat_me = theater_seat_mesh()
    lamp_me = lamp_panel_mesh()
    build_basketball_hall(c, lamp_me)
    build_swimming_pool(c, lamp_me)
    build_auditorium(c, seat_me, lamp_me)
    build_foyer(c, lamp_me)
    bpy.ops.wm.save_mainfile()
    print('Interior_Sports objects:', len(c.objects))


main()
