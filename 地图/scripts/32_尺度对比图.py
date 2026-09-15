#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火星有多大 —— 尺度对比图（2100 年 3 月）。所有对比都按同一比例尺真实绘制：
  ① 水手峡谷战区 × 中国轮廓（兰伯特等积方位，各自以中心展开，面积、距离可直接比）
  ② 火星与地球（正射投影地球仪，同比例）+ 基本数据
  ③ 北方海 × 北冰洋（北极心等积方位，同比例）
  ④ 面积配对（火星上的一块 ≈ 地球上的哪一块）
  ⑤ 高度：奥林匹斯山真实剖面 vs 珠穆朗玛峰、冒纳凯阿火山（同比例、垂直夸大 10 倍，另附 1:1）
  ⑥ 深度：水手峡谷真实横剖面 vs 雅鲁藏布大峡谷、科罗拉多大峡谷（同比例、垂直夸大 10 倍）
  ⑦ 距离与身体感受
火星数据全部从 MOLA 与本系列水体掩膜现场量；地球数据用 Natural Earth 与公认数值。

数据：DEM/dem_32ppd_avg.npy、产出/三海掩膜.npz、数据/火星地点.csv、数据/地球/（Natural Earth 1:5000 万陆地、1:1000 万国界·中国视角）
产出：产出/火星尺度对比图_2100.svg  产出/火星尺度对比图_2100.png（3 倍，印刷用）
运行：./.venv/bin/python scripts/32_尺度对比图.py
"""
import itertools, math, subprocess, sys
import numpy as np
from scipy import ndimage
from affine import Affine
import pyogrio
from shapely import from_wkb
from shapely.geometry import MultiPolygon
from pyproj import Geod
from rasterio import features
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Azimuthal, Identity, text_width

NAME = "火星尺度对比图_2100"
SW, SH = 1848, 1880
S = SVG(SW, SH, "火星有多大 · 尺度对比图")
RM_KM, RE_KM = M.R/1e3, 6371.0
EARTH = C["alert"]                                     # 本图不画闸坝，红色专给地球对照物
EARTH_LAND, EARTH_SEA = (234, 230, 222), (214, 229, 241)
GEOD = Geod(ellps="WGS84")

D = M.load_dem32_avg()
Z = M.load_masks()
PL = {r["id"]: r for r in M.load_places()}
PEAKS = {r["山"]: r for r in M.load_peaks()}
INFRA = M.load_infra()
WL = {"borealis": int(Z["level_borealis"]), "hellas": int(Z["level_hellas"]), "marineris_ius": int(Z["level_ius"]),
      "marineris_mid": int(Z["level_marineris"]), "marineris_eos": int(Z["level_eos"]), "lake_mutch": int(Z["level_mutch"])}
def pt(pid): return float(PL[pid]["纬度"]), float(PL[pid]["东经"])
def mkm(a, b): return float(M.hav_km(*pt(a), *pt(b)))

CITIES = {"北京": (39.904, 116.407), "上海": (31.230, 121.474), "广州": (23.129, 113.264), "深圳": (22.543, 114.058),
          "乌鲁木齐": (43.825, 87.617), "喀什": (39.470, 75.990), "拉萨": (29.652, 91.172), "哈尔滨": (45.803, 126.535),
          "成都": (30.573, 104.066), "重庆": (29.563, 106.551), "西安": (34.341, 108.940), "武汉": (30.593, 114.305),
          "南京": (32.060, 118.797), "杭州": (30.274, 120.155), "昆明": (25.040, 102.712), "三亚": (18.253, 109.512),
          "兰州": (36.061, 103.834), "沈阳": (41.806, 123.431), "漠河": (52.970, 122.530), "天津": (39.084, 117.201),
          "郑州": (34.746, 113.625), "长沙": (28.228, 112.939), "台北": (25.033, 121.565), "香港": (22.320, 114.170)}
PAIRS = sorted((GEOD.inv(CITIES[a][1], CITIES[a][0], CITIES[b][1], CITIES[b][0])[2]/1e3, a, b)
               for a, b in itertools.combinations(CITIES, 2))
def like(km):
    d, a, b = min(PAIRS, key=lambda p: abs(p[0]-km)); return f"{a}→{b} {d:,.0f} km"

# ── 地球数据 ───────────────────────────────────────────────────────
def read_shp(path, where=None):
    meta, _, geoms, fields = pyogrio.raw.read(path, columns=["ADMIN"] if where else [])[:4]
    out = []
    for i, g in enumerate(geoms):
        if where and fields[0][i] != where: continue
        out.append(from_wkb(g))
    return out
LAND = read_shp(str(M.DATA/"地球/ne_50m_land.shp"))
EPPD = 10
land_r = features.rasterize([(g, 1) for g in LAND], out_shape=(180*EPPD, 360*EPPD),
                            transform=Affine(1/EPPD, 0, -180, 0, -1/EPPD, 90), dtype=np.uint8).astype(bool)
def earth_land(lon, lat):
    lon = ((np.asarray(lon) + 180) % 360) - 180
    return M.sample_lonlat(land_r, EPPD, lon, lat, order=0).astype(bool)
CHINA = read_shp(str(M.DATA/"地球/ne_10m_admin_0_countries_chn.shp"), where="China")[0]

# ── 通用：方位投影底图 ─────────────────────────────────────────────
def mars_raster(P, x0, y0, w, h, ss=3, zfac=3.0, limb=False):
    n_w, n_h = int(w*ss), int(h*ss)
    ys, xs = np.mgrid[0:n_h, 0:n_w]
    lon, lat, ok = P.inverse(x0 + (xs+0.5)/ss, y0 + (ys+0.5)/ss)
    dem = M.sample_lonlat(D, 32, lon, lat, order=1).astype(np.float32)
    ms = []
    for k, lv in WL.items():
        m = M.sample_lonlat(Z[k], 32, lon, lat, order=0).astype(bool)
        ms.append(ndimage.binary_dilation(m, np.ones((3, 3), bool)) & (dem < lv) & ok)
    px_m = 1000/(P.scale*ss)
    rgb = M.colorize(dem, M.shade(dem, px_m, px_m, zfac), ms, list(WL.values()), albedo=M.albedo_at(lon, lat)).astype(np.float32)
    if limb:
        rho = np.hypot(x0 + (xs+0.5)/ss - P.cx, y0 + (ys+0.5)/ss - P.cy)/(P.scale*P.Rk)
        rgb *= (0.82 + 0.18*np.sqrt(np.clip(1 - rho**2, 0, 1)))[..., None]
    rgb[~ok] = 255
    return np.clip(rgb, 0, 255).astype(np.uint8), ms, ok

def earth_raster(P, x0, y0, w, h, ss=3, limb=False):
    n_w, n_h = int(w*ss), int(h*ss)
    ys, xs = np.mgrid[0:n_h, 0:n_w]
    lon, lat, ok = P.inverse(x0 + (xs+0.5)/ss, y0 + (ys+0.5)/ss)
    lon = np.where(lon > 180, lon - 360, lon)
    land = earth_land(lon, lat)
    rgb = np.where(land[..., None], np.array(EARTH_LAND, np.float32), np.array(EARTH_SEA, np.float32))
    if limb:
        rho = np.hypot(x0 + (xs+0.5)/ss - P.cx, y0 + (ys+0.5)/ss - P.cy)/(P.scale*P.Rk)
        rgb = rgb*(0.82 + 0.18*np.sqrt(np.clip(1 - rho**2, 0, 1)))[..., None]
    rgb[~ok] = 255
    return np.clip(rgb, 0, 255).astype(np.uint8), land & ok

def panel_title(x, y, num, t, sub):
    S.add("标题", f'<circle cx="{x+9}" cy="{y-5}" r="9" fill="{C["ink"]}"/>')
    S.text("标题", x+9, y-1.3, num, 11, "lat_b", fill="#FFFFFF", anchor="middle", weight="bold")
    S.text("标题", x+26, y, t, 15, "cjk_b", weight="bold")
    S.text("标题", x+26 + text_width(t, 15, "cjk_b") + 12, y, sub, 9, "cjk", fill=C["ink2"])

def image(layer, rgb, x, y, w, h, clip=None):
    c = f' clip-path="url(#{clip})"' if clip else ""
    S.add(layer, f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="none"{c} href="{M.png_data_uri(rgb, quality=90)}"/>')

def outline(rings_xy, stroke, width, dash=None, fill="none", halo=True):
    d = " ".join(M.path_d(r[:, 0], r[:, 1], close=True) for r in rings_xy)
    da = f' stroke-dasharray="{dash}"' if dash else ""
    if halo: S.add("对照", f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="{width+2.2}" stroke-linejoin="round" opacity="0.9"/>')
    S.add("对照", f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"{da}/>')

def dot_label(x, y, s, fill, size=8.4, dx=4, dy=-3, anchor="start", r=2.0, kind="cjk", weight="normal"):
    S.add("对照", f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="#FFFFFF" stroke-width="0.8"/>')
    S.text("对照", x+dx, y+dy, s, size, kind, fill=fill, anchor=anchor, halo=2.2, weight=weight)

# ════ ① 水手峡谷战区 × 中国 ════════════════════════════════════════
print("① 水手峡谷 × 中国 …")
X1, Y1, W1, H1 = 84.0, 150.0, 1030.0, 560.0
SC1 = 0.16
MC = (-6.0, 289.0)
P1 = Azimuthal(MC[0], MC[1], X1 + W1/2, Y1 + H1/2, SC1)
rgb, ms, _ = mars_raster(P1, X1, Y1, W1, H1)
S.add("底图", f'<clipPath id="c1"><rect x="{X1}" y="{Y1}" width="{W1}" height="{H1}"/></clipPath>')
image("底图", rgb, X1, Y1, W1, H1)
TF1 = Affine(1/3, 0, X1, 0, 1/3, Y1)
for m in ms:
    rings = M.mask_rings(m, 3, min_px=40, simplify=0.3, smooth=2, transform=TF1)
    if rings: S.add("底图", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{C["coast"]}" stroke-width="0.6" clip-path="url(#c1)"/>')
g = []
for lo in range(230, 360, 10):
    la = np.linspace(-60, 60, 121); x, y = P1.xy(np.full_like(la, lo), la); g.append(M.path_d(x, y))
for la in range(-40, 50, 10):
    lo = np.linspace(220, 360, 141); x, y = P1.xy(lo, np.full_like(lo, la)); g.append(M.path_d(x, y))
S.add("底图", f'<path d="{" ".join(g)}" fill="none" stroke="{C["grat"]}" stroke-width="0.3" opacity="0.25" clip-path="url(#c1)"/>')
S.add("底图", f'<rect x="{X1}" y="{Y1}" width="{W1}" height="{H1}" fill="none" stroke="{C["frame"]}" stroke-width="0.9"/>')

# 中国轮廓：以自身中心按地球半径做等积方位展开，再把中心放到画面中心（东偏一点，让峡谷两端都落在国土里）
cn_c = (35.5, 103.5)
PE = Azimuthal(cn_c[0], cn_c[1], X1 + W1/2 + 20, Y1 + H1/2 + 6, SC1, radius_km=RE_KM)
polys = sorted(CHINA.geoms if isinstance(CHINA, MultiPolygon) else [CHINA], key=lambda p: -p.area)
rings = []
for p in polys:
    if p.area < 0.05 and rings: continue
    q = p.simplify(0.02)
    x, y = PE.xy(*np.asarray(q.exterior.coords).T); rings.append(np.column_stack([x, y]))
S.add("对照", f'<g clip-path="url(#c1)">')
outline(rings, EARTH, 1.3, fill="rgba(179,38,30,0.05)")
for nm in ("北京", "上海", "广州", "乌鲁木齐", "拉萨", "喀什", "哈尔滨", "昆明"):
    x, y = PE.xy(CITIES[nm][1], CITIES[nm][0])
    anchor = "end" if nm in ("喀什", "拉萨", "昆明") else "start"
    dot_label(float(x), float(y), nm, EARTH, size=8.6, dx=-5 if anchor == "end" else 5, anchor=anchor)
S.add("对照", "</g>")

# 火星上的城市与距离标尺
for pid in ("new_shanghai", "haiyuan", "port_lowell", "robinson"):
    la, lo = pt(pid); x, y = map(float, P1.xy(lo, la))
    S.add("火星", M.symbol(M.faction_kind(PL[pid]["阵营"]), x, y, 3.2, major=True))
    S.text("火星", x+(-8 if pid == "robinson" else 8), y+(-8 if pid in ("new_shanghai", "robinson") else 13), PL[pid]["中文名"], 9.6,
           "cjk_b", anchor="end" if pid == "robinson" else "start", halo=2.4, weight="bold")
(la1, lo1), (la2, lo2) = pt("new_shanghai"), pt("robinson")
tt = np.linspace(0, 1, 60)
v = lambda la, lo: np.array([math.cos(math.radians(la))*math.cos(math.radians(lo)), math.cos(math.radians(la))*math.sin(math.radians(lo)), math.sin(math.radians(la))])
a, b = v(la1, lo1), v(la2, lo2); om = math.acos(float(a @ b))
w_ = (np.sin((1-tt)[:, None]*om)*a + np.sin(tt[:, None]*om)*b)/math.sin(om)
gla, glo = np.degrees(np.arcsin(w_[:, 2])), np.degrees(np.arctan2(w_[:, 1], w_[:, 0])) % 360
gx, gy = P1.xy(glo, gla)
OFF = 84                                                            # 尺寸线压到峡谷下方，两端用虚线引到城市
cx_, cy_ = gx.copy(), gy.copy(); gy = gy + OFF
S.add("火星", f'<path d="{M.path_d(gx, gy)}" fill="none" stroke="{C["ink"]}" stroke-width="1.0"/>')
for i in (0, -1):
    S.add("火星", f'<line x1="{gx[i]:.1f}" y1="{cy_[i]+6:.1f}" x2="{gx[i]:.1f}" y2="{gy[i]+5:.1f}" stroke="{C["ink"]}" stroke-width="0.6" stroke-dasharray="2 2"/>'
                  f'<line x1="{gx[i]:.1f}" y1="{gy[i]-5:.1f}" x2="{gx[i]:.1f}" y2="{gy[i]+5:.1f}" stroke="{C["ink"]}" stroke-width="1.0"/>')
d_ns_rb = mkm("new_shanghai", "robinson")
ang = math.degrees(math.atan2(float(gy[-1]-gy[0]), float(gx[-1]-gx[0])))
mx, my = float(gx[34]), float(gy[34])
S.add("火星", f'<text x="{mx:.1f}" y="{my-5:.1f}" transform="rotate({ang:.1f} {mx:.1f} {my:.1f})" font-family="{M.FAM_CJK}" font-size="10" font-weight="bold" '
              f'fill="{C["ink"]}" text-anchor="middle" stroke="#FFFFFF" stroke-width="2.6" stroke-linejoin="round" paint-order="stroke">{d_ns_rb:,.0f} km</text>')
BX_, BY_ = X1 + 360, Y1 + H1 - 58
S.add("火星", f'<rect x="{BX_}" y="{BY_}" width="360" height="48" fill="#FFFFFF" opacity="0.88"/>')
S.text("火星", BX_+12, BY_+19, f"新上海 ↔ 罗宾逊城（两国首府）　{d_ns_rb:,.0f} km", 10, "cjk_b", weight="bold")
S.text("火星", BX_+12, BY_+37, f"≈ {like(d_ns_rb)}", 9.6, "cjk", fill=EARTH)
for zh, (la, lo) in (("水手峡谷海", (-12.6, 297.0)), ("厄俄斯湖", (-16.6, 314.0)), ("克律塞湾", (8.0, 326.5)), ("诺克提斯迷宫", (-4.2, 256.0)),
                     ):
    x, y = map(float, P1.xy(lo, la))
    S.text("火星", x, y, zh, 9.2, "cjk", fill=C["water_label"] if "海" in zh or "湖" in zh or "湾" in zh else "#6A6A6A", anchor="middle", halo=2.4, spacing=1.5)
# 图内说明与比例尺
S.add("火星", f'<rect x="{X1+10}" y="{Y1+H1-58}" width="330" height="48" fill="#FFFFFF" opacity="0.88"/>')
M.scale_bar(S, "火星", X1+22, Y1+H1-30, SC1, 250, 4, size=7, h=4)
S.text("火星", X1+22, Y1+H1-40, "比例尺（火星与中国轮廓共用）", 8.4, "cjk_b", weight="bold")
S.add("火星", f'<rect x="{X1+W1-262}" y="{Y1+10}" width="252" height="38" fill="#FFFFFF" opacity="0.88"/>')
S.add("火星", f'<path d="M{X1+W1-250},{Y1+24} h20" stroke="{EARTH}" stroke-width="1.3"/>')
S.text("火星", X1+W1-224, Y1+27.5, "中国国土轮廓（地球，同比例尺）", 8.6, "cjk", fill=EARTH)
S.text("火星", X1+W1-250, Y1+42, "底图为火星真实地形与 2100 年水面", 8.2, "cjk", fill=C["ink2"])
panel_title(X1, Y1-18, "1", "水手峡谷战区有多大", f"把中国放在火星上，同一比例尺。整条水手峡谷塞得进中国，东西两端几乎顶到国境")

# ════ ② 火星与地球 ══════════════════════════════════════════════════
print("② 地球仪 …")
X2, Y2 = 1180.0, 150.0
SC2 = 300/(2*RE_KM)
PEg = Azimuthal(28.0, 105.0, X2 + 160, Y2 + 162, SC2, radius_km=RE_KM, kind="ortho")
PMg = Azimuthal(-4.0, 290.0, X2 + 160 + 150 + 30 + RM_KM*SC2, Y2 + 162 + 150 - RM_KM*SC2, SC2, radius_km=RM_KM, kind="ortho")
rgbE, _ = earth_raster(PEg, X2+10, Y2+12, 300, 300, limb=True)
image("底图", rgbE, X2+10, Y2+12, 300, 300)
rm = RM_KM*SC2
rgbM, _, _ = mars_raster(PMg, PMg.cx-rm, PMg.cy-rm, 2*rm, 2*rm, zfac=2.0, limb=True)
image("底图", rgbM, PMg.cx-rm, PMg.cy-rm, 2*rm, 2*rm)
for P_, R_ in ((PEg, RE_KM), (PMg, RM_KM)):
    g = []
    for lo in range(0, 360, 30):
        la = np.linspace(-89, 89, 90); vis = P_.visible(np.full_like(la, lo), la); x, y = P_.xy(np.full_like(la, lo), la)
        for sl in ndimage.find_objects(ndimage.label(vis)[0]): g.append(M.path_d(x[sl], y[sl]))
    for la in range(-60, 90, 30):
        lo = np.linspace(0, 360, 181); vis = P_.visible(lo, np.full_like(lo, la)); x, y = P_.xy(lo, np.full_like(lo, la))
        for sl in ndimage.find_objects(ndimage.label(vis)[0]): g.append(M.path_d(x[sl], y[sl]))
    S.add("底图", f'<path d="{" ".join(g)}" fill="none" stroke="{C["grat"]}" stroke-width="0.3" opacity="0.28"/>')
    S.add("底图", f'<circle cx="{P_.cx:.1f}" cy="{P_.cy:.1f}" r="{R_*SC2:.1f}" fill="none" stroke="{C["frame"]}" stroke-width="0.8"/>')
yb = Y2 + 162 + 150
S.add("底图", f'<line x1="{X2}" y1="{yb+0.5}" x2="{PMg.cx+rm+20:.1f}" y2="{yb+0.5}" stroke="{C["ink3"]}" stroke-width="0.5"/>')
S.text("对照", PEg.cx, yb+20, "地球", 11, "cjk_b", anchor="middle", weight="bold", fill=EARTH)
S.text("对照", PEg.cx, yb+34, "直径 12,742 km", 8.6, "cjk", anchor="middle", fill=C["ink2"])
S.text("对照", PMg.cx, yb+20, "火星", 11, "cjk_b", anchor="middle", weight="bold")
S.text("对照", PMg.cx, yb+34, "直径 6,779 km（地球的 53%）", 8.6, "cjk", anchor="middle", fill=C["ink2"])
cell = (math.radians(1/32)*RM_KM)**2*np.cos(np.radians(90 - (np.arange(5760)+0.5)/32))[:, None]
mars_area = float(cell.sum())*11520
area = {k: float((cell*Z[k]).sum()) for k in ("borealis", "hellas", "marineris")}
area["breath"] = float((cell*(D > 5*1609.344)).sum())
rows = [("", "火星 2100", "地球"),
        ("表面积", f"{mars_area/1e8:.2f} 亿 km²", "5.10 亿 km²（陆地 1.49 亿）"),
        ("重力", "0.38 g", "1 g"),
        ("一天", "24 小时 40 分", "24 小时"),
        ("一年", "669 火星日（687 地球日）", "365 天"),
        ("气压", "0.4 atm（低地最高 0.45）", "1 atm"),
        ("氧气", "15%（二氧化碳 75%）", "21%"),
        ("赤道均温", "略高于冰点", "约 26 °C"),
        ("1° 纬度", f"{M.KMPD:.1f} km", "111.2 km"),
        ("地平线", "3.4 km（眼高 1.7 m）", "4.7 km")]
ty = yb + 64
for i, (a_, b_, c_) in enumerate(rows):
    yy = ty + i*17
    bold = i == 0
    S.text("数据", X2, yy, a_, 8.8, "cjk", fill=C["ink2"])
    S.text("数据", X2+78, yy, b_, 8.8, "cjk_b" if bold else "cjk", weight="bold" if bold else "normal")
    S.text("数据", X2+300, yy, c_, 8.8, "cjk_b" if bold else "cjk", fill=EARTH if bold else C["ink"], weight="bold" if bold else "normal")
    if i == 0: S.add("数据", f'<line x1="{X2}" y1="{yy+5}" x2="{X2+560}" y2="{yy+5}" stroke="{C["ink"]}" stroke-width="0.5"/>')
S.text("数据", X2, ty + len(rows)*17 + 4, "2100 年的气压、成分、气温取自正典（ITW p.34 与世界数据表），其余为实测值。", 7.6, "cjk", fill=C["ink3"])
panel_title(X2, Y2-18, "2", "火星与地球", "同一比例尺。火星总面积 ≈ 地球全部陆地")

# ════ ③ 北方海 × 北冰洋 ══════════════════════════════════════════════
print("③ 北方海 × 北冰洋 …")
Y3 = 820.0
R3 = 165.0
SC3 = R3/(2*RM_KM*math.sin(math.radians(85)/2))
PMp = Azimuthal(90, 300, 84 + R3, Y3 + 30 + R3, SC3)
PEp = Azimuthal(90, 110, 84 + 3*R3 + 60, Y3 + 30 + R3, SC3, radius_km=RE_KM)
rgb, ms, okm = mars_raster(PMp, PMp.cx-R3, PMp.cy-R3, 2*R3, 2*R3, zfac=4.0)
S.add("底图", f'<clipPath id="c3m"><circle cx="{PMp.cx}" cy="{PMp.cy}" r="{R3}"/></clipPath><clipPath id="c3e"><circle cx="{PEp.cx}" cy="{PEp.cy}" r="{R3}"/></clipPath>')
image("底图", rgb, PMp.cx-R3, PMp.cy-R3, 2*R3, 2*R3, clip="c3m")
rgbE, landE = earth_raster(PEp, PEp.cx-R3, PEp.cy-R3, 2*R3, 2*R3)
image("底图", rgbE, PEp.cx-R3, PEp.cy-R3, 2*R3, 2*R3, clip="c3e")
rings = M.mask_rings(ms[0], 3, min_px=30, simplify=0.3, smooth=2, transform=Affine(1/3, 0, PMp.cx-R3, 0, 1/3, PMp.cy-R3))
S.add("底图", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{C["coast"]}" stroke-width="0.6" clip-path="url(#c3m)"/>')
rings = M.mask_rings(landE, 3, min_px=30, simplify=0.3, smooth=2, transform=Affine(1/3, 0, PEp.cx-R3, 0, 1/3, PEp.cy-R3))
S.add("底图", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{C["coast"]}" stroke-width="0.6" clip-path="url(#c3e)"/>')
lat_e = 90 - math.degrees(2*math.asin(R3/SC3/(2*RE_KM)))
for P_, clipid, edge in ((PMp, "c3m", 5.0), (PEp, "c3e", lat_e)):
    g = [f'<circle cx="{P_.cx}" cy="{P_.cy}" r="{P_.radius_of(la):.1f}"/>' for la in (30, 60) if la > edge]
    for lo in range(0, 360, 30):
        x0_, y0_ = P_.xy(lo, 80); x1_, y1_ = P_.xy(lo, edge)
        g.append(f'<line x1="{x0_:.1f}" y1="{y0_:.1f}" x2="{x1_:.1f}" y2="{y1_:.1f}"/>')
    S.add("底图", f'<g fill="none" stroke="{C["grat"]}" stroke-width="0.3" opacity="0.3" clip-path="url(#{clipid})">{"".join(g)}</g>')
    S.add("底图", f'<circle cx="{P_.cx}" cy="{P_.cy}" r="{R3}" fill="none" stroke="{C["frame"]}" stroke-width="0.8"/>')
S.text("对照", PMp.cx, PMp.cy - R3*0.35, "北方海", 12, "cjk_b", fill=C["water_label"], anchor="middle", halo=2.6, weight="bold")
S.text("对照", PMp.cx, PMp.cy - R3*0.35 + 14, f"{area['borealis']/1e4:,.0f} 万 km²", 9, "lat", fill=C["water_label"], anchor="middle", halo=2.4)
S.text("对照", PEp.cx, PEp.cy + 4, "北冰洋", 12, "cjk_b", fill=C["water_label"], anchor="middle", halo=2.6, weight="bold")
S.text("对照", PEp.cx, PEp.cy + 18, "约 1,475 万 km²", 9, "cjk", fill=C["water_label"], anchor="middle", halo=2.4)
for nm, la, lo in (("格陵兰", 73, -40), ("西伯利亚", 64, 105), ("加拿大", 60, -105), ("阿拉斯加", 64, -152), ("北欧", 64, 18)):
    x, y = PEp.xy(lo % 360, la)
    if math.hypot(float(x)-PEp.cx, float(y)-PEp.cy) < R3-14:
        S.text("对照", float(x), float(y), nm, 8.2, "cjk", fill="#6A6A6A", anchor="middle", halo=2.2)
S.text("对照", PMp.cx, PMp.cy + R3 + 22, "火星：北极到 5°N", 9, "cjk_b", anchor="middle", weight="bold")
S.text("对照", PEp.cx, PEp.cy + R3 + 22, f"地球：北极到 {lat_e:.0f}°N", 9, "cjk_b", anchor="middle", weight="bold", fill=EARTH)
M.scale_bar(S, "对照", (PMp.cx + PEp.cx)/2 - 1000*SC3, PMp.cy + R3 + 14, SC3, 1000, 2, size=6.8, h=3.5)
panel_title(84, Y3 - 6, "3", "北方海与北冰洋", "同一比例尺。北方海比北冰洋大七成——而火星只有地球一半大")

# ════ ④ 面积配对 ════════════════════════════════════════════════════
X4, Y4 = 880.0, 820.0
panel_title(X4, Y4 - 6, "4", "面积：火星上的这一块 ≈ 地球上的哪一块", "火星数值按 MOLA 与本系列水面现场量算")
eos = float((cell*Z["marineris_eos"]).sum())
oly = math.pi*(float(PEAKS["Olympus Mons"]["基底直径_km"])/2)**2
pairs = [("火星全部表面", mars_area, "land", "地球全部陆地", 1.489e8),
         ("北方海（−3,700 m）", area["borealis"], "water", "北美洲", 2.422e7),
         ("呼吸线（8,047 m）以上", area["breath"], "land", "四川省", 4.86e5),
         ("奥林匹斯山山体", oly, "land", "意大利", 3.02e5),
         ("水手峡谷海三段水面", area["marineris"], "water", "广东省", 1.797e5),
         ("海拉斯海（−7,000 m）", area["hellas"], "water", "福建省", 1.24e5),
         ("厄俄斯湖", eos, "water", "海南岛", 3.39e4)]
def wan(v): return f"{v/1e8:.2f} 亿 km²" if v >= 1e8 else f"{v/1e4:,.0f} 万 km²" if v >= 1e5 else f"{v/1e4:,.1f} 万 km²"
BW = 250
for i, (mn, mv, kind, en, ev) in enumerate(pairs):
    yy = Y4 + 36 + i*44
    mx_ = max(mv, ev)
    col = "rgb(165,199,228)" if kind == "water" else "rgb(226,210,186)"
    S.text("面积", X4, yy, mn, 9.4, "cjk")
    S.add("面积", f'<rect x="{X4}" y="{yy+6}" width="{BW*mv/mx_:.1f}" height="9" fill="{col}"/>')
    S.text("面积", X4 + BW + 10, yy+14.5, wan(mv), 8.8, "cjk")
    S.text("面积", X4 + 400, yy+14.5, "≈", 12, "lat", fill=C["ink2"], anchor="middle")
    ex = X4 + 440
    S.text("面积", ex, yy, en, 9.4, "cjk", fill=EARTH)
    S.add("面积", f'<rect x="{ex}" y="{yy+6}" width="{BW*ev/mx_:.1f}" height="9" fill="rgba(179,38,30,0.35)"/>')
    S.text("面积", ex + BW + 10, yy+14.5, wan(ev), 8.8, "cjk", fill=EARTH)
S.text("面积", X4, Y4 + 36 + len(pairs)*44 - 6, "每行两根条按同一尺度画；火星蓝色为水面、黄色为陆地，红色为地球对照物。奥林匹斯山山体按 IAU 基底直径 610 km 的圆算。",
       7.8, "cjk", fill=C["ink3"])

# ════ ⑤ 高度 ⑥ 深度 ═══════════════════════════════════════════════
print("⑤⑥ 剖面 …")
Y5 = 1262.0
KX = 1.2                                             # km / 屏幕单位（水平，⑤⑥共用）
VE = 10.0
KY = KX/VE
LAND_FILL, EARTH_FILL = "rgb(226,210,186)", "rgba(179,38,30,0.18)"
def mars_profile(lat0, lon0, lat1, lon1, n=1500):
    la = np.linspace(lat0, lat1, n); lo = np.linspace(lon0, lon1, n)
    s = np.r_[0, np.cumsum(M.hav_km(la[:-1], lo[:-1], la[1:], lo[1:]))]
    return s, M.sample_lonlat(D, 32, lo, la, order=1).astype(float)
def km_axis(x, y_zero, km_max, step, down=False, label="km"):
    for km in range(0, km_max + 1, step):
        y = y_zero + (km if down else -km)/KY
        S.add("剖面", f'<line x1="{x-4}" y1="{y:.1f}" x2="{x}" y2="{y:.1f}" stroke="{C["ink"]}" stroke-width="0.6"/>')
        S.text("剖面", x-7, y+3, f"{km}", 7.4, "lat", anchor="end")
    y_end = y_zero + (km_max if down else -km_max)/KY
    S.add("剖面", f'<line x1="{x}" y1="{y_zero}" x2="{x}" y2="{y_end:.1f}" stroke="{C["ink"]}" stroke-width="0.6"/>')
    S.text("剖面", x, (y_zero - 8) if down else (y_end - 8), label, 7.4, "cjk", anchor="middle")

# ⑤ 奥林匹斯山：沿峰顶纬线东西向实测
pk = PEAKS["Olympus Mons"]; plat, plon = float(pk["峰顶纬度"]), float(pk["峰顶东经"])
sO, zO = mars_profile(plat, plon - 6.6, plat, plon + 6.6)
base = float(np.percentile(zO[:40], 50))
X5 = 124.0
BASE5 = Y5 + 44 + 25/KY
xs = X5 + sO/KX; ys = BASE5 - (zO - base)/1e3/KY
EX0 = xs[-1] + 44
REF_END = EX0 + 310
S.add("剖面", f'<line x1="{X5-20}" y1="{BASE5}" x2="{REF_END:.1f}" y2="{BASE5}" stroke="{C["ink3"]}" stroke-width="0.5"/>')
REFS = ((10.5, "客机巡航 10.5 km", C["ink2"]), (5*1.609344, "火星呼吸线 8,047 m", "#7B3F98"))
for h_km, lab, colr in REFS:
    y = BASE5 - h_km/KY
    S.add("剖面", f'<line x1="{X5}" y1="{y:.1f}" x2="{REF_END:.1f}" y2="{y:.1f}" stroke="{colr}" stroke-width="0.5" stroke-dasharray="3 2.5"/>')
S.add("剖面", f'<path d="{M.path_d(xs, ys)} L{xs[-1]:.1f},{BASE5} L{xs[0]:.1f},{BASE5} Z" fill="{LAND_FILL}" stroke="{C["ink"]}" stroke-width="0.8"/>')
top_i = int(np.argmax(zO)); rel_O = (zO.max() - base)/1e3
S.text("剖面", xs[top_i], ys[top_i]-24, f"奥林匹斯山　比西侧平原高 {rel_O:.1f} km", 9.6, "cjk_b", anchor="middle", weight="bold", halo=2.4)
S.text("剖面", xs[top_i], ys[top_i]-10, f"峰顶 {zO.max():,.0f} m（火星基准面起算）", 8.2, "cjk", anchor="middle", fill=C["ink2"], halo=2.2)
def earth_peak(x, h_km, half_w_km, name, sub):
    xx = np.linspace(-half_w_km, half_w_km, 60)
    yy = h_km*np.clip(1 - np.abs(xx)/half_w_km, 0, 1)**1.5
    px, py = x + xx/KX, BASE5 - yy/KY
    S.add("剖面", f'<path d="{M.path_d(px, py)} Z" fill="{EARTH_FILL}" stroke="{EARTH}" stroke-width="0.9"/>')
    S.text("剖面", x, BASE5 - h_km/KY - 8, name, 9.2, "cjk_b", anchor="middle", fill=EARTH, weight="bold", halo=2.2)
    S.text("剖面", x, BASE5 + 13, sub, 7.8, "cjk", anchor="middle", fill=EARTH)
earth_peak(EX0 + 36, 8.849, 30, "珠穆朗玛峰", "海拔 8,849 m")
earth_peak(EX0 + 140, 10.21, 55, "冒纳凯阿", "从海底算 10,210 m")
for h_km, lab, colr in REFS:
    S.text("剖面", REF_END, BASE5 - h_km/KY - 4, lab, 7.8, "cjk", fill=colr, halo=2, anchor="end")
km_axis(X5-14, BASE5, 25, 5)
y11 = BASE5 + 40
S.text("剖面", X5, y11, "同一座山，不做垂直夸大（1:1）：", 8.8, "cjk_b", weight="bold")
ys1 = y11 + 26 - (zO - base)/1e3/KX
S.add("剖面", f'<path d="{M.path_d(xs, ys1)} L{xs[-1]:.1f},{y11+26} L{xs[0]:.1f},{y11+26} Z" fill="{LAND_FILL}" stroke="{C["ink"]}" stroke-width="0.6"/>')
flank = math.degrees(math.atan(rel_O/(sO[-1]/2)))
S.text("剖面", X5, y11 + 44, f"山体宽约 {float(pk['基底直径_km']):,.0f} km、平均坡度约 {flank:.0f}°：站在山坡上，看不出自己在一座 {rel_O:.0f} km 高的山上。", 8.4, "cjk", fill=C["ink2"])
panel_title(84, Y5 - 6, "5", "高度", f"同一比例尺，垂直夸大 {VE:.0f} 倍（下附 1:1）。奥林匹斯山沿 {plat:.1f}°N 实测，地球山体为示意轮廓")

# ⑥ 水手峡谷：沿 300°E 南北向横切科普来特斯峡谷
X6 = 1190.0
sV, zV = mars_profile(-9.0, 300.0, -18.0, 300.0)
rim = float(zV.max())
TOP6 = Y5 + 70
xs6 = X6 + sV/KX; ys6 = TOP6 + (rim - zV)/1e3/KY
bottom6 = TOP6 + 11/KY
lv = WL["marineris_mid"]
S.add("剖面", f'<path d="{M.path_d(xs6, ys6)} L{xs6[-1]:.1f},{bottom6:.1f} L{xs6[0]:.1f},{bottom6:.1f} Z" fill="{LAND_FILL}" stroke="{C["ink"]}" stroke-width="0.8"/>')
wet = ndimage.binary_opening(zV < lv, np.ones(3, bool))
for sl in ndimage.find_objects(ndimage.label(wet)[0]):
    i0, i1 = sl[0].start, sl[0].stop - 1
    yw = TOP6 + (rim - lv)/1e3/KY
    S.add("剖面", f'<path d="M{xs6[i0]:.1f},{yw:.1f} L{xs6[i1]:.1f},{yw:.1f} {M.path_d(xs6[i0:i1+1][::-1], ys6[i0:i1+1][::-1]).replace("M", "L", 1)} Z" '
                  f'fill="rgb(190,218,238)" stroke="{C["coast"]}" stroke-width="0.6"/>')
depth_V = (rim - zV.min())/1e3
S.text("剖面", xs6[len(xs6)//2], bottom6 + 18, f"科普来特斯峡谷（沿 300°E 横切 {sV[-1]:,.0f} km）　崖顶到谷底 {depth_V:.1f} km", 9.6, "cjk_b", anchor="middle", weight="bold")
S.text("剖面", xs6[len(xs6)//2], bottom6 + 32, "谷底蓝色为 2100 年的水手峡谷海（−3,800 m）", 8.2, "cjk", anchor="middle", fill=C["ink2"])
def earth_gorge(x, depth_km, top_w_km, name, sub):
    xx = np.linspace(-top_w_km/2, top_w_km/2, 40)
    yy = depth_km*(1 - (np.abs(xx)/(top_w_km/2))**1.4)
    px, py = x + xx/KX, TOP6 + yy/KY
    notch = " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py))
    S.add("剖面", f'<path d="M{px[0]-22:.1f},{TOP6} L{notch} L{px[-1]+22:.1f},{TOP6} L{px[-1]+22:.1f},{bottom6:.1f} L{px[0]-22:.1f},{bottom6:.1f} Z" '
                  f'fill="{EARTH_FILL}" stroke="{EARTH}" stroke-width="0.9"/>')
    S.text("剖面", x, bottom6 + 18, name, 9.2, "cjk_b", anchor="middle", fill=EARTH, weight="bold")
    S.text("剖面", x, bottom6 + 32, sub, 7.8, "cjk", anchor="middle", fill=EARTH)
GX = xs6[-1] + 50
earth_gorge(GX, 6.009, 18, "雅鲁藏布", "最深 6,009 m")
earth_gorge(GX + 70, 1.857, 16, "科罗拉多", "深 1,857 m")
km_axis(X6-14, TOP6, 10, 2, down=True, label="深 km")
panel_title(X6 - 30, Y5 - 6, "6", "深度", f"同一比例尺，垂直夸大 {VE:.0f} 倍，以崖顶对齐")
M.scale_bar(S, "剖面", X6, bottom6 + 66, 1/KX, 100, 3, size=6.8, h=3.5)
S.text("剖面", X6 + 300/KX + 44, bottom6 + 73, "水平比例尺（⑤⑥共用）", 8, "cjk", fill=C["ink2"])

# ════ ⑦ 距离与身体感受 ═══════════════════════════════════════════════
Y7 = 1664.0
panel_title(84, Y7 - 6, "7", "在火星上走一走", "距离按本系列地图坐标量算；地球对照为城市间大圆距离")
rail = 0.0
for ft in INFRA:
    if ft["geometry"]["type"] == "LineString" and ft["properties"]["kind"] in ("干线", "桥"):
        c_ = np.array(ft["geometry"]["coordinates"])
        rail += float(M.hav_km(c_[:-1, 1], c_[:-1, 0], c_[1:, 1], c_[1:, 0]).sum())
items = [(f"新上海 → 罗宾逊城 {mkm('new_shanghai', 'robinson'):,.0f} km", f"≈ {like(mkm('new_shanghai', 'robinson'))}（两国首府）"),
         (f"海源城 → 罗宾逊城 {mkm('haiyuan', 'robinson'):,.0f} km", f"≈ {like(mkm('haiyuan', 'robinson'))}"),
         (f"新上海 → 洛厄尔港 {mkm('new_shanghai', 'port_lowell'):,.0f} km", f"≈ {like(mkm('new_shanghai', 'port_lowell'))}"),
         (f"新上海 → 尼克斯奥林匹卡 {mkm('new_shanghai', 'nix_olympica'):,.0f} km", f"≈ {like(mkm('new_shanghai', 'nix_olympica'))}"),
         (f"赤道铁路已通车 {rail:,.0f} km", "≈ 京广高铁（2,298 km）的 9.6 倍，火星赤道一整圈"),
         ("火星 1 角分 ≈ 0.99 km", "地图上差 1′ 就差 1 km；地球上 1′ 是 1.85 km（1 海里）"),
         ("0.38 g", "地球上 30 kg 的背包在火星只压肩 11 kg；同样蹬地能跳 2.6 倍高"),
         ("站着看地平线 3.4 km", "地球是 4.7 km：同样的开阔地，人和车会更早沉到地平线下")]
for i, (a_, b_) in enumerate(items):
    col, row = i % 2, i // 2
    x = 84 + col*860; y = Y7 + 28 + row*36
    S.text("距离", x, y, a_, 10, "cjk_b", weight="bold")
    S.text("距离", x, y+15, b_, 8.8, "cjk", fill=EARTH if "≈" in b_ else C["ink2"])

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", 84, 52, "火星有多大", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", 84 + text_width("火星有多大", 30, "cjk_b", 3) + 18, 52, "尺度对比图 · 与地球同一比例尺", 14, "cjk", fill=C["ink2"])
S.text("图名", 84, 72, "HOW BIG IS MARS  ·  SCALE COMPARISONS WITH EARTH  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
S.text("图名", SW-84, 46, "①③ 兰伯特等积方位投影　② 正射投影　⑤⑥ 剖面，垂直夸大 10 倍", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", SW-84, 60, "红色 = 地球对照物；火星为真实地形，水面为 2100 年 3 月推算值", 8.2, "cjk", fill=EARTH, anchor="end")
S.text("出处", 84, SH-20, "火星：MGS MOLA 数字高程模型（NASA GSFC · USGS Astrogeology），陆地色调 MGS TES 反照率；城镇位置见《火星坐标对照表》；2100 年环境数据：GURPS Transhuman Space《In The Well》。"
       "地球：Natural Earth 陆地与国界（中国视角版）；珠峰、冒纳凯阿、雅鲁藏布大峡谷、科罗拉多大峡谷为公认数值，剖面形状为示意。", 7.0, "cjk", fill=C["ink3"])

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
