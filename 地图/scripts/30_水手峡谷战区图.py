#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水手峡谷战区图（2100 年 3 月）—— 白底简约，仿 USGS/NASA 行星地形图。

数据：DEM 原始 463 m 高程；水体 产出/三海掩膜.npz；地点 数据/火星地点.csv；铁路 产出/基础设施_2100.geojson
产出：产出/水手峡谷战区图_2100.svg（除晕渲外全矢量）  产出/水手峡谷战区图_2100.png（3 倍，印刷用）
运行：./.venv/bin/python scripts/30_水手峡谷战区图.py
"""
import math, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Equirect, text_width

NAME = "水手峡谷战区图_2100"

# ── 版面 ───────────────────────────────────────────────────────────
LON0, LON1, LAT0, LAT1 = 238.0, 334.0, 5.0, -20.0
PPD = 17.5
X0, Y0 = 84.0, 118.0
MAIN = Equirect(LON0, LON1, LAT0, LAT1, X0, Y0, PPD)
SW = int(X0 + MAIN.w + 84)
# 放大图：厄俄斯湖坝区
ILON0, ILON1, ILAT0, ILAT1 = 311.5, 322.5, -10.0, -18.5
IPPD = 46.0
INSET = Equirect(ILON0, ILON1, ILAT0, ILAT1, X0, Y0 + MAIN.h + 96, IPPD)
SH = int(INSET.y0 + INSET.h + 58)
S = SVG(SW, SH, "水手峡谷战区图 · 2100 年 3 月")

Z = M.load_masks()
LV = {"borealis": int(Z["level_borealis"]), "marineris_ius": int(Z["level_ius"]),
      "marineris_mid": int(Z["level_marineris"]), "marineris_eos": int(Z["level_eos"]), "lake_mutch": int(Z["level_mutch"])}
PLACES = {r["id"]: r for r in M.load_places()}
PEAKS = {r["山"]: r for r in M.load_peaks()}
INFRA = M.load_infra()

def panel(proj, ppd_hr, scale, clip_id, coast_w):
    """一个地图面：晕渲底图 + 矢量海岸线。返回细化后的水体掩膜（给注记避让参考）。"""
    dem = M.read_dem_window(proj.lon0, proj.lon1, proj.lat0, proj.lat1, ppd_hr)
    masks = {k: M.refine_water(Z[k], LV[k], dem, ppd_hr, proj.lon0, proj.lat0) for k in LV}
    rgb = M.relief_rgb(dem, list(masks.values()), list(LV.values()), ppd_hr, lat_top=proj.lat0)
    img = Image.fromarray(rgb).resize((int(proj.w*scale), int(proj.h*scale)), Image.LANCZOS)
    S.add("底图", f'<clipPath id="{clip_id}"><rect x="{proj.x0}" y="{proj.y0}" width="{proj.w:.1f}" height="{proj.h:.1f}"/></clipPath>')
    S.add("底图", f'<image x="{proj.x0}" y="{proj.y0}" width="{proj.w:.1f}" height="{proj.h:.1f}" preserveAspectRatio="none" '
                  f'href="{M.png_data_uri(np.array(img), quality=90)}"/>')
    for k, m in masks.items():
        rings = M.mask_rings(m, ppd_hr, lon_left=proj.lon0, lat_top=proj.lat0,
                             min_px=max(6, int(ppd_hr*ppd_hr/300)), simplify=6/ppd_hr/4, smooth=2)
        if not rings: continue
        S.add("海岸线", f'<path d="{M.rings_to_path(rings, proj)}" fill="none" stroke="{C["coast"]}" '
                        f'stroke-width="{coast_w}" stroke-linejoin="round" clip-path="url(#{clip_id})"/>')
    return masks

def graticule(proj, major, minor, label_every, tick=True, size=8.5):
    M.graticule_rect(S, proj, major, minor, label_every, tick, size)

# ── 主图 ───────────────────────────────────────────────────────────
print("主图：读 DEM、细化水体、晕渲 …")
panel(MAIN, 64, 3, "clipMain", 0.7)
graticule(MAIN, 5, 1, 5)

# 放大图框在主图上的位置
ix0, iy0 = MAIN.xy(ILON0, ILAT0); ix1, iy1 = MAIN.xy(ILON1, ILAT1)
S.add("图框标注", f'<rect x="{ix0:.1f}" y="{iy0:.1f}" width="{ix1-ix0:.1f}" height="{iy1-iy0:.1f}" fill="none" stroke="{C["ink"]}" stroke-width="0.6" stroke-dasharray="3 2"/>')

placer = Placer((MAIN.x0+2, MAIN.y0+2, MAIN.x0+MAIN.w-2, MAIN.y0+MAIN.h-2))
placer.block(ix0, iy0, ix1, iy1)                                   # 放大区内不放主图注记
S.text("注记", ix1-3, iy1-4, "见放大图", 7.5, "cjk", fill=C["ink2"], anchor="end", halo=2)

def rail(proj, clip):
    for f in INFRA:
        if f["geometry"]["type"] != "LineString": continue
        for seg in M.split_line(f["geometry"]["coordinates"], proj):
            xy = [proj.xy(lo, la) for lo, la in seg]
            S.add("铁路", f'<g clip-path="url(#{clip})">' + M.rail_svg(xy, f["properties"]["kind"]) + "</g>")
    for f in INFRA:
        if f["properties"]["kind"] != "车站": continue
        lo, la = f["geometry"]["coordinates"]; lo %= 360
        if not proj.inside(lo, la): continue
        x, y = proj.xy(lo, la)
        S.add("铁路", f'<rect x="{x-2.2:.1f}" y="{y-2.2:.1f}" width="4.4" height="4.4" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')

def canal(proj, w):
    a, b = PLACES["ius_locks_w"], PLACES["ius_locks_e"]
    (x1, y1), (x2, y2) = proj.xy(float(a["东经"]), float(a["纬度"])), proj.xy(float(b["东经"]), float(b["纬度"]))
    S.add("水系", f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" stroke="{C["coast"]}" stroke-width="{w}" stroke-dasharray="3 1.6" fill="none"/>')

def dam(proj, r, L, label=True):
    x, y = proj.xy(float(r["东经"]), float(r["纬度"]))
    S.add("闸坝", f'<rect x="{x-1.3:.1f}" y="{y-L/2:.1f}" width="2.6" height="{L:.1f}" fill="{C["alert"]}"/>')
    return x, y

rail(MAIN, "clipMain")
canal(MAIN, 1.1)

# 先把所有符号的位置占住，注记不许压符号
POINT_CATS = {"城市", "城镇", "遗址", "军事"}
main_pts = []
for r in PLACES.values():
    lo, la = float(r["东经"]), float(r["纬度"])
    if r["类别"] in POINT_CATS and MAIN.inside(lo, la):
        x, y = MAIN.xy(lo, la)
        if ix0 < x < ix1 and iy0 < y < iy1: continue                # 坝区的点交给放大图
        main_pts.append(r)
        rad = {"1": 3.4, "2": 2.9, "3": 2.4}[r["等级"]]
        S.add("符号", M.symbol(M.faction_kind(r["阵营"]), x, y, rad, major=r["等级"] == "1"))
        br = rad + (2.4 if r["等级"] == "1" else 0) + 1
        placer.block(x-br, y-br, x+br, y+br)
for k in ("ius_locks_w", "ius_locks_e"):
    x, y = dam(MAIN, PLACES[k], 8); placer.block(x-3, y-5, x+3, y+5)
for k in ("capri_dam", "eos_dam"):
    dam(MAIN, PLACES[k], 6)

# 固定注记：水体与地貌（按真实位置手工摆放，先放，城镇注记避让它们）
def label2(layer, x, y, zh, en, zh_size, en_size, fill, spacing=2.5, anchor="middle", rotate=0, block=True):
    wz = text_width(zh, zh_size, "cjk", spacing); we = text_width(en, en_size, "lat_i", 0.9) if en else 0
    hgt = zh_size + (en_size*1.3 if en else 0)
    tf = f' transform="rotate({rotate:.1f} {x:.1f} {y:.1f})"' if rotate else ""
    S.add(layer, f'<g{tf}>')
    S.text(layer, x, y, zh, zh_size, "cjk", fill=fill, anchor=anchor, spacing=spacing, halo=2.4)
    if en: S.text(layer, x, y+en_size*1.35, en, en_size, "lat_i", fill=fill, anchor=anchor, spacing=0.9, halo=2.0, italic=True)
    S.add(layer, "</g>")
    if block:
        w = max(wz, we); bx = x - w/2 if anchor == "middle" else x
        pad = abs(math.sin(math.radians(rotate)))*w/2
        placer.block(bx, y-zh_size-pad, bx+w, y+hgt-zh_size+pad+2)

WATER_FILL, TERR_FILL = C["water_label"], "#707070"
WATER = [("水手峡谷海", "MARINERIS SEA", 298.2, -13.35, 13, 7.5, 11.0),
         ("坎多尔湖", "LAKE CANDOR", 290.9, -4.1, 10, 6.8, 0),
         ("伊乌斯段", "", 278.6, -9.95, 8.5, 0, 0),
         ("克律塞湾南支", "BOREALIS SEA · CHRYSE GULF", 327.8, -3.2, 10.5, 6.8, 0),
         ("Mutch 陨坑湖", "", 304.8, 3.1, 8.5, 0, 0),
         ("赫柏湖", "", 284.1, 0.9, 8, 0, 0)]
for zh, en, lo, la, zs, es, rot in WATER:
    x, y = MAIN.xy(lo, la); label2("水体注记", x, y, zh, en, zs, es, WATER_FILL, spacing=3 if zs >= 10 else 1.5, rotate=rot)
TERR = [("诺克提斯迷宫", "NOCTIS LABYRINTHUS", 257.5, -4.2), ("叙利亚高原", "SYRIA PLANUM", 259.5, -15.6),
        ("西奈高原", "SINAI PLANUM", 273.0, -15.2), ("月神高原", "LUNAE PLANUM", 293.0, 2.4),
        ("俄斐高原", "OPHIR PLANUM", 297.5, -8.7), ("曙光高原", "AURORAE PLANUM", 309.0, -12.1),
        ("赞西高地", "XANTHE TERRA", 313.0, 1.6), ("塔西斯", "THARSIS", 243.5, 3.2),
        ("代达利亚高原", "DAEDALIA PLANUM", 243.0, -16.8), ("珍珠高地", "MARGARITIFER TERRA", 328.5, -17.2),
        ("提托尼乌姆峡谷", "TITHONIUM CHASMA", 271.0, -3.3), ("恒河峡谷", "GANGES CHASMA", 311.6, -6.1),
        ("回声峡谷", "ECHUS CHASMA", 276.2, 1.0)]
for zh, en, lo, la in TERR:
    x, y = MAIN.xy(lo, la); label2("地貌注记", x, y, zh, en, 9.5, 6.2, TERR_FILL, spacing=2.2)

# 山峰
arsia = PEAKS["Arsia Mons"]
ax, ay = MAIN.xy(float(arsia["峰顶东经"]), float(arsia["峰顶纬度"]))
S.add("符号", f'<path d="M{ax:.1f},{ay-3.6:.1f} L{ax+3.4:.1f},{ay+2.4:.1f} L{ax-3.4:.1f},{ay+2.4:.1f} Z" fill="{C["ink"]}"/>')
placer.block(ax-4, ay-4, ax+4, ay+3)

# 城镇注记
def place_label(proj, pl, r, x, y, big=1.0, extra=None):
    tier = r["等级"]; star = " ☆" if r["正典"] == "仅地图" else ""
    zs = {"1": 11.5, "2": 9.8, "3": 8.8}[tier]*big
    lines = [(r["中文名"] + star, zs, "cjk_b" if tier == "1" else "cjk", C["ink"])]
    if tier == "1": lines.append((r["英文名"], 7.0*big, "lat", C["ink2"]))
    if extra: lines.append((extra, 6.8*big, "cjk", C["ink2"]))
    w = max(text_width(t, s, k) for t, s, k, _ in lines)
    h = sum(s*1.18 for _, s, _, _ in lines)
    rad = {"1": 3.4, "2": 2.9, "3": 2.4}[tier]*(big if big > 1 else 1)*(1.24 if big > 1 else 1)
    gap = rad + (2.4 if tier == "1" else 0) + 1 + 2.5
    got = pl.place(x, y, w, h, gap=gap)
    if not got: return False
    bx, by, side = got
    yy = by
    for t, s, k, f in lines:
        yy += s*1.02
        S.text("城镇注记", bx, yy, t, s, k, fill=f, halo=2.3, weight="bold" if k == "cjk_b" else "normal")
        yy += s*0.16
    return True

EXTRA = {"new_shanghai": "Pavonis 火山口南缘 · 13,810 m", "haiyuan": "锈色中国首府",
         "port_lowell": "企业城邦", "robinson": "火星联邦最大城市"}
miss = []
for r in sorted(main_pts, key=lambda r: (r["等级"], -float(r["东经"]))):
    x, y = MAIN.xy(float(r["东经"]), float(r["纬度"]))
    if not place_label(MAIN, placer, r, x, y, extra=EXTRA.get(r["id"])): miss.append(r["中文名"])
# 闸坝注记
for k, zh in (("ius_locks_w", "Ius 船闸（西）"), ("ius_locks_e", "Ius 船闸（东）")):
    r = PLACES[k]; x, y = MAIN.xy(float(r["东经"]), float(r["纬度"]))
    w = text_width(zh, 8.6, "cjk"); got = placer.place(x, y, w, 10, 7, order=("S", "N", "SW", "SE", "NW", "NE", "W", "E"))
    if got: S.text("闸坝注记", got[0], got[1]+8.8, zh, 8.6, "cjk", fill=C["alert"], halo=2.2)
    else: miss.append(zh)
w = text_width("阿尔西亚山", 8.6, "cjk")
got = placer.place(ax, ay, w, 18, 7, order=("E", "NE", "SE", "S", "N"))
if got:
    S.text("地貌注记", got[0], got[1]+8.6, "阿尔西亚山", 8.6, "cjk", halo=2.2)
    S.text("地貌注记", got[0], got[1]+17, f"{int(float(arsia['峰顶MOLA高程_m'])):,} m", 6.8, "lat", fill=C["ink2"], halo=2)
if miss: print("  ⚠ 主图没放下的注记：", "、".join(miss))

# ── 放大图：厄俄斯湖坝区 ─────────────────────────────────────────────
print("放大图：厄俄斯湖坝区 …")
panel(INSET, 128, 3, "clipInset", 0.9)
graticule(INSET, 2, 0.5, 2, size=7.5)
rail(INSET, "clipInset")
S.text("图框标注", INSET.x0, INSET.y0-24, "厄俄斯湖坝区放大图", 11.5, "cjk_b", weight="bold")
S.text("图框标注", INSET.x0 + text_width("厄俄斯湖坝区放大图", 11.5, "cjk_b") + 10, INSET.y0-24, "LAKE EOS DAMS  ·  比例为主图的 2.6 倍", 7.2, "lat", fill=C["ink2"])
ipl = Placer((INSET.x0+2, INSET.y0+2, INSET.x0+INSET.w-2, INSET.y0+INSET.h-2))
for r in PLACES.values():
    lo, la = float(r["东经"]), float(r["纬度"])
    if not INSET.inside(lo, la) or r["类别"] not in POINT_CATS | {"设施"}: continue
    x, y = INSET.xy(lo, la)
    rad = {"1": 4.2, "2": 3.6, "3": 3.0}[r["等级"]]
    S.add("符号", M.symbol(M.faction_kind(r["阵营"]), x, y, rad, major=r["等级"] == "1"))
    br = rad + (2.4 if r["等级"] == "1" else 0) + 1
    ipl.block(x-br, y-br, x+br, y+br)
for k in ("capri_dam", "eos_dam"):
    x, y = dam(INSET, PLACES[k], 16); ipl.block(x-2.5, y-8.5, x+2.5, y+8.5)
for zh, en, lo, la, zs in [("厄俄斯湖", "LAKE EOS · −3,700 m", 314.6, -15.6, 12), ("克律塞湾南支", "BOREALIS SEA · −3,700 m", 320.4, -11.4, 11),
                           ("水手峡谷海", "MARINERIS SEA · −3,800 m", 313.2, -13.2, 10)]:
    x, y = INSET.xy(lo, la)
    wz = text_width(zh, zs, "cjk", 2.5); we = text_width(en, 6.8, "lat_i", 0.9)
    S.text("水体注记", x, y, zh, zs, "cjk", fill=WATER_FILL, anchor="middle", spacing=2.5, halo=2.6)
    S.text("水体注记", x, y+9.5, en, 6.8, "lat_i", fill=WATER_FILL, anchor="middle", spacing=0.9, halo=2.2, italic=True)
    ipl.block(x-max(wz, we)/2, y-zs, x+max(wz, we)/2, y+12)
IEXTRA = {"robinson": "穹顶城市 · Capri 坝以西", "plymouth": "美国第一个火星基地（崖顶）", "burroughs": ""}
for r in sorted([r for r in PLACES.values() if INSET.inside(float(r["东经"]), float(r["纬度"])) and r["类别"] in POINT_CATS | {"设施"}],
                key=lambda r: r["等级"]):
    x, y = INSET.xy(float(r["东经"]), float(r["纬度"]))
    if not place_label(INSET, ipl, r, x, y, big=1.15, extra=IEXTRA.get(r["id"])): print("  ⚠ 放大图没放下：", r["中文名"])
for k, zh, order in (("capri_dam", "Capri 峡谷大坝 · 兼铁路桥", ("NE", "E", "N")), ("eos_dam", "Eos 大坝 ☆", ("E", "SE", "S"))):
    r = PLACES[k]; x, y = INSET.xy(float(r["东经"]), float(r["纬度"]))
    w = text_width(zh, 10, "cjk"); got = ipl.place(x, y, w, 12, 9, order=order + ("W", "SW", "NW", "S"))
    if got: S.text("闸坝注记", got[0], got[1]+10, zh, 10, "cjk", fill=C["alert"], halo=2.4)
    else: print("  ⚠ 放大图没放下：", zh)

# ── 图名与图廓外说明 ─────────────────────────────────────────────────
S.text("图名", X0, 52, "水手峡谷战区", 30, "cjk_b", weight="bold", spacing=2)
S.text("图名", X0 + text_width("水手峡谷战区", 30, "cjk_b", 2) + 16, 52, "地形与水系图 · 2100 年 3 月", 14, "cjk", fill=C["ink2"])
S.text("图名", X0, 72, "VALLES MARINERIS THEATER  ·  TOPOGRAPHY AND HYDROGRAPHY  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
RX = X0 + MAIN.w
S.text("图名", RX, 46, "等距圆柱投影  ·  火星 2000 参考球  R = 3,396.19 km", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 60, "经度：图框上沿标东经，下沿标西经（正典地图用西经）", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 74, "海岸线测绘于 2100 年 3 月　北方海仍在上涨，本图岸线逐年失效", 8.2, "cjk", fill=C["alert"], anchor="end")

# 图例
LX, LY = INSET.x0 + INSET.w + 70, INSET.y0 - 4
S.text("图例", LX, LY, "图例", 11.5, "cjk_b", weight="bold")
items = [("cn", "锈色中国城镇"), ("us", "火星联邦（美）城镇"), ("corp", "企业城邦"), ("other", "独立 / 其他"),
         ("major", "主要城市"), ("dam", "闸 / 坝（军事目标）"), ("canal", "越岭运河"), ("rail", "赤道铁路及支线"),
         ("station", "车站"), ("peak", "山峰"), ("star", "☆ 仅见于正典地图")]
for i, (k, t) in enumerate(items):
    col, row = i % 2, i // 2
    x = LX + col*190; y = LY + 24 + row*21
    if k in ("cn", "us", "corp", "other"): S.add("图例", M.symbol(k, x+8, y-3.5, 3.0))
    elif k == "major": S.add("图例", M.symbol("cn", x+8, y-3.5, 3.4, major=True))
    elif k == "dam": S.add("图例", f'<rect x="{x+6.7:.1f}" y="{y-8:.1f}" width="2.6" height="9" fill="{C["alert"]}"/>')
    elif k == "canal": S.add("图例", f'<path d="M{x:.1f},{y-3.5:.1f} h17" stroke="{C["coast"]}" stroke-width="1.1" stroke-dasharray="3 1.6"/>')
    elif k == "rail": S.add("图例", M.rail_svg([(x-1, y-3.5), (x+19, y-3.5)], "干线"))
    elif k == "station": S.add("图例", f'<rect x="{x+5.8:.1f}" y="{y-5.7:.1f}" width="4.4" height="4.4" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')
    elif k == "peak": S.add("图例", f'<path d="M{x+8:.1f},{y-7.1:.1f} L{x+11.4:.1f},{y-1.1:.1f} L{x+4.6:.1f},{y-1.1:.1f} Z" fill="{C["ink"]}"/>')
    S.text("图例", x+(26 if k != "star" else 0), y, t, 9, "cjk")
ly = LY
LX2 = LX + 420
S.text("图例", LX2, ly, "水面高程", 11.5, "cjk_b", weight="bold")
for i, t in enumerate(["Ius 段 −3,300 m　　水手峡谷海中段（含坎多尔湖）−3,800 m",
                       "厄俄斯湖 −3,700 m　　北方海 −3,700 m　　Mutch 陨坑湖 +862 m"]):
    S.text("图例", LX2, ly+24+i*15, t, 9, "cjk", fill=C["ink2"])

# 分层设色色标与比例尺
BX, BY, BW = LX2, ly + 82, 380
S.text("图例", BX, BY, "高程（m，火星大地水准面起算）", 9.5, "cjk_b", weight="bold")
vals = np.linspace(-6000, 14000, 200)
cols = M.ramp(vals, M.HYPSO)*1.0
stops = "".join(f'<stop offset="{i/199:.3f}" stop-color="rgb({int(c[0])},{int(c[1])},{int(c[2])})"/>' for i, c in enumerate(cols[::1]))
S.add("图例", f'<linearGradient id="hyp">{stops}</linearGradient><rect x="{BX}" y="{BY+8}" width="{BW}" height="9" fill="url(#hyp)" stroke="{C["ink"]}" stroke-width="0.5"/>')
for v in range(-6000, 14001, 4000):
    x = BX + (v+6000)/20000*BW
    S.add("图例", f'<line x1="{x:.1f}" y1="{BY+17}" x2="{x:.1f}" y2="{BY+20}" stroke="{C["ink"]}" stroke-width="0.5"/>')
    S.text("图例", x, BY+29, f"{v:+,}".replace("+0", "0").replace("-", "−"), 7.2, "lat", anchor="middle")
# 比例尺（10°S 处）
kpu = M.KMPD*math.cos(math.radians(10))/PPD
SBX, SBY = BX, BY + 56
S.text("图例", SBX, SBY, "比例尺（主图，10°S 处）", 9.5, "cjk_b", weight="bold")
# 说明
S.text("图例", SBX, SBY + 52, "注：", 9.5, "cjk_b", weight="bold")
M.note_lines(S, "图例", SBX, SBY + 66, ["· 水位为按真实地形推算的值，推算过程见《火星坐标对照表》第 7 节。",
                                       "· 两座 Ius 船闸之间是约 170 km 的越岭运河，中间谷底高于两端水面。",
                                       "· Capri 与 Eos 两坝是厄俄斯湖东出口的北、南两道坝，坝下是北方海的克律塞湾南支；",
                                       "　赤道铁路经 Capri 坝顶跨越出口。",
                                       "· 正典未划定中美边界，本图不画国界。"], lh=14)
for i in range(5):
    x = SBX + i*100/kpu
    S.add("图例", f'<rect x="{x:.1f}" y="{SBY+8}" width="{100/kpu:.1f}" height="4.5" fill="{C["ink"] if i % 2 == 0 else "#FFFFFF"}" stroke="{C["ink"]}" stroke-width="0.5"/>')
    S.text("图例", x, SBY+23, f"{i*100}", 7.2, "lat", anchor="middle")
S.text("图例", SBX + 500/kpu, SBY+23, "500 km", 7.2, "lat", anchor="middle")

# 出处
NY = INSET.y0 + INSET.h + 26
for i, t in enumerate(["底图：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接）；晕渲光源方位 315°、高度 40°。"
                       "地貌名：IAU 行星地名库。城镇、工程与铁路：GURPS Transhuman Space《In The Well》，位置按正典给出的地理关系在真实地形上重新确定。",
                       ""]):
    S.text("出处", X0, NY + i*12, t, 7.2, "cjk", fill=C["ink3"])
    break

svg_path = M.OUT/f"{NAME}.svg"
S.save(svg_path)
png_path = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png_path), str(svg_path)], check=True)
print(f"→ {svg_path.name}  {svg_path.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
print(f"→ {png_path.name}  {png_path.stat().st_size/1e6:.1f} MB")
