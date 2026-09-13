#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
废井站导航图（2198 年冬）—— 序章那条履带舰的导航终端屏。插图，不进系列图。
左：主图 84 km 见方，塞韦尔坑（Sevel，7.4 km）西南坑缘的废井站 → 50 km 外的活井站，船在冰道上 10 km 处；
右上：总览 900 km，冰盖岸、北极峡谷口、附近陨坑、往克律塞湾的冰道；右下：状态卡。
底图是真实轨道影像：MRO CTX 5 m 全球拼接（Caltech Murray Lab，经 NASA Trek / astro.arcgis.com 瓦片服务取用）。
书里它是海图的海底底图，水来之前拍的。水深等值线来自 MOLA，水面 −3,700 m。
数据：DEM/CTX缓存/（瓦片，缺了自动下载）、DEM/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif、产出/路线_2198.geojson、数据/IAU
产出：产出/废井站导航图_2198.svg / .png（3 倍）
运行：./.venv/bin/python scripts/38_废井站导航图.py
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Azimuthal, text_width, hav_km

NAME = "废井站导航图_2198"
CACHE = M.MAP_DIR/"DEM"/"CTX缓存"; CACHE.mkdir(exist_ok=True)
TILE_URL = "https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{r}/{c}"
LV_SEA = -3700.0
KM_LAT = M.KMPD                                   # km / 度纬度

# ── 站与船 ───────────────────────────────────────────────────────────
DEAD = (79.1816, 323.4506)                        # 废井站：塞韦尔坑西南坑缘最高点（MOLA 128 px/度）
ROUTE = json.load(open(M.OUT/"路线_2198.geojson", encoding="utf-8"))
leg1 = [f for f in ROUTE["features"] if f["properties"].get("leg", "").startswith("第一程")][0]["geometry"]["coordinates"]
L1 = np.array([(la, lo) for lo, la in leg1])       # (lat, lon)
cum = np.r_[0, np.cumsum(hav_km(L1[:-1, 0], L1[:-1, 1], L1[1:, 0], L1[1:, 1]))]
def along(km):
    i = np.searchsorted(cum, km); i = min(max(i, 1), len(cum)-1)
    t = (km - cum[i-1])/(cum[i] - cum[i-1])
    return tuple(L1[i-1] + t*(L1[i] - L1[i-1]))
SPACING = 50.0                                    # 井站间距（设定）
LIVE = along(SPACING); NEXT2 = along(2*SPACING); NEXT3 = along(3*SPACING)
SHIP_KM = 10.0                                    # 船离废井站
def lerp(p, q, t): return (p[0] + (q[0]-p[0])*t, p[1] + (q[1]-p[1])*t)
SHIP = lerp(DEAD, LIVE, SHIP_KM/SPACING)
def bearing(p, q):
    la1, la2 = math.radians(p[0]), math.radians(q[0]); dl = math.radians(q[1]-p[1])
    x = math.sin(dl)*math.cos(la2); y = math.cos(la1)*math.sin(la2) - math.sin(la1)*math.cos(la2)*math.cos(dl)
    return math.degrees(math.atan2(x, y)) % 360
HDG = bearing(SHIP, LIVE)
SPEED = 35.0
TO_LIVE = SPACING - SHIP_KM
eta_min = TO_LIVE/SPEED*60

# ── 版面 ─────────────────────────────────────────────────────────────
SW = 1848
TOP = 64                                          # 状态条高
MX0, MY0, MS = 24, TOP + 12, 1100                 # 主图
MAIN_KM = 84.0
OX0, OY0, OS = MX0 + MS + 36, TOP + 12, 664       # 总览
OV_KM = 900.0
SH = MY0 + MS + 60
S = SVG(SW, SH, "废井站导航图 · 履带舰导航终端 · 2198 年冬")
UI = dict(bg="#EEF0F3", panel="#FFFFFF", line="#C9CED6", ink="#1B1F26", ink2="#5B6470", ink3="#8B93A0",
          route="#E8710A", route_done="#B8BEC8", live="#1F9D55", dead="#8B93A0", ship="#1E6FD9",
          contour="#6C88A8", index="#4B6A8E", cap="#FFFFFF", cap_line="#9EB8D0", warn="#C8382B")
C["paper"] = UI["bg"]
FONT_UI = "cjk"

MID_MAIN = lerp(DEAD, LIVE, 0.5)
PM = Azimuthal(MID_MAIN[0], MID_MAIN[1], MX0 + MS/2, MY0 + MS/2, MS/MAIN_KM)
PO = Azimuthal(SHIP[0], SHIP[1], OX0 + OS/2, OY0 + OS/2, OS/OV_KM)

# ── CTX 瓦片 → 等距圆柱镶嵌 ───────────────────────────────────────────
def tile_res(z): return 0.3515625/2**z            # 度/像素，512 px 瓦片
def fetch(z, r, c):
    f = CACHE/f"z{z}_{r}_{c}.png"
    if not f.exists() or f.stat().st_size < 1000:
        subprocess.run(["curl", "-sS", "--max-time", "60", "-A", "Mozilla/5.0", "-o", str(f), TILE_URL.format(z=z, r=r, c=c)])
    return f
def mosaic(z, lon0, lon1, lat0, lat1):
    """[lon0, lon1] × [lat1, lat0]（东经，可为负）→ (灰度数组, 每像素度数, 左上角 lon/lat)。缺瓦片补中灰。"""
    res = tile_res(z); dt = res*512; n = 2**z
    c0, c1 = int(math.floor((lon0 + 180)/dt)), int(math.floor((lon1 + 180)/dt))
    r0, r1 = int(math.floor((90 - lat0)/dt)), int(math.floor((90 - lat1)/dt))
    jobs = [(r, c % (2*n)) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    with ThreadPoolExecutor(8) as ex: list(ex.map(lambda j: fetch(z, *j), jobs))
    out = np.full(((r1 - r0 + 1)*512, (c1 - c0 + 1)*512), 128, np.float32)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            try: im = np.asarray(Image.open(fetch(z, r, c % (2*n))).convert("L"), np.float32)
            except Exception: continue
            out[(r-r0)*512:(r-r0+1)*512, (c-c0)*512:(c-c0+1)*512] = im
    return out, res, (-180 + c0*dt, 90 - r0*dt)

def flatten(img, sig_rc, lo=188, hi=234, gain=1.1):
    """局部对比归一化：减局部均值、除局部标准差，拼接块的明暗差和各条带的对比差一起消掉；再压到浅色区间。
    sig_rc 是等距圆柱像素里的 (行, 列) 窗口，列向要乘 cos(纬度) 的倒数才是等地面尺度。"""
    mu = ndimage.gaussian_filter(img, sig_rc); hp = img - mu
    sd = np.sqrt(ndimage.gaussian_filter(hp**2, sig_rc)) + 2.0
    z = np.clip(hp/sd*gain, -2.5, 2.5)
    return lo + (z + 2.5)/5*(hi - lo)

def unseam(out, pct=99.3, sig=8, min_len=220):
    """投影后再抓一遍残余拼缝：低通梯度里又长又直的线（Hough），沿线用大模糊补掉。"""
    from PIL import ImageDraw
    from skimage.transform import probabilistic_hough_line
    from skimage.morphology import skeletonize
    mu = ndimage.gaussian_filter(out, sig)
    gm = np.hypot(ndimage.sobel(mu, 0), ndimage.sobel(mu, 1))
    sk = skeletonize(gm > np.percentile(gm, pct))
    lines = probabilistic_hough_line(sk, threshold=30, line_length=min_len, line_gap=40)
    mk = Image.new("L", (out.shape[1], out.shape[0]), 0); d = ImageDraw.Draw(mk)
    for (x0, y0), (x1, y1) in lines: d.line([(x0, y0), (x1, y1)], fill=255, width=22)
    seam = np.asarray(mk) > 0
    fill = ndimage.gaussian_filter(out, 11)
    res = out.copy(); res[seam] = fill[seam]
    return res, len(lines)

def reproject(img, res, origin, proj, x0, y0, size, ss):
    """把等距圆柱灰度图重采样到方位投影的正方形面板。"""
    n = int(size*ss)
    X, Y = np.meshgrid(x0 + (np.arange(n) + 0.5)/ss, y0 + (np.arange(n) + 0.5)/ss)
    lon, lat, ok = proj.inverse(X, Y)
    lon = ((lon - origin[0] + 180) % 360) - 180 + origin[0]
    col = (lon - origin[0])/res - 0.5; row = (origin[1] - lat)/res - 0.5
    return ndimage.map_coordinates(img, [row, col], order=1, mode="nearest")

print("主图影像 …")
pad = MAIN_KM/2*1.45
la_hi, la_lo = MID_MAIN[0] + pad/KM_LAT, MID_MAIN[0] - pad/KM_LAT
lo_w = pad/(KM_LAT*math.cos(math.radians(MID_MAIN[0])))
img9, res9, org9 = mosaic(9, MID_MAIN[1] - 360 - lo_w, MID_MAIN[1] - 360 + lo_w, la_hi, la_lo)
img9 = flatten(img9, (14, 70))
main_gray, n1 = unseam(reproject(img9, res9, org9, PM, MX0, MY0, MS, 2), pct=99.0, sig=8, min_len=200)
main_gray, n2 = unseam(main_gray, pct=99.3, sig=14, min_len=300)
main_gray = ndimage.gaussian_filter(main_gray, 1.2)
print(f"  补掉长拼缝 {n1} + {n2} 条")
main_rgb = np.repeat(main_gray[..., None], 3, axis=2).astype(np.uint8)

print("总览底图 …")
# 900 km 一级的 CTX 拼接（650 m/px）覆盖有洞、条带明显，总览改用 MOLA 晕渲（真实地形），淡色。
D32 = M.load_dem32_avg()
n_ov = OS*2
Xo, Yo = np.meshgrid(OX0 + (np.arange(n_ov) + 0.5)/2, OY0 + (np.arange(n_ov) + 0.5)/2)
lon_o, lat_o, _ = PO.inverse(Xo, Yo)
dem_o = M.sample_lonlat(D32, 32, lon_o % 360, lat_o, order=1)
px_m = OV_KM*1000/n_ov
hs_o = M.shade(dem_o, px_m, px_m, zfac=4.0)
hs_o = np.clip((hs_o - np.percentile(hs_o, 2))/(np.percentile(hs_o, 98) - np.percentile(hs_o, 2) + 1e-9), 0, 1)
ov = 196 + hs_o*40
ov_rgb = np.repeat(ov[..., None], 3, axis=2).astype(np.uint8)

# ── 水深 ─────────────────────────────────────────────────────────────
print("水深 …")
D128 = M.read_dem_window(MID_MAIN[1] - lo_w - 0.2, MID_MAIN[1] + lo_w + 0.2, la_hi + 0.05, la_lo - 0.05, 128)
d_lon0, d_lat0 = MID_MAIN[1] - lo_w - 0.2, la_hi + 0.05
def to_xy_main(r, c): return PM.xy(d_lon0 + (c + 0.5)/128, d_lat0 - (r + 0.5)/128)
sm128 = ndimage.gaussian_filter(D128.astype(np.float64), 1.6)
levels_main = list(range(-5300, -4700, 25))
cm = {lv: M.contour_lines(sm128, lv, to_xy_main, 0, 10, 0.4) for lv in levels_main}

strip = D32[:int((90 - 64)*32), :].astype(np.float64)
def to_xy_ov(r, c): return PO.xy(-180 + (c + 0.5)/32, 90 - (r + 0.5)/32)
sm32 = ndimage.gaussian_filter(strip, 1.2)
levels_ov = list(range(-5400, -3700, 200))
co = {lv: M.contour_lines(sm32, lv, to_xy_ov, 0, 8, 0.5) for lv in levels_ov}
shore = M.contour_lines(sm32, LV_SEA, to_xy_ov, 0, 8, 0.5)
capmask = sm32 > LV_SEA

def depth_at(lat, lon):
    return LV_SEA - float(M.sample_lonlat(D32, 32, lon % 360, lat, order=1))
KEEL = LV_SEA - float(M.sample_window(D128, 128, d_lon0, d_lat0, np.array([SHIP[1]]), np.array([SHIP[0]]))[0])

# ── 画：底 ───────────────────────────────────────────────────────────
S.add("defs", f'<clipPath id="clipMain"><rect x="{MX0}" y="{MY0}" width="{MS}" height="{MS}" rx="10"/></clipPath>'
              f'<clipPath id="clipOv"><rect x="{OX0}" y="{OY0}" width="{OS}" height="{OS}" rx="10"/></clipPath>'
              f'<pattern id="thin" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
              f'<line x1="0" y1="0" x2="0" y2="6" stroke="{UI["warn"]}" stroke-width="1.2" opacity="0.55"/></pattern>')
S.add("主图底", f'<image x="{MX0}" y="{MY0}" width="{MS}" height="{MS}" clip-path="url(#clipMain)" '
               f'xlink:href="{M.png_data_uri(main_rgb, quality=88)}"/>')
S.add("总览底", f'<image x="{OX0}" y="{OY0}" width="{OS}" height="{OS}" clip-path="url(#clipOv)" '
               f'xlink:href="{M.png_data_uri(ov_rgb, quality=85)}"/>')
# 冰盖：−3,700 以上填白
cap_rings = M.mask_rings(capmask.astype(np.uint8), 32, lon_left=-180.0, lat_top=90.0, min_px=30, smooth=2)
S.add("总览底", f'<g clip-path="url(#clipOv)"><path d="{M.rings_to_path(cap_rings, PO)}" fill="{UI["cap"]}" fill-rule="evenodd" '
               f'stroke="{UI["cap_line"]}" stroke-width="1.1"/></g>')

# ── 等深线 ────────────────────────────────────────────────────────────
clipM = 'clip-path="url(#clipMain)"'; clipO = 'clip-path="url(#clipOv)"'
for lv, lines in cm.items():
    if not lines: continue
    idx = lv % 100 == 0
    d = " ".join(M.path_d(p[:, 0], p[:, 1]) for p in lines)
    S.add("主图等深线", f'<path d="{d}" fill="none" stroke="{UI["index"] if idx else UI["contour"]}" '
                       f'stroke-width="{0.9 if idx else 0.45}" opacity="{0.9 if idx else 0.7}" {clipM}/>')
for lv, lines in co.items():
    if not lines: continue
    idx = lv % 1000 == 0
    d = " ".join(M.path_d(p[:, 0], p[:, 1]) for p in lines)
    S.add("总览等深线", f'<path d="{d}" fill="none" stroke="{UI["index"] if idx else UI["contour"]}" '
                       f'stroke-width="{0.7 if idx else 0.35}" opacity="0.75" {clipO}/>')

placerM = Placer((MX0 + 6, MY0 + 6, MX0 + MS - 6, MY0 + MS - 6))
placerO = Placer((OX0 + 6, OY0 + 6, OX0 + OS - 6, OY0 + OS - 6))
fmt_depth = lambda lv: f"{LV_SEA - lv:,.0f}"
nM = M.label_contours(S, placerM, {lv: ls for lv, ls in cm.items() if lv % 100 == 0}, size=7.6, every=300,
                      layer="主图等深线注记", fmt=fmt_depth, color=UI["index"])
nO = M.label_contours(S, placerO, {lv: ls for lv, ls in co.items() if lv % 1000 == 0}, size=6.8, every=260,
                      layer="总览等深线注记", fmt=fmt_depth, color=UI["index"])
print(f"  等深线注记 主图 {nM} 处 · 总览 {nO} 处")

# ── 冰道与站 ──────────────────────────────────────────────────────────
def seg(proj, p, q, n=40):
    pts = [proj.xy(*reversed(lerp(p, q, t))) for t in np.linspace(0, 1, n)]
    return " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
# 主图：走过的一段灰，前方橙
S.add("主图冰道", f'<path d="{seg(PM, DEAD, SHIP)}" fill="none" stroke="{UI["route_done"]}" stroke-width="5" stroke-linecap="round" {clipM}/>')
S.add("主图冰道", f'<path d="{seg(PM, SHIP, LIVE)}" fill="none" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round" opacity="0.8" {clipM}/>')
S.add("主图冰道", f'<path d="{seg(PM, SHIP, LIVE)}" fill="none" stroke="{UI["route"]}" stroke-width="4.5" stroke-linecap="round" {clipM}/>')
S.add("主图冰道", f'<path d="{seg(PM, LIVE, NEXT2)}" fill="none" stroke="{UI["route"]}" stroke-width="3" stroke-dasharray="9 7" stroke-linecap="round" opacity="0.8" {clipM}/>')
# 公里标
for km in range(10, int(SPACING*2), 10):
    p = lerp(DEAD, LIVE, km/SPACING) if km <= SPACING else lerp(LIVE, NEXT2, (km - SPACING)/SPACING)
    x, y = PM.xy(p[1], p[0])
    if MX0 < x < MX0 + MS and MY0 < y < MY0 + MS and km not in (SPACING,):
        S.add("主图冰道", f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="#FFFFFF" stroke="{UI["route"]}" stroke-width="1.2"/>')
        S.text("主图冰道注记", x + 6, y + 3, f"{km}", 7.5, "lat", fill=UI["route"], halo=2.4)
# 薄冰区：活井 3 km
r_thin = 3.0*PM.scale
lx, ly = PM.xy(LIVE[1], LIVE[0])
S.add("主图冰道", f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="{r_thin:.1f}" fill="url(#thin)" stroke="{UI["warn"]}" stroke-width="1.2" stroke-dasharray="4 3"/>')

def station(layer, proj, p, alive, size=9):
    x, y = proj.xy(p[1], p[0]); col = UI["live"] if alive else UI["dead"]
    S.add(layer, f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size+3}" fill="#FFFFFF" opacity="0.9"/>'
                 f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size}" fill="{col}"/>'
                 f'<rect x="{x-size*0.42:.1f}" y="{y-size*0.55:.1f}" width="{size*0.84:.1f}" height="{size*1.1:.1f}" fill="#FFFFFF" rx="1"/>'
                 + (f'<path d="M{x-size*0.42:.1f},{y-size*0.55:.1f} l{size*0.42:.1f},-{size*0.5:.1f} l{size*0.42:.1f},{size*0.5:.1f}" fill="#FFFFFF"/>' if alive else
                    f'<line x1="{x-size*0.5:.1f}" y1="{y+size*0.7:.1f}" x2="{x+size*0.5:.1f}" y2="{y-size*0.7:.1f}" stroke="{UI["warn"]}" stroke-width="2"/>'))
    return x, y
def ship(layer, proj, p, hdg, size=13):
    x, y = proj.xy(p[1], p[0])
    S.add(layer, f'<g transform="translate({x:.1f},{y:.1f}) rotate({hdg:.1f})">'
                 f'<path d="M0,-{size*3.2} L{size*1.6},{size*0.6} L-{size*1.6},{size*0.6} Z" fill="{UI["ship"]}" opacity="0.16"/>'
                 f'<circle r="{size*0.95}" fill="#FFFFFF"/><circle r="{size*0.62}" fill="{UI["ship"]}"/>'
                 f'<path d="M0,-{size*0.55} L{size*0.32},{size*0.25} L0,{size*0.05} L-{size*0.32},{size*0.25} Z" fill="#FFFFFF"/></g>')
    return x, y

dx, dy = station("主图站", PM, DEAD, False, 10)
lx, ly = station("主图站", PM, LIVE, True, 10)
sx, sy = ship("主图站", PM, SHIP, HDG)

def label(layer, x, y, main, sub=None, size=11.5, fill=None, anchor="start", sub_size=8.2):
    S.text(layer, x, y, main, size, "cjk_b", fill=fill or UI["ink"], anchor=anchor, weight="bold", halo=3.2)
    if sub: S.text(layer, x, y + sub_size + 4, sub, sub_size, "cjk", fill=UI["ink2"], anchor=anchor, halo=2.6)

# 塞韦尔坑：注在坑心东侧
cx_, cy_ = PM.xy(323.78, 79.21)
label("主图注记", cx_ + 3.7*PM.scale + 10, cy_ + 4, "塞韦尔坑", "Sevel · 7.4 km · 坑缘水深 840 m")
label("主图注记", dx - 16, dy - 4, "废井站", f"塞韦尔坑缘 · 已停 12 年 · 后方 {SHIP_KM:.0f} km", fill=UI["dead"], anchor="end")
label("主图注记", lx + 16, ly + 4, "活井站", f"{TO_LIVE:.0f} km · 薄冰区 3 km · 沿冰道进", fill=UI["live"])
label("主图注记", sx + 20, sy + 4, "本船", f"航向 {HDG:.0f}° · {SPEED:.0f} km/h · 龙骨下 {KEEL:,.0f} m", fill=UI["ship"])
# 冰道名
mx_, my_ = PM.xy(*reversed(lerp(SHIP, LIVE, 0.55)))
ang = HDG - 90
S.add("主图注记", f'<text x="{mx_:.1f}" y="{my_-9:.1f}" transform="rotate({ang:.1f} {mx_:.1f} {my_:.1f})" font-family="{M.FAM_CJK}" font-size="9" '
                  f'fill="{UI["route"]}" text-anchor="middle" stroke="#FFFFFF" stroke-width="2.6" paint-order="stroke">冰道 · 2197 年标定</text>')
# 下一站方向
nx_, ny_ = PM.xy(NEXT2[1], NEXT2[0])
if not (MX0 < nx_ < MX0 + MS and MY0 < ny_ < MY0 + MS):
    ex_, ey_ = PM.xy(*reversed(lerp(LIVE, NEXT2, 0.13)))
    label("主图注记", ex_ - 12, ey_ + 4, "第三站 ↓", f"{2*SPACING - SHIP_KM:.0f} km · 克律塞湾口 {1438 - SHIP_KM:,.0f} km", size=9.5, fill=UI["route"], anchor="end")

# 主图：比例尺、指北、坐标
def scale_ui(x, y, proj, step, n, size=7.8):
    seg_ = step*proj.scale
    for i in range(n):
        S.add("界面", f'<rect x="{x+i*seg_:.1f}" y="{y}" width="{seg_:.1f}" height="4" fill="{UI["ink"] if i%2==0 else "#FFFFFF"}" stroke="{UI["ink"]}" stroke-width="0.6"/>')
    S.text("界面", x, y - 4, "0", size, "lat", fill=UI["ink"], halo=2.4)
    S.text("界面", x + n*seg_, y - 4, f"{n*step:,} km", size, "lat", fill=UI["ink"], anchor="middle", halo=2.4)
scale_ui(MX0 + 26, MY0 + MS - 28, PM, 5, 4)
scale_ui(OX0 + 22, OY0 + OS - 24, PO, 100, 3)
# 指北（主图：极方向）
nxp, nyp = PM.xy(SHIP[1], 89.9)
angN = math.degrees(math.atan2(nxp - sx, -(nyp - sy)))
ax, ay = MX0 + MS - 50, MY0 + 52
S.add("界面", f'<g transform="translate({ax},{ay}) rotate({angN:.1f})"><circle r="19" fill="#FFFFFF" opacity="0.85"/>'
              f'<path d="M0,-15 L6,4 L0,0 L-6,4 Z" fill="{UI["ink"]}"/><text y="-19" font-family="{M.FAM_LAT}" font-size="8" text-anchor="middle" fill="{UI["ink"]}">N</text></g>')
S.text("界面", MX0 + MS - 16, MY0 + MS - 14, f"{SHIP[0]:.2f}°N  {SHIP[1]:.2f}°E   ·   84 × 84 km   ·   等深线 25 m（水深，米）", 8, "cjk", fill=UI["ink2"], anchor="end", halo=2.6)

# ── 总览 ─────────────────────────────────────────────────────────────
# 冰道全程（第一程）
pts = [PO.xy(lo, la) for la, lo in L1]
S.add("总览冰道", f'<path d="{" ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))}" '
                 f'fill="none" stroke="{UI["route"]}" stroke-width="2.4" {clipO}/>')
for km in (200, 300, 400):
    p = along(km); x, y = PO.xy(p[1], p[0])
    S.add("总览冰道", f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="#FFFFFF" stroke="{UI["route"]}" stroke-width="1"/>')
    S.text("总览注记", x + 5, y + 3, f"{km}", 6.8, "lat", fill=UI["route"], halo=2.2)
for p, alive in ((DEAD, False), (LIVE, True), (NEXT2, True), (NEXT3, True)):
    station("总览站", PO, p, alive, 5)
ship("总览站", PO, SHIP, HDG, 6)
# 纬线
for la in (75, 80, 85):
    pts = [PO.xy(lo, la) for lo in np.linspace(180, 540, 361)]
    S.add("总览网", f'<path d="{" ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))}" '
                   f'fill="none" stroke="{UI["ink3"]}" stroke-width="0.5" stroke-dasharray="2 3" opacity="0.8" {clipO}/>')
    x, y = PO.xy(SHIP[1] + 40, la)
    if OX0 < x < OX0 + OS and OY0 < y < OY0 + OS: S.text("总览注记", x, y - 2, f"{la}°N", 6.8, "lat", fill=UI["ink3"], halo=2)
# 地名
IAU = M.load_iau()
def iau(name): r = IAU[name]; return float(r["center_lat"]), float(r["center_lon"]) % 360
OV_NAMES = [("塞韦尔坑", "Sevel", iau("Sevel"), 7), ("伊努维克坑", "Inuvik", iau("Inuvik"), 7),
            ("埃斯科里亚尔坑", "Escorial", iau("Escorial"), 7), ("北极峡谷", "Chasma Boreale", iau("Chasma Boreale"), 0),
            ("极北沙丘", "Hyperboreae Undae", iau("Hyperboreae Undae"), 0), ("极北洼地", "Hyperborei Cavi", iau("Hyperborei Cavi"), 0)]
for zh, en, (la, lo), dot in OV_NAMES:
    x, y = PO.xy(lo, la)
    if not (OX0 + 10 < x < OX0 + OS - 10 and OY0 + 10 < y < OY0 + OS - 10): continue
    if dot: S.add("总览注记", f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot*0.35:.1f}" fill="none" stroke="{UI["ink"]}" stroke-width="0.8"/>')
    w = text_width(zh, 8.6, "cjk"); r = placerO.place(x, y, w, 20, 6)
    if r:
        bx, by, _ = r
        S.text("总览注记", bx, by + 8.6, zh, 8.6, "cjk", fill=UI["ink"], halo=2.6)
        S.text("总览注记", bx, by + 18, en, 6.4, "lat_i", fill=UI["ink2"], halo=2, italic=True)
# 冰盖、峡谷、湾口方向
xcap, ycap = PO.xy(334, 86.0)
S.text("总览注记", xcap, ycap, "北极冰盖", 10, "cjk_b", fill=UI["ink2"], anchor="middle", weight="bold", halo=3)
S.text("总览注记", xcap, ycap + 12, "岸线 −3,700 m · 离本船 414 km", 7, "cjk", fill=UI["ink2"], anchor="middle", halo=2.4)
xb, yb = PO.xy(L1[-1][1] if False else 321.0, SHIP[0] - OV_KM/2/KM_LAT + 1.2)
S.text("总览注记", xb - 8, yb, "克律塞湾口 1,438 km · 回声河口 3,355 km ↓", 8, "cjk", fill=UI["route"], anchor="end", halo=2.6)
S.text("界面", OX0 + OS - 12, OY0 + OS - 10, "900 × 900 km · MOLA 晕渲 · 等深线 200 m · 冰盖白", 7.6, "cjk", fill=UI["ink2"], anchor="end", halo=2.4)
S.text("界面", OX0 + 12, OY0 + 18, "总览", 10.5, "cjk_b", fill=UI["ink"], weight="bold", halo=3)

# ── 面板边框 ──────────────────────────────────────────────────────────
for (x, y, w) in ((MX0, MY0, MS), (OX0, OY0, OS)):
    S.add("界面", f'<rect x="{x}" y="{y}" width="{w}" height="{w}" rx="10" fill="none" stroke="{UI["line"]}" stroke-width="1.2"/>')

# ── 状态条 ────────────────────────────────────────────────────────────
S.add("界面", f'<rect x="0" y="0" width="{SW}" height="{TOP}" fill="{UI["panel"]}"/><line x1="0" y1="{TOP}" x2="{SW}" y2="{TOP}" stroke="{UI["line"]}"/>')
S.text("界面", MX0, 30, "导航 · 冰道", 17, "cjk_b", fill=UI["ink"], weight="bold")
S.text("界面", MX0, 50, "北方海 · 极区 · 塞韦尔段", 9.5, "cjk", fill=UI["ink2"])
x = MX0 + 300
for k, v in (("下一站", f"活井站  {TO_LIVE:.0f} km"), ("到站", f"{int(eta_min//60)} h {int(eta_min%60):02d} min"),
             ("航向", f"{HDG:.0f}°"), ("速度", f"{SPEED:.0f} km/h"), ("龙骨下", f"{KEEL:,.0f} m"), ("日落", "17:41  到站前")):
    S.text("界面", x, 26, k, 8.5, "cjk", fill=UI["ink3"])
    S.text("界面", x, 47, v, 14, "cjk_b", fill=UI["ink"], weight="bold")
    x += text_width(v, 14, "cjk") + 46
S.add("界面", f'<rect x="{SW-262}" y="16" width="238" height="32" rx="6" fill="#FBEAE7" stroke="{UI["warn"]}" stroke-width="0.8"/>')
S.text("界面", SW - 250, 37, "无网 · 极区 · 海图为本地副本 · 上次同步 2186", 9.2, "cjk", fill=UI["warn"])

# ── 右下状态卡 ────────────────────────────────────────────────────────
CY = OY0 + OS + 22; CX = OX0; CW = OS
S.add("界面", f'<rect x="{CX}" y="{CY}" width="{CW}" height="{MY0 + MS - CY}" rx="10" fill="{UI["panel"]}" stroke="{UI["line"]}" stroke-width="1.2"/>')
y = CY + 26
S.text("界面", CX + 16, y, "沿线井站", 11.5, "cjk_b", fill=UI["ink"], weight="bold"); y += 10
rows = [(DEAD, "废井站 · 塞韦尔坑缘", False, -SHIP_KM), (LIVE, "活井站", True, TO_LIVE),
        (NEXT2, "第三站", True, 2*SPACING - SHIP_KM), (NEXT3, "第四站", True, 3*SPACING - SHIP_KM)]
for p, name, alive, km in rows:
    y += 22
    col = UI["live"] if alive else UI["dead"]
    S.add("界面", f'<circle cx="{CX+24}" cy="{y-4}" r="5" fill="{col}"/>')
    S.text("界面", CX + 36, y, name, 10, "cjk", fill=UI["ink"])
    S.text("界面", CX + 250, y, f"{p[0]:.2f}°N {p[1]:.2f}°E", 8.2, "lat", fill=UI["ink2"])
    S.text("界面", CX + CW - 16, y, ("后方 " if km < 0 else "") + f"{abs(km):.0f} km", 10, "cjk_b", fill=col, anchor="end", weight="bold")
    S.text("界面", CX + CW - 16, y + 11, "井已停 · 冰厚 · 无补给" if not alive else "井在冒 · 有电 · 有码头", 7.4, "cjk", fill=UI["ink3"], anchor="end")
    y += 12
y += 18
S.add("界面", f'<line x1="{CX+16}" y1="{y}" x2="{CX+CW-16}" y2="{y}" stroke="{UI["line"]}"/>'); y += 20
S.text("界面", CX + 16, y, "图例", 11.5, "cjk_b", fill=UI["ink"], weight="bold"); y += 8
leg = [("route", "冰道 · 前方"), ("route_done", "冰道 · 走过"), ("index", "等深线（水深，米）"), ("warn", "薄冰区（活井周围 3 km）"),
       ("live", "活井站"), ("dead", "废井站"), ("ship", "本船与航向")]
for i, (k, t) in enumerate(leg):
    yy = y + 20 + (i % 4)*20; xx = CX + 16 + (i // 4)*300
    if k == "warn": S.add("界面", f'<rect x="{xx}" y="{yy-9}" width="26" height="10" fill="url(#thin)" stroke="{UI["warn"]}" stroke-width="0.8"/>')
    elif k in ("route", "route_done", "index"):
        S.add("界面", f'<line x1="{xx}" y1="{yy-4}" x2="{xx+26}" y2="{yy-4}" stroke="{UI[k]}" stroke-width="{4 if k.startswith("route") else 1}"/>')
    else: S.add("界面", f'<circle cx="{xx+13}" cy="{yy-4}" r="5" fill="{UI[k]}"/>')
    S.text("界面", xx + 34, yy, t, 9.2, "cjk", fill=UI["ink"])
y += 100
S.add("界面", f'<line x1="{CX+16}" y1="{y}" x2="{CX+CW-16}" y2="{y}" stroke="{UI["line"]}"/>'); y += 18
M.note_lines(S, "界面", CX + 16, y, [
    "底图  轨道影像 2031 年 · 水来之前拍的海底",
    "水深  2100 年测量 · 水面基准 −3,700 m",
    "冰道  2197 年标定 · 活井周围冰薄，离开冰道自负",
    "本机  离线 · 站点状态为上次同步时的记录，以目视白气为准",
], size=8.4, lh=14, fill=UI["ink2"])

# ── 屏外出处 ──────────────────────────────────────────────────────────
S.text("出处", MX0, SH - 22, "插图，不进系列图。主图底图：MRO CTX 5 m 全球拼接（Caltech Murray Lab；NASA Trek / astro.arcgis.com 瓦片），局部对比归一化去拼接块、压成浅色；总览底图：MOLA 晕渲。"
       "水深：MGS MOLA 463 m 高程，水面 −3,700 m（2100 年设定）。塞韦尔坑：IAU Sevel（79.2°N 323.8°E，7.4 km）。井站、冰道、船位：本书设定。", 7.0, "cjk", fill=C["ink3"])
S.text("出处", SW - MX0, SH - 22, "主图与总览均为以船（主图为两站中点）为心的兰伯特等积方位投影，北在上", 7.0, "cjk", fill=C["ink3"], anchor="end")

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
print(f"  废井站 {DEAD}  活井站 {LIVE[0]:.4f},{LIVE[1]:.4f}  船 {SHIP[0]:.4f},{SHIP[1]:.4f}  航向 {HDG:.0f}°  龙骨下 {KEEL:.0f} m  到活井站 {TO_LIVE:.0f} km {eta_min:.0f} min")
