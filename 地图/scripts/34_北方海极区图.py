#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北方海极区图（2100 年 3 月）—— 北极心兰伯特等积方位投影，画到 5°N。
风格与 30_/31_ 一致：白纸、MOLA 晕渲、浅蓝水面、细黑经纬网；除晕渲外全矢量。
比全图多三样：1,000 m 间隔等深线；「海面再涨 200 m」会淹掉的沿岸带（斜线）；北方海数据表。

数据：DEM/dem_32ppd_avg.npy（晕渲）、DEM/dem_32ppd_min.npy（连通判断）、产出/三海掩膜.npz、数据/火星地点.csv
产出：产出/北方海极区图_2100.svg（除晕渲外全矢量）  产出/北方海极区图_2100.png（3 倍，印刷用）
运行：./.venv/bin/python scripts/34_北方海极区图.py
"""
import math, subprocess, sys
import numpy as np
from scipy import ndimage
from affine import Affine
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Azimuthal, Identity, text_width

NAME = "北方海极区图_2100"
LAT_EDGE = 5.0
LON_BOTTOM = 300.0                   # 朝正下方的经线：克律塞湾向下伸出，塔西斯在左下
RM = 540.0                           # 图面半径
CX, CY = 84 + 36 + RM, 124 + 34 + RM
SS, PAD = 3, 10                      # 底图超采样倍数；底图比图框多画一圈，免得边上露白
P = Azimuthal(90, LON_BOTTOM, CX, CY, RM/(2*M.R/1e3*math.sin(math.radians(90-LAT_EDGE)/2)))
SW, SH = 1848, int(CY + RM + 96)
S = SVG(SW, SH, "北方海极区图 · 2100 年 3 月")
RISE = 200

Z = M.load_masks()
LV = int(Z["level_borealis"])
PLACES = M.load_places()
PEAKS = {r["山"]: r for r in M.load_peaks()}
IAU = M.load_iau()

# ── 北方海数据（32 px/度全球网格上统计）─────────────────────────────
print("统计 …")
d_avg = M.load_dem32_avg()
lat_rows = 90 - (np.arange(5760) + 0.5)/32
cell = (math.radians(1/32)*M.R/1e3)**2*np.cos(np.radians(lat_rows))[:, None]
sea32 = Z["borealis"]
area = float((cell*sea32).sum())
depth32 = np.clip(LV - d_avg, 0, None)*sea32
vol = float((cell*depth32/1e3).sum())                               # km³
mars_area = float(cell.sum())*11520
max_depth = float(depth32.max())
d_min = M.load_dem32()
low = d_min < LV + RISE
lab, _ = ndimage.label(low)
ids = np.unique(lab[sea32 & low]); ids = ids[ids > 0]
fut32 = np.isin(lab, ids)
rise_area = float((cell*(fut32 & ~sea32)).sum())
del lab, low
STATS = dict(area=area, vol=vol, gel=vol/mars_area*1e3, max_depth=max_depth, mean_depth=vol/area*1e3, rise_area=rise_area)
print("  面积 {area:,.0f} km²  体积 {vol:,.0f} km³  全球等效水层 {gel:.0f} m  最深 {max_depth:,.0f} m  平均 {mean_depth:,.0f} m  "
      "再涨 {r} m 新淹 {rise_area:,.0f} km²".format(r=RISE, **STATS))

# ── 底图：逆投影采样 ─────────────────────────────────────────────────
print("底图 …")
n = int((2*RM + 2*PAD)*SS)
OX, OY = CX - RM - PAD, CY - RM - PAD
ys, xs = np.mgrid[0:n, 0:n]
lon, lat, ok = P.inverse(OX + (xs + 0.5)/SS, OY + (ys + 0.5)/SS)
del xs, ys
ok &= lat >= LAT_EDGE - 1
dem = M.sample_lonlat(d_avg, 32, lon, lat, order=1).astype(np.float32)
def grab(mask32):
    """32 px/度掩膜 → 投影网格，再按细高程修一遍岸线（沿用 32 px/度的水位与连通关系）。"""
    m = M.sample_lonlat(mask32, 32, lon, lat, order=0).astype(bool)
    return ndimage.binary_dilation(m, np.ones((5, 5), bool)) & (dem < LV + (RISE if mask32 is fut32 else 0)) & ok
sea = grab(sea32)
fut = grab(fut32) & ~sea
del lon, lat
px_m = 1000/(P.scale*SS)
rgb = M.colorize(dem, M.shade(dem, px_m, px_m, zfac=4.0), [sea], [LV])
rgb[~ok] = 255
S.add("底图", f'<clipPath id="clipMap"><circle cx="{CX}" cy="{CY}" r="{RM}"/></clipPath>')
S.add("底图", f'<image x="{OX}" y="{OY}" width="{2*RM+2*PAD}" height="{2*RM+2*PAD}" preserveAspectRatio="none" '
              f'clip-path="url(#clipMap)" href="{M.png_data_uri(rgb, quality=90)}"/>')
del rgb

TF = Affine(1/SS, 0, OX, 0, 1/SS, OY)
to_xy = lambda r, c: (OX + (c + 0.5)/SS, OY + (r + 0.5)/SS)

# 再涨 200 m 的淹没带：蓝色细斜线
S.add("水系", f'<pattern id="rise" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
              f'<line x1="0" y1="0" x2="0" y2="4" stroke="{C["coast"]}" stroke-width="0.7"/></pattern>')
rings = M.mask_rings(fut, SS, min_px=60, simplify=0.3, smooth=2, transform=TF)
S.add("水系", f'<path d="{M.rings_to_path(rings, Identity())}" fill="url(#rise)" fill-rule="evenodd" opacity="0.75" clip-path="url(#clipMap)"/>')
# 等深线
dsea = np.where(ndimage.binary_erosion(sea, np.ones((3, 3), bool)), dem, LV + 400)
for dep, w in ((1000, 0.4), (2000, 0.4)):
    for lv, d in M.contour_paths(dsea, [LV - dep], to_xy, sigma=2.0, min_len=18, tol=0.4).items():
        S.add("水系", f'<path d="{d}" fill="none" stroke="{C["coast"]}" stroke-width="{w}" opacity="0.55" clip-path="url(#clipMap)"/>')
# 海岸线
rings = M.mask_rings(sea, SS, min_px=30, simplify=0.25, smooth=2, transform=TF)
S.add("海岸线", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{C["coast"]}" stroke-width="0.7" stroke-linejoin="round" clip-path="url(#clipMap)"/>')
del dem, dsea

# ── 经纬网 ─────────────────────────────────────────────────────────
g = []
for la in range(10, 90, 10):
    g.append(f'<circle cx="{CX}" cy="{CY}" r="{P.radius_of(la):.1f}"/>')
r80 = P.radius_of(80)
for lo in range(0, 360, 30):
    x0, y0 = P.xy(lo, 80); x1, y1 = P.xy(lo, LAT_EDGE)
    g.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}"/>')
S.add("经纬网", f'<g fill="none" stroke="{C["grat"]}" stroke-width="0.35" opacity="0.28">' + "".join(g) + "</g>")
t = []
for lo in range(0, 360, 2):
    L = 7 if lo % 30 == 0 else (4.5 if lo % 10 == 0 else 2.2)
    a = math.radians(lo - LON_BOTTOM)
    ux, uy = math.sin(a), math.cos(a)
    t.append(f'<line x1="{CX+RM*ux:.1f}" y1="{CY+RM*uy:.1f}" x2="{CX+(RM+L)*ux:.1f}" y2="{CY+(RM+L)*uy:.1f}"/>')
S.add("图廓", f'<g stroke="{C["frame"]}" stroke-width="0.6">' + "".join(t) + "</g>")
S.add("图廓", f'<circle cx="{CX}" cy="{CY}" r="{RM}" fill="none" stroke="{C["frame"]}" stroke-width="1.0"/>')
for lo in range(0, 360, 30):
    a = math.radians(lo - LON_BOTTOM); ux, uy = math.sin(a), math.cos(a)
    x, y = CX + (RM+22)*ux, CY + (RM+22)*uy + 3
    anchor = "middle" if abs(ux) < 0.5 else ("start" if ux > 0 else "end")
    if abs(ux) >= 0.5: x -= 8*ux
    S.text("图廓", x, y - (4 if uy < -0.5 else 0) + (5 if uy > 0.5 else 0), f"{lo}°E", 8.5, "lat", anchor=anchor)
    S.text("图廓", x, y + 9.5 - (4 if uy < -0.5 else 0) + (5 if uy > 0.5 else 0), f"{(360-lo) % 360}°W", 7, "lat", anchor=anchor, fill=C["ink2"])
S.add("图廓", f'<path d="M{CX-4:.1f} {CY}h8M{CX} {CY-4:.1f}v8" fill="none" stroke="{C["ink"]}" stroke-width="0.8"/>')   # 极点：细十字，不与城镇圆点混淆

pl_bounds = (CX-RM, CY-RM, CX+RM, CY+RM)
class CPlacer(Placer):
    def free(self, b, pad=1.5):
        x0, y0, x1, y1 = b
        if any(math.hypot(xx-CX, yy-CY) > RM-4 for xx, yy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))): return False
        return super().free(b, pad)
pl = CPlacer(pl_bounds)
LAT_LABEL_LON = 75.0
for la in range(10, 90, 10):
    x, y = P.xy(LAT_LABEL_LON, la); x, y = float(x), float(y)
    s = f"{la}°N"; w = text_width(s, 7, "lat")
    S.text("经纬网", x+2, y-2.5, s, 7, "lat", fill=C["ink2"], halo=2)
    pl.block(x, y-10, x+w+4, y)

# ── 符号 ───────────────────────────────────────────────────────────
POINT_CATS = {"城市", "城镇", "遗址", "军事"}
def in_map(lo, la):
    x, y = P.xy(lo, la); return la > LAT_EDGE and math.hypot(float(x)-CX, float(y)-CY) < RM-6
pts = []
for r in PLACES:
    lo, la = float(r["东经"]), float(r["纬度"])
    if r["类别"] not in POINT_CATS or not in_map(lo, la): continue
    x, y = map(float, P.xy(lo, la))
    rad = {"1": 3.3, "2": 2.8, "3": 2.3}[r["等级"]]
    S.add("符号", M.symbol(M.faction_kind(r["阵营"]), x, y, rad, major=r["等级"] == "1"))
    br = rad + (2.4 if r["等级"] == "1" else 0) + 1
    pl.block(x-br, y-br, x+br, y+br)
    pts.append((r, x, y, br))
PEAK_ZH = {"Olympus Mons": "奥林匹斯山", "Ascraeus Mons": "艾斯克雷尔斯山", "Elysium Mons": "伊利瑟姆山",
           "Alba Mons": "阿尔巴山", "Uranius Mons": "乌拉纽斯山", "Ceraunius Tholus": "刻拉尼俄斯山丘",
           "Hecates Tholus": "赫卡忒山丘", "Albor Tholus": "阿尔博尔山丘", "Tharsis Tholus": "塔西斯山丘"}
for nme in PEAK_ZH:
    pk = PEAKS[nme]; x, y = map(float, P.xy(float(pk["峰顶东经"]), float(pk["峰顶纬度"])))
    S.add("符号", M.peak_svg(x, y, 0.9)); pl.block(x-3.5, y-3.5, x+3.5, y+2.5)

# ── 注记 ───────────────────────────────────────────────────────────
WATER_FILL, TERR_FILL = C["water_label"], "#707070"

def arc_text(layer, lat, lon_c, s, size, fill, kind="cjk", spacing=0.0, italic=False, halo=2.4):
    """沿纬线弧排字：上半圈顺时针读，下半圈逆时针读，字头都朝外 / 朝上。"""
    r = P.radius_of(lat)
    phi_c = 180 - (lon_c - LON_BOTTOM)                                  # 屏幕角：正上方为 0，顺时针为正
    phi_c = ((phi_c + 180) % 360) - 180
    bottom = abs(phi_c) > 90
    ws = [text_width(ch, size, kind) + spacing for ch in s]
    total = sum(ws) - spacing
    pos = -total/2
    for ch, w in zip(s, ws):
        mid = pos + (w - spacing)/2
        d = math.degrees(mid/r)
        phi = phi_c + (-d if bottom else d)
        rr = r - size*0.35 if not bottom else r + size*0.35
        x = CX + rr*math.sin(math.radians(phi)); y = CY - rr*math.cos(math.radians(phi))
        rot = phi - 180 if bottom else phi
        st = ' font-style="italic"' if italic else ""
        S.add(layer, f'<text x="{x:.1f}" y="{y:.1f}" transform="rotate({rot:.1f} {x:.1f} {y:.1f})" '
                     f'font-family="{M.FAM_CJK if "cjk" in kind else M.FAM_LAT}" font-size="{size}"{st} fill="{fill}" '
                     f'text-anchor="middle" dominant-baseline="central" stroke="#FFFFFF" stroke-width="{halo}" '
                     f'stroke-linejoin="round" paint-order="stroke">{M.esc(ch)}</text>')
        pl.block(x-size*0.6, y-size*0.6, x+size*0.6, y+size*0.6)
        pos += w

arc_text("水体注记", 64.0, 128.0, "北　方　海", 22, WATER_FILL, spacing=2)
arc_text("水体注记", 68.2, 128.0, "BOREALIS SEA", 8.5, WATER_FILL, kind="lat_i", spacing=3.2, italic=True)   # 上半圈：往极点方向才是字的下方
arc_text("水体注记", 64.5, 318.0, "北　方　海", 17, WATER_FILL, spacing=2)
arc_text("水体注记", 61.4, 318.0, "BOREALIS SEA", 7.5, WATER_FILL, kind="lat_i", spacing=2.8, italic=True)

def put_area(lo, la, zh, en, zs, es, fill, sp, italic_zh=False):
    x, y = map(float, P.xy(lo, la))
    wz = text_width(zh, zs, "cjk", sp); we = text_width(en, es, "lat_i", 0.8) if en else 0; w = max(wz, we)
    for dx, dy in ((0, 0), (0, -9), (0, 9), (-14, 0), (14, 0), (0, -18), (0, 18), (-26, 0), (26, 0)):
        box = (x+dx-w/2, y+dy-zs, x+dx+w/2, y+dy+(es*1.6 if en else 2))
        if pl.free(box):
            pl.block(*box)
            S.text("面状注记", x+dx, y+dy, zh, zs, "cjk", fill=fill, anchor="middle", spacing=sp, halo=2.4, italic=italic_zh)
            if en: S.text("面状注记", x+dx, y+dy+es*1.35, en, es, "lat_i", fill=fill, anchor="middle", spacing=0.8, halo=2, italic=True)
            return True
    print("   面状注记没放下：", zh)
    return False

def put_peak(nme, zh):
    pk = PEAKS[nme]; x, y = map(float, P.xy(float(pk["峰顶东经"]), float(pk["峰顶纬度"])))
    e = f"{int(float(pk['峰顶MOLA高程_m'])):,} m"
    w = max(text_width(zh, 7.6, "cjk"), text_width(e, 6.2, "lat"))
    for gap in (5, 9):
        got = pl.place(x, y, w, 15.5, gap=gap)
        if got:
            S.text("城镇注记", got[0], got[1]+7.4, zh, 7.6, "cjk", halo=2)
            S.text("城镇注记", got[0], got[1]+14.6, e, 6.2, "lat", fill=C["ink2"], halo=2)
            return True
    print("   山峰注记没放下：", zh)
    return False

def put_town(r, x, y, br, gap_extra=2.0):
    tier = r["等级"]; star = " ☆" if r["正典"] == "仅地图" else ""
    zs = {"1": 10.5, "2": 9.0, "3": 8.0}[tier]
    s = r["中文名"].split("（")[0].replace("维京公园·海盗 1 号着陆点", "维京公园") + star
    lines = [(s, zs, "cjk_b" if tier == "1" else "cjk", C["ink"])]
    if tier in ("1", "2") and r["英文名"] != r["中文名"]: lines.append((r["英文名"].split(" / ")[0], 6.4, "lat", C["ink2"]))
    w = max(text_width(t, sz, k) for t, sz, k, _ in lines); h = sum(sz*1.18 for _, sz, _, _ in lines)
    got = pl.place(x, y, w, h, gap=br+gap_extra)
    if not got: return False
    yy = got[1]
    for t, sz, k, f in lines:
        yy += sz*1.02
        S.text("城镇注记", got[0], yy, t, sz, k, fill=f, halo=2.2, weight="bold" if k == "cjk_b" else "normal")
        yy += sz*0.16
    return True

for zh, en, la, lo, zs in [("克律塞湾", "CHRYSE BAY", 30.5, 318.5, 11), ("亚马逊湾", "AMAZONIS BAY", 33.0, 197.0, 11),
                           ("Adamas 湾", "ADAMAS BAY", 40.5, 110.0, 10.5)]:
    put_area(lo, la, zh, en, zs, 6.6, WATER_FILL, 2.5)
miss = []
order = sorted(pts, key=lambda t: (t[0]["等级"], t[0]["id"]))
for r, x, y, br in order:
    if r["等级"] == "1" and not put_town(r, x, y, br): miss.append(r)
for nme, zh in PEAK_ZH.items(): put_peak(nme, zh)
for r, x, y, br in order:
    if r["等级"] != "1" and not put_town(r, x, y, br): miss.append(r)
for r in list(miss):
    _, x, y, br = next(p for p in pts if p[0] is r)
    if put_town(r, x, y, br, gap_extra=6.0): miss.remove(r)
if miss: print("  ⚠ 没放下的城镇注记：", "、".join(r["中文名"] for r in miss))

# 海底地名（蓝色斜体）与陆上地貌（灰色）
UNDER = [("乌托邦平原", "UTOPIA PLANITIA", "Utopia Planitia"), ("阿西达利亚平原", "ACIDALIA PLANITIA", "Acidalia Planitia"),
         ("阿卡迪亚平原", "ARCADIA PLANITIA", "Arcadia Planitia"), ("亚马逊平原", "AMAZONIS PLANITIA", None),
         ("利奥陨坑", "LYOT", "Lyot"), ("科罗廖夫陨坑", "KOROLEV", "Korolev"), ("奥林匹亚沙丘带", "OLYMPIA UNDAE", "Olympia Undae"),
         ("北极大峡谷", "CHASMA BOREALE", "Chasma Boreale"), ("斯堪迪亚丘陵", "SCANDIA COLLES", "Scandia Colles"),
         ("基多尼亚桌山群", "CYDONIA MENSAE", "Cydonia Mensae")]
POS_OVERRIDE = {"亚马逊平原": (37.0, 204.0), "阿卡迪亚平原": (52.0, 188.0)}
for zh, en, key in UNDER:
    la, lo = POS_OVERRIDE.get(zh) or (float(IAU[key]["center_lat"]), float(IAU[key]["center_lon"]) % 360)
    put_area(lo, la, zh, en, 7.8, 5.6, WATER_FILL, 1.2, italic_zh=True)
LAND = [("北极冰盖", "PLANUM BOREUM", 86.0, 20.0), ("塔西斯", "THARSIS", 9.0, 262.0), ("滕比高地", "TEMPE TERRA", 38.7, 289.4),
        ("阿拉伯高地", "ARABIA TERRA", 22.0, 8.0), ("伊利瑟姆", "ELYSIUM", 16.0, 140.0), ("大瑟提斯", "SYRTIS MAJOR", 10.0, 67.0),
        ("伊希斯平原", "ISIDIS PLANITIA", 13.9, 88.4), ("弗莱格拉山脉", "PHLEGRA MONTES", 40.4, 163.7),
        ("月神高原", "LUNAE PLANUM", 11.0, 294.5), ("马瑞奥提斯堑沟群", "MAREOTIS FOSSAE", 45.0, 283.9),
        ("坦塔罗斯堑沟群", "TANTALUS FOSSAE", 49.8, 263.9), ("第二尼罗桌山群", "DEUTERONILUS MENSAE", 44.5, 24.0),
        ("卡塞谷", "KASEI VALLES · 劫道土匪出没", 26.0, 292.5), ("秘鲁殖民地", "PERUVIAN COLONY", 25.0, 140.0)]
for zh, en, la, lo in LAND:
    put_area(lo, la, zh, en, 8.6, 5.6, TERR_FILL, 1.8)

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", 84, 52, "北方海", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", 84 + text_width("北方海", 30, "cjk_b", 3) + 18, 52, "北极区地形与水系图 · 2100 年 3 月", 14, "cjk", fill=C["ink2"])
S.text("图名", 84, 72, "BOREALIS SEA  ·  NORTH POLAR REGION  ·  TOPOGRAPHY AND BATHYMETRY  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
RX = SW - 84
S.text("图名", RX, 46, "北极心兰伯特等积方位投影 · 5°N 以北  ·  火星 2000 参考球  R = 3,396.19 km", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 60, "面积比例处处正确；离北极越远，南北向越扁、东西向越宽", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 74, "海岸线测绘于 2100 年 3 月　北方海仍在上涨，本图岸线逐年失效", 8.2, "cjk", fill=C["alert"], anchor="end")

# ── 右栏：图例、数据、比例尺 ───────────────────────────────────────
LX = CX + RM + 96
LY = 176
S.text("图例", LX, LY, "图例", 11.5, "cjk_b", weight="bold")
items = [("cn", "锈色中国"), ("us", "火星联邦（美）"), ("corp", "企业城邦"), ("other", "独立 / 其他"),
         ("major", "主要城市"), ("peak", "山峰（MOLA 峰顶高程）"), ("coast", "海岸线（−3,700 m）"),
         ("iso", "等深线（间隔 1,000 m）"), ("rise", f"海面再涨 {RISE} m 将淹没"), ("star", "☆ 仅见于正典地图")]
for i, (k, t_) in enumerate(items):
    col, row = i % 2, i // 2
    x = LX + col*200; y = LY + 26 + row*21
    if k in ("cn", "us", "corp", "other"): S.add("图例", M.symbol(k, x+8, y-3.5, 3.0))
    elif k == "major": S.add("图例", M.symbol("other", x+8, y-3.5, 3.2, major=True))
    elif k == "peak": S.add("图例", M.peak_svg(x+8, y-3.5, 0.95))
    elif k == "coast": S.add("图例", f'<path d="M{x:.1f},{y-3.5:.1f} h18" stroke="{C["coast"]}" stroke-width="0.9"/>')
    elif k == "iso": S.add("图例", f'<path d="M{x:.1f},{y-3.5:.1f} h18" stroke="{C["coast"]}" stroke-width="0.45" opacity="0.7"/>')
    elif k == "rise": S.add("图例", f'<rect x="{x:.1f}" y="{y-9:.1f}" width="18" height="11" fill="url(#rise)" stroke="{C["coast"]}" stroke-width="0.4"/>')
    S.text("图例", x+(26 if k != "star" else 0), y, t_, 9, "cjk")

y0 = LY + 26 + 5*21 + 22
S.text("图例", LX, y0, "北方海数据", 11.5, "cjk_b", weight="bold")
rows = [("水面高程", "−3,700 m（火星大地水准面起算）"),
        ("面积", f"{STATS['area']/1e4:,.0f} 万 km²  ≈ 北美洲，地中海的 10 倍"),
        ("平均水深", f"{STATS['mean_depth']:,.0f} m"),
        ("最深处", f"{STATS['max_depth']:,.0f} m（陨坑坑底）"),
        ("水量", f"{STATS['vol']/1e4:,.0f} 万 km³"),
        ("全球等效水层", f"{STATS['gel']:,.0f} m（全部水铺满火星的厚度）"),
        (f"再涨 {RISE} m", f"新淹 {STATS['rise_area']/1e4:,.0f} 万 km²，主要在克律塞、阿西达利亚沿岸")]
for i, (a, b) in enumerate(rows):
    yy = y0 + 24 + i*17
    S.text("图例", LX, yy, a, 9, "cjk", fill=C["ink2"])
    S.text("图例", LX + 88, yy, b, 9, "cjk")

y1 = y0 + 24 + len(rows)*17 + 30
S.text("图例", LX, y1, "水深（m）", 9.5, "cjk_b", weight="bold")
BW = 170
vals = np.linspace(0, 2000, 100); cols = M.ramp(vals, M.BATHY)
stops = "".join(f'<stop offset="{i/99:.3f}" stop-color="rgb({int(c[0])},{int(c[1])},{int(c[2])})"/>' for i, c in enumerate(cols))
S.add("图例", f'<linearGradient id="bath">{stops}</linearGradient><rect x="{LX}" y="{y1+10}" width="{BW}" height="8" fill="url(#bath)" stroke="{C["ink"]}" stroke-width="0.5"/>')
for v in range(0, 2001, 500):
    xx = LX + v/2000*BW
    S.add("图例", f'<line x1="{xx:.1f}" y1="{y1+18}" x2="{xx:.1f}" y2="{y1+21}" stroke="{C["ink"]}" stroke-width="0.5"/>')
    S.text("图例", xx, y1+30, f"{v:,}", 6.8, "lat", anchor="middle")
M.hypso_bar(S, "图例", LX + 210, y1 + 10, 220, -4000, 20000, 6000, "hyp", title="陆地高程（m）")

y2 = y1 + 72
M.scale_bar(S, "图例", LX, y2 + 12, P.scale, 250, 4, title="比例尺（北极点处）")
S.text("图例", LX, y2 + 44, "等积投影：离极点越远，南北向比例越小、东西向越大。", 8.4, "cjk", fill=C["ink2"])
S.text("图例", LX, y2 + 58, "5°N 图边上，南北向 × 0.74，东西向 × 1.36。", 8.4, "cjk", fill=C["ink2"])

yt = y2 + 92
S.text("图例", LX, yt, "沿岸聚落离海面有多高", 11.5, "cjk_b", weight="bold")
S.text("图例", LX + 150, yt, "按 463 m 高程格网取值，海面每涨过这个高度就进城", 7.6, "cjk", fill=C["ink2"])
coast = sorted([r for r in PLACES if r["最近水体"] == "北方海" and float(r["离水_km"]) <= 100 and float(r["纬度"]) > LAT_EDGE
                and r["类别"] in POINT_CATS], key=lambda r: float(r["MOLA高程_m"]))
TX = (LX, LX + 170, LX + 250, LX + 330)
for j, hd in enumerate(("聚落", "高出海面", "离岸", "阵营")):
    S.text("图例", TX[j], yt + 22, hd, 8.4, "cjk_b", fill=C["ink2"], weight="bold", anchor="end" if j in (1, 2) else "start")
S.add("图例", f'<line x1="{LX}" y1="{yt+27}" x2="{LX+440}" y2="{yt+27}" stroke="{C["ink"]}" stroke-width="0.5"/>')
for i, r in enumerate(coast):
    yy = yt + 41 + i*14.5
    nm = r["中文名"].split("（")[0].replace("维京公园·海盗 1 号着陆点", "维京公园（海盗 1 号）") + (" ☆" if r["正典"] == "仅地图" else "")
    S.text("图例", TX[0], yy, nm, 8.6, "cjk")
    S.text("图例", TX[1], yy, f"+{float(r['MOLA高程_m']) - LV:,.0f} m", 8.6, "lat", anchor="end")
    S.text("图例", TX[2], yy, f"{float(r['离水_km']):,.0f} km", 8.6, "lat", anchor="end")
    S.text("图例", TX[3], yy, r["阵营"].replace("（按命名推断）", "？"), 8.2, "cjk", fill=C["ink2"])
y3 = yt + 41 + len(coast)*14.5 + 22
S.text("图例", LX, y3, "注", 9.5, "cjk_b", weight="bold")
notes = ["· 北方海绕北极整整一圈，中间的北极冰盖是岛。正典：冰盖处在消失边缘，",
         "　 无人值守的钻机在上面采冰，运冰机把冰送到沙罗纳。",
         "· 海面仍在上涨，沿岸聚落少有永久建筑，每隔几年往坡上搬一次（正典）。",
         "· 克律塞湾向南一直伸到厄俄斯湖两座坝下，见《水手峡谷战区图》。",
         "· 地名：黑色为城镇，蓝色斜体为已没入海中的地貌，灰色为陆上地貌。",
         "· 正典未划定中美边界，本图不画国界。"]
y4 = M.note_lines(S, "图例", LX, y3 + 20, notes)
M.index_map(S, "图例", LX, y4 + 26, 300, "北方海极区图")

S.text("出处", 84, SH-24, "底图：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接），重采样到 32 px/度；晕渲光源方位 315°、高度 40°。"
       "地貌名：IAU 行星地名库。城镇：GURPS Transhuman Space《In The Well》，位置按正典给出的地理关系在真实地形上重新确定。水位为推算值，见《火星坐标对照表》第 7 节。",
       7.0, "cjk", fill=C["ink3"])

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
