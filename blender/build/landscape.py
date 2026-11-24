"""P5–P10 景观：
- 3 类低模实例化热带树种（4 段弧形自然垂坠棕榈羽叶、分层伞形阔叶树、团簇多球冠大乔木，全走 GPU Instancing）
- 严格排除全部建筑外轮廓 3.4 m 缓冲（杜绝树冠穿出宿舍/幕墙）、市政道路带、4 片球场与星形庭院内部误种树
- 24 段圆润有机曲面北入口校名景石 + 带落地玻璃窗框的北门房 + 石材纹理大台阶与折线台地
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
CLOUD = json.load(open(os.path.join(ROOT, 'data', 'bldg_cloud.json')))
SPORTS = json.load(open(os.path.join(ROOT, 'data', 'bldg_sports.json')))
X0, Y0, X1, Y1 = TR['extent']
COLL = 'Landscape'
TOP_SURFACES = ['Site_Campus', 'Site_Zone_操场平台周边', 'Bldg_Cloud_Podium', 'Bldg_Dorm_Base']


def fresh_mesh(name):
    old = bpy.data.meshes.get(name)
    if old is not None:
        bpy.data.meshes.remove(old, do_unlink=True)
    return bpy.data.meshes.new(name)


def simple_mat(name, col, rough=0.7, metal=0.0):
    m = bpy.data.materials.get(name)
    if name == 'M_Paving' and m is not None and m.node_tree and any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes):
        return m
    m = m or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
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
    """3 类热带校园实例化树种网格（全场景共仅占 3 次 GPU Instancing 绘制）：
    1. Landscape_PalmUnit: 热带棕榈/王棕/蒲葵（4 段自然垂弧羽叶，告别硬折纸三角）
    2. Landscape_BroadleafUnit: 分层伞形阔叶树
    3. Landscape_CanopyUnit: 团簇多球冠大乔木
    """
    m_trunk = simple_mat('M_TreeTrunk', (0.30, 0.22, 0.16, 1), rough=0.90)
    m_crown = simple_mat('M_TreeCrown', (0.14, 0.32, 0.11, 1), rough=0.86)
    m_palm = simple_mat('M_PalmCrown', (0.20, 0.42, 0.13, 1), rough=0.78)

    # --- 1. 热带棕榈/蒲葵（12 片 4 段平滑拱弧羽叶） ---
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.068, radius2=0.036, depth=0.82,
                          matrix=Matrix.Translation((0, 0, 0.41)))
    trunk_f = set(bm.faces[:])
    for f in trunk_f:
        f.material_index = 0
        f.smooth = True

    fronds = [
        (7, 0.79, 0.96, -0.20, 0.0),
        (5, 0.84, 0.72, 0.08, 0.45),
    ]
    for count, zc, rlen, tip_dz, phase in fronds:
        for i in range(count):
            ang = 2 * math.pi * i / count + phase
            ca, sa = math.cos(ang), math.sin(ang)
            tx, ty = -sa, ca
            # 沿叶轴 5 个节点生成自然拱弧 + 中肋 V 型折角
            ts = (0.0, 0.26, 0.55, 0.80, 1.0)
            ws = (0.02, 0.18, 0.23, 0.15, 0.0)
            zs = (0.0, 0.09 + tip_dz * 0.05, 0.12 + tip_dz * 0.28, 0.06 + tip_dz * 0.65, tip_dz)
            rings = []
            for k in range(len(ts)):
                r_k = rlen * ts[k]
                cx_k, cy_k, cz_k = ca * r_k, sa * r_k, zc + zs[k]
                wk = ws[k]
                if wk <= 0.001:
                    v_tip = bm.verts.new((cx_k, cy_k, cz_k))
                    rings.append((v_tip,))
                else:
                    vl = bm.verts.new((cx_k + tx * wk, cy_k + ty * wk, cz_k - 0.035 * wk / 0.23))
                    vc = bm.verts.new((cx_k, cy_k, cz_k + 0.025))
                    vr = bm.verts.new((cx_k - tx * wk, cy_k - ty * wk, cz_k - 0.035 * wk / 0.23))
                    rings.append((vl, vc, vr))
            for k in range(len(rings) - 1):
                r0, r1 = rings[k], rings[k + 1]
                if len(r0) == 3 and len(r1) == 3:
                    for quad in ((r0[0], r1[0], r1[1], r0[1]), (r0[1], r1[1], r1[2], r0[2])):
                        f = bm.faces.new(quad); f.material_index = 1; f.smooth = True
                elif len(r0) == 3 and len(r1) == 1:
                    for tri in ((r0[0], r1[0], r0[1]), (r0[1], r1[0], r0[2])):
                        f = bm.faces.new(tri); f.material_index = 1; f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me_palm = fresh_mesh('Landscape_PalmUnit')
    bm.to_mesh(me_palm)
    bm.free()
    me_palm.materials.append(m_trunk)
    me_palm.materials.append(m_palm)

    # --- 2. 分层伞形阔叶树 ---
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.08, radius2=0.045, depth=0.55,
                          matrix=Matrix.Translation((0, 0, 0.275)))
    trunk_f = set(bm.faces[:])
    for f in trunk_f:
        f.material_index = 0; f.smooth = True
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
    me_broad = fresh_mesh('Landscape_BroadleafUnit')
    bm.to_mesh(me_broad)
    bm.free()
    me_broad.materials.append(m_trunk)
    me_broad.materials.append(m_crown)

    # --- 3. 团簇多球冠大乔木 ---
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.09, radius2=0.055, depth=0.52,
                          matrix=Matrix.Translation((0, 0, 0.26)))
    trunk_f = set(bm.faces[:])
    for f in trunk_f:
        f.material_index = 0; f.smooth = True
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
    me_can = fresh_mesh('Landscape_CanopyUnit')
    bm.to_mesh(me_can)
    bm.free()
    me_can.materials.append(m_trunk)
    me_can.materials.append(m_crown)

    return me_palm, me_broad, me_can


# ---------- 精确 2D 建筑与道路树位排除几何工具 ----------

def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    return inside


def pt_seg_dist(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(x - ax, y - ay)
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def inside_or_near_poly(x, y, poly, margin):
    if point_in_poly(x, y, poly):
        return True
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        if pt_seg_dist(x, y, ax, ay, bx, by) < margin:
            return True
    return False


BLDG_FOOTPRINTS = [
    (DORM['shell'][0]['outer'], 3.8),      # 宿舍综合楼外缘保护 3.8 m（含挑檐与树冠，杜绝树冠穿出 2-3 层外墙！）
    (CLOUD['shell'][0]['outer'], 3.4),     # 学术中心外缘保护 3.4 m
    (SPORTS['outer'], 3.6),                # 体育及艺术中心幕墙保护 3.6 m
]


def near_any_road(x, y, extra=1.5):
    for r in SITE['roads']:
        (x0, y0), (x1, y1) = r['centerline']
        if pt_seg_dist(x, y, x0, y0, x1, y1) < r['width'] * 0.5 + extra:
            return True
    return False


def inside_any_court(x, y, margin=2.6):
    for k, v in SITE['courts'].items():
        cx, cy = v['center']
        a = math.radians(v['long_axis_deg_from_E'])
        L, W = v['size']
        pad = (3.5 if v['kind'] == 'tennis' else 2.0) + margin
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = x - cx, y - cy
        lx = dx * ca + dy * sa
        ly = -dx * sa + dy * ca
        ly_min = -(W / 2 + pad + (4.5 if v['kind'] == 'tennis' else 0.0))
        ly_max = W / 2 + pad
        if abs(lx) <= L / 2 + pad and ly_min <= ly <= ly_max:
            return True
    return False


def inside_excluded_zone(x, y):
    # 1. 4 片球场与休憩亭
    if inside_any_court(x, y, margin=4.5):
        return True
    # 2. 全部主建筑外轮廓 + 3.4~3.8 m 树冠安全缓冲区（杜绝任何穿墙树！）
    for poly, mrg in BLDG_FOOTPRINTS:
        if inside_or_near_poly(x, y, poly, mrg):
            return True
    # 3. 市政与校园道路沥青路面保护
    if near_any_road(x, y, extra=1.6):
        return True
    # 4. 体育中心看台与跑道过渡拐角
    if -230.0 <= x <= -178.0 and -134.0 <= y <= -42.0:
        return True
    # 5. 体育中心西侧混凝土地坪
    if -292.0 <= x <= -248.0 and -172.0 <= y <= -68.0:
        return True
    # 6. 星形庭院内部
    if -58.0 <= x <= 55.0 and -112.0 <= y <= -14.0:
        return True
    # 7. 北入口中轴校名石、门房与主台阶礼仪广场
    if -56.0 <= x <= 34.0 and 10.0 <= y <= 84.0:
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

    # 1. 全园卫星检测树木（已严格过滤建筑外墙缓冲、道路、球场、看台、庭院与北广场）
    for x, y, r in TR['trees']:
        if inside_excluded_zone(x, y):
            continue
        z, hit = ground_z(x, y, dg, sc)
        if hit.startswith(('Bldg_Cloud', 'Bldg_Dorm', 'Bldg_SportsArt', 'Site_Track', 'Site_Court',
                           'Site_Tennis', 'Site_Road', 'Site_Plaza', 'Landscape_North',
                           'Landscape_Gatehouse', 'Landscape_SchoolBoulder')):
            continue
        is_boulevard = (y < -176.0) or (82.0 <= y <= 116.0) or (-80.0 <= x <= 40.0 and -160.0 <= y <= -118.0)
        if is_boulevard and random.random() < 0.55:
            h = random.uniform(8.0, 11.5)
            spawn(me_palm, x, y, z, random.uniform(2.6, 3.6), h, 'Landscape_Palm')
        elif r < 3.4:
            if random.random() < 0.18:
                spawn(me_palm, x, y, z, random.uniform(2.4, 3.2), random.uniform(7.5, 10.5), 'Landscape_Palm')
            else:
                h = max(4.8, r * 2.4) * random.uniform(0.88, 1.12)
                spawn(me_broad, x, y, z, r * 1.04, h)
        else:
            h = max(6.0, r * 2.15) * random.uniform(0.88, 1.12)
            spawn(me_can, x, y, z, r * 1.02, h)

    # 2. 星形庭院精确定位乔木（已校准确认零穿台阶）
    for x, y, r, z_base in CY.get('courtyard_trees', []):
        h = max(5.6, r * 2.4) * random.uniform(0.92, 1.08)
        spawn(me_broad, x, y, z_base + (0.22 if z_base < 0.1 else 0.14), r, h)

    # 3. 宿舍 4 座大庭院花池内的蒲葵棕榈
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
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 6.0, lp.vert.co.y / 6.0)
    me = fresh_mesh(name)
    bm.to_mesh(me)
    bm.free()
    m = bpy.data.materials.get(matname) or bpy.data.materials.new(matname)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def gatehouse(name, x0, y0, x1, y1, z0, z1, c):
    """P10 细化北门房：浅灰石材基座 + 深蓝灰落地玻璃幕墙 + 竖向金属竖梃 + 白色实墙端翼 + 悬挑暗灰屋檐。"""
    m_gl = simple_mat('M_Cloud_Skylight', (0.14, 0.20, 0.27, 1), rough=0.08, metal=0.40)
    m_fa = simple_mat('M_Cloud_Slab', (0.22, 0.24, 0.27, 1), rough=0.45, metal=0.25)
    m_rf = simple_mat('M_Cloud_RoofRim', (0.76, 0.77, 0.76, 1), rough=0.60, metal=0.15)
    m_wh = simple_mat('M_Cloud_Core', (0.91, 0.91, 0.89, 1), rough=0.72, metal=0.0)

    bm = bmesh.new()
    def add_b(xa, ya, za, xb, yb, zb, mi):
        vs = [bm.verts.new(p) for p in (
            (xa, ya, za), (xb, ya, za), (xb, yb, za), (xa, yb, za),
            (xa, ya, zb), (xb, ya, zb), (xb, yb, zb), (xa, yb, zb),
        )]
        for q in (
            (vs[0], vs[3], vs[2], vs[1]), (vs[4], vs[5], vs[6], vs[7]),
            (vs[0], vs[1], vs[5], vs[4]), (vs[1], vs[2], vs[6], vs[5]),
            (vs[2], vs[3], vs[7], vs[6]), (vs[3], vs[0], vs[4], vs[7]),
        ):
            bm.faces.new(q).material_index = mi

    # 玻璃体主体 (mat 0) + 底部踢脚勒脚 (mat 1)
    add_b(x0 + 0.8, y0 + 0.8, z0 + 0.25, x1 - 0.8, y1 - 0.8, z1 - 0.85, 0)
    add_b(x0 + 0.72, y0 + 0.72, z0, x1 - 0.72, y1 - 0.72, z0 + 0.28, 1)
    # 两侧白色端墙翼 (mat 3)
    add_b(x0 + 0.65, y0 + 0.75, z0, x0 + 3.2, y1 - 0.75, z1 - 0.85, 3)
    add_b(x1 - 3.2, y0 + 0.75, z0, x1 - 0.65, y1 - 0.75, z1 - 0.85, 3)
    # 前后玻璃立面金属竖梃 (每 3.2 m 一根, mat 1)
    span_x = (x1 - 3.2) - (x0 + 3.2)
    n_mul = max(2, int(round(span_x / 3.2)))
    for k in range(n_mul + 1):
        mx = (x0 + 3.2) + span_x * (k / n_mul)
        add_b(mx - 0.06, y1 - 0.86, z0 + 0.25, mx + 0.06, y1 - 0.70, z1 - 0.85, 1)
        add_b(mx - 0.06, y0 + 0.70, z0 + 0.25, mx + 0.06, y0 + 0.86, z1 - 0.85, 1)
    # 悬挑暗灰屋檐 (mat 1) + 浅灰顶面压顶 (mat 2)
    add_b(x0, y0, z1 - 0.85, x1, y1, z1 - 0.08, 1)
    add_b(x0 + 0.15, y0 + 0.15, z1 - 0.08, x1 - 0.15, y1 - 0.15, z1, 2)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh(name)
    bm.to_mesh(me); bm.free()
    for m in (m_gl, m_fa, m_rf, m_wh):
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


def school_boulder(c):
    """P10 升级版北入口校名景石：24 段圆润有机曲面平滑景石 + 2048x768 细腻花岗岩大字 + 倒角石材底座绿篱。"""
    cx, cy, z0 = -16.0, 56.0, -6.0
    box('Landscape_SchoolBoulder_Curb', cx - 6.8, cy - 1.8, cx + 6.8, cy + 1.8, z0, z0 + 0.28, 'M_Cloud_Core', c)
    box('Landscape_SchoolBoulder_Hedge', cx - 6.45, cy - 1.45, cx + 6.45, cy + 1.45, z0 + 0.28, z0 + 0.86, 'M_TreeCrown', c)

    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    # 24 段沿 X 生成自然流畅山石顶部包络与微凸弧面
    N = 24
    half_w = 5.6
    xs = [-half_w + (2.0 * half_w) * (i / N) for i in range(N + 1)]

    def crest_h(u):
        # u in [0, 1]：柔和不对称自然石峰轮廓（两肩微圆、中偏西略高）
        s = math.sin(u * math.pi)
        return 1.28 + 1.52 * (s ** 0.58) + 0.14 * math.sin(u * math.pi * 2.0 + 0.5) + 0.05 * math.sin(u * math.pi * 5.0)

    # 沿断面构造 4 个纵层（底缘 -> 饱满石腹 -> 上肩 -> 圆润顶脊），前立面微凸自然反光
    y_f0, y_b0 = cy + 0.92, cy - 0.92
    f_rows = [[], [], [], []]
    b_rows = [[], [], [], []]
    row_fracs = (0.0, 0.36, 0.74, 1.0)
    row_yoff = (0.0, 0.14, -0.06, -0.34)  # 前面微外鼓再向顶内收
    for i, x in enumerate(xs):
        u = i / N
        h_top = crest_h(u)
        z_base = z0 + 0.56
        bulge_x = math.sin(u * math.pi)
        for r_idx, (rf, dy) in enumerate(zip(row_fracs, row_yoff)):
            zr = z_base + (h_top - 0.56) * rf
            yf = y_f0 + dy * (0.5 + 0.5 * bulge_x)
            yb = y_b0 - dy * (0.5 + 0.5 * bulge_x)
            f_rows[r_idx].append(bm.verts.new((cx + x, yf, zr)))
            b_rows[r_idx].append(bm.verts.new((cx + x, yb, zr)))

    # 顶脊中心闭合顶点，形成圆润石顶
    top_mid = [
        bm.verts.new((cx + xs[i], cy, z0 + crest_h(i / N) + 0.08 * math.sin((i / N) * math.pi)))
        for i in range(N + 1)
    ]

    v_uvs = (0.06, 0.38, 0.72, 0.94)
    for i in range(N):
        u0, u1 = i / N, (i + 1) / N
        # 正面 (+Y，镜像 U 保证从北向南看正读“北京大学附属中学海口学校”）
        for r_idx in range(3):
            f_front = bm.faces.new((
                f_rows[r_idx][i + 1], f_rows[r_idx][i],
                f_rows[r_idx + 1][i], f_rows[r_idx + 1][i + 1]
            ))
            f_front.material_index = 0
            f_front.smooth = True
            va, vb = v_uvs[r_idx], v_uvs[r_idx + 1]
            for lp, uv in zip(f_front.loops, [(1.0 - u1, va), (1.0 - u0, va), (1.0 - u0, vb), (1.0 - u1, vb)]):
                lp[uvl].uv = uv
            # 背面
            f_back = bm.faces.new((
                b_rows[r_idx][i], b_rows[r_idx][i + 1],
                b_rows[r_idx + 1][i + 1], b_rows[r_idx + 1][i]
            ))
            f_back.material_index = 1
            f_back.smooth = True
        # 圆润顶脊两坡
        for q in (
            (f_rows[3][i + 1], f_rows[3][i], top_mid[i], top_mid[i + 1]),
            (top_mid[i + 1], top_mid[i], b_rows[3][i], b_rows[3][i + 1]),
        ):
            ft = bm.faces.new(q)
            ft.material_index = 1
            ft.smooth = True

    # 左右端面平滑封口
    for r_idx in range(3):
        f_l = bm.faces.new((b_rows[r_idx][0], f_rows[r_idx][0], f_rows[r_idx + 1][0], b_rows[r_idx + 1][0]))
        f_r = bm.faces.new((f_rows[r_idx][N], b_rows[r_idx][N], b_rows[r_idx + 1][N], f_rows[r_idx + 1][N]))
        f_l.material_index = 1; f_l.smooth = True
        f_r.material_index = 1; f_r.smooth = True
    for tri in ((b_rows[3][0], f_rows[3][0], top_mid[0]), (f_rows[3][N], b_rows[3][N], top_mid[N])):
        ft = bm.faces.new(tri); ft.material_index = 1; ft.smooth = True

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh('Landscape_SchoolBoulder')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(img_mat('M_SchoolStone', 'school_stone.png', 0.82, 0.0, (0.64, 0.64, 0.63, 1)))
    me.materials.append(simple_mat('M_BoulderBack', (0.62, 0.62, 0.61, 1), 0.86))
    c.objects.link(bpy.data.objects.new('Landscape_SchoolBoulder', me))


def north_entrance(c):
    for o in [o for o in c.objects if o.name.startswith(('Landscape_North', 'Landscape_Gatehouse', 'Landscape_SchoolBoulder'))]:
        bpy.data.objects.remove(o, do_unlink=True)
    gatehouse('Landscape_Gatehouse_W', -90, 66, -55, 79, -6.0, -1.5, c)
    gatehouse('Landscape_Gatehouse_E', 0, 66, 32, 79, -6.0, -1.5, c)
    school_boulder(c)

    m_step = bpy.data.materials.get('M_Paving') or simple_mat('M_Paving', (0.66, 0.66, 0.64, 1), rough=0.84)
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
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x / 6.0, lp.vert.co.y / 6.0)
    me = fresh_mesh('Landscape_NorthSteps')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_step)
    c.objects.link(bpy.data.objects.new('Landscape_NorthSteps', me))

    # 主台阶两侧 3 级白边绿草阶梯花坛
    bm_t = bmesh.new()
    for side, sx0, sx1 in (('W', -74.0, -35.0), ('E', 3.0, 44.0)):
        for lv_i in range(3):
            ya = 35.0 - lv_i * 8.2
            yb = ya - 6.8
            zt = -6.0 + (lv_i + 1) * 1.85
            vs_b = [bm_t.verts.new((sx0, ya, -6.0)), bm_t.verts.new((sx1, ya, -6.0)),
                    bm_t.verts.new((sx1, yb, -6.0)), bm_t.verts.new((sx0, yb, -6.0)),
                    bm_t.verts.new((sx0, ya, zt)), bm_t.verts.new((sx1, ya, zt)),
                    bm_t.verts.new((sx1, yb, zt)), bm_t.verts.new((sx0, yb, zt))]
            bm_t.faces.new(vs_b[0:4]).material_index = 0
            f_top = bm_t.faces.new(vs_b[4:8])
            f_top.material_index = 1
            for j in range(4):
                bm_t.faces.new((vs_b[j], vs_b[(j + 1) % 4], vs_b[(j + 1) % 4 + 4], vs_b[j + 4])).material_index = 0
    bmesh.ops.recalc_face_normals(bm_t, faces=bm_t.faces)
    me_t = fresh_mesh('Landscape_NorthTerraces')
    bm_t.to_mesh(me_t)
    bm_t.free()
    me_t.materials.append(bpy.data.materials.get('M_Cloud_Core') or simple_mat('M_Cloud_Core', (0.90, 0.90, 0.88, 1)))
    me_t.materials.append(bpy.data.materials.get('M_Turf') or simple_mat('M_Turf', (0.18, 0.39, 0.13, 1), 0.92))
    c.objects.link(bpy.data.objects.new('Landscape_NorthTerraces', me_t))

    # 北外落客广场石材铺装与圆形徽章
    bm_p = bmesh.new()
    vs_p = [bm_p.verts.new((x, y, -5.96)) for x, y in ((-54, 36), (0, 36), (0, 80), (-54, 80))]
    bm_p.faces.new(vs_p).material_index = 0
    cx_m, cy_m, r_m = -35.0, 98.5, 5.6
    cv_pts = [bm_p.verts.new((cx_m + r_m * math.cos(2 * math.pi * k / 32),
                              cy_m + r_m * math.sin(2 * math.pi * k / 32), -5.95)) for k in range(32)]
    f_c = bm_p.faces.new(cv_pts)
    f_c.material_index = 1
    bmesh.ops.triangulate(bm_p, faces=bm_p.faces[:])
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    uvl_p = bm_p.loops.layers.uv.new('UVMap')
    for f in bm_p.faces:
        for lp in f.loops:
            lp[uvl_p].uv = (lp.vert.co.x / 6.0, lp.vert.co.y / 6.0)
    me_p = fresh_mesh('Landscape_NorthPlazaAccent')
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
