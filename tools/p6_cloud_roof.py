"""P6 学术中心屋面：坡屋面的平面数据 → data/bldg_cloud_roof.json（三角网在 Blender 中生成，blender/build/bldg_cloud.py）。

照片（wx_01、wx_08、wx_35）：金属板屋面沿每翼中线有屋脊，转角处有斜脊，外缘一圈浅色圆角檐口。
05 剖面画成平屋面加收薄檐口，说明坡度很小：取排水坡 SLOPE（推定），屋脊只高出檐口约 0.5 m。
屋脊平面位置 = 到屋面外缘与庭院缘距离的脊线（翼宽约 21.6 m，脊距外缘约 10.8 m）；
wx_01 中东北翼的屋脊折线与该脊线投影重合。翼交汇处距离更大，按 CAP 截平。

输出：panel = 外缘内收 RIM 后的屋面板区域（多边形带洞），edge = 屋面外缘与庭院缘（量距离用）。
建模时 z = 屋面标高(y) + SLOPE × min(d, CAP)，d 为到 edge 的距离。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worldgrid as wg, p2_cloud as PC, p3_cloud as P3

SLOPE = 0.05
CAP = 11.0
RIM = 1.2


def main():
    shell = P3.shell_mask()
    panel = PC.polys(PC.offset(shell, -RIM), eps=0.1, min_area=4)
    edge = PC.polys(shell, eps=0.1, min_area=4)
    out = dict(source='tools/p6_cloud_roof.py：照片所见屋脊/斜脊 + 05 剖面（近平屋面）', slope=SLOPE, cap=CAP, rim=RIM,
               note='z = 屋面标高（P3 levels.roof，南北线性过渡）+ slope × min(d, cap)；坡度为推定',
               panel=panel, edge=edge)
    json.dump(out, open(os.path.join(wg.ROOT, 'data', 'bldg_cloud_roof.json'), 'w'), ensure_ascii=False)
    print('panel parts', len(panel), [len(p['holes']) for p in panel], 'edge parts', len(edge))


if __name__ == '__main__':
    main()
