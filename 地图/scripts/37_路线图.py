#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路线图（2198 年冬）—— 北方海极区 → 回声河（卡塞谷）→ 塔西斯 → 尼克斯奥林匹卡。
主图：墨卡托，204–326°E × 6°S–38°N，风格与 35_ 相同；右上插图：北极心方位投影，画第一程海路；
下方：沿整条路线的高程剖面（同 33_ 的画法）。
路线全部在真实地形上算出：
  第一程 海路 = −3,700 m 水面掩膜上的最短路（8 px/度）；
  第二程 河   = 沿谷底的最小代价路径（代价随高程指数增长，同剖面图 A 线），从南通到第一个海面像元；
  第三程 高原 = 坡度平方 + 高程封顶 3,500 m 的最小代价路径，南通 → 尼克斯奥林匹卡。
数据：DEM、产出/三海掩膜.npz、数据/火星地点.csv、数据/火星山峰.csv、产出/基础设施_2100.geojson、数据/IAU
产出：产出/路线图_2198.svg / .png（3 倍）；产出/路线_2198.geojson（三程折线 + 关键点）
运行：./.venv/bin/python scripts/37_路线图.py
"""
import json, math, subprocess, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from affine import Affine
from skimage.graph import route_through_array
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Mercator, Azimuthal, Identity, text_width

NAME = "路线图_2198"
LON0, LON1, LAT0, LAT1 = 204.0, 326.0, 38.0, -6.0
PPD, SS, HR = 11.5, 3, 64
X0, Y0 = 76.0, 118.0
P = Mercator(LON0, LON1, LAT0, LAT1, X0, Y0, PPD)
LX = int(X0 + P.w + 58)                       # 右栏
SW = 1848
PX0, PX1, PH = 150.0, LX - 40.0, 200.0         # 剖面区
PTOP = int(Y0 + P.h + 64)
SH = int(PTOP + PH + 96)
S = SVG(SW, SH, "路线图 · 北方海到火大 · 2198 年冬")
ROUTE_C = "#C0392B"
STEP = 2.0
clip = 'clip-path="url(#clipMap)"'

D = M.load_dem32_avg().astype(np.float64)
Z = M.load_masks(); B = Z["borealis"]
LV = {"borealis": int(Z["level_borealis"]), "marineris_ius": int(Z["level_ius"]), "marineris_mid": int(Z["level_marineris"]),
      "marineris_eos": int(Z["level_eos"]), "lake_mutch": int(Z["level_mutch"])}
PL = {r["id"]: r for r in M.load_places()}
PEAKS = {r["山"]: r for r in M.load_peaks()}
INFRA = M.load_infra()
IAU = M.load_iau()
def pt(pid): return float(PL[pid]["纬度"]), float(PL[pid]["东经"])
def zat(lat, lon): return M.sample_lonlat(D, 32, np.asarray(lon) % 360, np.asarray(lat), order=1)
def is_sea(lat, lon): return M.sample_lonlat(B, 32, np.asarray(lon) % 360, np.asarray(lat), order=0).astype(bool)

START = (79.1816, 323.4506)                    # 序章废井站：塞韦尔坑（Sevel, 7.4 km）西南坑缘，2026-09-13 定
NAN, NIX = pt("nantong"), pt("nix_olympica")

# ── 路线 ───────────────────────────────────────────────────────────
def cost_path(cost, lat_top, lon_left, ppd, points):
    rc = lambda p: (int((lat_top - p[0])*ppd), int((p[1] - lon_left)*ppd))
    path = []
    for p, q in zip(points[:-1], points[1:]):
        seg, _ = route_through_array(cost, rc(p), rc(q), fully_connected=True, geometric=True)
        path += seg if not path else seg[1:]
    r, c = np.array(path, float).T
    return lat_top - (r + 0.5)/ppd, lon_left + (c + 0.5)/ppd

def window(arr, lon0, lon1, lat0, lat1, ppd=32):
    c0, r0 = int(((lon0 + 180) % 360)*ppd), int((90 - lat0)*ppd)
    return arr[r0:int((90 - lat1)*ppd), c0:c0 + int((lon1 - lon0)*ppd)]

def smooth(la, lo, n):
    return ndimage.uniform_filter1d(la, n, mode="nearest"), ndimage.uniform_filter1d(lo, n, mode="nearest")

print("第二程：沿谷底 …")
win = window(D, 272, 318, 32, -6)
la, lo = cost_path(np.exp((win - win.min())/700.0), 32, 272, 32, [NAN, pt("zhigansk")])
la, lo = smooth(la, lo, 9)
sea_flag = is_sea(la, lo)
j = int(np.argmax(sea_flag)) if sea_flag.any() else len(la)
RIV = (la[:j], lo[:j])                                                # 南通 → 河口
MOUTH = (float(la[j-1]), float(lo[j-1]))

print("第一程：海冰 …")
B8 = B.reshape(720, 8, 1440, 8).mean(axis=(1, 3)) > 0.5
w8 = window(B8, 280, 360, 90, 20, 8)
la, lo = cost_path(np.where(w8, 1.0, 1e4), 90, 280, 8, [START, MOUTH])
SEA = smooth(la, lo, 7)

print("第三程：高原 …")
win = window(D, 220, 284, 32, -6)
latg = 32 - (np.arange(win.shape[0]) + 0.5)/32
cell = 2*math.pi*M.R/360/32
gy, gx = np.gradient(win, cell); gx = gx/np.cos(np.radians(latg))[:, None]
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
la, lo = cost_path(1.0 + (slope/2.0)**2 + np.where(win > 3500.0, 200.0, 0.0), 32, 220, 32, [NAN, NIX])
THA = smooth(la, lo, 5)

def length_km(la, lo):
    return float(M.hav_km(la[:-1], lo[:-1], la[1:], lo[1:]).sum())
LEGS = [("第一程 · 冰上", SEA[0], SEA[1]), ("第二程 · 河上", RIV[0][::-1], RIV[1][::-1]), ("第三程 · 高原", THA[0], THA[1])]
LEN = [length_km(a, b) for _, a, b in LEGS]
print("  ", "  ".join(f"{n} {L:,.0f} km" for (n, _, _), L in zip(LEGS, LEN)), f"  合计 {sum(LEN):,.0f} km")

# 整条路线的剖面
la_all = np.concatenate([a for _, a, _ in LEGS]); lo_all = np.concatenate([b for _, _, b in LEGS])
lo_u = np.degrees(np.unwrap(np.radians(lo_all)))
seg = M.hav_km(la_all[:-1], lo_u[:-1], la_all[1:], lo_u[1:]); cum = np.r_[0, np.cumsum(seg)]
s = np.arange(0, cum[-1], STEP)
pla, plo = np.interp(s, cum, la_all), np.interp(s, cum, lo_u) % 360
pz = zat(pla, plo).astype(float)
wet = is_sea(pla, plo) & (pz < LV["borealis"]) & (s <= LEN[0] + 5)
S_MOUTH, S_NAN = LEN[0], LEN[0] + LEN[1]
def s_of(lat, lon): return float(s[int(np.argmin(M.hav_km(lat, lon, pla, plo)))])
def at_s(sv): i = int(np.argmin(np.abs(s - sv))); return float(pla[i]), float(plo[i]), float(pz[i])

# 关键点：编号、名字、路线上的里程
KEY = [(1, "废井站（塞韦尔坑缘）", 0.0), (2, "克律塞湾口", s_of(55.0, 322.0)), (3, "回声河口", S_MOUTH),
       (4, "下卡塞峡口", S_MOUTH + 600), (5, "卡塞落差", S_MOUTH + 1450), (6, "南通", S_NAN),
       (7, "出回声峡谷", S_NAN + 256), (8, "鞍部", S_NAN + float(np.argmax(np.where((s > S_NAN + 500) & (s < S_NAN + 2500), pz, -9e9))*STEP - S_NAN)),
       (9, "崖脚", S_NAN + float(np.argmin(np.where(s > cum[-1] - 300, pz, 9e9))*STEP - S_NAN)), (10, "尼克斯奥林匹卡", float(s[-1]))]
KEYP = [(n, nm, sv, *at_s(sv)) for n, nm, sv in KEY]
for n, nm, sv, a, b, z in KEYP: print(f"  {n:2d} {nm:8s} {sv:6.0f} km  {a:6.2f}°N {b:7.2f}°E  {z:6.0f} m")

# 导出 GeoJSON
feats = [{"type": "Feature", "properties": {"leg": n, "km": round(L)}, "geometry": {"type": "LineString",
          "coordinates": [[round(float(x), 3), round(float(y), 3)] for x, y in zip(b[::3], a[::3])]}} for (n, a, b), L in zip(LEGS, LEN)]
feats += [{"type": "Feature", "properties": {"n": n, "name": nm, "km": round(sv), "z": round(z)},
           "geometry": {"type": "Point", "coordinates": [round(b, 3), round(a, 3)]}} for n, nm, sv, a, b, z in KEYP]
json.dump({"type": "FeatureCollection", "features": feats}, open(M.OUT/"路线_2198.geojson", "w", encoding="utf-8"), ensure_ascii=False)

# ── 主图底图 ────────────────────────────────────────────────────────
print("底图 …")
dem = M.read_dem_window(LON0, LON1, LAT0, LAT1, HR)
masks = {k: M.refine_water(Z[k], LV[k], dem, HR, LON0, LAT0) for k in LV}
rgb = M.relief_rgb(dem, list(masks.values()), list(LV.values()), HR, lat_top=LAT0, zfac=2.6, lon_left=LON0)
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

print("等高线 …")
d32 = dem.reshape(dem.shape[0]//2, 2, dem.shape[1]//2, 2).mean(axis=(1, 3))
sm = ndimage.gaussian_filter(d32.astype(np.float64), 1.3)
to_xy = lambda rr, cc: P.xy(LON0 + (cc + 0.5)/32, LAT0 - (rr + 0.5)/32)
normal, bold, index_lines = [], [], {}
for lv in range(-4000, 22000, 1000):
    lines = M.contour_lines(sm, lv, to_xy, sigma=0, min_len=14, tol=0.4)
    (bold if lv % 5000 == 0 else normal).extend(M.path_d(p[:, 0], p[:, 1]) for p in lines)
    if lv % 5000 == 0: index_lines[lv] = lines
S.add("等高线", f'<path d="{" ".join(normal)}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.28" opacity="0.42" {clip}/>')
S.add("等高线", f'<path d="{" ".join(bold)}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.55" opacity="0.6" {clip}/>')
for k, m in masks.items():
    rings = M.mask_rings(m, HR, lon_left=LON0, lat_top=LAT0, min_px=30, simplify=0.01, smooth=2)
    if rings: S.add("海岸线", f'<path d="{M.rings_to_path(rings, P)}" fill="none" stroke="{C["coast"]}" stroke-width="0.75" stroke-linejoin="round" {clip}/>')
del dem, masks, d32, sm

M.graticule_rect(S, P, 10, 2, 10)
placer = Placer((P.x0+2, P.y0+2, P.x0+P.w-2, P.y0+P.h-2))

# ── 战前铁路（2198 年已停）──────────────────────────────────────────
for ft in INFRA:
    if ft["geometry"]["type"] != "LineString": continue
    for sg in M.split_line(ft["geometry"]["coordinates"], P):
        xy = [P.xy(lo_, la_) for lo_, la_ in sg]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in xy)
        S.add("铁路", f'<path d="{d}" fill="none" stroke="#8C8C8C" stroke-width="0.9" stroke-dasharray="3.2 2.2" {clip}/>')

# ── 直线（不走）──────────────────────────────────────────────────────
def gc(p, q, n=200):
    v = lambda la_, lo_: np.array([math.cos(math.radians(la_))*math.cos(math.radians(lo_)), math.cos(math.radians(la_))*math.sin(math.radians(lo_)), math.sin(math.radians(la_))])
    a, b = v(*p), v(*q); om = math.acos(max(-1, min(1, float(a @ b)))); t = np.linspace(0, 1, n)[:, None]
    w = (np.sin((1-t)*om)*a + np.sin(t*om)*b)/math.sin(om)
    return np.degrees(np.arcsin(w[:, 2])), np.degrees(np.arctan2(w[:, 1], w[:, 0])) % 360
gla, glo = gc(pt("liangzhen"), NIX)
gx_, gy_ = P.xy(glo, gla)
S.add("路线", f'<path d="{M.path_d(gx_, gy_)}" fill="none" stroke="#707070" stroke-width="1.1" stroke-dasharray="6 3" {clip}/>')
xm, ym = float(gx_[100]), float(gy_[100])
S.text("路线注记", xm - 6, ym - 8, "直线 1,120 km（不走）", 8.2, "cjk", fill="#606060", anchor="end", halo=2.2)
placer.block(xm - 6 - text_width("直线 1,120 km（不走）", 8.2, "cjk"), ym - 17, xm - 6, ym - 5)

# ── 路线 ───────────────────────────────────────────────────────────
for name, a, b in LEGS:
    sgs = M.split_line(list(zip(b, a)), P, max_jump_deg=2.0)
    for sg in sgs:
        xy = [P.xy(lo_, la_) for lo_, la_ in sg]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in xy)
        S.add("路线", f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linejoin="round" stroke-linecap="round" opacity="0.85" {clip}/>')
        S.add("路线", f'<path d="{d}" fill="none" stroke="{ROUTE_C}" stroke-width="2.1" stroke-linejoin="round" stroke-linecap="round" {clip}/>')
for i in range(0, len(pla), 10):                                    # 路线两侧留白，注记别压线
    if P.inside(plo[i], pla[i]):
        x, y = map(float, P.xy(plo[i], pla[i])); placer.block(x-2.5, y-2.5, x+2.5, y+2.5)

def keypoint(layer, x, y, n, r=6.2, fs=7.6):
    S.add(layer, f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#FFFFFF" stroke="{ROUTE_C}" stroke-width="1.4"/>')
    S.text(layer, x, y + fs*0.36, str(n), fs, "lat_b", fill=ROUTE_C, anchor="middle", weight="bold")

# ── 城镇与山峰 ──────────────────────────────────────────────────────
POINT_CATS = {"城市", "城镇", "遗址", "军事"}
pts = []
for r_ in PL.values():
    lo_, la_ = float(r_["东经"]), float(r_["纬度"])
    if not P.inside(lo_, la_) or r_["类别"] not in POINT_CATS: continue
    x, y = map(float, P.xy(lo_, la_))
    rad = {"1": 3.4, "2": 2.9, "3": 2.4}[r_["等级"]]
    S.add("符号", M.symbol(M.faction_kind(r_["阵营"]), x, y, rad, major=r_["等级"] == "1"))
    br = rad + (2.4 if r_["等级"] == "1" else 0) + 1
    placer.block(x-br, y-br, x+br, y+br)
    pts.append((r_, x, y, br))
PEAK_ZH = {"Olympus Mons": "奥林匹斯山", "Ascraeus Mons": "艾斯克雷尔斯山", "Pavonis Mons": "帕弗尼斯山",
           "Uranius Mons": "乌拉纽斯山", "Ceraunius Tholus": "刻拉尼俄斯山丘", "Tharsis Tholus": "塔西斯山丘"}
peak_pts = []
for n, zh in PEAK_ZH.items():
    pk = PEAKS[n]; lo_, la_, z_ = float(pk["峰顶东经"]), float(pk["峰顶纬度"]), float(pk["峰顶MOLA高程_m"])
    if P.inside(lo_, la_):
        x, y = map(float, P.xy(lo_, la_)); S.add("符号", M.peak_svg(x, y, 1.0)); placer.block(x-4, y-4, x+4, y+3); peak_pts.append((zh, x, y, z_))

# 关键点符号（城镇处不重复画圈，编号放在名字里）
TOWN_KEY = {6: "nantong", 10: "nix_olympica"}
for n, nm, sv, a, b, z in KEYP:
    if n in TOWN_KEY or not P.inside(b, a): continue
    x, y = map(float, P.xy(b, a)); keypoint("路线", x, y, n); placer.block(x-7, y-7, x+7, y+7)

# ── 注记 ───────────────────────────────────────────────────────────
WATER_FILL, TERR_FILL = C["water_label"], "#707070"
def area_label(zh, en, lo_, la_, zs, es, fill, spacing=2.2, rotate=0):
    x, y = map(float, P.xy(lo_, la_))
    wz = text_width(zh, zs, "cjk", spacing); we = text_width(en, es, "lat_i", 0.9) if en else 0; w = max(wz, we)
    tf = f' transform="rotate({rotate:.1f} {x:.1f} {y:.1f})"' if rotate else ""
    S.add("地貌注记", f"<g{tf}>")
    S.text("地貌注记", x, y, zh, zs, "cjk", fill=fill, anchor="middle", spacing=spacing, halo=2.4)
    if en: S.text("地貌注记", x, y+es*1.35, en, es, "lat_i", fill=fill, anchor="middle", spacing=0.9, halo=2, italic=True)
    S.add("地貌注记", "</g>")
    ext = abs(math.sin(math.radians(rotate)))*w/2
    placer.block(x-w/2*abs(math.cos(math.radians(rotate)))-4, y-zs-ext, x+w/2*abs(math.cos(math.radians(rotate)))+4, y+es*1.6+ext)

area_label("克律塞湾", "CHRYSE BAY", 321.0, 31.5, 12, 6.8, WATER_FILL, 3)
area_label("亚马逊湾", "AMAZONIS BAY", 207.5, 32.5, 11, 6.5, WATER_FILL, 3)
area_label("塔西斯", "THARSIS", 250.0, 20.5, 15, 7.5, TERR_FILL, 9)
for zh, en, lo_, la_, rot in [("月神高原", "LUNAE PLANUM", 293.0, 12.0, 0), ("滕比高地", "TEMPE TERRA", 284.0, 31.0, 0),
                             ("赞西高地", "XANTHE TERRA", 309.0, 6.0, 0), ("萨克拉台地", "SACRA MENSA", 293.0, 25.0, 0),
                             ("卡塞谷", "KASEI VALLES", 281.8, 9.5, -80), ("回声峡谷", "ECHUS CHASMA", 276.0, 0.5, 0),
                             ("吕科斯沟群", "LYCUS SULCI", 214.5, 26.5, 0), ("亚马逊平原", "AMAZONIS PLANITIA", 205.5, 13.0, 0),
                             ("奥林匹斯断崖", "OLYMPUS RUPES", 219.5, 15.5, 0), ("刻拉尼俄斯堑沟群", "CERAUNIUS FOSSAE", 250.0, 30.0, 0),
                             ("克律塞平原", "CHRYSE PLANITIA", 316.0, 24.0, 0)]:
    area_label(zh, en, lo_, la_, 9.0, 5.9, TERR_FILL, 2.2, rot)

def place_town(r_, x, y, br, tag=None):
    tier = r_["等级"]
    zs = {"1": 10.5, "2": 9.2, "3": 8.4}[tier]
    nm = (tag + " " if tag else "") + r_["中文名"].replace("·海盗 1 号着陆点", "").replace("卡尔·萨根纪念站（火星探路者）", "萨根纪念站")
    lines = [(nm, zs, "cjk_b" if tier == "1" or tag else "cjk", ROUTE_C if tag else C["ink"])]
    lines.append((f"{float(r_['MOLA高程_m']):,.0f} m", 6.4, "cjk", C["ink2"]))
    w = max(text_width(t, sz, k) for t, sz, k, _ in lines); h = sum(sz*1.18 for _, sz, _, _ in lines)
    got = None
    for extra in (2.5, 7, 13):
        got = placer.place(x, y, w, h, gap=br+extra)
        if got: break
    if not got: return False
    yy = got[1]
    for t, sz, k, fl in lines:
        yy += sz*1.02
        S.text("城镇注记", got[0], yy, t, sz, k, fill=fl, halo=2.3, weight="bold" if k == "cjk_b" else "normal")
        yy += sz*0.16
    return True

miss = []
TAGS = {"nantong": "⑥", "nix_olympica": "⑩"}
order = sorted(pts, key=lambda t: (0 if t[0]["id"] in TAGS else 1, t[0]["等级"], -t[2]))
for r_, x, y, br in order:
    if not place_town(r_, x, y, br, TAGS.get(r_["id"])): miss.append(r_["中文名"])
for zh, x, y, z_ in peak_pts:
    e = f"{z_:,.0f} m"; zs = 8.6
    w = max(text_width(zh, zs, "cjk"), text_width(e, 6.4, "lat")); h = zs*1.2 + 8
    got = placer.place(x, y, w, h, gap=6)
    if not got: miss.append(zh); continue
    S.text("地貌注记", got[0], got[1]+zs, zh, zs, "cjk", halo=2.2)
    S.text("地貌注记", got[0], got[1]+zs+8.2, e, 6.4, "lat", fill=C["ink2"], halo=2)
# 关键点名字
for n, nm, sv, a, b, z in KEYP:
    if n in TOWN_KEY or not P.inside(b, a): continue
    x, y = map(float, P.xy(b, a)); t = f"{nm}"
    w = text_width(t, 8.6, "cjk_b"); got = None
    for extra in (3, 8, 14):
        got = placer.place(x, y, w, 10.5, gap=7+extra)
        if got: break
    if got: S.text("路线注记", got[0], got[1]+8.8, t, 8.6, "cjk_b", fill=ROUTE_C, halo=2.3, weight="bold")
    else: miss.append(nm)
# 分程名
def leg_label(txt, lat_, lon_, rot=0, size=9.4):
    x, y = map(float, P.xy(lon_, lat_)); w = text_width(txt, size, "cjk_b", 1.2)
    tf = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ""
    S.add("路线注记", f"<g{tf}>"); S.text("路线注记", x, y, txt, size, "cjk_b", fill=ROUTE_C, anchor="middle", spacing=1.2, halo=2.6, weight="bold"); S.add("路线注记", "</g>")
    placer.block(x-w/2, y-size, x+w/2, y+3)
leg_label(f"第一程 · 冰上 {LEN[0]:,.0f} km（见插图）", 31.6, 313.0, -50, 8.6)
leg_label(f"第二程 · 河上 {LEN[1]:,.0f} km", 20.2, 292.3, 0)
leg_label(f"第三程 · 高原 {LEN[2]:,.0f} km", 19.0, 240.0, 0)
# 河名沿河排：取南通以北、卡塞落差以南那段河道（月神高原西缘，近南北向），字放在河线东侧
sel = (s >= S_MOUTH + 1650) & (s <= S_MOUTH + 2350)
river_xy = M.chaikin([tuple(map(float, P.xy(b_, a_))) for a_, b_ in zip(pla[sel][::6], plo[sel][::6])], 3)
M.text_along(S, "水体注记", river_xy, "回　声　河", 10.5, "cjk", fill=WATER_FILL, spacing=2, halo=2.4, offset=7.5, placer=placer)
if miss: print("  ⚠ 没放下的注记：", "、".join(miss))
for _, x, y, br in pts: placer.block(x-br-7, y-br-7, x+br+7, y+br+7)
print(f"  计曲线注记 {M.label_contours(S, placer, index_lines, every=520)} 处")

# ── 插图：第一程（北极心方位投影）──────────────────────────────────
print("插图 …")
RM = 122.0; LAT_EDGE = 14.0; LON_BOTTOM = 320.0
CX, CY = LX + 8 + RM, Y0 + 26 + RM
A = Azimuthal(90, LON_BOTTOM, CX, CY, RM/(2*M.R/1e3*math.sin(math.radians(90-LAT_EDGE)/2)))
n = int(2*RM) + 12; OX, OY = CX - RM - 6, CY - RM - 6; SSi = 2
ys, xs = np.mgrid[0:n*SSi, 0:n*SSi]
lon_i, lat_i, ok = A.inverse(OX + (xs + 0.5)/SSi, OY + (ys + 0.5)/SSi)
ok &= lat_i >= LAT_EDGE - 1
dem_i = M.sample_lonlat(D, 32, lon_i, lat_i, order=1).astype(np.float32)
sea_i = M.sample_lonlat(B, 32, lon_i, lat_i, order=0).astype(bool) & (dem_i < LV["borealis"]) & ok
px_m = 1000/(A.scale*SSi)
rgb_i = M.colorize(dem_i, M.shade(dem_i, px_m, px_m, zfac=4.0), [sea_i], [LV["borealis"]], albedo=M.albedo_at(lon_i, lat_i)); rgb_i[~ok] = 255
S.add("插图", f'<clipPath id="clipIns"><circle cx="{CX}" cy="{CY}" r="{RM}"/></clipPath>')
S.add("插图", f'<image x="{OX}" y="{OY}" width="{n}" height="{n}" preserveAspectRatio="none" clip-path="url(#clipIns)" href="{M.png_data_uri(rgb_i, quality=88)}"/>')
rings = M.mask_rings(sea_i, SSi, min_px=40, simplify=0.4, smooth=2, transform=Affine(1/SSi, 0, OX, 0, 1/SSi, OY))
S.add("插图", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{C["coast"]}" stroke-width="0.6" clip-path="url(#clipIns)"/>')
del lon_i, lat_i, dem_i, sea_i, rgb_i
g = "".join(f'<circle cx="{CX}" cy="{CY}" r="{A.radius_of(la_):.1f}"/>' for la_ in (30, 60)) + \
    "".join(f'<line x1="{A.xy(lo_, 85)[0]:.1f}" y1="{A.xy(lo_, 85)[1]:.1f}" x2="{A.xy(lo_, LAT_EDGE)[0]:.1f}" y2="{A.xy(lo_, LAT_EDGE)[1]:.1f}"/>' for lo_ in range(0, 360, 90))
S.add("插图", f'<g fill="none" stroke="{C["grat"]}" stroke-width="0.35" opacity="0.4" clip-path="url(#clipIns)">{g}</g>')
S.add("插图", f'<circle cx="{CX}" cy="{CY}" r="{RM}" fill="none" stroke="{C["frame"]}" stroke-width="0.9"/>')
for lo_ in (0, 90, 180, 270):
    x, y = A.xy(lo_, LAT_EDGE - 4.5); S.text("插图", float(x), float(y) + 3, f"{lo_}°E", 6.4, "lat", fill=C["ink2"], anchor="middle")
# 主图范围
bx = np.r_[np.linspace(LON0, LON1, 60), np.full(30, LON1), np.linspace(LON1, LON0, 60), np.full(30, LON0)]
by = np.r_[np.full(60, LAT0), np.linspace(LAT0, LAT_EDGE, 30), np.full(60, LAT_EDGE), np.linspace(LAT_EDGE, LAT0, 30)]
fx, fy = A.xy(bx, by)
S.add("插图", f'<path d="{M.path_d(fx, fy, close=True)}" fill="none" stroke="{C["ink"]}" stroke-width="0.8" stroke-dasharray="3 2" clip-path="url(#clipIns)"/>')
# 海路
sx, sy = A.xy(SEA[1], SEA[0])
S.add("插图", f'<path d="{M.path_d(sx, sy)}" fill="none" stroke="#FFFFFF" stroke-width="4" opacity="0.85" clip-path="url(#clipIns)"/>'
              f'<path d="{M.path_d(sx, sy)}" fill="none" stroke="{ROUTE_C}" stroke-width="1.8" clip-path="url(#clipIns)"/>')
for n_, nm, sv, a, b, z in KEYP[:3]:
    x, y = map(float, A.xy(b, a)); keypoint("插图", x, y, n_, r=5.4, fs=6.8)
    S.text("插图", x + 8, y + 3, nm, 7.4, "cjk_b", fill=ROUTE_C, halo=2.2, weight="bold")
x, y = map(float, A.xy(0, 89.9)); S.text("插图", x, y - 6, "北极冰盖", 6.8, "cjk", fill=C["ink2"], anchor="middle", halo=2)
S.text("插图", CX, CY - RM - 12, "第一程 · 北方海冰上", 10.5, "cjk_b", weight="bold", anchor="middle")
S.text("插图", CX, CY + RM + 14, "北极心兰伯特等积方位投影 · 画到 14°N · 虚线框为主图范围", 6.8, "cjk", fill=C["ink2"], anchor="middle")

# ── 右栏图例（插图下方）─────────────────────────────────────────────
LY = CY + RM + 40
S.text("图例", LX, LY, "图例", 11, "cjk_b", weight="bold")
items = [("route", "路线（三程）"), ("key", "关键点，编号同剖面与文档"), ("straight", "直线（不走）"), ("rail", "战前赤道铁路与支线（2198 年已停）"),
         ("cn", "锈色中国（战前）"), ("us", "火星联邦（战前）"), ("other", "独立 / 其他"), ("peak", "火山峰顶"),
         ("coast", "岸线（−3,700 m，沿用 2100 年图）"), ("contour", "等高线 1,000 m，每 5,000 m 加粗")]
for i, (k, t_) in enumerate(items):
    y = LY + 22 + i*17; x = LX
    if k == "route": S.add("图例", f'<path d="M{x},{y-3.5} h20" stroke="#FFFFFF" stroke-width="5"/><path d="M{x},{y-3.5} h20" stroke="{ROUTE_C}" stroke-width="2.1"/>')
    elif k == "key": keypoint("图例", x+10, y-3.5, 3, r=5.4, fs=6.8)
    elif k == "straight": S.add("图例", f'<path d="M{x},{y-3.5} h20" stroke="#707070" stroke-width="1.1" stroke-dasharray="6 3"/>')
    elif k == "rail": S.add("图例", f'<path d="M{x},{y-3.5} h20" stroke="#8C8C8C" stroke-width="0.9" stroke-dasharray="3.2 2.2"/>')
    elif k in ("cn", "us", "other"): S.add("图例", M.symbol(k, x+10, y-3.5, 3.0))
    elif k == "peak": S.add("图例", M.peak_svg(x+10, y-3.5))
    elif k == "coast": S.add("图例", f'<path d="M{x},{y-3.5} h20" stroke="{C["coast"]}" stroke-width="0.9"/>')
    elif k == "contour": S.add("图例", f'<path d="M{x},{y-5.5} h20" stroke="{M.CONTOUR}" stroke-width="0.35" opacity="0.7"/><path d="M{x},{y-1.5} h20" stroke="{M.CONTOUR}" stroke-width="0.7" opacity="0.8"/>')
    S.text("图例", x+27, y, t_, 8.4, "cjk")
ys_ = LY + 22 + len(items)*17 + 12
S.text("图例", LX, ys_, "比例尺", 9.5, "cjk_b", weight="bold")
for i, la_ in enumerate((0, 30)):
    S.text("图例", LX, ys_ + 22 + i*32, "赤道" if la_ == 0 else f"{la_}°N", 8, "cjk", fill=C["ink2"])
    M.scale_bar(S, "图例", LX + 38, ys_ + 14 + i*32, 1/P.km_per_unit(la_), 200, 4, size=6.4, h=4)

# ── 剖面 ───────────────────────────────────────────────────────────
print("剖面 …")
L = float(s[-1])
zmin = math.floor((pz.min() - 400)/1000)*1000; zmax = math.ceil((pz.max() + 1300)/1000)*1000
xo = lambda d: PX0 + (PX1-PX0)*np.asarray(d)/L
yo = lambda h: PTOP + PH*(zmax - np.asarray(h))/(zmax - zmin)
ve = (L/(PX1-PX0))/((zmax-zmin)/1e3/PH)
pl = Placer((PX0+2, PTOP-40, PX1-2, PTOP+PH-2))
S.text("剖面", PX0, PTOP-30, "沿路线的高程剖面", 15, "cjk_b", weight="bold")
S.text("剖面", PX0 + text_width("沿路线的高程剖面", 15, "cjk_b") + 14, PTOP-30,
       f"全长 {L:,.0f} km  ·  垂直夸大约 {ve:,.0f} 倍  ·  最高 {pz.max():,.0f} m（尼克斯奥林匹卡）  ·  最低 {pz.min():,.0f} m（克律塞湾底）", 9, "cjk", fill=C["ink2"])
gl = []
h = zmin
while h <= zmax:
    y = float(yo(h)); gl.append(f'<line x1="{PX0}" y1="{y:.1f}" x2="{PX1}" y2="{y:.1f}"/>')
    lab = f"{h/1000:+g}".replace("+0", "0").replace("-", "−")
    S.text("剖面", PX0-7, y+3, lab, 7.6, "lat", anchor="end"); S.text("剖面", PX1+7, y+3, lab, 7.6, "lat")
    h += 1000
S.add("剖面", f'<g stroke="{C["grat"]}" stroke-width="0.35" opacity="0.2">{"".join(gl)}</g>')
S.add("剖面", f'<text x="{PX0-36:.1f}" y="{PTOP+PH/2:.1f}" transform="rotate(-90 {PX0-36:.1f} {PTOP+PH/2:.1f})" font-family="{M.FAM_CJK}" font-size="8.4" fill="{C["ink2"]}" text-anchor="middle">高程（km）</text>')
hs = np.linspace(zmax, zmin, 40); cols = M.ramp(hs, M.HYPSO)*0.93
stops = "".join(f'<stop offset="{i/39:.3f}" stop-color="rgb({int(c[0])},{int(c[1])},{int(c[2])})"/>' for i, c in enumerate(cols))
S.add("剖面", f'<linearGradient id="pg" gradientUnits="userSpaceOnUse" x1="0" y1="{yo(zmax):.1f}" x2="0" y2="{yo(zmin):.1f}">{stops}</linearGradient>')
X, Y = xo(s), yo(pz)
ground = M.path_d(X, Y)
S.add("剖面", f'<path d="{ground} L{PX1:.1f},{PTOP+PH:.1f} L{PX0:.1f},{PTOP+PH:.1f} Z" fill="url(#pg)"/>')
for sl in ndimage.find_objects(ndimage.label(wet)[0]):
    i0, i1 = sl[0].start, sl[0].stop
    if i1 - i0 < 2: continue
    d = M.path_d(X[i0:i1], np.full(i1-i0, float(yo(LV["borealis"]))))
    back = M.path_d(X[i0:i1][::-1], Y[i0:i1][::-1]).replace("M", "L", 1)
    S.add("剖面", f'<path d="{d} {back} Z" fill="rgb(190,218,238)"/><path d="{d}" fill="none" stroke="{C["coast"]}" stroke-width="0.9"/>')
S.add("剖面", f'<path d="{ground}" fill="none" stroke="{C["ink"]}" stroke-width="0.75" stroke-linejoin="round"/>')
y0_ = float(yo(0)); S.add("剖面", f'<line x1="{PX0}" y1="{y0_:.1f}" x2="{PX1}" y2="{y0_:.1f}" stroke="{C["ink2"]}" stroke-width="0.5" stroke-dasharray="1.5 2"/>')
S.add("剖面", f'<rect x="{PX0}" y="{PTOP}" width="{PX1-PX0:.1f}" height="{PH}" fill="none" stroke="{C["frame"]}" stroke-width="0.9"/>')
tk = []
d = 0.0
while d <= L + 1e-6:
    x = float(xo(d)); major = abs(d/1000 - round(d/1000)) < 1e-6
    tk.append(f'<line x1="{x:.1f}" y1="{PTOP+PH}" x2="{x:.1f}" y2="{PTOP+PH+(6 if major else 3)}"/>')
    if major: S.text("剖面", x, PTOP+PH+16, f"{d:,.0f}", 7.6, "lat", anchor="middle")
    d += 200
S.add("剖面", f'<g stroke="{C["frame"]}" stroke-width="0.6">{"".join(tk)}</g>')
S.text("剖面", PX1, PTOP+PH+28, "自废井站起算的里程（km）", 8, "cjk", fill=C["ink2"], anchor="end")
# 分程分隔线与标题
for sv, (nm, Lk) in zip((0.0, S_MOUTH, S_NAN), [(n_, Lk) for (n_, _, _), Lk in zip(LEGS, LEN)]):
    x = float(xo(sv))
    if sv > 0: S.add("剖面", f'<line x1="{x:.1f}" y1="{PTOP}" x2="{x:.1f}" y2="{PTOP+PH}" stroke="{ROUTE_C}" stroke-width="0.8" stroke-dasharray="4 2"/>')
    S.text("剖面", x + 6, PTOP - 7, f"{nm}  {Lk:,.0f} km", 8.8, "cjk_b", fill=ROUTE_C, weight="bold")
    pl.block(x, PTOP-18, x + text_width(f"{nm}  {Lk:,.0f} km", 8.8, "cjk_b") + 8, PTOP-2)
# 水面注记
xm_ = float(xo(S_MOUTH*0.22)); S.text("剖面", xm_, float(yo(LV["borealis"])) + 11, "北方海 −3,700 m（冰面）", 7.6, "cjk", fill=C["water_label"], anchor="middle", halo=2)
pl.block(xm_-60, float(yo(LV["borealis"])) + 2, xm_+60, float(yo(LV["borealis"])) + 13)
# 关键点：圈在地面上方
for n_, nm, sv, a, b, z in KEYP:
    x = float(xo(sv)); i = int(np.argmin(np.abs(s - sv)))
    yg = float(yo(pz[max(0, i-8):i+9].max()))
    keypoint("剖面", x, yg - 11, n_, r=5.8, fs=7.2); pl.block(x-6, yg-17, x+6, yg-5)
    w = text_width(nm, 8, "cjk"); placed = False
    bx = min(max(x - w/2, PX0 + 3), PX1 - 3 - w)
    for dy in (26, 38, 50, 62, 74, 86):
        box = (bx, yg-dy-9, bx+w, yg-dy+2)
        if yg-dy-9 > PTOP-40 and pl.free(box, 1):
            S.text("剖面", bx, yg-dy, nm, 8, "cjk", fill="#444444", halo=2.2); pl.block(*box); placed = True; break
    if not placed: print("   剖面没放下：", nm)
# 地貌注记（段名）
for nm, sv in [("三角洲", S_MOUTH+300), ("下卡塞峡", S_MOUTH+950), ("上卡塞", S_MOUTH+2050), ("塔西斯东坡", S_NAN+800), ("熔岩平原（沿 17°N）", S_NAN+2400), ("断崖", L-40)]:
    x = float(xo(sv)); i = int(np.argmin(np.abs(s - sv))); yg = float(yo(pz[max(0, i-30):i+31].max()))
    w = text_width(nm, 7.6, "cjk")
    for dy in (10, 22, 34, 46):
        box = (x-w/2, yg-dy-8, x+w/2, yg-dy+2)
        if pl.free(box, 1):
            S.text("剖面", x, yg-dy, nm, 7.6, "cjk", fill="#666666", anchor="middle", halo=2.2); pl.block(*box); break

# ── 剖面右侧：三程与要点 ─────────────────────────────────────────────
TX = LX; ty = PTOP - 30
S.text("要点", TX, ty, "三程", 11, "cjk_b", weight="bold")
DAYS = (8, 9, 15)
rows = [("一 · 冰上", f"{LEN[0]:,.0f} km", f"{DAYS[0]} 天", "海冰，井站到井站"), ("二 · 河上", f"{LEN[1]:,.0f} km", f"{DAYS[1]} 天", "河冰，落差段走岸"),
        ("三 · 高原", f"{LEN[2]:,.0f} km", f"{DAYS[2]} 天", "无路，末段断崖")]
for i, (a_, b_, c_, d_) in enumerate(rows):
    y = ty + 20 + i*15
    S.text("要点", TX, y, a_, 8.4, "cjk_b", weight="bold"); S.text("要点", TX+108, y, b_, 8.4, "lat", anchor="end"); S.text("要点", TX+140, y, c_, 8.4, "cjk", anchor="end"); S.text("要点", TX+148, y, d_, 8.0, "cjk", fill=C["ink2"])
y = ty + 20 + 3*15 + 4
S.text("要点", TX, y, f"合计 {sum(LEN):,.0f} km，纯行驶 {sum(DAYS)} 个火星日；停留另算，按两到三个月写。", 7.8, "cjk", fill=C["ink2"])
S.text("要点", TX, y+13, "天数按冰面履带舰：冰上 35、河冰 25、高原 20 km/h，每天 12 小时。", 7.8, "cjk", fill=C["ink2"])
k4, k5, k8, k9 = KEYP[3], KEYP[4], KEYP[7], KEYP[8]
notes = [f"· 河床从河口 −3,700 m 到南通 −820 m，{LEN[1]:,.0f} km 只升 2.9 km，",
         f"　 其中 1.8 km 集中在卡塞落差 300 km 里（⑤）。",
         f"· 下卡塞峡（④ 起）谷深 2.5 到 2.8 km，宽 30 到 60 km。",
         f"· 高原最高点在鞍部（⑧）{k8[5]:,.0f} m，比 2100 年呼吸线低 5 km。",
         f"· 崖脚（⑨）{k9[5]:,.0f} m 到城里 4,375 m，70 km 拔起 4.9 km。",
         "· 直线（Liangzhen 登陆）合计 5,200 km，是本路线的一半多一点。",
         "· 岸线沿用 2100 年图（待定 F）；起点位置为假定（待定 I）。"]
M.note_lines(S, "要点", TX, y + 34, notes, size=7.8, lh=13)

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", X0, 52, "路线", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", X0 + text_width("路线", 30, "cjk_b", 3) + 18, 52, "北方海到火大 · 沿回声河 · 2198 年冬", 14, "cjk", fill=C["ink2"])
S.text("图名", X0, 72, "MARS  ·  THE RIVER ROUTE  ·  BOREALIS SEA TO NIX OLYMPICA  ·  WINTER 2198", 8.4, "lat", fill=C["ink2"], spacing=1.6)
RX = SW - 48
S.text("图名", RX, 46, "主图墨卡托投影，204–326°E × 6°S–38°N  ·  火星 2000 参考球  R = 3,396.19 km", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 60, "路线在 MOLA 地形上算出：海路为水面掩膜上的最短路，河为沿谷底的最低路径，高原为坡度最省力路径（高程封顶 3,500 m）", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 74, "2198 年镜子已关，北方海与河面冬季封冻，冰面即路；铁路已停", 8.2, "cjk", fill=C["alert"], anchor="end")
S.text("出处", X0, SH-22, "底图：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接）；陆地色调：MGS TES 反照率（USGS 7.4 km 拼接）；等高线由 32 px/度重采样高程平滑后提取。地貌名：IAU 行星地名库。"
       "城镇与铁路：GURPS Transhuman Space《In The Well》，位置按正典给出的地理关系在真实地形上重新确定。路线：本书设定，见《路线：北方海到火大》。", 7.0, "cjk", fill=C["ink3"])

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
