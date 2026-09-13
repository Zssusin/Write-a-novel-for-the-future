#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
塔西斯区域地形图（2100 年 3 月）—— 墨卡托投影，192–272°E × 22°S–32°N，赤道比例与战区图相同。
在白底晕渲之上加：1,000 m 等高线（每 5,000 m 加粗并注记）、正典「呼吸线」（海拔 5 英里 = 8,047 m，
以上连基因改造者也无法呼吸，ITW p.34）及其以上区域的斜线、火山口高程点。

数据：DEM 原始 463 m 高程；水体 产出/三海掩膜.npz；地点 数据/火星地点.csv；铁路 产出/基础设施_2100.geojson
产出：产出/塔西斯区域图_2100.svg（除晕渲外全矢量）  产出/塔西斯区域图_2100.png（3 倍，印刷用）
运行：./.venv/bin/python scripts/35_塔西斯区域图.py
"""
import math, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Mercator, text_width

NAME = "塔西斯区域图_2100"
LON0, LON1, LAT0, LAT1 = 192.0, 272.0, 32.0, -22.0
PPD, SS, HR = 17.5, 3, 64                     # 赤道每度屏幕单位；底图超采样；读 DEM 的 px/度
X0, Y0 = 76.0, 118.0
P = Mercator(LON0, LON1, LAT0, LAT1, X0, Y0, PPD)
LX = int(X0 + P.w + 58)
SW, SH = 1848, int(Y0 + P.h + 62)
S = SVG(SW, SH, "塔西斯区域地形图 · 2100 年 3 月")
BREATH = 5*1609.344                            # 正典：海拔 5 英里以上无法呼吸
BREATH_C = "#7B3F98"
CONTOUR_STEP, INDEX_STEP = 1000, 5000

Z = M.load_masks()
LV = {"borealis": int(Z["level_borealis"]), "marineris_ius": int(Z["level_ius"])}
PLACES = {r["id"]: r for r in M.load_places()}
PEAKS = {r["山"]: r for r in M.load_peaks()}
INFRA = M.load_infra()
IAU = M.load_iau()
clip = f'clip-path="url(#clipMap)"'

# ── 底图：等距圆柱上算好晕渲，再按行重采样成墨卡托 ──────────────────
print("读 DEM、晕渲 …")
dem = M.read_dem_window(LON0, LON1, LAT0, LAT1, HR)
masks = {k: M.refine_water(Z[k], LV[k], dem, HR, LON0, LAT0) for k in LV}
rgb = M.relief_rgb(dem, list(masks.values()), list(LV.values()), HR, lat_top=LAT0, zfac=2.6)
W3, H3 = int(round(P.w*SS)), int(round(P.h*SS))
img = np.asarray(Image.fromarray(rgb).resize((W3, rgb.shape[0]), Image.LANCZOS), np.float32)
lat = P.lat_of(P.y0 + (np.arange(H3) + 0.5)/SS)
r = (LAT0 - lat)*HR - 0.5
r0 = np.clip(np.floor(r).astype(int), 0, img.shape[0]-2); f = np.clip(r - r0, 0, 1)[:, None, None]
merc = np.clip(img[r0]*(1-f) + img[r0+1]*f, 0, 255).astype(np.uint8)
del img, rgb
S.add("底图", f'<clipPath id="clipMap"><rect x="{P.x0}" y="{P.y0}" width="{P.w:.1f}" height="{P.h:.1f}"/></clipPath>')
S.add("底图", f'<image x="{P.x0}" y="{P.y0}" width="{P.w:.1f}" height="{P.h:.1f}" preserveAspectRatio="none" href="{M.png_data_uri(merc, quality=90)}"/>')
del merc

# ── 等高线（32 px/度上提取）─────────────────────────────────────────
print("等高线 …")
from scipy import ndimage
d32 = dem.reshape(dem.shape[0]//2, 2, dem.shape[1]//2, 2).mean(axis=(1, 3))
sm = ndimage.gaussian_filter(d32.astype(np.float64), 1.3)
to_xy = lambda rr, cc: P.xy(LON0 + (cc + 0.5)/32, LAT0 - (rr + 0.5)/32)
levels = list(range(-4000, 22000, CONTOUR_STEP))
index_lines = {}
normal, bold = [], []
for lv in levels:
    lines = M.contour_lines(sm, lv, to_xy, sigma=0, min_len=14, tol=0.4)
    (bold if lv % INDEX_STEP == 0 else normal).extend(M.path_d(p[:, 0], p[:, 1]) for p in lines)
    if lv % INDEX_STEP == 0: index_lines[lv] = lines
S.add("等高线", f'<path d="{" ".join(normal)}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.3" opacity="0.5" {clip}/>')
S.add("等高线", f'<path d="{" ".join(bold)}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.6" opacity="0.7" {clip}/>')

# 呼吸线及其以上区域
S.add("呼吸线", f'<pattern id="thin" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">'
                f'<line x1="0" y1="0" x2="0" y2="5" stroke="{BREATH_C}" stroke-width="0.6"/></pattern>')
rings = M.mask_rings(dem > BREATH, HR, lon_left=LON0, lat_top=LAT0, min_px=40, simplify=0.012, smooth=2)
d_b = M.rings_to_path(rings, P)
S.add("呼吸线", f'<path d="{d_b}" fill="url(#thin)" fill-rule="evenodd" opacity="0.45" {clip}/>')
S.add("呼吸线", f'<path d="{d_b}" fill="none" stroke="{BREATH_C}" stroke-width="0.9" stroke-dasharray="5 2.2" {clip}/>')

# 海岸线
for k, m in masks.items():
    rings = M.mask_rings(m, HR, lon_left=LON0, lat_top=LAT0, min_px=30, simplify=0.01, smooth=2)
    if rings:
        S.add("海岸线", f'<path d="{M.rings_to_path(rings, P)}" fill="none" stroke="{C["coast"]}" stroke-width="0.75" stroke-linejoin="round" {clip}/>')

# ── 经纬网 ─────────────────────────────────────────────────────────
M.graticule_rect(S, P, 10, 2, 10)
placer = Placer((P.x0+2, P.y0+2, P.x0+P.w-2, P.y0+P.h-2))

# ── 铁路 ───────────────────────────────────────────────────────────
rail_max = (-1e9, None)
for ft in INFRA:
    if ft["geometry"]["type"] != "LineString": continue
    for seg in M.split_line(ft["geometry"]["coordinates"], P):
        xy = [P.xy(lo, la) for lo, la in seg]
        S.add("铁路", f'<g {clip}>' + M.rail_svg(xy, ft["properties"]["kind"]) + "</g>")
        for lo, la in seg:
            if P.inside(lo, la) and ft["properties"]["kind"] in ("干线", "桥"):
                z = float(dem[int((LAT0-la)*HR), int((P.unwrap(lo)-LON0)*HR) % dem.shape[1]])
                if z > rail_max[0]: rail_max = (z, (lo, la))
for ft in INFRA:
    if ft["properties"]["kind"] != "车站": continue
    lo, la = ft["geometry"]["coordinates"]; lo %= 360
    if not P.inside(lo, la): continue
    x, y = P.xy(lo, la)
    S.add("铁路", f'<rect x="{x-2.2:.1f}" y="{y-2.2:.1f}" width="4.4" height="4.4" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')
    placer.block(x-3, y-3, x+3, y+3)
print(f"  赤道铁路图内最高点 {rail_max[0]:,.0f} m @ {rail_max[1]}")

# ── 符号 ───────────────────────────────────────────────────────────
POINT_CATS = {"城市", "城镇", "遗址", "军事"}
pts = []
for r in PLACES.values():
    lo, la = float(r["东经"]), float(r["纬度"])
    if not P.inside(lo, la) or not (r["类别"] in POINT_CATS or r["id"] == "zeus_caldera"): continue
    x, y = map(float, P.xy(lo, la))
    rad = {"1": 3.4, "2": 2.9, "3": 2.4}[r["等级"]]
    kind = M.faction_kind(r["阵营"]) if r["类别"] != "设施" else "corp"
    S.add("符号", M.symbol(kind, x, y, rad, major=r["等级"] == "1"))
    br = rad + (2.4 if r["等级"] == "1" else 0) + 1
    placer.block(x-br, y-br, x+br, y+br)
    pts.append((r, x, y, br))

PEAK_ZH = {"Olympus Mons": "奥林匹斯山", "Ascraeus Mons": "艾斯克雷尔斯山", "Pavonis Mons": "帕弗尼斯山",
           "Arsia Mons": "阿尔西亚山", "Uranius Mons": "乌拉纽斯山", "Ceraunius Tholus": "刻拉尼俄斯山丘",
           "Tharsis Tholus": "塔西斯山丘"}
SPOTS = {"Biblis Tholus": "比布利斯山丘", "Ulysses Tholus": "尤利西斯山丘", "Jovis Tholus": "朱庇特山丘", "Uranius Tholus": "乌拉纽斯山丘"}
peak_pts = []
for n, zh in PEAK_ZH.items():
    pk = PEAKS[n]; lo, la, z = float(pk["峰顶东经"]), float(pk["峰顶纬度"]), float(pk["峰顶MOLA高程_m"])
    if P.inside(lo, la): peak_pts.append((zh, lo, la, z, True))
for n, zh in SPOTS.items():
    it = IAU[n]; la, lo = float(it["center_lat"]), float(it["center_lon"]) % 360; rad = max(float(it["diameter"])/2/M.KMPD, 0.3)
    r0, r1 = int((LAT0-la-rad)*HR), int((LAT0-la+rad)*HR); c0, c1 = int((lo-rad-LON0)*HR), int((lo+rad-LON0)*HR)
    win = dem[r0:r1, c0:c1]; i, j = np.unravel_index(np.argmax(win), win.shape)
    peak_pts.append((zh, LON0 + (c0+j+0.5)/HR, LAT0 - (r0+i+0.5)/HR, float(win.max()), False))
for zh, lo, la, z, major in peak_pts:
    x, y = map(float, P.xy(lo, la))
    S.add("符号", M.peak_svg(x, y, 1.0 if major else 0.75)); placer.block(x-4, y-4, x+4, y+3)

# ── 注记 ───────────────────────────────────────────────────────────
WATER_FILL, TERR_FILL = C["water_label"], "#707070"
def area_label(zh, en, lo, la, zs, es, fill, spacing=2.2, rotate=0):
    x, y = map(float, P.xy(lo, la))
    wz = text_width(zh, zs, "cjk", spacing); we = text_width(en, es, "lat_i", 0.9) if en else 0; w = max(wz, we)
    tf = f' transform="rotate({rotate:.1f} {x:.1f} {y:.1f})"' if rotate else ""
    S.add("地貌注记", f"<g{tf}>")
    S.text("地貌注记", x, y, zh, zs, "cjk", fill=fill, anchor="middle", spacing=spacing, halo=2.4)
    if en: S.text("地貌注记", x, y+es*1.35, en, es, "lat_i", fill=fill, anchor="middle", spacing=0.9, halo=2, italic=True)
    S.add("地貌注记", "</g>")
    ext = abs(math.sin(math.radians(rotate)))*w/2
    placer.block(x-w/2*abs(math.cos(math.radians(rotate)))-4, y-zs-ext, x+w/2*abs(math.cos(math.radians(rotate)))+4, y+es*1.6+ext)

area_label("亚马逊湾", "BOREALIS SEA · AMAZONIS BAY", 199.5, 28.6, 12, 6.8, WATER_FILL, 3)
area_label("塔西斯山脉", "THARSIS MONTES", 243.4, 7.0, 15, 7.5, TERR_FILL, 9, rotate=-51)
TERR = [("诺克提斯迷宫", "NOCTIS LABYRINTHUS", 259.5, -4.6), ("叙利亚高原", "SYRIA PLANUM", 260.5, -13.5),
        ("代达利亚高原", "DAEDALIA PLANUM", 232.0, -18.3), ("亚马逊平原", "AMAZONIS PLANITIA", 205.0, 12.5),
        ("吕科斯沟群", "LYCUS SULCI", 214.5, 25.0), ("刻拉尼俄斯堑沟群", "CERAUNIUS FOSSAE", 250.0, 27.0),
        ("曼加拉谷", "MANGALA VALLES", 208.6, -11.3), ("美杜莎堑沟群", "MEDUSAE FOSSAE", 198.5, -3.5),
        ("阿尔西亚沟群", "ARSIA SULCI", 229.0, -6.3), ("奥林匹斯断崖", "OLYMPUS RUPES", 219.0, 16.2),
        ("Oudemans 陨坑", "", 268.2, -12.4)]
SPACING = {"Oudemans 陨坑": 0.5}
for zh, en, lo, la in TERR:
    area_label(zh, en, lo, la, 9.2, 6.0, TERR_FILL, SPACING.get(zh, 2.2))

def place_town(r, x, y, br, extra=None):
    tier = r["等级"]; star = " ☆" if r["正典"] == "仅地图" else ""
    zs = {"1": 11.0, "2": 9.6, "3": 8.6}[tier]
    nm = r["中文名"].replace("宙斯度假区·火山口分部", "宙斯度假区火山口分部")
    lines = [(nm + star, zs, "cjk_b" if tier == "1" else "cjk", C["ink"])]
    if tier == "1": lines.append((r["英文名"], 6.8, "lat", C["ink2"]))
    z = float(r["MOLA高程_m"])
    lines.append(((extra + "·" if extra else "") + f"{z:,.0f} m", 6.6, "cjk", BREATH_C if z > BREATH else C["ink2"]))
    w = max(text_width(t, s, k) for t, s, k, _ in lines); h = sum(s*1.18 for _, s, _, _ in lines)
    for g_extra in (2.5, 7):
        got = placer.place(x, y, w, h, gap=br+g_extra)
        if got: break
    if not got: return False
    yy = got[1]
    for t, s, k, fl in lines:
        yy += s*1.02
        S.text("城镇注记", got[0], yy, t, s, k, fill=fl, halo=2.3, weight="bold" if k == "cjk_b" else "normal")
        yy += s*0.16
    return True

EXTRA = {"new_shanghai": "太空电梯地面站", "nix_olympica": "火星大学·宙斯度假区", "haiyuan": "锈色中国首府",
         "zeus_caldera": "山顶火山口底", "guxiang": "锈色中国第一个定居点"}
miss = []
for r, x, y, br in sorted(pts, key=lambda t: (t[0]["等级"], -t[2])):
    if not place_town(r, x, y, br, EXTRA.get(r["id"])): miss.append(r["中文名"])
for zh, lo, la, z, major in peak_pts:
    x, y = map(float, P.xy(lo, la)); e = f"{z:,.0f} m"
    zs = 8.8 if major else 7.4
    w = max(text_width(zh, zs, "cjk"), text_width(e, 6.6, "lat")); h = zs*1.2 + 8
    got = placer.place(x, y, w, h, gap=6)
    if not got: miss.append(zh); continue
    S.text("地貌注记", got[0], got[1]+zs, zh, zs, "cjk", halo=2.2, weight="normal")
    S.text("地貌注记", got[0], got[1]+zs+8.4, e, 6.6, "lat", fill=BREATH_C if z > BREATH else C["ink2"], halo=2)
if miss: print("  ⚠ 没放下的注记：", "、".join(miss))

for _, x, y, br in pts: placer.block(x-br-7, y-br-7, x+br+7, y+br+7)   # 计曲线数字离城镇符号远一点
n_lab = M.label_contours(S, placer, index_lines)
print(f"  计曲线注记 {n_lab} 处")

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", X0, 52, "塔西斯", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", X0 + text_width("塔西斯", 30, "cjk_b", 3) + 18, 52, "火山高原地形图 · 2100 年 3 月", 14, "cjk", fill=C["ink2"])
S.text("图名", X0, 72, "THARSIS  ·  TOPOGRAPHIC MAP  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
RX = SW - 48
S.text("图名", RX, 46, "墨卡托投影 · 赤道比例与《水手峡谷战区图》相同  ·  火星 2000 参考球  R = 3,396.19 km", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 60, f"等高线间距 {CONTOUR_STEP:,} m，每 {INDEX_STEP:,} m 加粗；高程从火星大地水准面起算", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 74, "海岸线测绘于 2100 年 3 月　北方海仍在上涨，本图岸线逐年失效", 8.2, "cjk", fill=C["alert"], anchor="end")

# ── 右栏 ───────────────────────────────────────────────────────────
LY = Y0 + 8
S.text("图例", LX, LY, "图例", 11.5, "cjk_b", weight="bold")
items = [("cn", "锈色中国"), ("us", "火星联邦（美）"), ("other", "独立 / 沙特 / 其他"), ("corp", "设施"),
         ("major", "主要城市"), ("rail", "赤道铁路及支线"), ("station", "车站"), ("peak", "火山峰顶"),
         ("spot", "山丘顶（高程点）"), ("contour", "等高线 1,000 m"), ("index", "计曲线 5,000 m"),
         ("breath", "呼吸线 8,047 m"), ("coast", "海岸线（−3,700 m）"), ("star", "☆ 仅见于正典地图")]
for i, (k, t_) in enumerate(items):
    col, row = i % 2, i // 2
    x = LX + col*140; y = LY + 24 + row*19
    if k in ("cn", "us", "corp", "other"): S.add("图例", M.symbol(k, x+8, y-3.5, 3.0))
    elif k == "major": S.add("图例", M.symbol("cn", x+8, y-3.5, 3.2, major=True))
    elif k == "rail": S.add("图例", M.rail_svg([(x-1, y-3.5), (x+19, y-3.5)], "干线"))
    elif k == "station": S.add("图例", f'<rect x="{x+5.8:.1f}" y="{y-5.7:.1f}" width="4.4" height="4.4" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')
    elif k == "peak": S.add("图例", M.peak_svg(x+8, y-3.5))
    elif k == "spot": S.add("图例", M.peak_svg(x+8, y-3.5, 0.75))
    elif k == "contour": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{M.CONTOUR}" stroke-width="0.35" opacity="0.7"/>')
    elif k == "index": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{M.CONTOUR}" stroke-width="0.7" opacity="0.8"/>')
    elif k == "breath": S.add("图例", f'<rect x="{x:.1f}" y="{y-9:.1f}" width="18" height="11" fill="url(#thin)" opacity="0.7" stroke="{BREATH_C}" stroke-width="0.9" stroke-dasharray="4 1.8"/>')
    elif k == "coast": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{C["coast"]}" stroke-width="0.9"/>')
    S.text("图例", x+(25 if k != "star" else 0), y, t_, 8.6, "cjk")

d_avg = M.load_dem32_avg()
cell = (math.radians(1/32)*M.R/1e3)**2*np.cos(np.radians(90 - (np.arange(5760) + 0.5)/32))[:, None]
BREATH_AREA, MARS_AREA = float((cell*(d_avg > BREATH)).sum()), float(cell.sum())*11520
del d_avg
yb = LY + 24 + 7*19 + 18
S.text("图例", LX, yb, "呼吸线", 11.5, "cjk_b", weight="bold", fill=BREATH_C)
for i, t_ in enumerate(["正典：海拔 5 英里（8,047 m）以上气压太低，",
                        "连基因改造的动物和人也无法呼吸（ITW p.34）。",
                        "斜线区里的城市必须封顶，新上海就是这样（正典）。",
                        "图上高于这条线的高程数字用紫色。",
                        f"全火星只有 {BREATH_AREA/MARS_AREA:.2%}（约 {BREATH_AREA/1e4:,.0f} 万 km²，≈ 四川省）",
                        "在线以上，几乎全在这张图里。"]):
    S.text("图例", LX, yb + 20 + i*14, t_, 8.4, "cjk", fill=C["ink2"])

yc = yb + 20 + 6*14 + 26
M.hypso_bar(S, "图例", LX, yc + 8, 270, -4000, 20000, 6000, "hyp", title="高程（m）")
x8 = LX + (BREATH + 4000)/24000*270
S.add("图例", f'<line x1="{x8:.1f}" y1="{yc+4}" x2="{x8:.1f}" y2="{yc+19}" stroke="{BREATH_C}" stroke-width="1.2"/>')

ys_ = yc + 62
S.text("图例", LX, ys_, "比例尺", 9.5, "cjk_b", weight="bold")
for i, la in enumerate((0, 30)):
    upk = 1/P.km_per_unit(la)
    S.text("图例", LX, ys_ + 22 + i*34, f"{'赤道' if la == 0 else f'{la}°N'}", 8, "cjk", fill=C["ink2"])
    M.scale_bar(S, "图例", LX + 38, ys_ + 14 + i*34, upk, 100, 5, size=6.6, h=4)
S.text("图例", LX, ys_ + 22 + 2*34 - 6, "墨卡托投影：纬度越高比例越大，量距离请用对应纬度的尺。", 7.8, "cjk", fill=C["ink2"])

yn = ys_ + 112
S.text("图例", LX, yn, "注", 9.5, "cjk_b", weight="bold")
ns = PLACES["new_shanghai"]
notes = [f"· 新上海在帕弗尼斯山顶火山口南缘，{float(ns['MOLA高程_m']):,.0f} m，",
         "　 比呼吸线高近 6 km，六座穹顶全封闭（正典）。",
         "· 尼克斯奥林匹卡在奥林匹斯山南坡断崖顶上，",
         f"　 城里 {float(PLACES['nix_olympica']['MOLA高程_m']):,.0f} m，山顶火山口分部 {float(PLACES['zeus_caldera']['MOLA高程_m']):,.0f} m。",
         f"· 赤道铁路在图内最高处约 {rail_max[0]:,.0f} m（{rail_max[1][0]:.1f}°E）。",
         "· 正典未划定中美边界，本图不画国界。"]
y4 = M.note_lines(S, "图例", LX, yn + 18, notes, size=8.4, lh=14)
M.index_map(S, "图例", LX, y4 + 30, 270, "塔西斯区域图")

S.text("出处", X0, SH-22, "底图：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接）；晕渲光源方位 315°、高度 40°；等高线由 32 px/度重采样高程平滑后提取。"
       "地貌名：IAU 行星地名库。城镇与铁路：GURPS Transhuman Space《In The Well》，位置按正典给出的地理关系在真实地形上重新确定。",
       7.0, "cjk", fill=C["ink3"])

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
