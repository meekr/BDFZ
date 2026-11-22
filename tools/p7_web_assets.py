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
    cloud, p3, dorm, sports = load('bldg_cloud.json'), load('bldg_cloud_p3.json'), load('bldg_dorm.json'), load('bldg_sports.json')
    L = cloud['levels']; DL = dorm['levels']; SL = sports['levels']
    ncols = len(p3['columns'])
    bldgs = [
        dict(id='Bldg_Cloud', name='学术中心', sub='S 形建筑带 · 星形庭院',
             facts=[f"南翼 5 层（屋面 +{L['eave']['south']} m），北翼 4 层（挑檐 +{L['eave']['north']} m），沿 −10° 轴平滑过渡",
                    '直立锁边金属坡屋面 + 东西北三处条形天窗；星形庭院三维开敞外廊、三大错落台地与扇形大台阶',
                    f"架空层柱 {ncols} 根（柱底落至 ±0.00 广场地坪）：北翼 8.4 m 全斜柱，南翼 4.2 m 竖 2 斜 1",
                    '南侧两座低层附楼：东块 +3.5 m 带采光天井，西块 +4.5→+1.5 m 缓坡露台'],
             src='05 剖面、02 屋顶平面；P6 十张实景照片（wx_01/03/08/09/14/15/18/23/35）联合校正'),
        dict(id='Bldg_Dorm', name='宿舍综合楼', sub='4 大庭院 + 17 小庭院',
             facts=[f"{DL['floors']} 层，±0.00 = Z {DL['ground']}，屋顶悬挑金属遮阳构架（顶约 Z 19 m）",
                    '外墙竖向窄窗 + 空调百叶 + 开敞楼梯阳台；4 处大庭院白墙外廊与草坪，17 处小庭院架高遮阳棚',
                    '西北连接体采用深灰蓝金属坡屋面（Z 13.8→7.5 m）衔接学术中心'],
             src='08 宿舍平面、13 等轴示意、02 屋顶平面；照片 wx_03/08/11/26/27/31/33/34 核对'),
        dict(id='Bldg_SportsArt', name='体育及艺术中心', sub='L 形 · 泳池 / 篮球馆 / 剧场',
             facts=[f"2 层，±0.00 = Z {SL['ground']}；西翼檐口 Z {SL.get('eave_west', SL['eave'])}（屋脊 Z {SL['ridge']}）",
                    f"东南翼自西向东平滑下坡至檐口 Z {SL.get('eave_east', 3.5)} m 衔接学术中心",
                    '深蓝灰金属坡屋面配浅灰檐口压顶；西翼东侧面向 400 m 田径场设 9 级混凝土看台'],
             src='02 屋顶平面、08 长轴剖透视；照片 wx_03/04/19/31/35/36 校正'),
    ]
    info = dict(note='坐标：Blender 世界坐标（米，Z 向上，+X 东 +Y 北）；网页按 glTF 转为 (x, z, −y)。',
                views=load('views.json'), tour=load('tour_stops.json'), overlays=dict(extent=EXT, z=0.3, items=ov), buildings=bldgs)
    json.dump(info, open(os.path.join(OUT, 'scene.json'), 'w'), ensure_ascii=False, indent=1)
    print('wrote', [o['file'] for o in ov], 'scene.json')


if __name__ == '__main__':
    main()
