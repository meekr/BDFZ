"""P6：按 data/cameras.json 在 Blender 中建立匹配相机（REF_Cameras 集合），工作台渲染，与照片半透明叠加 → checks/photo_match_*.jpg。
在 Blender 内执行：exec(open('.../blender/build/ref_cameras.py').read())；叠图由 tools/p6_overlay.py 完成。"""
import bpy, json, math, os
from mathutils import Matrix, Vector
ROOT = '/Users/perrylei/repos/BDFZ'
OUT = os.path.join(ROOT, 'checks', '_renders')
D = json.load(open(os.path.join(ROOT, 'data', 'cameras.json')))
W_WORK = D['W_WORK']


def basis(yaw, pitch, roll):
    y, p, r = (math.radians(v) for v in (yaw, pitch, roll))
    d = Vector((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)))
    rt = d.cross(Vector((0, 0, 1))).normalized()
    up = rt.cross(d)
    cr, sr = math.cos(r), math.sin(r)
    return d, cr * rt + sr * up, -sr * rt + cr * up


coll = bpy.data.collections.get('REF_Cameras')
if coll is None:
    coll = bpy.data.collections.new('REF_Cameras'); bpy.context.scene.collection.children.link(coll)
for name, c in D['cameras'].items():
    p = c['p']
    d, rt, up = basis(*p[3:6])
    cam_name = f'REF_Cam_{name}'
    cd = bpy.data.cameras.get(cam_name) or bpy.data.cameras.new(cam_name)
    cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36.0
    cd.lens = p[6] / W_WORK * 36.0
    cd.clip_start = 1.0; cd.clip_end = 5000.0
    o = bpy.data.objects.get(cam_name)
    if o is None:
        o = bpy.data.objects.new(cam_name, cd); coll.objects.link(o)
    o.data = cd
    M = Matrix((rt, up, -d)).transposed().to_4x4()
    M.translation = Vector(p[:3])
    o.matrix_world = M
    o['photo'] = c['photo']


def render_all(names=None):
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    keep = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage, sc.render.engine,
            sc.render.filepath)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_object_outline = True; sh.show_cavity = True
    # 树木与参考底图会遮挡建筑轮廓，检查渲染时隐藏
    hidden = [o for o in bpy.data.objects if (o.name.startswith('Landscape_Tree') or o.name.startswith('REF_'))
              and o.type != 'CAMERA' and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    for name, c in D['cameras'].items():
        if names and name not in names:
            continue
        sc.camera = bpy.data.objects[f'REF_Cam_{name}']
        sc.render.resolution_x, sc.render.resolution_y = c['size']
        sc.render.resolution_percentage = 100
        sc.render.filepath = os.path.join(OUT, f'{name}.png')
        bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage, sc.render.engine,
     sc.render.filepath) = keep
