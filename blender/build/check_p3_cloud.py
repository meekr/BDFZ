import bpy, json
lv = {'f1': (10.0, 8.0), 'f2': (14.5, 12.5), 'f3': (19.0, 17.0), 'roof': (23.5, 19.0)}
res = {}
for k, (s, n) in lv.items():
    o = bpy.data.objects['Bldg_Cloud_Slab_' + k]
    zs_n = [v.co.z for v in o.data.vertices if v.co.y > 0]
    zs_s = [v.co.z for v in o.data.vertices if v.co.y < -100]
    tn, ts = max(zs_n), max(zs_s)
    res[k] = dict(north=round(tn, 3), north_ref=n, south=round(ts, 3), south_ref=s,
                  err=round(max(abs(tn - n), abs(ts - s)), 3))
cols = [o for o in bpy.data.objects if o.name.startswith('Bldg_Cloud_Column_')]
res['columns'] = len(cols)
json.dump(res, open('/Users/perrylei/repos/BDFZ/data/_p3_cloud_gate.json', 'w'), indent=1)
print(json.dumps(res))
