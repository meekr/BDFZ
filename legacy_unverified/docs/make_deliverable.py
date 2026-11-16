# -*- coding: utf-8 -*-
"""把检索到的官方设计图纸整理为离线可浏览的图纸集。"""
import os, re, shutil, base64, io, html
from urllib.parse import quote
from PIL import Image

ROOT = '/Users/perrylei/WorkBuddy/2026-11-13-09-36-33'
SRC = f'{ROOT}/research/plans'
OUT = f'{ROOT}/北大附中海口学校_设计图纸集'
A = f'{OUT}/01_建成版官方图纸_2024'
B = f'{OUT}/02_方案阶段图纸_2020'
for d in [OUT, A, B]:
    os.makedirs(d, exist_ok=True)

# ---------- 2024 建成版：ArchDaily 中文版项目图库（图纸 © Crossboundaries） ----------
rows = [l.rstrip('\n').split('\t') for l in open(f'{SRC}/archdaily/manifest.txt', encoding='utf-8')]
names24 = [
    '平面图（彩色总平面·功能分区与层数标高）',
    '屋顶平面图',
    '总平面图（线稿·带尺寸标注与图例）',
    '三层平面图（学术中心·含功能图例与 50m 比例尺）',
    '剖面图（长向线稿·带图例）',
    '短轴剖面（剖透视）',
    '长轴剖面（S 形建筑带全貌剖透视）',
    '宿舍平面图（彩色单元平面·含材料色彩表与图例）',
    '高中宿舍 1（单元轴测剖切）',
    '高中宿舍 2（单元轴测剖切）',
    '初中宿舍（单元轴测剖切）',
    '职工宿舍（单元轴测剖切）',
    '宿舍局部等轴示意图（16 个小庭院阵列）',
    '学术中心等轴示意图（X 形连廊与中央庭院）',
]
desc24 = [
    '带功能分区中文标注：学术中心 / 宿舍综合楼 / 体育及艺术中心；2F、4F、5F 层数；场地标高；400m 跑道；四个出入口；右下角比例尺与指北针。建模最有用的一张。',
    '全校屋顶平面，可见 S 形连续建筑带、学术中心圆角菱形、宿舍四单元与田径场轮廓；下方带图例。',
    '线稿总平面，含尺寸链、轴网、标高与图例，可量测；与 2020 方案总图为同一套坐标系。',
    '学术中心三层教室平面：初中/高中书院、教师办公、公共活动、卫生间、露天庭院共 8 类功能图例；右下角 0–5–10–20–50m 比例尺与指北针。',
    '横向线稿剖面，展示建筑带沿地形起伏的层叠关系与底部架空。',
    '渲染剖透视，展示学术中心底部公共层与层层悬挑。',
    '长向剖透视：左体育艺术中心 → 中学术中心 → 右宿舍，可看见室内分层与红色人形尺度参照。',
    '宿舍单元彩色平面 + 房间类型图例 + 材料/色彩表，是宿舍单体最详细的一张。',
    '高中宿舍单元轴测剖切，右侧为英文空间说明。',
    '高中宿舍另一单元轴测剖切，可见套间与公共客厅。',
    '初中宿舍单元轴测剖切。',
    '职工宿舍单元轴测剖切。',
    '宿舍局部俯视轴测，清楚显示 4 大庭院 + 16 个 10m 净宽小庭院的阵列与晾衣区。',
    '学术中心俯视轴测，显示中央 X 形连廊、四叶庭院与错落教室体块，紧邻田径场。',
]

# ---------- 2020 方案阶段：有方《云朵般漂浮的教学楼》 ----------
scheme_files = sorted(f for f in os.listdir(f'{SRC}/scheme2020') if re.match(r'^D\d\d_', f))
scheme_names = [
    'SITE-PLAN 总平面', 'SITE-ANALYSIS 基地分析', 'OVERALL-DIAGRAMS 总体布局',
    'long-section 长轴剖面', 'LEARNING-CENTER 学术中心功能分区',
    'LEARNING-CENTER-ZOOMIN 学术中心等轴示意图', 'cross-section 短轴剖面',
    'DORMITORY-COMPLEX 宿舍功能分区', 'PUBLIC-SERVICE 公共服务功能分区',
    'DORM-ZOOMIN 宿舍局部等轴示意图', 'DORM-UNIT 宿舍单元',
    'ART-CENTER 艺术中心功能分区', 'SPORT-CENTER 体育中心功能分区',
]
scheme_desc = [
    '2020 方案阶段总平面（2500px），与建成版可逐项对比。',
    '基地分析：地形高差、风向、日照与 S 形布局的生成逻辑。',
    '总体布局：S 形建筑带的功能分段示意。',
    '长轴剖面（2500×742）：建筑带随 6m 场地高差起伏，两端升高至体育中心与宿舍。',
    '学术中心在 S 形建筑带中的位置高亮。',
    '学术中心等轴示意图（2500px）：45 组钢柱、底部四栋单体与中央漏斗形广场。',
    '短轴剖面（2500px）：云形学术中心悬挑、斜柱、中央庭院与屋顶架空层。',
    '宿舍综合体在 S 形建筑带中的位置高亮。',
    '公共服务（图书馆、创客、演艺广场等）在底层的分布。',
    '宿舍局部等轴：庭院、单向走廊、套间与开放消防楼梯。',
    '宿舍单元平面（2500px）：4 间卧室 + 公共客厅 + 独立卫浴的套间原型。',
    '艺术中心（剧场观演区）在 L 形体育艺术中心中的位置高亮。',
    '体育中心在 L 形体育艺术中心中的位置高亮，可与有方文字说明对照。',
]


def copy_rename(pairs, folder):
    out = []
    for idx, (src, cname, desc) in enumerate(pairs, 1):
        ext = '.jpg'
        fn = f'{idx:02d}_{re.sub(r"[/\\:]", "-", cname)}{ext}'
        dst = os.path.join(folder, fn)
        shutil.copyfile(src, dst)
        im = Image.open(dst)
        out.append(dict(idx=idx, name=cname, desc=desc, file=fn, size=im.size,
                        rel=os.path.relpath(dst, OUT)))
    return out


p24 = []
for k, (i, n, u) in enumerate(rows):
    p24.append((f'{SRC}/archdaily/{i}_{n}', names24[k], desc24[k]))
p20 = []
for k, f in enumerate(scheme_files):
    nm = scheme_names[k] if k < len(scheme_names) else f
    ds = scheme_desc[k] if k < len(scheme_desc) else ''
    p20.append((f'{SRC}/scheme2020/{f}', nm, ds))

a = copy_rename(p24, A)
b = copy_rename(p20, B)


def thumb(item):
    im = Image.open(os.path.join(OUT, item['rel'])).convert('RGB')
    im.thumbnail((460, 310))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=74, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def card(item):
    href = quote(item['rel'].replace(os.sep, '/'))
    return f'''<a class="card" href="{href}" target="_blank">
      <img src="{thumb(item)}" loading="lazy" alt="{html.escape(item['name'])}">
      <div class="cap"><b>{item['idx']:02d} · {html.escape(item['name'])}</b>
      <span>{item['size'][0]}×{item['size'][1]} px</span>
      <p>{html.escape(item['desc'])}</p></div></a>'''


cards_a = '\n'.join(card(x) for x in a)
cards_b = '\n'.join(card(x) for x in b)

CSS = '''
:root{--bg:#f5f7f8;--card:#fff;--ink:#1b2b33;--sub:#5d7079;--line:#dde5e8;--accent:#1d6b53;--warn:#b5642a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:36px 26px 70px}
h1{font-size:27px;margin:0 0 6px}h2{font-size:20px;margin:38px 0 6px;padding-bottom:9px;border-bottom:2px solid var(--accent)}
h3{font-size:16px;margin:22px 0 6px}.lead{color:var(--sub);margin:0 0 22px}
.kpi{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 8px}
.kpi div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:150px}
.kpi b{display:block;font-size:22px;color:var(--accent)}.kpi span{font-size:12px;color:var(--sub)}
.box{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:16px 20px;margin:14px 0}
.box.warn{border-left-color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px;margin-top:16px}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;text-decoration:none;color:inherit;transition:.18s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(20,50,60,.13);border-color:var(--accent)}
.card img{width:100%;height:210px;object-fit:contain;background:#eef1f2;display:block;border-bottom:1px solid var(--line)}
.cap{padding:11px 14px 14px}.cap b{font-size:14px}.cap span{float:right;font-size:11px;color:var(--sub)}
.cap p{margin:7px 0 0;font-size:12.5px;color:var(--sub);line-height:1.6}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:12px 0;background:#fff}
th,td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}
th{background:#eaf1ef}ul{padding-left:20px}li{margin:5px 0}
code{background:#eef1f2;padding:1px 5px;border-radius:4px;font-size:12px}
.src{font-size:12.5px;color:var(--sub)}.src a{color:var(--accent)}
.foot{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);font-size:12px;color:var(--sub)}
'''

HTML = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>北大附中海口学校 · 设计图纸集与 CAD 核查</title><style>{CSS}</style></head><body><div class="wrap">
<h1>北大附中海口学校 · 设计图纸集</h1>
<p class="lead">设计方 Crossboundaries 公开发布的建筑图纸整理 · 2024 建成版 14 张 + 2020 方案阶段 13 张 · 检索日期 2026-11-13</p>

<div class="kpi">
<div><b>14</b><span>2024 建成版官方图纸</span></div>
<div><b>13</b><span>2020 方案阶段图纸</span></div>
<div><b>2000 px</b><span>建成版图纸长边分辨率</span></div>
<div><b>0</b><span>公开 CAD / DWG 源文件</span></div>
</div>

<div class="box"><b>结论先说</b><br>
① <b>设计平面图找到了</b>，而且是设计方授权的官方图纸：总平面、屋顶平面、三层平面、长/短轴剖面、宿舍各类型单元平面与轴测示意图，均带功能图例、层数、标高和 50m 比例尺，可量测。<br>
② <b>没有找到单独的「场馆详图」</b>——游泳馆、篮球馆、1000 人剧场、图书馆的单体平面/施工图未公开；它们在总平面与剖面里只以体量出现。但设计方 2020 年发布的方案说明对各场馆的功能分区、标高、结构形式有非常详细的文字描述（见下文），可作为建模依据。<br>
③ <b>CAD / DWG 施工图未公开</b>。施工图属于设计方与业主的受控技术文件，公开渠道只有建筑媒体发布的 JPG 图纸。下文给出合法获取途径。<br>
④ 点击任意卡片可打开同目录下的高清原图；全部文件可离线使用。</div>

<h2>一、2024 建成版官方设计图纸（14 张）</h2>
<p class="lead">来源：ArchDaily 中文版项目图库（图纸 © Crossboundaries），与有方 2024 年公众号「新作」、建筑学院 53786 号项目页为同一套图纸。大部分 2000×1414 px。</p>
<div class="grid">{cards_a}</div>

<h2>二、2020 方案阶段图纸与分析图（13 张）</h2>
<p class="lead">来源：有方《云朵般漂浮的教学楼：北大附中海口学校 / Crossboundaries》。方案阶段的功能分区图与等轴示意图，可与建成版对照，也解释了各场馆为何这样布置。</p>
<div class="grid">{cards_b}</div>

<h2>三、场馆：图纸里有什么，缺什么</h2>
<table>
<tr><th>场馆</th><th>官方图纸中的呈现</th><th>设计方文字说明（有方 2020 方案 / 2024 新作）</th></tr>
<tr><td>体育及艺术中心</td><td>彩色总平面标注「体育及艺术中心 SPORTS / 2F」；长轴剖透视显示西侧扁平两层体量；无单体平面</td><td>依附地势形成 <b>L 形体量</b>，分东西两区：<b>西侧体育中心、东侧艺术中心观演区</b>；主入口在转角处的室外架空空间；整栋 <b>24m 高，分 0m 与 12m 两层</b></td></tr>
<tr><td>游泳馆 / 篮球馆</td><td>总平面与剖面中可见大跨体量，无独立平面</td><td>50m 标准泳池、篮球、羽毛球、乒乓球、跆拳道、空手道、体操、瑜伽等标准场馆合理布置在两层内；更衣淋浴与辅助空间置于夹层；<b>篮球场与游泳馆均采用网架结构实现大跨度无柱空间</b>；两侧玻璃幕墙双向自然采光</td></tr>
<tr><td>剧场（成就中心）</td><td>无线条平面</td><td>艺术中心观演区一层通高，<b>由西向东为黑匣子（暗室）、1000 人标准剧场、舞蹈排练室</b>；剧场含观众厅、舞台、后台辅助用房，后台设装卸平台供大型道具升降</td></tr>
<tr><td>图书馆 / 创客</td><td>短轴剖面图例中标出「图书馆 LIBRARY」；公共服务功能分区图</td><td>位于「云」下方底层，与创意工坊、演艺广场、实验室、多媒体教室一起构成底部公共层</td></tr>
<tr><td>学术中心（翔云）</td><td>三层平面图完整（8 类功能图例 + 50m 比例尺）、等轴示意图、短轴剖面</td><td>45 组钢柱支撑；3–4 层东西北三翼为初中书院，3–5 层南侧为高中教室；底层四栋单体对角斜坡围合中央广场</td></tr>
<tr><td>宿舍综合楼</td><td>单元平面、高中/初中/职工宿舍轴测、局部等轴示意图（最详细的一组）</td><td>4 个相连单元，高度由北向南递减；4 大庭院 + 16 个 10m 净宽小庭院；套间户型 = 4 间卧室 + 公共客厅 + 独立卫浴</td></tr>
<tr><td>400m 田径场</td><td>彩色总平面、屋顶平面、线稿总平面均完整；带入口与标高</td><td>跑道环绕体育中心体量，室外运动场抬高，下方为地下车库，两侧以阶梯式看台与两层场馆相连</td></tr>
</table>

<div class="box warn"><b>CAD / DWG 核查结论</b><br>
检索了以下渠道，均未发现可公开下载的 AutoCAD 施工图源文件：设计方 Crossboundaries 官网项目页、ArchDaily / 有方 / 建筑学院 / World-Architects / 知末 / 新浪的项目发布页（仅发布 JPG 图纸）、海口市政府与秀英区政府规划批前公示（仅检索到 2021 年接待室/保安室临时建筑的许可公示，无主体施工图附件）、环评与招采公告、筑龙等资料站（有该项目的资料打包页，但需登录/积分，且为方案文本转载，不是官方 CAD）。<br><br>
<b>为什么没有</b>：建筑施工图（含各层平面、节点、结构、机电）由业主、设计方与施工图审查机构保管，属受控技术文件，通常不对外发布；媒体发布的是经过排版的方案/扩初图纸。<br><br>
<b>合法获取途径</b>（按可行性排序）：<br>
1. 联系学校基建/后勤部门或举办方（恩祥集团）申请查阅竣工图档案；<br>
2. 向设计方 Crossboundaries 或合作单位「海南华磊建筑设计咨询有限公司 / DGN Design Studio」申请图纸授权（页面版权归设计方，需书面许可）；<br>
3. 向海口市自然资源和规划局 / 秀英区行政审批服务局申请政府信息公开，索取建设工程规划许可附图（一般为 PDF 总平面与立面，非 CAD）；<br>
4. 若用于教学研究，可基于本图纸集的高清 JPG + 50m 比例尺自行矢量描图（总平面与三层平面精度足够，误差约 0.5–1m）。</div>

<h2>四、用途与精度提示</h2>
<ul>
<li>本图纸集可直接用于核对上一版 3D 模型的形态与尺寸：<b>彩色总平面</b>给出三大功能体块、层数与出入口；<b>三层平面图</b>的 0–5–10–20–50m 比例尺可换算学术中心真实进深；<b>线稿总平面</b>带尺寸链，可复核 400m 跑道与建筑间距。</li>
<li>2020 方案与 2024 建成版存在差异（例如建筑带的屋面处理、宿舍单元划分），以 <b>2024 建成版</b>为准。</li>
<li>图纸均带 © Crossboundaries 版权，仅供个人学习与研究使用，请勿转载或商用；引用请注明设计方与来源媒体。</li>
<li>本图纸集是「方案 / 扩初深度」，不含轴网坐标、构造节点、门窗表与设备管线，不能替代施工图或竣工 BIM。</li>
</ul>

<h2>五、来源链接</h2>
<p class="src">
· ArchDaily 中文版项目页（14 张图纸原图）：<a href="https://www.archdaily.cn/zh/1020557/bei-jing-da-xue-fu-shu-zhong-xue-hai-kou-xue-xiao-crossboundaries">archdaily.cn/zh/1020557</a><br>
· 有方 2024《新作｜北京大学附属中学海口学校 / Crossboundaries》（图纸清单与项目信息）：<a href="https://mp.weixin.qq.com/s?__biz=MjM5OTAxNjY4MQ==&mid=2650352013&idx=2&sn=b638f1add19f7369d12b04f0ba8d0b7c">微信公众号原文</a><br>
· 有方 2020《方案｜云朵般漂浮的教学楼》（体育艺术中心与宿舍的详细文字说明）：<a href="https://www.youfangkongjian.cn/video?20201020015542">youfangkongjian.cn/video?20201020015542</a><br>
· 建筑学院 53786（项目图纸清单）：<a href="https://www.archcollege.com/53786.html">archcollege.com/53786.html</a>（图床链接已失效，图纸取自 ArchDaily 同源文件）<br>
· 项目数据：场地 133,340 m²、建筑面积 138,095 m²（地上 106,672 / 地下 31,423）、建筑占地 32,750 m²、容积率 0.8、3600 名学生、2019.09–2020.04 设计、2024.01 竣工。</p>

<div class="foot">整理于 2026-11-13 · 图纸版权归 Crossboundaries 及原发布媒体 · 仅供学习研究</div>
</div></body></html>'''

open(f'{OUT}/图纸索引.html', 'w', encoding='utf-8').write(HTML)

# 简明 Markdown 清单
md = ['# 北大附中海口学校 · 设计图纸集', '',
      '检索日期：2026-11-13　|　图纸 © Crossboundaries，仅供学习研究', '',
      '## 结论', '',
      '- 找到设计方公开发布的 **14 张 2024 建成版官方图纸**（总平面、屋顶平面、三层平面、长/短轴剖面、宿舍单元平面与轴测），另有 **13 张 2020 方案阶段图纸与分析图**。',
      '- **未找到** 单独的游泳馆 / 篮球馆 / 剧场 / 图书馆场馆平面详图；也未找到任何可公开下载的 **CAD / DWG 施工图**。',
      '- 官方图纸为方案/扩初深度（带功能图例、层数、标高、50m 比例尺），非施工图、非竣工 BIM。', '',
      '## 2024 建成版（01_建成版官方图纸_2024）', '']
for x in a:
    md.append(f"- {x['idx']:02d} {x['name']} — {x['size'][0]}×{x['size'][1]} px")
md += ['', '## 2020 方案阶段（02_方案阶段图纸_2020）', '']
for x in b:
    md.append(f"- {x['idx']:02d} {x['name']} — {x['size'][0]}×{x['size'][1]} px")
md += ['', '## CAD 获取途径', '',
       '1. 学校基建部门 / 举办方恩祥集团：查阅竣工图档案；',
       '2. Crossboundaries 或 海南华磊建筑设计咨询有限公司、DGN Design Studio：申请图纸授权；',
       '3. 海口市自然资源和规划局 / 秀英区行政审批服务局：申请规划许可附图政府信息公开（一般为 PDF）；',
       '4. 自行矢量描图：本图纸集高清 JPG + 50m 比例尺，误差约 0.5–1m。', '',
       '## 来源', '',
       '- ArchDaily 中文版：https://www.archdaily.cn/zh/1020557/bei-jing-da-xue-fu-shu-zhong-xue-hai-kou-xue-xiao-crossboundaries',
       '- 有方 2024 新作（公众号）：图纸清单与项目信息',
       '- 有方 2020 方案：https://www.youfangkongjian.cn/video?20201020015542 （体育艺术中心 / 宿舍详细文字）',
       '- 建筑学院：https://www.archcollege.com/53786.html （图床已失效）', '']
open(f'{OUT}/图纸清单与说明.md', 'w', encoding='utf-8').write('\n'.join(md))

# 总览图
shutil.copyfile(f'{SRC}/archdaily/图纸总览_2024.jpg', f'{OUT}/2024官方图纸_总览.jpg')

print('OUT:', OUT)
print('2024 drawings:', len(a), ' 2020 diagrams:', len(b))
print('HTML KB:', os.path.getsize(f'{OUT}/图纸索引.html') // 1024)
for f in sorted(os.listdir(OUT)):
    print(' ', f)
