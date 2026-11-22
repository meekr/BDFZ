"""P7 标准视点：按 data/views.json 建立 VIEW_Cameras 集合中的相机，并渲染标准图 → renders/<id>.jpg。
在 Blender 内执行：exec(open('.../blender/build/views.py').read())；然后 render_view('aerial', engine='CYCLES')。"""
import bpy, json, os, math
from mathutils import Vector
ROOT = '/Users/perrylei/repos/BDFZ_V3'
V = json.load(open(os.path.join(ROOT, 'data', 'views.json')))
OUT = os.path.join(ROOT, 'renders')
RES = (1920, 1080)

coll = bpy.data.collections.get('VIEW_Cameras')
if coll is None:
    coll = bpy.data.collections.new('VIEW_Cameras'); bpy.context.scene.collection.children.link(coll)
for v in V['views']:
    n = f"VIEW_{v['id']}"
    cd = bpy.data.cameras.get(n) or bpy.data.cameras.new(n)
    cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36.0; cd.lens = v['lens']
    cd.clip_start = 0.5; cd.clip_end = 6000.0
    o = bpy.data.objects.get(n)
    if o is None:
        o = bpy.data.objects.new(n, cd); coll.objects.link(o)
    o.data = cd
    o.location = v['eye']
    o.rotation_euler = (Vector(v['target']) - Vector(v['eye'])).to_track_quat('-Z', 'Y').to_euler()


def _sanitize_blender_jpeg(path):
    """无损剔除 Blender 写入的非标准 JPEG 段（APP1 NeoGeo、0-based 畸形 APP2 ICC_PROFILE、COM 注释），
    避免严格 JPEG 解码器（如 Google API）报 INVALID_MEDIA。"""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 4 or data[:2] != b'\xff\xd8':
        return
    out = bytearray(b'\xff\xd8')
    pos, n = 2, len(data)
    while pos < n:
        if data[pos] != 0xff:
            out.extend(data[pos:])
            break
        while pos < n and data[pos] == 0xff:
            pos += 1
        if pos >= n:
            break
        marker = data[pos]
        pos += 1
        if marker == 0xda:  # SOS：后续压缩流原样保留
            out.extend((0xff, marker))
            out.extend(data[pos:])
            break
        if marker == 0xd9:  # EOI
            out.extend((0xff, marker))
            break
        if 0xd0 <= marker <= 0xd7 or marker == 0x01:
            out.extend((0xff, marker))
            continue
        if pos + 2 > n:
            out.extend((0xff, marker))
            out.extend(data[pos:])
            break
        seg_len = (data[pos] << 8) | data[pos + 1]
        seg_end = pos + seg_len
        payload = data[pos + 2:seg_end]
        drop = (
            (marker == 0xe1 and payload.startswith(b'NeoGeo'))
            or (marker == 0xe2 and payload.startswith(b'ICC_PROFILE\x00') and len(payload) >= 14 and payload[12] == 0)
            or marker == 0xfe
        )
        if not drop:
            out.extend((0xff, marker))
            out.extend(data[pos:seg_end])
        pos = seg_end
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, path)


def render_view(vid, engine='CYCLES', samples=128, pct=100, out=None):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[f'VIEW_{vid}']
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = pct
    hidden = [o for o in bpy.data.objects if o.name.startswith('REF_') and o.type != 'CAMERA' and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    sc.render.engine = engine
    if engine == 'CYCLES':
        sc.cycles.device = 'GPU'; sc.cycles.samples = samples; sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
    os.makedirs(OUT, exist_ok=True)
    sc.render.filepath = out or os.path.join(OUT, f'{vid}.jpg')
    fmt = sc.render.image_settings
    fmt.file_format = 'JPEG' if sc.render.filepath.endswith('.jpg') else 'PNG'
    if fmt.file_format == 'JPEG':
        fmt.quality = 92
    bpy.ops.render.render(write_still=True)
    if fmt.file_format == 'JPEG' and os.path.isfile(sc.render.filepath):
        _sanitize_blender_jpeg(sc.render.filepath)
    for o in hidden:
        o.hide_render = False
    return sc.render.filepath
