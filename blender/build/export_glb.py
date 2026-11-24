"""P7 导出 web/public/bdfz.glb（glTF 2.0，Draco 压缩，重复构件按 EXT_mesh_gpu_instancing 实例化）。
/Applications/Blender.app/Contents/MacOS/Blender -b blender/bdfz.blend --python blender/build/export_glb.py
每个节点写 extras：layer（building / landscape / site）与 bldg（建筑编号，供网页标注与信息卡）。"""
import bpy, os
ROOT = '/Users/perrylei/repos/BDFZ'
OUT = os.path.join(ROOT, 'web', 'public', 'bdfz.glb')
LAYER = {'Bldg_': 'building', 'Landscape': 'landscape', 'Site': 'site', 'People': 'people'}

keep = []
for c in bpy.data.collections:
    layer = next((v for k, v in LAYER.items() if c.name.startswith(k)), None)
    if layer is None:
        continue
    for o in c.all_objects:
        if o.type != 'MESH' or o.name == 'Landscape_FarGround':
            continue
        o['layer'] = layer
        o['bldg'] = c.name if layer == 'building' else ''
        keep.append(o)
# Blender 的 EXT_mesh_gpu_instancing 只对同一空物体下共用网格的子物体生效：按网格分组挂到空物体下（只在导出进程里改，不保存）
groups = {}
for o in keep:
    if o.data.users > 1:
        groups.setdefault(o.data.name, []).append(o)
for mname, objs in groups.items():
    e = bpy.data.objects.new(f'Inst_{mname}', None)
    objs[0].users_collection[0].objects.link(e)
    e['layer'] = objs[0]['layer']; e['bldg'] = objs[0]['bldg']
    for o in objs:
        mw = o.matrix_world.copy(); o.parent = e; o.matrix_world = mw
    keep.append(e)
bpy.ops.object.select_all(action='DESELECT')
for o in keep:
    o.hide_set(False); o.select_set(True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', use_selection=True, export_apply=True, export_extras=True,
    export_yup=True, export_gpu_instances=True, export_cameras=False, export_lights=False,
    export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
    export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12,
    export_image_format='WEBP', export_materials='EXPORT')
print('exported', len(keep), 'objects', os.path.getsize(OUT) / 1e6, 'MB')
