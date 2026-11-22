"""P5–P8 景观：
- 4 类低模实例化热带树种（棕榈/蒲葵、分层伞形阔叶树、团簇多球冠大乔木，全走 GPU Instancing）
- 严格排除 4 片球场/看台拐角/星形庭院内部/北广场中轴的误种树，并在星形庭院与宿舍大庭院花池精准配植实景乔木与蒲葵
- 北入口标志性校名景石（“北京大学附属中学海口学校”）+ 折线台地绿化花坛 + 落客广场圆形铺装 + 门房与大台阶
- 海口低纬度日光与天空
在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/landscape.py').read())
"""
import bpy, bmesh, json, os, math, random
from mathutils import Matrix, Vector

ROOT = '/Users/perrylei/repos/BDFZ_V3'
TR = json.load(open(os.path.join(ROOT, 'data', 'trees.json')))
SITE = json.load(open(os.path.join(ROOT, 'data', 'site.json')))
CY = json.load(open(os.path.join(ROOT, 'data', 'cloud_courtyard.json')))
DORM = json.load(open(os.path.join(ROOT, 'data', 'bldg_dorm.json')))
X0, Y0, X1, Y1 = TR['extent']
COLL = 'Landscape'
# 不再将模糊的 landcover.png 强贴到北入口台阶广场，保持广场铺装洁净
TOP_SURFACES = ['Site_Campus', 'Site_Zone_操场平台周边', 'Bldg_Cloud_Podium', 'Bldg_Dorm_Base']


def simple_mat(name, col, rough=0.7, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = col
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = col
    return m


def img_mat(name, fname, rough=0.80, metal=0.0, fallback=(0.55, 0.55, 0.54, 1)):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
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


def landcover_mat():
    m = bpy.data.materials.get('M_Landcover')
    if m is None:
        m = bpy.data.materials.new('M_Landcover')
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes.get('Principled BSDF')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(os.path.join(ROOT, 'blender', 'textures', 'landcover.png'), check_existing=True)
        t.extension = 'EXTEND'
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.92
        m.diffuse_color = (0.45, 0.5, 0.4, 1)
    return m


def apply_landcover():
    lm = landcover_mat()
    for n in TOP_SURFACES:
        o = bpy.data.objects.get(n)
        if o is None:
            continue
        me = o.data
        if lm.name not in me.materials:
            me.materials.append(lm)
        slot = list(me.materials).index(me.materials[lm.name])
        bm = bmesh.new()
        bm.from_mesh(me)
        uvl = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            if f.normal.z > 0.5:
                f.material_index = slot
                for lp in f.loops:
                    lp[uvl].uv = ((lp.vert.co.x - X0) / (X1 - X0), (lp.vert.co.y - Y0) / (Y1 - Y0))
        bm.to_mesh(me)
        bm.free()


def make_tree_meshes():
    """构建 3 类热带校园低模实例化树种网格（全场景共仅占 3 次 GPU Instancing 绘制）：
    1. Landscape_PalmUnit: 热带棕榈/王棕/蒲葵（细高树干 + 10 片弯折放射羽叶）
    2. Landscape_BroadleafUnit: 分层伞形阔叶树（小叶榄仁/凤凰木风格，多枝干 + 3 层自然扁伞冠）
    3. Landscape_CanopyUnit: 团簇多叶团乔木（自然起伏 4 簇树冠，替代生硬单蛋球）
    """
    m_trunk = simple_mat('M_TreeTrunk', (0.30, 0.22, 0.16, 1), rough=0.90)
    m_crown = simple_mat('M_TreeCrown', (0.13, 0.31, 0.10, 1), rough=0.86)
    m_palm = simple_mat('M_PalmCrown', (0.19, 0.41, 0.12, 1), rough=0.80)

    def reset_mesh(name):
        old = bpy.data.meshes.get(name)
        if old:
            bpy.data.meshes.remove(old, do_unlink=True)

    # --- 1. 热带棕榈/蒲葵 (单位高度 Z=0..1，水平半径 ~0.95) ---
    reset_mesh('Landscape_PalmUnit')
    bm = bmesh.new()
    # 微微收尖的细长树干 (Z = 0 .. 0.82)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=0.065, radius2=0.038, depth=0.82,
                          matrix=Matrix.Translation((0, 0, 0.41)))
    trunk_f = set(bm.faces[:])
    for f in trunk_f:
        f.material_index = 0
        f.smooth = True
    # 10 片两层放射状弧形棕榈叶（上层 4 片微扬，下层 6 片舒展微垂）
    fronds = [(6, 0.80, 0.92, -0.14, 0.0), (4, 0.85, 0.68, 0.16, 0.52)]
    for count, zc, rlen, tip_dz, phase in fronds:
        for i in range(count):
            ang = 2 * math.pi * i / count + phase
            ca, sa = math.cos(ang), math.sin(ang)
            tx, ty = -sa, ca
            w1, w2 = 0.24, 0.18
            p0 = Vector((0, 0, zc))
            p1 = Vector((ca * rlen * 0.45, sa * rlen * 0.45, zc + 0.10 + tip_dz * 0.2))
            p2 = Vector((ca * rlen, sa * rlen, zc + tip_dz))
            v0 = bm.verts.new(p0)
            v1l = bm.verts.new(p1 + Vector((tx * w1, ty * w1, -0.02)))
            v1r = bm.verts.new(p1 - Vector((tx * w1, ty * w1, -0.02)))
            v1c = bm.verts.new(p1 + Vector((0, 0, 0.03)))
            v2 = bm.verts.new(p2)
            for tri in ((v0, v1l, v1c), (v0, v1c, v1r), (v1l, v2, v1c), (v1c, v2, v1r)):
                f = bm.faces.new(tri)
                f.material_index = 1
                f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me_palm = bpy.data.meshes.new('Landscape_PalmUnit')
    bm.to_mesh(me_palm)
    bm.free()
    me_palm.materials.append(m_trunk)
    me_palm.materials.append(m_palm)

    # --- 2. 分层伞形阔叶树 (单位半径 ~1.0，单位高度 ~1.0) ---
    reset_mesh('Landscape_BroadleafUnit')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.08, radius2=0.045, depth=0.55,
                          matrix=Matrix.Translation((0, 0, 0.275)))
    trunk_f = set(bm.faces[:])
    for f in trunk_f:
        f.material_index = 0
    # 3 个错落扁平伞状叶层（小叶榄仁/凤凰木风格）
    tiers = [
        (0.0, 0.0, 0.58, 0.92, 0.22),
        (0.22, -0.18, 0.74, 0.72, 0.20),
        (-0.18, 0.20, 0.84, 0.62, 0.19),
    ]
    for cx, cy, cz, rx, rz in tiers:
        r = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in r['verts']:
            k = 1.0 + 0.12 * math.sin(v.co.x * 3.7 + v.co.y * 2.9)
            v.co.x = cx + v.co.x * rx * k
            v.co.y = cy + v.co.y * rx * k
            v.co.z = cz + v.co.z * rz
    for f in bm.faces:
        if f not in trunk_f:
            f.material_index = 1
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me_broad = bpy.data.meshes.new('Landscape_BroadleafUnit')
    bm.to_mesh(me_broad)
    bm.free()
    me_broad.materials.append(m_trunk)
    me_broad.materials.append(m_crown)

    # --- 3. 团簇多球冠大乔木 ---
    reset_mesh('Landscape_CanopyUnit')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.09, radius2=0.055, depth=0.52,
                          matrix=Matrix.Translation((0, 0, 0.26)))
    trunk_f = set(bm.faces[:])
    for f in trunk_f:
        f.material_index = 0
    lobes = [
        (0.0, 0.0, 0.78, 0.72, 0.36),
        (0.42, 0.18, 0.64, 0.56, 0.30),
        (-0.38, 0.25, 0.68, 0.54, 0.30),
        (0.05, -0.40, 0.62, 0.55, 0.29),
    ]
    for cx, cy, cz, rx, rz in lobes:
        r = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for v in r['verts']:
            k = 1.0 + 0.10 * math.sin(v.co.x * 3.1 - v.co.y * 2.5)
            v.co.x = cx + v.co.x * rx * k
            v.co.y = cy + v.co.y * rx * k
            v.co.z = cz + v.co.z * rz
    for f in bm.faces:
        if f not in trunk_f:
            f.material_index = 1
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me_can = bpy.data.meshes.new('Landscape_CanopyUnit')
    bm.to_mesh(me_can)
    bm.free()
    me_can.materials.append(m_trunk)
    me_can.materials.append(m_crown)

    return me_palm, me_broad, me_can


def inside_any_court(x, y, margin=2.6):
    """检查 (x, y) 是否侵入任一篮球场、网球场或网球休憩亭（含外扩缓冲）。"""
    for k, v in SITE['courts'].items():
        cx, cy = v['center']
        a = math.radians(v['long_axis_deg_from_E'])
        L, W = v['size']
        pad = (3.5 if v['kind'] == 'tennis' else 2.0) + margin
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = x - cx, y - cy
        lx = dx * ca + dy * sa
        ly = -dx * sa + dy * ca
        # 网球场东侧 (-ly 方向) 额外保护 4.5 m 给休憩遮阳亭
        ly_min = -(W / 2 + pad + (4.5 if v['kind'] == 'tennis' else 0.0))
        ly_max = W / 2 + pad
        if abs(lx) <= L / 2 + pad and ly_min <= ly <= ly_max:
            return True
    return False


def inside_excluded_zone(x, y):
    # 1. 4 片球场与休憩亭
    if inside_any_court(x, y, margin=4.2):
        return True
    # 2. 体育中心看台与跑道过渡拐角（消除 renders/sports_art.jpg 中穿插看台的孤树）
    if -230.0 <= x <= -178.0 and -134.0 <= y <= -42.0:
        return True
    # 3. 体育中心西侧混凝土地坪（含室外篮架训练场）
    if -292.0 <= x <= -248.0 and -172.0 <= y <= -68.0:
        return True
    # 4. 星形庭院内部（改用 data/cloud_courtyard.json 精准配植，杜绝卫星错植）
    if -58.0 <= x <= 55.0 and -112.0 <= y <= -14.0:
        return True
    # 5. 北入口中轴校名石与主台阶视廊（保持正面视觉通透，wx_01/official_18）
    if -38.0 <= x <= 6.0 and 10.0 <= y <= 82.0:
        return True
    return False


def ground_z(x, y, dg, sc):
    ok, loc, n, i, ob, _ = sc.ray_cast(dg, Vector((x, y, 80)), Vector((0, 0, -1)))
    return (loc.z, ob.name) if ok else (-6.0, '')


def trees():
    c = bpy.data.collections[COLL]
    for o in [o for o in c.objects if o.name.startswith('Landscape_Tree') or o.name.startswith('Landscape_Palm')]:
        bpy.data.objects.remove(o, do_unlink=True)
    me_palm, me_broad, me_can = make_tree_meshes()
    random.seed(17)
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0

    def spawn(me, x, y, z, rx, h, prefix='Landscape_Tree'):
        nonlocal n
        o = bpy.data.objects.new(f'{prefix}_{n:04d}', me)
        o.location = (x, y, z)
        o.scale = (rx, rx, h)
        o.rotation_euler = (0, 0, random.uniform(0, 6.28))
        c.objects.link(o)
        n += 1

    # 1. 全园卫星检测树木（已过滤所有球场、看台拐角、星形庭院内部与北入口中轴）
    for x, y, r in TR['trees']:
        if inside_excluded_zone(x, y):
            continue
        z, hit = ground_z(x, y, dg, sc)
        if hit.startswith(('Bldg_Cloud_Slab', 'Bldg_Cloud_Roof', 'Bldg_Cloud_Court', 'Bldg_Cloud_Library',
                           'Bldg_Dorm_Mass', 'Bldg_Dorm_Pergola', 'Bldg_Dorm_Canopies', 'Bldg_Dorm_Court',
                           'Bldg_SportsArt', 'Site_Track', 'Site_Court', 'Site_Tennis', 'Landscape_NorthStep',
                           'Landscape_Gatehouse', 'Landscape_SchoolBoulder')):
            continue
        # 按校园实景分区分配热带树种：
        # 南大道/北大道/学术中心南广场优先种棕榈，中小型树用分层伞形阔叶树，大型防护树用多簇叶团乔木
        is_boulevard = (y < -176.0) or (82.0 <= y <= 116.0) or (-80.0 <= x <= 40.0 and -160.0 <= y <= -118.0)
        if is_boulevard and random.random() < 0.55:
            h = random.uniform(8.0, 11.5)
            spawn(me_palm, x, y, z, random.uniform(2.6, 3.6), h, 'Landscape_Palm')
        elif r < 3.4:
            if random.random() < 0.18:
                spawn(me_palm, x, y, z, random.uniform(2.4, 3.2), random.uniform(7.5, 10.5), 'Landscape_Palm')
            else:
                h = max(4.8, r * 2.4) * random.uniform(0.88, 1.12)
                spawn(me_broad, x, y, z, r * 1.08, h)
        else:
            h = max(6.0, r * 2.15) * random.uniform(0.88, 1.12)
            spawn(me_can, x, y, z, r * 1.05, h)

    # 2. 星形庭院照片精确定位乔木（data/cloud_courtyard.json：含 Z=0 花坛岛与 Z=4.5 图书馆露台）
    for x, y, r, z_base in CY.get('courtyard_trees', []):
        h = max(5.8, r * 2.5) * random.uniform(0.92, 1.08)
        spawn(me_broad, x, y, z_base + 0.14, r, h)

    # 3. 宿舍 4 座大庭院花池内的蒲葵棕榈（还原上传图 #1/#2 wx_33 & wx_26！）
    z_dorm = DORM['levels']['ground']
    def poly_area(ring):
        return abs(sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
                       for i in range(len(ring)))) * 0.5
    for h_ring in DORM['shell'][0]['holes']:
        if poly_area(h_ring) < 150.0:
            continue
        xs = [p[0] for p in h_ring]
        ys = [p[1] for p in h_ring]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        for dx in (-4.8, 4.8):
            for dy in (-4.2, 4.2):
                spawn(me_palm, cx + dx, cy + dy, z_dorm + 0.85, 2.3, random.uniform(6.2, 7.6), 'Landscape_Palm')

    return n


def sky():
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    sk = nt.nodes.new('ShaderNodeTexSky')
    try:
        sk.sky_type = 'NISHITA'
    except TypeError:
        pass
    for attr, v in (('sun_elevation', math.radians(40)), ('sun_rotation', math.radians(215)), ('altitude', 30.0)):
        if hasattr(sk, attr):
            setattr(sk, attr, v)
    if hasattr(sk, 'sun_disc'):
        sk.sun_disc = False
    bg.inputs['Strength'].default_value = 0.25
    nt.links.new(sk.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.objects.get('Sun')
    if sun is None:
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        bpy.data.collections[COLL].objects.link(sun)
    sun.data.energy = 3.5
    sun.data.angle = math.radians(0.6)
    sun.rotation_euler = (math.radians(50), 0, math.radians(215 - 90 + 180))
    sc.view_settings.exposure = 0.0
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    far = bpy.data.objects.get('Landscape_FarGround')
    if far is None:
        far = box('Landscape_FarGround', -4000, -4000, 4000, 4000, -6.6, -6.4, 'M_FarGround', bpy.data.collections[COLL])
        m = far.data.materials[0]
        m.use_nodes = True
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.20, 0.26, 0.15, 1)
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0
        m.diffuse_color = (0.20, 0.26, 0.15, 1)


def box(name, x0, y0, x1, y1, z0, z1, matname, c):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
    bm.faces.new(vs[0:4])
    bm.faces.new(vs[4:8])
    for i in range(4):
        bm.faces.new((vs[i], vs[(i + 1) % 4], vs[(i + 1) % 4 + 4], vs[i + 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    m = bpy.data.materials.get(matname) or bpy.data.materials.new(matname)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def gatehouse(name, x0, y0, x1, y1, z0, z1, c):
    m_gl = simple_mat('M_Cloud_Skylight', (0.12, 0.16, 0.20, 1), rough=0.12, metal=0.35)
    m_fa = simple_mat('M_Cloud_Slab', (0.22, 0.24, 0.27, 1), rough=0.45, metal=0.25)
    m_rf = simple_mat('M_Cloud_RoofRim', (0.76, 0.77, 0.76, 1), rough=0.80, metal=0.0)
    o1 = box(name, x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5, z0, z1 - 0.9, 'M_Cloud_Skylight', c)
    o2 = box(name + '_Roof', x0, y0, x1, y1, z1 - 0.9, z1, 'M_Cloud_Slab', c)
    o2.data.materials.append(m_rf)
    for p in o2.data.polygons:
        if p.normal.z > 0.7:
            p.material_index = 1
    return o1


def school_boulder(c):
    """北入口标志性校名景石（official_18.jpg、wx_01）：
    位于中轴线 (-16, 56, -6)，长 10.8 m × 高 2.7 m，正面面向 +Y（北侧入口），底座配规整修剪绿篱花坛。"""
    cx, cy, z0 = -16.0, 56.0, -6.0
    # 1. 花坛白石底座 + 规整绿篱
    box('Landscape_SchoolBoulder_Curb', cx - 6.6, cy - 1.7, cx + 6.6, cy + 1.7, z0, z0 + 0.25, 'M_Cloud_Core', c)
    box('Landscape_SchoolBoulder_Hedge', cx - 6.3, cy - 1.4, cx + 6.3, cy + 1.4, z0 + 0.25, z0 + 0.85, 'M_TreeCrown', c)

    # 2. 有机自然轮廓景石体块（顶缘起伏，正面映射“北京大学附属中学海口学校”）
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    # 沿 X 分 8 段，赋予自然山石顶轮廓
    xs = [-5.4, -4.4, -3.0, -1.2, 0.4, 2.2, 3.8, 4.9, 5.4]
    hs = [1.45, 2.15, 2.55, 2.85, 2.75, 2.65, 2.35, 1.90, 1.35]
    y_front, y_back = cy + 0.85, cy - 0.85
    vf_b = [bm.verts.new((cx + x, y_front, z0 + 0.55)) for x in xs]
    vf_t = [bm.verts.new((cx + x, y_front - 0.28, z0 + h)) for x, h in zip(xs, hs)]
    vb_b = [bm.verts.new((cx + x, y_back, z0 + 0.55)) for x in xs]
    vb_t = [bm.verts.new((cx + x, y_back + 0.28, z0 + h)) for x, h in zip(xs, hs)]
    n = len(xs)
    for i in range(n - 1):
        u0 = (xs[i] - xs[0]) / (xs[-1] - xs[0])
        u1 = (xs[i + 1] - xs[0]) / (xs[-1] - xs[0])
        # 北立面（正面 +Y，从北往南看时 +X 在左、-X 在右，因此 UV 镜像以保汉字正读！）
        f_front = bm.faces.new((vf_b[i + 1], vf_b[i], vf_t[i], vf_t[i + 1]))
        f_front.material_index = 0
        for lp, uv in zip(f_front.loops, [(1.0 - u1, 0.08), (1.0 - u0, 0.08), (1.0 - u0, 0.92), (1.0 - u1, 0.92)]):
            lp[uvl].uv = uv
        # 背面与顶面用通用石材/铺装色
        for quad in (
            (vb_b[i], vb_b[i + 1], vb_t[i + 1], vb_t[i]),
            (vf_t[i + 1], vf_t[i], vb_t[i], vb_t[i + 1]),
        ):
            ff = bm.faces.new(quad)
            ff.material_index = 1
    bm.faces.new((vb_b[0], vf_b[0], vf_t[0], vb_t[0])).material_index = 1
    bm.faces.new((vf_b[-1], vb_b[-1], vb_t[-1], vf_t[-1])).material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Landscape_SchoolBoulder')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(img_mat('M_SchoolStone', 'school_stone.png', 0.85, 0.0, (0.62, 0.62, 0.61, 1)))
    me.materials.append(bpy.data.materials.get('M_Paving') or simple_mat('M_Paving', (0.64, 0.64, 0.62, 1), 0.85))
    c.objects.link(bpy.data.objects.new('Landscape_SchoolBoulder', me))


def north_entrance(c):
    """北入口门房两座 + 校名景石 + 主入口大台阶 + 两侧折线分级绿化台地 + 外广场铺装圆纹（wx_01/08/11/official_18）。"""
    for o in [o for o in c.objects if o.name.startswith(('Landscape_North', 'Landscape_Gatehouse', 'Landscape_SchoolBoulder'))]:
        bpy.data.objects.remove(o, do_unlink=True)
    gatehouse('Landscape_Gatehouse_W', -90, 66, -55, 79, -6.0, -1.5, c)
    gatehouse('Landscape_Gatehouse_E', 0, 66, 32, 79, -6.0, -1.5, c)
    school_boulder(c)

    # 主入口宽大台阶（y=36 Z=-6 → y=10 Z=0，x=-34..+2）
    m_step = bpy.data.materials.get('M_Paving') or simple_mat('M_Paving', (0.66, 0.66, 0.64, 1), rough=0.85)
    bm = bmesh.new()
    steps = 16
    x0, x1 = -34.0, 2.0
    y_bot, y_top = 36.0, 10.0
    z_bot, z_top = -6.0, 0.0
    for i in range(steps):
        t0, t1 = i / steps, (i + 1) / steps
        ya = y_bot + (y_top - y_bot) * t0
        yb = y_bot + (y_top - y_bot) * t1
        zt = z_bot + (z_top - z_bot) * t1
        vs = [bm.verts.new((x0, ya, z_bot)), bm.verts.new((x1, ya, z_bot)),
              bm.verts.new((x1, yb, z_bot)), bm.verts.new((x0, yb, z_bot)),
              bm.verts.new((x0, ya, zt)), bm.verts.new((x1, ya, zt)),
              bm.verts.new((x1, yb, zt)), bm.verts.new((x0, yb, zt))]
        bm.faces.new(vs[0:4])
        bm.faces.new(vs[4:8])
        for j in range(4):
            bm.faces.new((vs[j], vs[(j + 1) % 4], vs[(j + 1) % 4 + 4], vs[j + 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('Landscape_NorthSteps')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_step)
    c.objects.link(bpy.data.objects.new('Landscape_NorthSteps', me))

    # 主台阶两侧折线分级绿化台地（wx_01 右侧、wx_08 标志景观：3 级白边绿草阶梯花坛）
    bm_t = bmesh.new()
    for side, sx0, sx1 in (('W', -74.0, -35.0), ('E', 3.0, 44.0)):
        for lv_i in range(3):
            ya = 35.0 - lv_i * 8.2
            yb = ya - 6.8
            zt = -6.0 + (lv_i + 1) * 1.85
            # 白色挡墙压顶底座 (mat 0 = M_Cloud_Core)
            vs_b = [bm_t.verts.new((sx0, ya, -6.0)), bm_t.verts.new((sx1, ya, -6.0)),
                    bm_t.verts.new((sx1, yb, -6.0)), bm_t.verts.new((sx0, yb, -6.0)),
                    bm_t.verts.new((sx0, ya, zt)), bm_t.verts.new((sx1, ya, zt)),
                    bm_t.verts.new((sx1, yb, zt)), bm_t.verts.new((sx0, yb, zt))]
            bm_t.faces.new(vs_b[0:4]).material_index = 0
            f_top = bm_t.faces.new(vs_b[4:8])
            f_top.material_index = 1  # 顶面绿草
            for j in range(4):
                bm_t.faces.new((vs_b[j], vs_b[(j + 1) % 4], vs_b[(j + 1) % 4 + 4], vs_b[j + 4])).material_index = 0
    bmesh.ops.recalc_face_normals(bm_t, faces=bm_t.faces)
    me_t = bpy.data.meshes.new('Landscape_NorthTerraces')
    bm_t.to_mesh(me_t)
    bm_t.free()
    me_t.materials.append(bpy.data.materials.get('M_Cloud_Core') or simple_mat('M_Cloud_Core', (0.90, 0.90, 0.88, 1)))
    me_t.materials.append(bpy.data.materials.get('M_Turf') or simple_mat('M_Turf', (0.18, 0.39, 0.13, 1), 0.92))
    c.objects.link(bpy.data.objects.new('Landscape_NorthTerraces', me_t))

    # 北外落客广场中央圆形铺装徽章 + 门房前礼仪铺装（卫星图 & wx_08）
    bm_p = bmesh.new()
    # 中央石材铺装广场连接两门房与主台阶 (y = 36..80, x = -54..0)
    vs_p = [bm_p.verts.new((x, y, -5.96)) for x, y in ((-54, 36), (0, 36), (0, 80), (-54, 80))]
    bm_p.faces.new(vs_p).material_index = 0
    # 外广场中央圆盘 (cx=-35, cy=98.5, r=5.6 m)
    cx_m, cy_m, r_m = -35.0, 98.5, 5.6
    cv_pts = [bm_p.verts.new((cx_m + r_m * math.cos(2 * math.pi * k / 24),
                              cy_m + r_m * math.sin(2 * math.pi * k / 24), -5.95)) for k in range(24)]
    f_c = bm_p.faces.new(cv_pts)
    f_c.material_index = 1
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    me_p = bpy.data.meshes.new('Landscape_NorthPlazaAccent')
    bm_p.to_mesh(me_p)
    bm_p.free()
    me_p.materials.append(m_step)
    me_p.materials.append(bpy.data.materials.get('M_TrackRed') or simple_mat('M_TrackRed', (0.55, 0.22, 0.18, 1), 0.85))
    c.objects.link(bpy.data.objects.new('Landscape_NorthPlazaAccent', me_p))


def main():
    apply_landcover()
    north_entrance(bpy.data.collections[COLL])
    n = trees()
    sky()
    bpy.ops.wm.save_mainfile()
    print('trees placed', n)


main()
