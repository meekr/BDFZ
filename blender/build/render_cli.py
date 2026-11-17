"""P7 命令行渲染（Cycles，Metal GPU）：
/Applications/Blender.app/Contents/MacOS/Blender -b blender/bdfz.blend --python blender/build/render_cli.py -- <id|all> [samples] [pct] [out_dir]"""
import bpy, sys, os
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
vid = argv[0] if argv else 'all'
samples = int(argv[1]) if len(argv) > 1 else 128
pct = int(argv[2]) if len(argv) > 2 else 100
out_dir = argv[3] if len(argv) > 3 else None
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'; prefs.get_devices()
for d in prefs.devices:
    d.use = d.type != 'CPU'
exec(open('/Users/perrylei/repos/BDFZ_V3/blender/build/views.py').read())
ids = [v['id'] for v in V['views']] if vid == 'all' else vid.split(',')
for i in ids:
    out = os.path.join(out_dir, f'{i}.png') if out_dir else None
    print('rendered', render_view(i, engine='CYCLES', samples=samples, pct=pct, out=out))
