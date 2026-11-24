"""P10 校园师生人物模型升级版（独立 People 集合，13 套圆润平滑建筑配景人原型，~800 三角面/原型，
全走 GPU Instancing 导出，兼顾近景质感与 120 FPS 性能）：
- 多截面椭圆放样躯干（含自然肩坡、收腰、衣领与男女体型差异）
- 2 级细分平滑椭圆头颅 + 颈部 + 3 种自然发型（男生短发 / 女生低马尾 / 齐耳短发）
- 10 边平滑锥形四肢 + 肩/肘/膝球形关节 + 手掌 + 严格落地圆润运动鞋（站/走/跑脚底严格 Z=0.0）
- 坐姿原型臀部基准面严格锚定 Z=0.0，完美贴合看台、星形庭院大台阶与宿舍长凳
数据：data/people.json，色板：blender/textures/people_palette.png（16 色格）。

在 Blender 中运行：exec(open('/Users/perrylei/repos/BDFZ/blender/build/people.py').read())
"""
import bpy, bmesh, json, os, math, random
from mathutils import Vector, Matrix, Euler

ROOT = '/Users/perrylei/repos/BDFZ'
D = json.load(open(os.path.join(ROOT, 'data', 'people.json')))
COLL = 'People'
NUM_SWATCHES = 16


def fresh_mesh(name):
    old = bpy.data.meshes.get(name)
    if old is not None:
        bpy.data.meshes.remove(old, do_unlink=True)
    return bpy.data.meshes.new(name)


def people_mat():
    """单一 16 格调色板材质 M_People，全员 133 人共用 1 份材质。"""
    m = bpy.data.materials.get('M_People')
    if m is None:
        m = bpy.data.materials.new('M_People')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(ROOT, 'blender', 'textures', 'people_palette.png'), check_existing=True)
    img.reload()
    tex.image = img
    tex.interpolation = 'Closest'
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.72
    m.diffuse_color = (0.85, 0.85, 0.85, 1.0)
    return m


def _paint_faces(faces, uvl, sw, smooth=True):
    u = (sw + 0.5) / float(NUM_SWATCHES)
    for f in faces:
        f.smooth = smooth
        for lp in f.loops:
            lp[uvl].uv = (u, 0.5)


def add_ellipsoid(bm, uvl, sw, center, radii, subdiv=2, rot_euler=(0.0, 0.0, 0.0)):
    rx, ry, rz = radii
    R = Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
    M = Matrix.Translation(center) @ R @ Matrix.Diagonal((rx, ry, rz, 1.0))
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0, matrix=M)
    vset = set(res['verts'])
    faces = [f for f in bm.faces if all(v in vset for v in f.verts)]
    _paint_faces(faces, uvl, sw, smooth=True)


def add_loft(bm, uvl, sw, rings_spec, segs=12, cap_bot=True, cap_top=True):
    """多截面椭圆放样体：rings_spec = [(cx, cy, z, rx, ry), ...]"""
    rings = []
    for (cx, cy, z, rx, ry) in rings_spec:
        ring = []
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ring.append(bm.verts.new((cx + rx * math.cos(a), cy + ry * math.sin(a), z)))
        rings.append(ring)
    created = []
    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(segs):
            j = (i + 1) % segs
            created.append(bm.faces.new((r0[i], r0[j], r1[j], r1[i])))
    if cap_bot and len(rings) > 0:
        f_b = bm.faces.new(list(reversed(rings[0])))
        created.extend(bmesh.ops.triangulate(bm, faces=[f_b])['faces'])
    if cap_top and len(rings) > 0:
        f_t = bm.faces.new(rings[-1])
        created.extend(bmesh.ops.triangulate(bm, faces=[f_t])['faces'])
    _paint_faces(created, uvl, sw, smooth=True)


def add_tapered_limb(bm, uvl, sw, p0, p1, r0, r1, segs=10, cap_j0=True, cap_j1=True):
    """平滑锥形肢体 + 端点球形关节无缝衔接。"""
    va, vb = Vector(p0), Vector(p1)
    d = vb - va
    L = d.length
    if L < 1e-4:
        return
    q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    M = Matrix.Translation((va + vb) * 0.5) @ q
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=segs, radius1=r0, radius2=r1, depth=L, matrix=M)
    vset = set(res['verts'])
    faces = [f for f in bm.faces if all(v in vset for v in f.verts)]
    _paint_faces(faces, uvl, sw, smooth=True)
    if cap_j0:
        add_ellipsoid(bm, uvl, sw, va, (r0 * 1.02, r0 * 1.02, r0 * 1.02), subdiv=1)
    if cap_j1:
        add_ellipsoid(bm, uvl, sw, vb, (r1 * 1.02, r1 * 1.02, r1 * 1.02), subdiv=1)


def add_shoe(bm, uvl, sw, ankle_pos, yaw_rad=0.0, pitch_rad=0.0, ground_flat=True):
    """圆润运动鞋模型：严格平底落地（ground_flat=True 时鞋底落在 Z=0.0）。"""
    ax, ay, az = ankle_pos
    z_sole = 0.0 if ground_flat else (az - 0.075)
    # 沿鞋底到鞋背 3 层椭圆放样，前脚掌向 +Y 略伸展
    c_x, c_y = ax, ay + 0.045
    ca, sa = math.cos(yaw_rad), math.sin(yaw_rad)
    rings_local = [
        (0.0, 0.00, z_sole,        0.046, 0.115),
        (0.0, 0.00, z_sole + 0.028, 0.048, 0.118),
        (0.0, -0.02, z_sole + 0.068, 0.040, 0.082),
    ]
    rings = []
    segs = 10
    for (lx, ly, lz, rx, ry) in rings_local:
        ring = []
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            px = lx + rx * math.cos(a)
            py = ly + ry * math.sin(a)
            # 旋转 + 轻微脚尖抬起
            rx_w = c_x + px * ca - py * sa
            ry_w = c_y + px * sa + py * ca
            rz_w = lz + (py * math.sin(pitch_rad) if not ground_flat else 0.0)
            ring.append(bm.verts.new((rx_w, ry_w, rz_w)))
        rings.append(ring)
    created = []
    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(segs):
            j = (i + 1) % segs
            created.append(bm.faces.new((r0[i], r0[j], r1[j], r1[i])))
    f_b = bm.faces.new(list(reversed(rings[0])))
    f_t = bm.faces.new(rings[-1])
    created.extend(bmesh.ops.triangulate(bm, faces=[f_b, f_t])['faces'])
    _paint_faces(created, uvl, sw, smooth=True)


def add_head_and_hair(bm, uvl, skin_sw, hair_sw, head_center, hair_style='short_m', lean_y=0.0):
    hx, hy, hz = head_center
    # 颈部
    add_tapered_limb(bm, uvl, skin_sw, (hx, hy - 0.01, hz - 0.17), (hx, hy, hz - 0.07), 0.046, 0.042, segs=8, cap_j0=False, cap_j1=False)
    # 圆润头颅（subdiv=2 -> 80 面全平滑）
    add_ellipsoid(bm, uvl, skin_sw, (hx, hy, hz), (0.092, 0.104, 0.116), subdiv=2)

    if hair_style == 'ponytail':
        # 顶发与后脑包覆 + 标志性自然下垂低马尾
        add_ellipsoid(bm, uvl, hair_sw, (hx, hy - 0.018, hz + 0.030), (0.098, 0.108, 0.098), subdiv=2)
        add_tapered_limb(bm, uvl, hair_sw, (hx, hy - 0.105, hz - 0.005), (hx, hy - 0.155, hz - 0.155), 0.036, 0.018, segs=8)
    elif hair_style == 'bob':
        # 齐耳柔顺短发（包裹顶部与两侧后脑）
        add_ellipsoid(bm, uvl, hair_sw, (hx, hy - 0.018, hz + 0.025), (0.103, 0.108, 0.104), subdiv=2)
        add_ellipsoid(bm, uvl, hair_sw, (hx - 0.068, hy - 0.025, hz - 0.042), (0.042, 0.068, 0.075), subdiv=1)
        add_ellipsoid(bm, uvl, hair_sw, (hx + 0.068, hy - 0.025, hz - 0.042), (0.042, 0.068, 0.075), subdiv=1)
        add_ellipsoid(bm, uvl, hair_sw, (hx, hy - 0.065, hz - 0.045), (0.088, 0.055, 0.075), subdiv=1)
    else:
        # 男生利落短发（圆润贴合头顶与后脑，微有额前层次）
        add_ellipsoid(bm, uvl, hair_sw, (hx, hy - 0.016, hz + 0.036), (0.096, 0.104, 0.088), subdiv=2)
        add_ellipsoid(bm, uvl, hair_sw, (hx, hy - 0.042, hz + 0.005), (0.092, 0.082, 0.078), subdiv=1)


def add_torso(bm, uvl, shirt_sw, collar_sw, pants_sw, z_hip, slim=False, lean_y=0.0):
    """自然人体工学多截面平滑躯干 + 衣领 + 臀胯。"""
    s_w = 0.90 if slim else 1.0
    # 臀部与裤腰 (z_hip - 0.06 .. z_hip + 0.10)
    add_loft(bm, uvl, pants_sw, [
        (0.0, lean_y * 0.1, z_hip - 0.07, 0.138 * s_w, 0.094),
        (0.0, lean_y * 0.2, z_hip + 0.02, 0.156 * s_w, 0.104),
        (0.0, lean_y * 0.3, z_hip + 0.10, 0.146 * s_w, 0.096),
    ], segs=12)
    # 上衣躯干 (z_hip + 0.08 .. z_hip + 0.58)
    add_loft(bm, uvl, shirt_sw, [
        (0.0, lean_y * 0.25, z_hip + 0.08, 0.152 * s_w, 0.098),
        (0.0, lean_y * 0.45, z_hip + 0.22, 0.146 * s_w, 0.096),  # 自然收腰
        (0.0, lean_y * 0.70, z_hip + 0.40, 0.172 * s_w, 0.108),  # 胸部饱满
        (0.0, lean_y * 0.90, z_hip + 0.53, 0.184 * s_w, 0.092),  # 圆润双肩
        (0.0, lean_y * 1.00, z_hip + 0.58, 0.082,       0.068),  # 领口收拢
    ], segs=12)
    # 精致衣领环
    add_loft(bm, uvl, collar_sw, [
        (0.0, lean_y * 0.98, z_hip + 0.56, 0.084, 0.070),
        (0.0, lean_y * 1.02, z_hip + 0.60, 0.062, 0.056),
    ], segs=10)


def add_backpack(bm, uvl, pack_sw, z_hip, lean_y=0.0):
    """圆润流线型双肩书包（告别硬方块）。"""
    add_loft(bm, uvl, pack_sw, [
        (0.0, -0.155 + lean_y * 0.4, z_hip + 0.16, 0.125, 0.055),
        (0.0, -0.175 + lean_y * 0.6, z_hip + 0.26, 0.135, 0.072),
        (0.0, -0.170 + lean_y * 0.7, z_hip + 0.42, 0.128, 0.066),
        (0.0, -0.145 + lean_y * 0.8, z_hip + 0.50, 0.092, 0.044),
    ], segs=10)


def add_arm(bm, uvl, shirt_sw, skin_sw, sh, el, wr, short_sleeve=True):
    if short_sleeve:
        # 短袖衣袖（肩到上臂中段）+ 露小臂与手掌
        mid = Vector(sh).lerp(Vector(el), 0.68)
        add_tapered_limb(bm, uvl, shirt_sw, sh, mid, 0.052, 0.044, segs=10, cap_j0=True, cap_j1=False)
        add_tapered_limb(bm, uvl, skin_sw, mid, el, 0.040, 0.036, segs=10, cap_j0=False, cap_j1=True)
    else:
        add_tapered_limb(bm, uvl, shirt_sw, sh, el, 0.052, 0.042, segs=10, cap_j0=True, cap_j1=True)
    add_tapered_limb(bm, uvl, skin_sw, el, wr, 0.036, 0.028, segs=10, cap_j0=False, cap_j1=False)
    add_ellipsoid(bm, uvl, skin_sw, wr, (0.030, 0.036, 0.042), subdiv=1)


def add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw, hip, knee, ankle, shorts=False, shoe_yaw=0.0, shoe_pitch=0.0, ground_flat=True):
    if shorts:
        mid = Vector(hip).lerp(Vector(knee), 0.78)
        add_tapered_limb(bm, uvl, pants_sw, hip, mid, 0.074, 0.062, segs=10, cap_j0=True, cap_j1=False)
        add_tapered_limb(bm, uvl, skin_sw, mid, knee, 0.056, 0.048, segs=10, cap_j0=False, cap_j1=True)
        add_tapered_limb(bm, uvl, skin_sw, knee, ankle, 0.048, 0.036, segs=10, cap_j0=False, cap_j1=True)
    else:
        add_tapered_limb(bm, uvl, pants_sw, hip, knee, 0.072, 0.056, segs=10, cap_j0=True, cap_j1=True)
        add_tapered_limb(bm, uvl, pants_sw, knee, ankle, 0.054, 0.042, segs=10, cap_j0=False, cap_j1=True)
    add_shoe(bm, uvl, shoe_sw, ankle, yaw_rad=shoe_yaw, pitch_rad=shoe_pitch, ground_flat=ground_flat)


def build_prototype(name, shirt_sw, pants_sw, pose='stand',
                    skin_sw=0, hair_sw=2, hair_style='short_m',
                    collar_sw=5, shoe_sw=12, backpack_sw=None,
                    slim=False, shorts=False, height_scale=1.0):
    """构建一套约 800-950 三角面的圆润建筑配景人物原型（面向 +Y；站/走/跑鞋底 Z=0.0，坐姿臀底 Z=0.0）。"""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    sx = 0.90 if slim else 1.0

    if pose == 'sit':
        # 坐姿：臀部接触面严格位于 Z = 0.0，大腿平伸向 +Y，小腿垂向 Z = -0.36
        z_hip = 0.06
        add_torso(bm, uvl, shirt_sw, collar_sw, pants_sw, z_hip, slim=slim, lean_y=0.02)
        add_head_and_hair(bm, uvl, skin_sw, hair_sw, (0.0, 0.03, z_hip + 0.72), hair_style)
        add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                (-0.09 * sx, 0.02, z_hip), (-0.10 * sx, 0.39, z_hip - 0.01), (-0.10 * sx, 0.42, -0.30),
                shorts=True, ground_flat=False)
        add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                (0.09 * sx, 0.02, z_hip), (0.10 * sx, 0.39, z_hip - 0.01), (0.10 * sx, 0.42, -0.30),
                shorts=True, ground_flat=False)
        # 双臂自然松弛搭于腿侧/膝上
        add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19 * sx, 0.01, z_hip + 0.49), (-0.21 * sx, 0.14, z_hip + 0.25), (-0.13 * sx, 0.30, z_hip + 0.11))
        add_arm(bm, uvl, shirt_sw, skin_sw, (0.19 * sx, 0.01, z_hip + 0.49), (0.21 * sx, 0.15, z_hip + 0.26), (0.14 * sx, 0.31, z_hip + 0.12))
    else:
        lean = 0.08 if pose == 'run' else (0.02 if pose == 'walk' else 0.0)
        z_hip = 0.85 if pose != 'run' else 0.82
        add_torso(bm, uvl, shirt_sw, collar_sw, pants_sw, z_hip, slim=slim, lean_y=lean)
        add_head_and_hair(bm, uvl, skin_sw, hair_sw, (0.0, lean * 1.15, z_hip + 0.72), hair_style)

        if pose == 'walk':
            # 自然大步行走 + 对侧摆臂
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.09 * sx, 0.00, z_hip), (-0.09 * sx, 0.15, 0.45), (-0.09 * sx, 0.22, 0.07),
                    shorts=shorts, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.09 * sx, 0.00, z_hip), (0.09 * sx, -0.10, 0.44), (0.09 * sx, -0.22, 0.08),
                    shorts=shorts, shoe_pitch=-0.22, ground_flat=False)
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19 * sx, lean * 0.9, z_hip + 0.49), (-0.22 * sx, -0.12, z_hip + 0.22), (-0.20 * sx, -0.22, z_hip - 0.02))
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19 * sx, lean * 0.9, z_hip + 0.49), (0.22 * sx, 0.13, z_hip + 0.23), (0.20 * sx, 0.25, z_hip + 0.02))
        elif pose == 'run':
            # 自然足球/田径冲刺奔跑姿态（前倾 + 自然屈肘摆臂，绝不僵尸举手！）
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.095, 0.00, z_hip), (-0.10, 0.26, 0.47), (-0.10, 0.20, 0.075),
                    shorts=True, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.095, 0.00, z_hip), (0.10, -0.18, 0.45), (0.10, -0.36, 0.19),
                    shorts=True, shoe_pitch=-0.45, ground_flat=False)
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19, 0.06, z_hip + 0.48), (-0.24, -0.16, z_hip + 0.24), (-0.20, 0.02, z_hip + 0.16))
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19, 0.06, z_hip + 0.48), (0.24, 0.20, z_hip + 0.26), (0.18, 0.36, z_hip + 0.36))
        elif pose == 'play_shoot':
            # 篮球场投篮/高传球自然动作（仅用于篮球场）
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.10, 0.00, z_hip), (-0.12, 0.12, 0.44), (-0.12, 0.10, 0.07),
                    shorts=True, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.10, 0.00, z_hip), (0.12, -0.10, 0.44), (0.12, -0.14, 0.07),
                    shorts=True, ground_flat=True)
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19, 0.02, z_hip + 0.49), (0.22, 0.18, z_hip + 0.66), (0.12, 0.30, z_hip + 0.84))
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19, 0.02, z_hip + 0.49), (-0.23, 0.15, z_hip + 0.32), (-0.12, 0.28, z_hip + 0.36))
        elif pose == 'play_guard':
            # 篮球/网球屈膝敏捷防守准备姿态
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.11, 0.00, z_hip), (-0.16, 0.14, 0.43), (-0.17, 0.06, 0.07),
                    shorts=True, shoe_yaw=0.22, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.11, 0.00, z_hip), (0.16, 0.10, 0.43), (0.17, -0.04, 0.07),
                    shorts=True, shoe_yaw=-0.22, ground_flat=True)
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19, 0.03, z_hip + 0.48), (-0.29, 0.14, z_hip + 0.28), (-0.34, 0.30, z_hip + 0.34))
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19, 0.03, z_hip + 0.48), (0.29, 0.14, z_hip + 0.28), (0.34, 0.30, z_hip + 0.34))
        elif pose == 'chat':
            # 自然放松侧身交谈姿态
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.09 * sx, 0.00, z_hip), (-0.10 * sx, 0.04, 0.44), (-0.10 * sx, 0.06, 0.07),
                    shorts=shorts, shoe_yaw=0.14, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.09 * sx, 0.00, z_hip), (0.10 * sx, -0.02, 0.44), (0.11 * sx, -0.04, 0.07),
                    shorts=shorts, shoe_yaw=-0.10, ground_flat=True)
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19 * sx, 0.00, z_hip + 0.49), (-0.22 * sx, 0.03, z_hip + 0.21), (-0.18 * sx, 0.10, z_hip - 0.01))
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19 * sx, 0.00, z_hip + 0.49), (0.23 * sx, 0.12, z_hip + 0.25), (0.12 * sx, 0.26, z_hip + 0.24))
        elif pose == 'stand_book':
            # 自然站姿（抱书/文件夹于胸前，贴合校园氛围）
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.085 * sx, 0.00, z_hip), (-0.09 * sx, 0.02, 0.44), (-0.09 * sx, 0.03, 0.07),
                    shorts=shorts, shoe_yaw=0.08, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.085 * sx, 0.00, z_hip), (0.09 * sx, -0.01, 0.44), (0.09 * sx, -0.02, 0.07),
                    shorts=shorts, shoe_yaw=-0.08, ground_flat=True)
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19 * sx, 0.00, z_hip + 0.49), (-0.21 * sx, 0.02, z_hip + 0.22), (-0.17 * sx, 0.05, z_hip - 0.02))
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19 * sx, 0.00, z_hip + 0.49), (0.21 * sx, 0.08, z_hip + 0.24), (0.06 * sx, 0.16, z_hip + 0.26))
            # 笔记本/课本
            add_ellipsoid(bm, uvl, 14, (0.02, 0.16, z_hip + 0.29), (0.10, 0.022, 0.13), subdiv=1)
        else:
            # 自然松弛站立（重心微偏、双臂自然垂放微曲）
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (-0.09 * sx, 0.00, z_hip), (-0.095 * sx, 0.02, 0.44), (-0.095 * sx, 0.03, 0.07),
                    shorts=shorts, shoe_yaw=0.10, ground_flat=True)
            add_leg(bm, uvl, pants_sw, skin_sw, shoe_sw,
                    (0.09 * sx, 0.00, z_hip), (0.095 * sx, -0.01, 0.44), (0.10 * sx, -0.02, 0.07),
                    shorts=shorts, shoe_yaw=-0.10, ground_flat=True)
            add_arm(bm, uvl, shirt_sw, skin_sw, (-0.19 * sx, 0.00, z_hip + 0.49), (-0.22 * sx, -0.01, z_hip + 0.22), (-0.19 * sx, 0.04, z_hip - 0.03))
            add_arm(bm, uvl, shirt_sw, skin_sw, (0.19 * sx, 0.00, z_hip + 0.49), (0.22 * sx, 0.01, z_hip + 0.22), (0.19 * sx, 0.05, z_hip - 0.02))

        if backpack_sw is not None:
            add_backpack(bm, uvl, backpack_sw, z_hip, lean_y=lean)

    if height_scale != 1.0:
        bmesh.ops.scale(bm, vec=(height_scale, height_scale, height_scale), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = fresh_mesh(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(people_mat())
    return me


def ground_z(x, y, dg, sc):
    ok, loc, n, i, ob, _ = sc.ray_cast(dg, Vector((x, y, 40)), Vector((0, 0, -1)))
    return loc.z if ok else 0.0


def main():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    # 16 色板索引: 0暖肤 1浅肤 2黑发 3深棕发 4白校服 5领边 6藏青裤 7教师浅蓝 8教师米白 9深灰裤 10蓝球衣 11红球衣 12白鞋 13深灰鞋 14藏青包 15酒红包
    protos = {
        'Student_Walk_M':  build_prototype('People_Student_Walk_M',  4, 6, 'walk',       skin_sw=0, hair_sw=2, hair_style='short_m',  shoe_sw=12, backpack_sw=14, height_scale=0.99),
        'Student_Walk_F':  build_prototype('People_Student_Walk_F',  4, 6, 'walk',       skin_sw=1, hair_sw=3, hair_style='ponytail', shoe_sw=12, backpack_sw=15, slim=True, height_scale=0.95),
        'Student_Stand_M': build_prototype('People_Student_Stand_M', 4, 6, 'stand',      skin_sw=0, hair_sw=2, hair_style='short_m',  shoe_sw=12, height_scale=0.98),
        'Student_Stand_F': build_prototype('People_Student_Stand_F', 4, 6, 'stand_book', skin_sw=1, hair_sw=2, hair_style='bob',      shoe_sw=12, slim=True, height_scale=0.94),
        'Student_Chat':    build_prototype('People_Student_Chat',    4, 6, 'chat',       skin_sw=0, hair_sw=3, hair_style='short_m',  shoe_sw=13, height_scale=0.97),
        'Student_Sit_M':   build_prototype('People_Student_Sit_M',   4, 6, 'sit',        skin_sw=0, hair_sw=2, hair_style='short_m',  shoe_sw=12, height_scale=0.98),
        'Student_Sit_F':   build_prototype('People_Student_Sit_F',   4, 6, 'sit',        skin_sw=1, hair_sw=3, hair_style='ponytail', shoe_sw=12, slim=True, height_scale=0.95),
        'Sport_Blue_Run':  build_prototype('People_Sport_Blue_Run',  10, 6, 'run',       skin_sw=0, hair_sw=2, hair_style='short_m',  collar_sw=10, shoe_sw=12, shorts=True, height_scale=1.00),
        'Sport_Red_Run':   build_prototype('People_Sport_Red_Run',   11, 9, 'run',       skin_sw=0, hair_sw=2, hair_style='short_m',  collar_sw=11, shoe_sw=13, shorts=True, height_scale=1.00),
        'Sport_Blue_Play': build_prototype('People_Sport_Blue_Play', 10, 6, 'play_guard',skin_sw=0, hair_sw=2, hair_style='short_m',  collar_sw=10, shoe_sw=12, shorts=True, height_scale=1.01),
        'Sport_Red_Play':  build_prototype('People_Sport_Red_Play',  11, 9, 'play_shoot',skin_sw=0, hair_sw=2, hair_style='short_m',  collar_sw=11, shoe_sw=12, shorts=True, height_scale=1.01),
        'Teacher_Stand':   build_prototype('People_Teacher_Stand',   7, 9, 'stand_book', skin_sw=0, hair_sw=2, hair_style='short_m',  collar_sw=4,  shoe_sw=13, height_scale=1.04),
        'Teacher_Walk':    build_prototype('People_Teacher_Walk',    8, 9, 'walk',       skin_sw=1, hair_sw=3, hair_style='bob',      collar_sw=8,  shoe_sw=13, slim=True, height_scale=1.01),
    }

    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    random.seed(2026)

    for idx, p in enumerate(D['people']):
        k = p['kind']
        me = protos.get(k) or protos['Student_Stand_M']
        px, py = p['x'], p['y']
        zone = p.get('zone', '')
        yaw_deg = p['yaw']
        if zone == 'bleachers':
            # 按新看台 8 级阶梯（track_local x in [-52.10, -45.70], h_tot=4.40）精准对齐踏步前缘并面朝跑道
            S_tr = json.load(open(os.path.join(ROOT, 'data', 'site.json')))['track']
            tcx, tcy = S_tr['center']
            tang = math.radians(S_tr['long_axis_deg_west_of_north'])
            ca, sa = math.cos(tang), math.sin(tang)
            dx, dy = px - tcx, py - tcy
            ly = max(-84.0, min(-22.0, -dx * sa + dy * ca))
            # 均匀分布在第 1..6 级踏步前缘内缩 0.22 m 处（臀部贴实、双腿垂在踏步外绝不穿模）
            k_tier = (idx % 5) + 1
            step_w = 6.40 / 7.0
            lx = -52.10 + (k_tier + 1) * step_w - 0.22
            px = tcx + lx * ca - ly * sa
            py = tcy + lx * sa + ly * ca
            z = 1.12 + (4.62 - 1.12) * (1.0 - k_tier / 6.0) + 0.02
            # 原型面向 +Y；旋转至跑道局部 +X (ca, sa) => (-sin(yaw), cos(yaw)) = (ca, sa) => yaw = ang - 90 deg
            yaw_deg = S_tr['long_axis_deg_west_of_north'] - 90.0
        elif zone == 'star_courtyard_steps':
            # 按 15 级扇形大台阶精确公式对齐踏步前缘与实际顶面高程（杜绝半埋入台阶！）
            steps_n = 15
            step_d = 14.5 / steps_n
            si = max(1, min(steps_n - 1, int(round((-55.0 - py) / step_d))))
            if 'Sit' in k:
                # 坐在第 si 级踏步前缘内缩 0.24 m 处，双腿自然垂在踏步立面前方
                py = -55.0 - (si - 1) * step_d - 0.24
            else:
                py = -55.0 - (si - 0.5) * step_d
            z = 0.08 + (4.5 - 0.08) * (si / steps_n) + (0.02 if 'Sit' in k else 0.0)
        else:
            z = p['z'] if 'z' in p else ground_z(px, py, dg, sc)
            if zone == 'star_courtyard_z0' and z < 0.07:
                z = 0.08
        o = bpy.data.objects.new(f'People_{k}_{idx:03d}', me)
        o.location = (px, py, z)
        o.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
        sc_j = random.uniform(0.96, 1.04)
        o.scale = (sc_j, sc_j, sc_j)
        c.objects.link(o)

    bpy.ops.wm.save_mainfile()
    print('people placed', len(c.objects), 'across', len(protos), 'instanced prototypes')
    for k, me in protos.items():
        me.calc_loop_triangles()
        zs = [v.co.z for v in me.vertices]
        print(f'  proto {k:16s}: tris={len(me.loop_triangles):4d} z=[{min(zs):6.3f}, {max(zs):6.3f}]')


main()
