"""T2–T5 分包 GLB 导出管线（Draco 压缩 + EXT_mesh_gpu_instancing）：
- web/public/bdfz.glb            (室外主包：建筑外壳 + 场地 + 景观 + 师生人物)
- web/public/interior_sports.glb (体育及艺术中心室内：泳池 + 双篮球馆 + 大剧场 + 门厅)
- web/public/interior_cloud.glb  (学术中心室内：图书馆 + 艺术馆展厅 + 3F 教室与外廊)
- web/public/interior_dorm.glb   (宿舍综合楼高中示范单元)
- web/public/nav_collision.glb   (不可见轻量化步行导航与碰撞网)

运行：/Applications/Blender.app/Contents/MacOS/Blender -b blender/bdfz.blend --python blender/build/export_chunks.py
"""
import bpy, os

ROOT = '/Users/perrylei/repos/BDFZ_V3'
PUB = os.path.join(ROOT, 'web', 'public')
os.makedirs(PUB, exist_ok=True)


def export_subset(filename, coll_map):
    """按集合映射分组实例化并导出独立 GLB（不保存修改回 .blend）。"""
    keep = []
    temp_empties = []
    orig_parents = {}

    for c in bpy.data.collections:
        layer = next((v for k, v in coll_map.items() if c.name.startswith(k)), None)
        if layer is None:
            continue
        for o in c.all_objects:
            if o.type != 'MESH' or o.name == 'Landscape_FarGround':
                continue
            o['layer'] = layer
            o['bldg'] = c.name if layer == 'building' else ''
            keep.append(o)

    if not keep:
        print('SKIP empty chunk:', filename)
        return

    # 按共享网格打包到临时空物体下，触发 EXT_mesh_gpu_instancing
    groups = {}
    for o in keep:
        if o.data.users > 1:
            groups.setdefault(o.data.name, []).append(o)
    for mname, objs in groups.items():
        if len(objs) < 2:
            continue
        e = bpy.data.objects.new(f'Inst_{mname}', None)
        objs[0].users_collection[0].objects.link(e)
        e['layer'] = objs[0]['layer']
        e['bldg'] = objs[0]['bldg']
        for o in objs:
            orig_parents[o] = (o.parent, o.matrix_world.copy())
            mw = o.matrix_world.copy()
            o.parent = e
            o.matrix_world = mw
        keep.append(e)
        temp_empties.append(e)

    bpy.ops.object.select_all(action='DESELECT')
    for o in keep:
        o.hide_set(False)
        o.select_set(True)

    out_path = os.path.join(PUB, filename)
    bpy.ops.export_scene.gltf(
        filepath=out_path, export_format='GLB', use_selection=True, export_apply=True, export_extras=True,
        export_yup=True, export_gpu_instances=True, export_cameras=False, export_lights=False,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12,
        export_image_format='WEBP', export_image_quality=92, export_materials='EXPORT'
    )
    mb = os.path.getsize(out_path) / 1e6
    print(f'CHUNK {filename:22s}: {len(keep):4d} objs | {mb:.3f} MB')

    # 恢复父子关系并清理临时空物体，确保后续分包导出干净无污染
    for o, (par, mw) in orig_parents.items():
        o.parent = par
        o.matrix_world = mw
    for e in temp_empties:
        bpy.data.objects.remove(e, do_unlink=True)


def main():
    export_subset('bdfz.glb', {'Bldg_': 'building', 'Landscape': 'landscape', 'Site': 'site', 'People': 'people'})
    export_subset('interior_sports.glb', {'Interior_Sports': 'interior_sports'})
    export_subset('interior_cloud.glb',  {'Interior_Cloud': 'interior_cloud'})
    export_subset('interior_dorm.glb',   {'Interior_Dorm': 'interior_dorm'})
    export_subset('nav_collision.glb',   {'Nav_Collision': 'nav'})


main()
