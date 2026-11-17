"""导出模型特征边（边界边 + 折角 > 30° 的边）上的采样点，供照片相机匹配用。→ data/_feature_pts.npz"""
import bpy, bmesh, math, numpy as np
ROOT = '/Users/perrylei/repos/BDFZ_V3'
GROUPS = {
    'cloud_roof': ['Bldg_Cloud_Slab_roof'],
    'cloud_slab': ['Bldg_Cloud_Slab_f1', 'Bldg_Cloud_Slab_f2', 'Bldg_Cloud_Slab_f3'],
    'track': ['Site_Track_Surface', 'Site_Track_Infield'],
    'dorm': ['Bldg_Dorm_Mass', 'Bldg_Dorm_Link'],
    'sports': ['Bldg_SportsArt_Mass'],
    'annex': ['Bldg_Cloud_Annex_S_East', 'Bldg_Cloud_Annex_S_West'],
    'courts': ['Site_Court_tennis_N_Lines', 'Site_Court_tennis_S_Lines', 'Site_Court_basket_W_Lines', 'Site_Court_basket_NE_Lines'],
}
STEP = 0.8
out = {}
dg = bpy.context.evaluated_depsgraph_get()
for g, names in GROUPS.items():
    P = []
    # 重建脚本多次运行后对象名可能带 .00N 后缀
    objs = [o for n in names for o in bpy.data.objects if o.type == 'MESH' and (o.name == n or o.name.startswith(n + '.'))]
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world)
        for e in bm.edges:
            fs = e.link_faces
            if len(fs) == 2 and fs[0].normal.angle(fs[1].normal, 0) < math.radians(30):
                continue
            a, b = e.verts[0].co, e.verts[1].co
            L = (b - a).length; k = max(1, int(L / STEP))
            for i in range(k + 1):
                P.append(tuple(a.lerp(b, i / k)))
        bm.free(); o.evaluated_get(dg).to_mesh_clear()
    P = np.unique(np.round(np.array(P), 1), axis=0)
    out[g] = P
    print(g, len(P))
np.savez(ROOT + '/data/_feature_pts.npz', **out)
