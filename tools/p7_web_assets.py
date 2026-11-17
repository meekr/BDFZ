"""P7 网页资源 → web/public/：2024 图纸叠图（按 data/frames.json 重采样到世界网格）、标准视点、建筑信息。"""
import os, sys, json, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg

OUT = os.path.join(wg.ROOT, 'web', 'public')
EXT = (-330.0, -220.0, 330.0, 220.0)
RES = 0.4
OVERLAYS = {'01': ('overlay_01.jpg', '2024 彩色总平面（01）'), '02': ('overlay_02.jpg', '2024 屋顶平面（02）')}


def load(name):
    return json.load(open(os.path.join(wg.ROOT, 'data', name)))


def main():
    os.makedirs(OUT, exist_ok=True)
    ov = []
    for key, (fn, label) in OVERLAYS.items():
        im = wg.warp(key, res=RES, extent=EXT, interp=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(OUT, fn), im, [cv2.IMWRITE_JPEG_QUALITY, 82])
        ov.append(dict(id=key, file=fn, label=label))
    cloud, dorm, sports = load('bldg_cloud.json'), load('bldg_dorm.json'), load('bldg_sports.json')
    L = cloud['levels']; DL = dorm['levels']; SL = sports['levels']
    bldgs = [
        dict(id='Bldg_Cloud', name='学术中心', sub='S 形建筑带 · 星形庭院',
             facts=[f"南翼 5 层：架空 +{L['south'][0]:.0f} m，屋面 +{L['eave']['south']} m",
                    f"北翼 4 层：架空 ±0，挑檐 +{L['eave']['north']} m",
                    '金属板坡屋面，屋脊沿各翼中线（坡度推定 5%）', '架空层柱 184 根：北翼斜柱，南翼竖柱 2 + 斜柱 1',
                    '内院图书馆、南侧两座一层附楼'],
             src='05 剖面、02 屋顶平面；照片 wx_01/08/18/35 校正'),
        dict(id='Bldg_Dorm', name='宿舍综合楼', sub='16 个小庭院',
             facts=[f"{DL['floors']} 层，层高 {DL['floor_h']} m（推定）", f"±0.00 = Z {DL['ground']}，女儿墙 {DL['parapet']} m",
                    '高中、初中与职工宿舍单元'],
             src='08 宿舍平面、13 等轴示意；02 屋顶平面'),
        dict(id='Bldg_SportsArt', name='体育及艺术中心', sub='L 形 · 泳池 / 篮球馆 / 剧场',
             facts=[f"2 层，±0.00 = Z {SL['ground']}", f"檐口 Z {SL['eave']}，屋脊 Z {SL['ridge']}（wx_35 校正）", '四坡金属屋面沿 L 形两翼'],
             src='02 屋顶平面、07 长轴剖面；照片 wx_35'),
    ]
    info = dict(note='坐标：Blender 世界坐标（米，Z 向上，+X 东 +Y 北）；网页按 glTF 转为 (x, z, −y)。',
                views=load('views.json'), overlays=dict(extent=EXT, z=0.3, items=ov), buildings=bldgs)
    json.dump(info, open(os.path.join(OUT, 'scene.json'), 'w'), ensure_ascii=False, indent=1)
    print('wrote', [o['file'] for o in ov], 'scene.json')


if __name__ == '__main__':
    main()
