"""P2 重新标定：P0 的图纸帧整体偏移。用 02_cloud（单栋拟合，全图叠合验证）求出世界→世界校正，作用到所有图纸帧。"""
import os, json, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, 'data', 'frames.json')
FR = json.load(open(p))
H = lambda m: np.vstack([np.array(m), [0, 0, 1]])
if 'frames_p0' not in FR:
    FR['frames_p0'] = {k: v for k, v in FR['frames'].items() if k != '02_cloud'}
old02 = H(FR['frames_p0']['02']['px_to_world'])
new02 = H(FR['frames']['02_cloud']['px_to_world'])
C = new02 @ np.linalg.inv(old02)
s = float(np.hypot(C[0, 0], C[1, 0])); rot = float(np.degrees(np.arctan2(C[1, 0], C[0, 0])))
print('correction scale %.4f rot %.3f deg t' % (s, rot), C[:2, 2].round(2))
for k, f in FR['frames_p0'].items():
    T = C @ H(f['px_to_world'])
    nf = dict(f); nf['px_to_world'] = T[:2].round(8).tolist()
    nf['px_per_m'] = round(1 / float(np.hypot(T[0, 0], T[1, 0])), 4)
    FR['frames'][k] = nf
FR['frames']['02_cloud'] = dict(FR['frames']['02'], note='别名，= 02（P2 重标定后）')
FR['correction_p2'] = dict(matrix=C[:2].round(8).tolist(), scale=round(s, 4), rot_deg=round(rot, 3),
    note='2026-11-17：P0 图纸帧整体偏移。02 对卫星学术中心屋面单栋倒角拟合后，全图（宿舍、体育中心、跑道、球场）同时吻合，'
         '故把同一校正作用于 01/02/03/04。旧帧保留在 frames_p0')
FR['world']['origin'] = '固定地理点 origin_latlon（P0 时按旧帧取的"庭院质心"，P2 重标定后不再是庭院中心；坐标系不变）'
json.dump(FR, open(p, 'w'), ensure_ascii=False, indent=1)
