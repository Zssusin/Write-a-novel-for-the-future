#!/usr/bin/env python3
"""把抽出的海岸线渲染成一张带经纬网的 2100 年火星水手峡谷海图。

坐标系：
  图幅 = 120°W–30°W × 5°N–25°S，等距圆柱投影，21.81 单位/度
  图面单位 (0,0) = 图幅左上角 = 120°W, 5°N
  x = (120 - lonW) * PPD        y = (5 - lat) * PPD      （lat 北正南负）
潮流：正典地图用西经，现代工具用东经；边框双标。
"""
import pathlib, re

HERE    = pathlib.Path(__file__).resolve().parent
MAP_DIR = HERE.parent
OUT     = MAP_DIR / "产出"
OUT.mkdir(exist_ok=True)

PPD   = 21.81                       # 单位/度
W, H  = 90*PPD, 30*PPD              # 1962.9 × 654.3
M     = 52                          # 刻度边框宽度

def X(lonW):  return (120 - lonW) * PPD
def Y(lat):   return (5 - lat)    * PPD

# ── 颜色：火星测绘局的纸 ──────────────────────────────────────────
C = dict(
    paper   = "#D8C7B2",   # 尘土色图纸（陆地）
    paper_e = "#CDB9A2",   # 边框底
    water   = "#6E4A3F",   # 正典：褐红色，富含盐与淤泥
    coast   = "#4A2E26",   # 海岸线
    ink     = "#2B2521",   # 主墨
    grat    = "#8A7A69",   # 经纬网
    infra   = "#1E5464",   # 人工构筑物（铁路）——冷色 = 工程
    alert   = "#A3301C",   # 闸与坝：全海的命门
    white   = "#F2EADF",
)
F_LAT = "'CMU Serif','Inria Serif','FreeSerif',serif"
F_CJK = "'Noto Serif CJK SC','LXGW WenKai','FandolSong',serif"
F_DSP = "'LXGW WenKai','Noto Serif CJK SC',serif"

# 文字助手：halo = 纸色描边，让压在深色水面上的字也能读
def txt(x, y, s, size=13, fam=F_LAT, fill=None, anchor="start", ls=0,
        weight="normal", style="normal", op=1.0, halo=0):
    f = fill or C["ink"]
    h = (f' stroke="{C["paper"]}" stroke-width="{halo}" paint-order="stroke"'
         f' stroke-linejoin="round"') if halo else ''
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" '
            f'fill="{f}" text-anchor="{anchor}" letter-spacing="{ls}" '
            f'font-weight="{weight}" font-style="{style}" opacity="{op}"{h}>{s}</text>')

# ── 据点 ────────────────────────────────────────────────────────
# (英文名, 中文名, 西经, 纬度, 阵营, 等级, 标注方位)
#   阵营 cn=锈色中国 us=美国火星联邦 corp=企业 oth=第三方
#   等级 1=主要城市 2=次级 3=小据点   ☆=仅见于地图、正文零描写
S = [
 ("New Shanghai","新上海",        116.4,  2.2,"cn",1,"E"),
 ("Guxiang","故乡",                99.4, -1.7,"cn",3,"N"),
 ("Ge'gyai","",                   101.9, -8.7,"cn",3,"W"),
 ("Urumqi","",                    107.1,-11.7,"cn",3,"W"),
 ("Wudu","",                      107.3,-17.3,"cn",3,"S"),
 ("Haiyuan City","海源城",         92.3,-12.5,"cn",1,"SW"),
 ("Hanggin Qi","",                 86.8, -7.9,"cn",3,"N"),
 ("Harbin","",                     80.0,-15.6,"cn",3,"S"),
 ("Bako","",                       74.0, -8.0,"oth",3,"N"),
 ("Santo Tomas","",                72.0,-17.8,"us",3,"S"),
 ("Port Lowell","",                70.3,-11.1,"corp",1,"SE"),
 ("Vlore","",                      65.5, -9.2,"oth",3,"E"),
 ("Fortuna","",                    58.4,-14.7,"us",3,"SW"),
 ("Chester Habitat","",            56.1,-12.2,"us",3,"S"),
 ("Plymouth","",                   53.8,-18.9,"us",3,"S"),
 ("Robinson City","罗宾逊城",       48.9, -9.8,"us",1,"NW"),
 ("Red Lake","红湖",               45.3, -5.6,"us",3,"N"),
 ("Timbuktu","",                   44.8, -2.6,"us",3,"E"),
 ("Anchorage","",                  44.2,-17.1,"us",3,"SE"),
]
STAR = {"Urumqi","Harbin","Vlore","Fortuna","Anchorage"}   # 正文零描写

# 工程构筑物（军事目标）
ENG = [("Ius Locks","Ius 闸群",82.2,-12.7,"lock"),
       ("","",              80.9,-11.6,"lock"),
       ("Capri Chasma Dam","Capri 坝",47.6,-9.7,"dam"),
       ("Eos Dam","Eos 坝",      42.7,-14.7,"dam")]

# 赤道铁路主线（西→东），沿海北岸
RAIL = [(120,-0.6),(116.4,2.2),(110,1.0),(104,-0.4),(99.4,-1.7),(94,-5.2),
        (89,-7.2),(86.8,-7.9),(81,-8.6),(76,-7.4),(72.6,-9.6),(70.3,-11.1),
        (64,-12.3),(58.4,-12.6),(56.1,-12.2),(51,-10.6),(48.9,-9.8),
        (44,-7.6),(38,-5.2),(30,-3.4)]
RAIL_SPUR = [[(92.3,-12.5),(90.6,-9.4),(88.8,-8.2)],           # 海源城支线
             [(116.4,2.2),(118.2,4.2)],                         # Olympus / Ascraeus 支线
             [(116.4,2.2),(118.6,-4.6)]]                        # Arsia 支线

# 水体与地貌注记 (文字, 中文, 西经, 纬度, 字号, 字距, 样式)
HYDRO = [("LAKE TITHONIUM","提托尼乌姆湖",87.2,-2.6,15,2.2),
         ("LAKE CANDOR","坎多尔湖",       70.5,-4.2,15,2.2),
         ("LAKE EOS","厄俄斯湖",          48.6,-12.4,15,2.2)]
CHAN  = [("IUS",85.4,-9.4),("MELAS",72.4,-12.4),("COPRATES",62.4,-13.0)]
REGION= [("LUNAE PLANUM","",68,3.2,19,5.0),
         ("SINAI PLANUM","",99,-19.0,19,5.0),
         ("SYRIA PLANUM","",113,-21.5,19,5.0),
         ("XANTHE TERRA","赞西高地",39,3.2,19,5.0),
         ("NOCTIS LABYRINTHUS","诺克提斯迷宫",104.6,-4.0,16,3.2)]
PEAK  = [("PAVONIS MONS",113.4,0.8),("ARSIA MONS",119.4,-8.35)]
MISC  = [("HEBES CHASMA",76.5,-1.1),("MUTCH CRATER",55.3,0.6)]

# ── 取 potrace 的路径 ───────────────────────────────────────────
raw = (OUT / "water.svg").read_text()
paths = "\n".join(re.findall(r'<path d="[^"]*"\s*/>', raw))
if not paths:
    paths = "\n".join(f'<path d="{d}"/>' for d in re.findall(r'<path d="([^"]*)"', raw))

o = []
A = o.append
TW, TH = W + 2*M, H + M + 84
A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{TW:.0f}" height="{TH:.0f}" '
  f'viewBox="0 0 {TW:.1f} {TH:.1f}">')
A('<defs>')
A(f'''<pattern id="hatch" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
  <line x1="0" y1="0" x2="0" y2="7" stroke="{C['grat']}" stroke-width="0.7" opacity="0.45"/></pattern>''')
A('</defs>')
A(f'<rect width="{TW}" height="{TH}" fill="{C["paper_e"]}"/>')

# ── 经纬网 + 刻度边框 ───────────────────────────────────────────
A(f'<g transform="translate({M},{M})">')
A(f'<rect width="{W:.1f}" height="{H:.1f}" fill="{C["paper"]}"/>')
A(f'<g stroke="{C["grat"]}" fill="none" stroke-width="0.55" opacity="0.85">')
for lw in range(30, 121, 5):                       # 子午线
    A(f'<line x1="{X(lw):.1f}" y1="0" x2="{X(lw):.1f}" y2="{H:.1f}"/>')
for la in range(-25, 6, 5):                        # 纬线
    A(f'<line x1="0" y1="{Y(la):.1f}" x2="{W:.1f}" y2="{Y(la):.1f}"/>')
A('</g>')
A(f'<line x1="0" y1="{Y(0):.1f}" x2="{W:.1f}" y2="{Y(0):.1f}" '
  f'stroke="{C["ink"]}" stroke-width="1.1" opacity="0.55"/>')
A(txt(W-8, Y(0)-6, "EQUATOR", 11, F_LAT, C["ink"], "end", 3, op=0.6, halo=3))

# ── 水体 ────────────────────────────────────────────────────────
A(f'<g transform="translate(0,{H:.1f}) scale(0.1,-0.1)" fill="{C["water"]}" '
  f'stroke="{C["coast"]}" stroke-width="9">')
A(paths)
A('</g>')

# ── 赤道铁路 ────────────────────────────────────────────────────
def poly(pts): return " ".join(f"{X(a):.1f},{Y(b):.1f}" for a,b in pts)
for sp in RAIL_SPUR:
    A(f'<polyline points="{poly(sp)}" fill="none" stroke="{C["infra"]}" '
      f'stroke-width="1.6" stroke-dasharray="5 4" opacity="0.75"/>')
A(f'<polyline points="{poly(RAIL)}" fill="none" stroke="{C["white"]}" stroke-width="4.4" opacity="0.55"/>')
A(f'<polyline points="{poly(RAIL)}" fill="none" stroke="{C["infra"]}" '
  f'stroke-width="2.1" stroke-dasharray="9 5"/>')

# ── 闸与坝 ──────────────────────────────────────────────────────
for name, zh, lw, la, kind in ENG:
    x, y = X(lw), Y(la)
    A(f'<g transform="translate({x:.1f},{y:.1f}) rotate(38)">'
      f'<rect x="-2.6" y="-11" width="5.2" height="22" fill="{C["alert"]}" '
      f'stroke="{C["white"]}" stroke-width="1.1"/></g>')

# ── 注记 ────────────────────────────────────────────────────────

for en, zh, lw, la, sz, ls in REGION:
    A(txt(X(lw), Y(la), en, sz, F_LAT, C["ink"], "middle", ls, op=0.42))
    if zh: A(txt(X(lw), Y(la)+sz+4, zh, sz-4, F_CJK, C["ink"], "middle", 3, op=0.38))
for en, zh, lw, la, sz, ls in HYDRO:
    A(txt(X(lw), Y(la), en, sz, F_LAT, C["coast"], "middle", ls, style="italic", op=0.95, halo=3.4))
    if zh: A(txt(X(lw), Y(la)+sz+2, zh, sz-3, F_CJK, C["coast"], "middle", 2, op=0.9, halo=3.4))
for en, lw, la in CHAN:
    A(txt(X(lw), Y(la), en, 13, F_LAT, C["white"], "middle", 3.4, style="italic", op=0.72))
for en, lw, la in PEAK:
    x, y = X(lw), Y(la)
    A(f'<path d="M{x-6:.1f},{y+5} L{x:.1f},{y-6} L{x+6:.1f},{y+5} Z" fill="{C["ink"]}" opacity="0.6"/>')
    # 贴左框的山（Arsia 在 120.1°W，已在图幅外）改左对齐，否则居中会被裁掉
    if x < 90: A(txt(x+10, y+4, en, 11, F_LAT, C["ink"], "start", 1.6, op=0.6, halo=3))
    else:      A(txt(x, y+18, en, 11, F_LAT, C["ink"], "middle", 1.6, op=0.55, halo=3))
for en, lw, la in MISC:
    A(txt(X(lw), Y(la), en, 10.5, F_LAT, C["ink"], "middle", 1.4, op=0.55, halo=3))

# 海名沿水体走向压一道（小字，不与区域注记打架）
A(txt(X(66), Y(-16.4), 'M A R I N E R I S<tspan dx="44">S E A</tspan>', 17,
      F_LAT, C["coast"], "middle", 4, op=0.55, halo=3.4))

# ── 据点符号 ────────────────────────────────────────────────────
OFF = {"N":(0,-13,"middle"),"S":(0,20,"middle"),"E":(11,4.5,"start"),
       "W":(-11,4.5,"end"),"NE":(10,-8,"start"),"NW":(-10,-8,"end"),
       "SE":(10,15,"start"),"SW":(-10,15,"end")}
for en, zh, lw, la, fac, rank, pos in S:
    x, y = X(lw), Y(la)
    r = {1:6.4, 2:5.0, 3:3.7}[rank]
    if fac == "cn":     sym = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{C["ink"]}" stroke="{C["white"]}" stroke-width="1.2"/>'
    elif fac == "us":   sym = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="2.0"/>'
    elif fac == "corp": sym = (f'<rect x="{x-r:.1f}" y="{y-r:.1f}" width="{2*r}" height="{2*r}" '
                               f'fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="2.0" transform="rotate(45 {x:.1f} {y:.1f})"/>')
    else:               sym = (f'<rect x="{x-r+0.4:.1f}" y="{y-r+0.4:.1f}" width="{2*r-0.8}" height="{2*r-0.8}" '
                               f'fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1.8"/>')
    if rank == 1:
        A(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+4.2}" fill="none" stroke="{C["ink"]}" stroke-width="1.0" opacity="0.75"/>')
    A(sym)
    dx, dy, an = OFF[pos]
    star = ' ☆' if en in STAR else ''
    sz   = 15 if rank == 1 else 12
    A(txt(x+dx, y+dy, en + star, sz, F_LAT, C["ink"], an, 0.5,
          weight="bold" if rank == 1 else "normal", halo=3.4))
    if zh:
        A(txt(x+dx, y+dy+sz+2, zh, sz-2, F_CJK, C["ink"], an, 1.5, op=0.88, halo=3.4))

# 闸坝名（画在符号之后，压在最上）
for name, zh, lw, la, kind in ENG:
    if not name: continue
    ddx, ddy = {"Ius Locks": (14, -12), "Capri Chasma Dam": (13, 26), "Eos Dam": (15, 28)}[name]
    A(txt(X(lw)+ddx, Y(la)+ddy, name, 11.5, F_LAT, C["alert"], "start", 0.6, weight="bold", halo=3.4))
    A(txt(X(lw)+ddx, Y(la)+ddy+12, zh, 10.5, F_CJK, C["alert"], "start", 1, halo=3.4))
A('</g>')

# ── 刻度边框（双经度标注）────────────────────────────────────────
A(f'<g transform="translate({M},{M})">')
A(f'<rect width="{W:.1f}" height="{H:.1f}" fill="none" stroke="{C["ink"]}" stroke-width="2.2"/>')
A(f'<rect x="-11" y="-11" width="{W+22:.1f}" height="{H+22:.1f}" fill="none" stroke="{C["ink"]}" stroke-width="1.0"/>')
# 1° 小刻度
A(f'<g stroke="{C["ink"]}" stroke-width="0.9">')
for lw in range(30, 121):
    x = X(lw); L = 9 if lw % 5 == 0 else 4.5
    A(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{-L}"/><line x1="{x:.1f}" y1="{H:.1f}" x2="{x:.1f}" y2="{H+L:.1f}"/>')
for la in range(-25, 6):
    y = Y(la); L = 9 if la % 5 == 0 else 4.5
    A(f'<line x1="0" y1="{y:.1f}" x2="{-L}" y2="{y:.1f}"/><line x1="{W:.1f}" y1="{y:.1f}" x2="{W+L:.1f}" y2="{y:.1f}"/>')
A('</g>')
for lw in range(30, 121, 5):
    x, e = X(lw), 360 - lw
    A(txt(x, -17, f"{lw}°W", 13, F_LAT, C["ink"], "middle", 0.4))
    A(txt(x, H+30, f"{lw}°W", 13, F_LAT, C["ink"], "middle", 0.4))
    A(txt(x, H+42, f"({e}°E)", 10, F_LAT, C["ink"], "middle", 0.2, op=0.5))
for la in range(-25, 6, 5):
    y  = Y(la)
    lb = "0°" if la == 0 else f"{abs(la)}°{'N' if la>0 else 'S'}"
    A(txt(-15, y+4.5, lb, 13, F_LAT, C["ink"], "end", 0.4))
    A(txt(W+15, y+4.5, lb, 13, F_LAT, C["ink"], "start", 0.4))
A('</g>')

# ── 图题框（画在空的 Lunae Planum 里）──────────────────────────
cx, cy, cw, ch = M+X(63.5), M+Y(4.6), 405, 132
A(f'<g><rect x="{cx:.1f}" y="{cy:.1f}" width="{cw}" height="{ch}" fill="{C["paper"]}" '
  f'fill-opacity="0.93" stroke="{C["ink"]}" stroke-width="1.6"/>')
A(f'<rect x="{cx+4:.1f}" y="{cy+4:.1f}" width="{cw-8}" height="{ch-8}" fill="none" stroke="{C["ink"]}" stroke-width="0.6"/>')
tx = cx + cw/2
A(txt(tx, cy+34, "水 手 峡 谷 海", 26, F_DSP, C["ink"], "middle", 7))
A(txt(tx, cy+55, 'M A R I N E R I S<tspan dx="34">S E A</tspan>', 13, F_LAT, C["ink"], "middle", 3.4, op=0.8))
A(f'<line x1="{cx+40:.1f}" y1="{cy+66:.1f}" x2="{cx+cw-40:.1f}" y2="{cy+66:.1f}" stroke="{C["ink"]}" stroke-width="0.7" opacity="0.6"/>')
A(txt(tx, cy+83,  "火星测绘  第三图幅  等距圆柱投影", 12, F_CJK, C["ink"], "middle", 1.2, op=0.85))
A(txt(tx, cy+101, "海岸线测绘于 2100 年 3 月", 12.5, F_CJK, C["alert"], "middle", 1.2, weight="bold"))
A(txt(tx, cy+118, "北方海仍在上涨，本图海岸线逐年失效", 10.5, F_CJK, C["ink"], "middle", 0.8, op=0.72))
A('</g>')

# ── 图例：横贯南部空白的四栏窄条（该带唯一据点 Wudu / Santo Tomas 都在更北）──
LX, LY, LW, LH = M+300, M+548, 710, 104
A(f'<g><rect x="{LX:.1f}" y="{LY:.1f}" width="{LW}" height="{LH}" fill="{C["paper"]}" '
  f'fill-opacity="0.94" stroke="{C["ink"]}" stroke-width="1.3"/>')
A(txt(LX+14, LY+20, "图 例", 12.5, F_DSP, C["ink"], "start", 4))
A(txt(LX+72, LY+20, "L E G E N D", 10, F_LAT, C["ink"], "start", 2.4, op=0.55))
A(f'<line x1="{LX+14:.1f}" y1="{LY+28:.1f}" x2="{LX+LW-14:.1f}" y2="{LY+28:.1f}" '
  f'stroke="{C["ink"]}" stroke-width="0.7" opacity="0.5"/>')

items = [("cn","锈色中国据点"), ("us","美国火星联邦据点"),
         ("corp","企业属地（Port Lowell）"), ("major","主要城市 / 首府"),
         ("oth","第三方据点"), ("rail","赤道铁路（含支线）"),
         ("eng","船闸 · 大坝"), ("star","仅见于正典地图，正文零描写")]
COLS = [LX+26, LX+204, LX+382, LX+560]
for i, (kind, label) in enumerate(items):
    sx = COLS[i % 4]; yy = LY + (46 if i < 4 else 74)
    if   kind == "cn":   A(f'<circle cx="{sx}" cy="{yy-4}" r="5.4" fill="{C["ink"]}" stroke="{C["white"]}" stroke-width="1.1"/>')
    elif kind == "us":   A(f'<circle cx="{sx}" cy="{yy-4}" r="5.4" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="2"/>')
    elif kind == "corp": A(f'<rect x="{sx-5}" y="{yy-9}" width="10" height="10" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="2" transform="rotate(45 {sx} {yy-4})"/>')
    elif kind == "oth":  A(f'<rect x="{sx-5}" y="{yy-9}" width="10" height="10" fill="{C["paper"]}" stroke="{C["ink"]}" stroke-width="1.8"/>')
    elif kind == "major":A(f'<circle cx="{sx}" cy="{yy-4}" r="9.6" fill="none" stroke="{C["ink"]}" stroke-width="1"/>'
                           f'<circle cx="{sx}" cy="{yy-4}" r="5.4" fill="{C["ink"]}" stroke="{C["white"]}" stroke-width="1.1"/>')
    elif kind == "rail": A(f'<line x1="{sx-11}" y1="{yy-4}" x2="{sx+11}" y2="{yy-4}" stroke="{C["infra"]}" stroke-width="2.1" stroke-dasharray="9 5"/>')
    elif kind == "eng":  A(f'<g transform="translate({sx},{yy-4}) rotate(38)"><rect x="-2.6" y="-9.5" width="5.2" height="19" fill="{C["alert"]}" stroke="{C["white"]}" stroke-width="1"/></g>')
    elif kind == "star": A(txt(sx, yy, "☆", 14, F_LAT, C["ink"], "middle", 0))
    A(txt(sx + 20, yy, label, 11, F_CJK, C["ink"], "start", 0.6))
A('</g>')

# ── 比例尺：图例右侧 ───────────────────────────────────────────
km_per_deg = 59.16
seg = 200 / km_per_deg * PPD                # 200 km 一格
BX, BY = M + 1052, M + 600
A('<g>')
for i in range(3):
    A(f'<rect x="{BX+i*seg:.1f}" y="{BY}" width="{seg:.1f}" height="7.5" '
      f'fill="{C["ink"] if i%2==0 else C["paper"]}" stroke="{C["ink"]}" stroke-width="0.8"/>')
for i in range(4):
    A(txt(BX+i*seg, BY-6, f"{i*200}", 10, F_LAT, C["ink"], "middle", 0, halo=3))
A(txt(BX+3*seg+14, BY+7, "km", 10, F_LAT, C["ink"], "start", 0, halo=3))
A(txt(BX, BY+26, "赤道处比例；等距圆柱投影，东西向随纬度放大（25°S 约 +10%）",
      9.5, F_CJK, C["ink"], "start", 0.4, op=0.75, halo=3))
A(txt(BX, BY+41, "正典未划定中美territorial边界；本图仅以符号示意据点归属",
      9.5, F_CJK, C["ink"], "start", 0.4, op=0.75, halo=3))
A('</g>')

# ── 页脚 ────────────────────────────────────────────────────────
A(txt(M, TH-16, "底图：GURPS Transhuman Space: In The Well, p.22 — 海岸线由原图灰度阈值抽取后矢量化",
      10.5, F_CJK, C["ink"], "start", 0.3, op=0.6))
A(txt(TW-M, TH-16, "经度双标：西经（正典惯例） / 东经（SpaceEngine · Mars Trek · USGS）",
      10.5, F_CJK, C["ink"], "end", 0.3, op=0.6))
A('</svg>')

out = OUT / "水手峡谷海图.svg"
out.write_text("\n".join(o), encoding="utf-8")
print(f"→ {out}  {out.stat().st_size/1024:.1f} KB   画幅 {TW:.0f}×{TH:.0f}")
