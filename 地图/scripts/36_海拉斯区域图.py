#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海拉斯区域图（2100 年 3 月）—— 以盆地为中心的兰伯特等积方位投影，画到盆地外缘。
在白底晕渲之上加：
  · 1,000 m 等高线（偶数千米加粗并注记），水下 −8,000 m 等深线
  · 现在的海拉斯海（−7,000 m）与两条预测岸线（−6,000 m、−5,000 m）——正典：海拉斯正在被四周排下来的水填满，
    22 世纪某个时候会成为自给自足的海洋（ITW p.25）
  · 按地形推算的径流水道与海拉斯集水区界——正典：全火星 15% 以上的地面是海拉斯的「上游」（ITW p.25）
  · 绕开海拉斯海的时区界——正典：海拉斯海整个划在叙尔蒂斯时区（ITW p.33）
  · 海拉斯铁路支线（正典只说「有支线通往海拉斯」，走向为推定）

数据：DEM 原始 463 m 高程（晕渲、等高线）、DEM/dem_32ppd_avg.npy（水文）、产出/三海掩膜.npz、数据/火星地点.csv、
      产出/基础设施_2100.geojson、数据/IAU
产出：产出/海拉斯区域图_2100.svg（除晕渲外全矢量）  产出/海拉斯区域图_2100.png（3 倍，印刷用）
运行：./.venv/bin/python scripts/36_海拉斯区域图.py
"""
import math, subprocess, sys
import numpy as np
from scipy import ndimage
from affine import Affine
from shapely.geometry import LineString
from skimage.morphology import reconstruction
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Azimuthal, Identity, text_width

NAME = "海拉斯区域图_2100"
LAT_C, LON_C, SCALE = -39.0, 70.0, 0.40                # 图幅中心；屏幕单位/千米
X0, Y0, W, H = 76.0, 118.0, 1400.0, 1000.0
SS = 3                                                 # 底图超采样倍数
P = Azimuthal(LAT_C, LON_C, X0 + W/2, Y0 + H/2, SCALE)
LX = int(X0 + W + 58); SW, SH = 1848, int(Y0 + H + 62)
S = SVG(SW, SH, "海拉斯区域图 · 2100 年 3 月")
S.layer("底图"); S.layer("土地利用")
clip = 'clip-path="url(#clipMap)"'
CONTOUR_STEP, INDEX_STEP = 1000, 2000
FUTURE = [-6000, -5000]                                # 预测岸线
FUTURE_C = "#2F6FB0"
RIVER_C = "#4F7FA8"
TZ_C = "#8A5A2B"

Z = M.load_masks()
LV = int(Z["level_hellas"])
PLACES = {r["id"]: r for r in M.load_places()}
INFRA = M.load_infra()
IAU = M.load_iau()
def iau(n): return float(IAU[n]["center_lat"]), float(IAU[n]["center_lon"]) % 360

# ── 图框覆盖的经纬范围 ───────────────────────────────────────────────
t = np.linspace(0, 1, 200)
ex = np.r_[X0 + t*W, np.full(200, X0+W), X0 + (1-t)*W, np.full(200, X0)]
ey = np.r_[np.full(200, Y0), Y0 + t*H, np.full(200, Y0+H), Y0 + (1-t)*H]
elon, elat, _ = P.inverse(ex, ey)
LON0W, LON1W = math.floor(elon.min()) - 1, math.ceil(elon.max()) + 1
LAT0W, LAT1W = math.ceil(elat.max()) + 1, math.floor(elat.min()) - 1
print(f"图框范围 {LON0W}–{LON1W}°E × {LAT1W}…{LAT0W}°")

# ── 底图：463 m DEM 重采样到 64 px/度，再逆投影到屏幕网格 ───────────────
print("读 DEM、晕渲 …")
d64 = M.read_dem_window(LON0W, LON1W, LAT0W, LAT1W, 64)
n_w, n_h = int(W*SS), int(H*SS)
ys, xs = np.mgrid[0:n_h, 0:n_w]
lon, lat, ok = P.inverse(X0 + (xs+0.5)/SS, Y0 + (ys+0.5)/SS)
del xs, ys
dem_hr = M.sample_window(d64, 64, LON0W, LAT0W, lon, lat, order=1).astype(np.float32)

# ── 水文：16 px/度，窗口 0–140°E × 5°S–南极 ──────────────────────────────
print("水文：填洼、流向、汇流 …")
HP = 16
HLON0, HLON1, HLAT0 = 0, 140, -5
D32 = M.load_dem32_avg()
cell32 = (M.KMPD/32)**2*np.cos(np.radians(90-(np.arange(5760)+0.5)/32))[:, None]
sea32 = Z["hellas"]
sea_area = float((cell32*sea32).sum())
vol = float((cell32*np.clip(LV - D32, 0, None)*sea32).sum())/1e3          # km³
sea_max_depth = float(LV - D32[sea32].min()); basin_min = float(D32[sea32].min())
cc_ = np.nonzero(sea32.any(axis=0))[0]; ext_km = float((cc_.max()-cc_.min()+1)/32*M.KMPD*math.cos(math.radians(-35)))
d16 = D32.reshape(2880, 2, 5760, 2).mean(axis=(1, 3))
del D32
hr0, hc0, hc1 = int((90-HLAT0)*HP), int((HLON0+180)*HP), int((HLON1+180)*HP)
demw = d16[hr0:, hc0:hc1].astype(np.float64)
del d16
seaw = Z["hellas"].reshape(2880, 2, 5760, 2).any(axis=(1, 3))[hr0:, hc0:hc1]
HH, HW = demw.shape
h_lat = HLAT0 - (np.arange(HH)+0.5)/HP
h_cell = (M.KMPD/HP)**2*np.cos(np.radians(h_lat))[:, None]*np.ones((1, HW))  # km²
MARS_AREA = 4*math.pi*(M.R/1e3)**2

# 预测岸线：从海拉斯海最低点连通填充
seed = np.unravel_index(np.argmin(demw), demw.shape)
fut = {}
for L in FUTURE:
    lab, _ = ndimage.label(demw < L)
    fut[L] = lab == lab[seed]
fut_area = {L: float((h_cell*fut[L]).sum()) for L in FUTURE}

# 填洼：出口 = 现在的海 + 窗口上、左、右边（流出窗口的水不归海拉斯）；下边是南极，不当出口
outlet = seaw.copy()
outlet[0, :] = True; outlet[:, 0] = True; outlet[:, -1] = True
filled = reconstruction(np.where(outlet, demw, demw.max() + 1.0), demw, method="erosion")

NB = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
dy_km = M.KMPD/HP; dx_km = dy_km*np.maximum(np.cos(np.radians(h_lat)), 0.02)[:, None]
pad = np.pad(filled, 1, mode="edge")
best = np.full(filled.shape, -1, np.int8); bestdrop = np.zeros(filled.shape)
for k, (di, dj) in enumerate(NB):
    nb = pad[1+di:1+di+HH, 1+dj:1+dj+HW]
    dist = dy_km if dj == 0 else (dx_km if di == 0 else np.hypot(dx_km, dy_km))
    drop = (filled - nb)/dist
    better = drop > bestdrop
    best[better] = k; bestdrop[better] = drop[better]
best[outlet] = -1
resolved = (best >= 0) | outlet
for it in range(400):                                    # 平地（填平的湖面）：向已有流向的同高邻元靠
    un = ~resolved
    if not un.any(): break
    pres = np.pad(resolved, 1, mode="constant")
    changed = False
    for k, (di, dj) in enumerate(NB):
        cand = un & (pad[1+di:1+di+HH, 1+dj:1+dj+HW] == filled) & pres[1+di:1+di+HH, 1+dj:1+dj+HW]
        if cand.any():
            best[cand] = k; un &= ~cand; changed = True
    resolved = (best >= 0) | outlet
    if not changed: break
idx = np.arange(filled.size).reshape(filled.shape)
down = idx.copy()
for k, (di, dj) in enumerate(NB):
    r, c = np.nonzero(best == k)
    down[r, c] = idx[np.clip(r+di, 0, HH-1), np.clip(c+dj, 0, HW-1)]
down = down.ravel()
term = down.copy()
for _ in range(24): term = term[term]                     # 指针跳跃 → 每个格的终点汇
catch = seaw.ravel()[term].reshape(filled.shape)
catch_area = float((h_cell*catch).sum())
touch = catch[0, :].any() or catch[:, 0].any() or catch[:, -1].any()
print(f"  海拉斯集水区 {catch_area/1e4:,.0f} 万 km² = 全火星 {catch_area/MARS_AREA:.1%}（正典：15% 以上）"
      + ("  ⚠ 集水区碰到窗口边，窗口该再放大" if touch else ""))
# 汇流（拓扑序：入度为 0 的先算）
N = down.size
acc = h_cell.ravel().copy()                                # 以面积计
indeg = np.bincount(down, minlength=N); selfloop = down == np.arange(N); indeg[selfloop] -= 1
frontier = np.nonzero(indeg == 0)[0]
while frontier.size:
    m = ~selfloop[frontier]
    src, tgt = frontier[m], down[frontier[m]]
    np.add.at(acc, tgt, acc[src])
    np.subtract.at(indeg, tgt, 1)
    frontier = np.unique(tgt[indeg[tgt] == 0])
acc = acc.reshape(filled.shape)
del pad, bestdrop, resolved, idx

# ── 底图着色 ────────────────────────────────────────────────────────
def to_screen(mask, level):
    m = M.sample_window(mask.astype(np.uint8), HP, HLON0, HLAT0, lon, lat, order=0).astype(bool)
    return ndimage.binary_dilation(m, np.ones((7, 7), bool)) & (dem_hr < level) & ok
sea = to_screen(seaw, LV)
futs = {L: to_screen(fut[L], L) for L in FUTURE}
px_m = 1000/(SCALE*SS)
rgb = M.colorize(dem_hr, M.shade(dem_hr, px_m, px_m, zfac=3.0), [sea], [LV], albedo=M.albedo_at(lon, lat))
rgb[~ok] = 255
S.add("底图", f'<clipPath id="clipMap"><rect x="{X0}" y="{Y0}" width="{W}" height="{H}"/></clipPath>')
S.add("底图", f'<image x="{X0}" y="{Y0}" width="{W}" height="{H}" preserveAspectRatio="none" href="{M.png_data_uri(rgb, quality=90)}"/>')
del rgb
TF = Affine(1/SS, 0, X0, 0, 1/SS, Y0)
def _lu_inside(lo, la):
    x_, y_ = P.xy(lo, la); return X0 <= x_ <= X0 + W and Y0 <= y_ <= Y0 + H
print("  土地利用", M.landuse_svg(S, "土地利用", P, "clipMap", _lu_inside, classes=("草场",)), "块")

# ── 等高线（屏幕网格 1 单位 = 2.5 km）────────────────────────────────
print("等高线 …")
ys1, xs1 = np.mgrid[0:int(H), 0:int(W)]
lon1, lat1, _ = P.inverse(X0 + xs1 + 0.5, Y0 + ys1 + 0.5)
dem1 = M.sample_window(d64, 64, LON0W, LAT0W, lon1, lat1, order=1)
del xs1, ys1, lon1, lat1, d64
sm = ndimage.gaussian_filter(dem1.astype(np.float64), 1.2)
to_xy = lambda rr, cc: (X0 + cc + 0.5, Y0 + rr + 0.5)
index_lines, normal, bold, bathy = {}, [], [], []
for lv in range(-8000, 5000, CONTOUR_STEP):
    if lv in FUTURE: continue                                          # 这两条改画成预测岸线
    lines = M.contour_lines(sm, lv, to_xy, sigma=0, min_len=14, tol=0.4)
    if lv < LV: bathy.extend(M.path_d(p[:, 0], p[:, 1]) for p in lines); continue
    (bold if lv % INDEX_STEP == 0 else normal).extend(M.path_d(p[:, 0], p[:, 1]) for p in lines)
    if lv % INDEX_STEP == 0: index_lines[lv] = lines
S.add("等高线", f'<path d="{" ".join(normal)}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.3" opacity="0.5" {clip}/>')
S.add("等高线", f'<path d="{" ".join(bold)}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.6" opacity="0.7" {clip}/>')
S.add("等高线", f'<path d="{" ".join(bathy)}" fill="none" stroke="{C["coast"]}" stroke-width="0.4" opacity="0.6" {clip}/>')

# ── 水系：径流水道、集水区界、预测岸线、海岸线 ───────────────────────────
print("水系 …")
def h_ll(i):
    r, c = divmod(np.asarray(i), HW)
    return HLON0 + (c+0.5)/HP, HLAT0 - (r+0.5)/HP
CLASSES = [(2e4, 0.4), (1e5, 0.7), (4e5, 1.0)]                      # 集水面积 km² → 线宽
is_ch = catch & (acc >= CLASSES[0][0]) & ~seaw
ch_idx = np.nonzero(is_ch.ravel())[0]
has_up = np.zeros(N, bool); has_up[down[ch_idx]] = True
cls_of = np.zeros(N, np.int8)
for i, (thr, _) in enumerate(CLASSES): cls_of[acc.ravel() >= thr] = i + 1
visited = np.zeros(N, bool)
river_paths = {i: [] for i in range(len(CLASSES))}
for head in ch_idx[~has_up[ch_idx]]:
    i = head; run = [i]; c = cls_of[i]
    while True:
        j = down[i]
        if j == i or seaw.ravel()[j]:
            run.append(j); break
        run.append(j)
        if visited[j] or cls_of[j] != c or not is_ch.ravel()[j]:
            break
        visited[j] = True; i = j
        if cls_of[j] != c: break
    if len(run) < 3: continue
    lo_, la_ = h_ll(np.array(run)); x, y = P.xy(lo_, la_)
    pts = np.column_stack([x, y])
    for _ in range(2):                                                 # Chaikin 平滑
        p_, q_ = pts[:-1], pts[1:]
        pts = np.vstack([pts[:1], np.column_stack([0.75*p_+0.25*q_, 0.25*p_+0.75*q_]).reshape(-1, 2), pts[-1:]])
    pts = np.asarray(LineString(pts).simplify(0.35).coords)
    river_paths[c-1].append(M.path_d(pts[:, 0], pts[:, 1]))
for i, (thr, wdt) in enumerate(CLASSES):
    if river_paths[i]:
        S.add("水系", f'<path d="{" ".join(river_paths[i])}" fill="none" stroke="{RIVER_C}" stroke-width="{wdt}" stroke-linecap="round" stroke-linejoin="round" opacity="0.85" {clip}/>')
print(f"  水道 {sum(len(v) for v in river_paths.values())} 段")
# 集水区界
catch_rings = M.mask_rings(catch, HP, lon_left=HLON0, lat_top=HLAT0, min_px=300, simplify=0.04, smooth=2)
S.add("水系", f'<path d="{M.rings_to_path(catch_rings, P)}" fill="none" stroke="{C["ink"]}" stroke-width="0.9" stroke-dasharray="6 2 1.2 2" opacity="0.8" {clip}/>')
# 预测岸线
fut_lines = {}
for L in FUTURE:
    rings = M.mask_rings(futs[L], SS, min_px=200, simplify=0.3, smooth=2, transform=TF)
    area2 = lambda h: abs(float((h[:-1, 0]*h[1:, 1] - h[1:, 0]*h[:-1, 1]).sum()))/2       # 鞋带公式
    rings = [(e, [h for h in hs_ if area2(h) > 2500]) for e, hs_ in rings]                # 小岛不画
    S.add("水系", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{FUTURE_C}" stroke-width="0.7" stroke-dasharray="4 2.5" {clip}/>')
    fut_lines[L] = [np.vstack([e, e[:1]]) for e, _ in rings]
# 海岸线
rings = M.mask_rings(sea, SS, min_px=30, simplify=0.25, smooth=2, transform=TF)
S.add("海岸线", f'<path d="{M.rings_to_path(rings, Identity())}" fill="none" stroke="{C["coast"]}" stroke-width="0.8" stroke-linejoin="round" {clip}/>')
del dem_hr, sea

# ── 时区界（正典：60°E = 300°W 是叙尔蒂斯 / 阿拉伯时区界，海拉斯海整个划入叙尔蒂斯时区）──
def ll_path(pts, n=60):
    la = np.concatenate([np.linspace(a[0], b[0], n) for a, b in zip(pts[:-1], pts[1:])])
    lo = np.concatenate([np.linspace(a[1], b[1], n) for a, b in zip(pts[:-1], pts[1:])])
    return P.xy(lo, la)
tzx, tzy = ll_path([(-5, 60), (-27, 60), (-29, 49.5), (-41.5, 49.5), (-43, 60), (-80, 60)])
S.add("时区", f'<path d="{M.path_d(tzx, tzy)}" fill="none" stroke="{TZ_C}" stroke-width="0.9" stroke-dasharray="7 2.5 1.5 2.5" opacity="0.85" {clip}/>')

# ── 经纬网、铁路 ──────────────────────────────────────────────────────
M.graticule_frame(S, P, X0, Y0, W, H, step=10, tick_step=2)
placer = Placer((X0+2, Y0+2, X0+W-2, Y0+H-2))
def in_frame(x, y, pad=0): return X0+pad <= x <= X0+W-pad and Y0+pad <= y <= Y0+H-pad
for ft in INFRA:
    if ft["geometry"]["type"] != "LineString": continue
    for seg in M.split_line(ft["geometry"]["coordinates"], P):
        xy = [tuple(map(float, P.xy(lo_, la_))) for lo_, la_ in seg]
        if not any(in_frame(x, y, -20) for x, y in xy): continue
        S.add("铁路", f'<g {clip}>' + M.rail_svg(xy, ft["properties"]["kind"]) + "</g>")
for ft in INFRA:
    if ft["properties"]["kind"] != "车站": continue
    lo_, la_ = ft["geometry"]["coordinates"]; x, y = map(float, P.xy(lo_ % 360, la_))
    if not in_frame(x, y): continue
    S.add("铁路", f'<rect x="{x-2.2:.1f}" y="{y-2.2:.1f}" width="4.4" height="4.4" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')
    placer.block(x-3.5, y-3.5, x+3.5, y+3.5)

# ── 符号与注记 ──────────────────────────────────────────────────────
WATER_FILL, TERR_FILL = C["water_label"], "#707070"
def area_label(zh, en, lo_, la_, zs, es, fill, spacing=2.2, rotate=0, italic_zh=False, tries=((0, 0),)):
    x, y = map(float, P.xy(lo_, la_))
    wz = text_width(zh, zs, "cjk", spacing); we = text_width(en, es, "lat_i", 0.9) if en else 0; w = max(wz, we)
    hgt = zs + (es*1.6 if en else 2)
    for dx, dy in tries:
        box = (x+dx-w/2-2, y+dy-zs, x+dx+w/2+2, y+dy+hgt-zs)
        if rotate or placer.free(box):
            tf = f' transform="rotate({rotate:.1f} {x+dx:.1f} {y+dy:.1f})"' if rotate else ""
            S.add("地貌注记", f"<g{tf}>")
            S.text("地貌注记", x+dx, y+dy, zh, zs, "cjk", fill=fill, anchor="middle", spacing=spacing, halo=2.4, italic=italic_zh)
            if en: S.text("地貌注记", x+dx, y+dy+es*1.35, en, es, "lat_i", fill=fill, anchor="middle", spacing=0.9, halo=2, italic=True)
            S.add("地貌注记", "</g>")
            ext = abs(math.sin(math.radians(rotate)))*w/2
            placer.block(x+dx-w/2*abs(math.cos(math.radians(rotate)))-2, y+dy-zs-ext, x+dx+w/2*abs(math.cos(math.radians(rotate)))+2, y+dy+hgt-zs+ext)
            return True
    print("   注记没放下：", zh); return False

TRIES = ((0, 0), (0, -10), (0, 10), (-16, 0), (16, 0), (0, -20), (0, 20))
area_label("海拉斯海", f"HELLAS SEA · {M.fmt_m(LV)} m", 60.5, -35.4, 15, 7.5, WATER_FILL, 4)
# 海底地貌：蓝色斜体
for zh, en, la_, lo_ in (("阿尔费奥斯丘陵", "ALPHEUS COLLES", -39.4, 61.5), ("佩纽斯沼", "PENEUS PALUS", -33.5, 55.0)):
    area_label(zh, en, lo_, la_, 7.8, 5.6, WATER_FILL, 1.2, italic_zh=True, tries=TRIES)
BIG = [("海拉斯平原", "HELLAS PLANITIA", -44.5, 76.0, 12, 0), ("普罗米修斯高地", "PROMETHEI TERRA", -52.0, 99.0, 10, 0),
       ("诺亚高地", "NOACHIS TERRA", -40.0, 39.0, 10, 0), ("萨巴高地", "TERRA SABAEA", -21.0, 52.0, 10, 0),
       ("第勒尼安高地", "TYRRHENA TERRA", -20.0, 88.0, 10, 0), ("马利亚高原", "MALEA PLANUM", -59.0, 66.5, 10, 0),
       ("赫斯珀里亚高原", "HESPERIA PLANUM", -31.5, 101.5, 9, 0), ("赫勒斯滂山脉", "HELLESPONTUS MONTES", -44.4, 42.8, 9.2, 75)]
for zh, en, la_, lo_, zs, rot in BIG:
    area_label(zh, en, lo_, la_, zs, 6.2, TERR_FILL, 3, rotate=rot, tries=TRIES)
SMALL = [("海拉斯混沌地", "HELLAS CHAOS", "Hellas Chaos"), ("科罗奈崖", "CORONAE SCOPULUS", "Coronae Scopulus"),
         ("科罗奈山脉", "CORONAE MONTES", "Coronae Montes"), ("海拉斯山脉", "HELLAS MONTES", "Hellas Montes"),
         ("半人马山脉", "CENTAURI MONTES", "Centauri Montes"), ("奥索尼亚山脉", "AUSONIA MONTES", "Ausonia Montes"),
         ("泽亚脊", "ZEA DORSA", "Zea Dorsa"), ("哈德里亚库斯沼", "HADRIACUS PALUS", "Hadriacus Palus"),
         ("道谷", "DAO VALLIS", "Dao Vallis"), ("尼日尔谷", "NIGER VALLIS", "Niger Vallis"),
         ("哈马基斯谷", "HARMAKHIS VALLIS", "Harmakhis Vallis"), ("雷乌尔谷", "REULL VALLIS", "Reull Vallis"),
         ("阿克西乌斯谷群", "AXIUS VALLES", "Axius Valles"), ("马德谷", "MAD VALLIS", "Mad Vallis"),
         ("松花谷", "SUNGARI VALLIS", "Sungari Vallis"), ("纳武阿谷群", "NAVUA VALLES", "Navua Valles"),
         ("泰尔比陨坑", "TERBY", "Terby"), ("塞基陨坑", "SECCHI", "Secchi"), ("华莱士陨坑", "WALLACE", "Wallace")]
for zh, en, key in SMALL:
    la_, lo_ = iau(key)
    x, y = map(float, P.xy(lo_, la_))
    if in_frame(x, y, 30): area_label(zh, en, lo_, la_, 8.2, 5.4, TERR_FILL, 1.6, tries=TRIES)
# 火山：峰顶符号 + 高程
PATERAE = [("哈德里亚库斯山", "Hadriacus Mons"), ("第勒尼安山", "Tyrrhenus Mons"), ("安菲特里忒火山", "Amphitrites Patera"),
           ("佩纽斯火山", "Peneus Patera"), ("马利亚火山", "Malea Patera"), ("欧里普斯山", "Euripus Mons")]
D32 = M.load_dem32_avg()
for zh, key in PATERAE:
    it = IAU[key]; la_, lo_ = iau(key); rad = max(float(it["diameter"])/2/M.KMPD, 0.4)
    r0, r1 = int((90-la_-rad)*32), int((90-la_+rad)*32); c0, c1 = int((lo_-rad+180)*32), int((lo_+rad+180)*32)
    win = D32[r0:r1, c0:c1]; i, j = np.unravel_index(np.argmax(win), win.shape)
    plo, pla, z = (c0+j+0.5)/32-180, 90-(r0+i+0.5)/32, float(win.max())
    x, y = map(float, P.xy(plo, pla))
    if not in_frame(x, y, 10): continue
    S.add("符号", M.peak_svg(x, y, 0.9)); placer.block(x-4, y-4, x+4, y+3)
    e = f"{z:,.0f} m"; w = max(text_width(zh, 8.2, "cjk"), text_width(e, 6.4, "lat"))
    got = placer.place(x, y, w, 17, gap=6)
    if got:
        S.text("地貌注记", got[0], got[1]+8, zh, 8.2, "cjk", halo=2.2)
        S.text("地貌注记", got[0], got[1]+16, e, 6.4, "lat", fill=C["ink2"], halo=2)
    else: print("   火山注记没放下：", zh)
del D32

# 城镇与聚落带
def place_town(r, x, y, br, extra=None, big=1.0):
    tier = r["等级"]; star = " ☆" if r["正典"] == "仅地图" else ""
    zs = {"1": 11.0, "2": 9.6, "3": 8.8}[tier]*big
    lines = [(r["中文名"].split("（")[0] + star, zs, "cjk_b" if tier == "1" else "cjk", C["ink"])]
    lines.append((r["英文名"], 6.8, "lat", C["ink2"]))
    if extra: lines.append((extra, 6.8, "cjk", C["ink2"]))
    w = max(text_width(t_, s_, k) for t_, s_, k, _ in lines); h = sum(s_*1.18 for _, s_, _, _ in lines)
    for g_extra in (2.5, 7, 14):
        got = placer.place(x, y, w, h, gap=br+g_extra)
        if got: break
    if not got: print("   城镇注记没放下：", r["中文名"]); return
    yy = got[1]
    for t_, s_, k, fl in lines:
        yy += s_*1.02
        S.text("城镇注记", got[0], yy, t_, s_, k, fill=fl, halo=2.3, weight="bold" if k == "cjk_b" else "normal")
        yy += s_*0.16
sym_pts = []
for r in PLACES.values():
    lo_, la_ = float(r["东经"]), float(r["纬度"]); x, y = map(float, P.xy(lo_, la_))
    if not in_frame(x, y, 6): continue
    sym_pts.append((x, y))
    if r["类别"] in ("城市", "城镇", "遗址", "军事"):
        rad = {"1": 3.4, "2": 2.9, "3": 2.4}[r["等级"]]
        S.add("符号", M.symbol(M.faction_kind(r["阵营"]), x, y, rad, major=r["等级"] == "1"))
        br = rad + 1; placer.block(x-br, y-br, x+br, y+br)
        place_town(r, x, y, br, extra=f"正典图上在海东岸 · 河口离水 {float(r['离水_km']):,.0f} km" if r["id"] == "dao_city" else None)
    elif r["id"] == "hellas_shore":
        place_town(r, x, y, 3.5, extra="支线终点 · 美、欧、南美人为主", big=1.05)

for x, y in sym_pts: placer.block(x-11, y-11, x+11, y+11)   # 计曲线数字离城镇符号远一点（注记已放完，只挡等高线数字）
# 预测岸线与计曲线注记
n1 = M.label_contours(S, placer, {L: fut_lines[L] for L in FUTURE}, size=6.8, every=520,
                      fmt=lambda L: f"{M.fmt_m(L)} m 岸线", color=FUTURE_C)
n2 = M.label_contours(S, placer, index_lines, every=380)
print(f"  注记：预测岸线 {n1} 处，计曲线 {n2} 处")
# 时区界注记
for la_, lo_, s_ in ((-16.5, 56.5, "← 阿拉伯时区（AT）　叙尔蒂斯时区（ST）→"), (-46.0, 55.5, "时区界绕开海拉斯海（正典）")):
    x, y = map(float, P.xy(lo_, la_))
    w = text_width(s_, 7.6, "cjk")
    for dy in (0, -12, 12, -24, 24):
        box = (x - w/2, y+dy-8, x + w/2, y+dy+2)
        if placer.free(box):
            placer.block(*box)
            S.text("时区", x, y+dy, s_, 7.6, "cjk", fill=TZ_C, anchor="middle", halo=2.2); break
    else: print("   时区注记没放下：", s_)
# 集水区界注记
xg, yg = map(float, P.xy(100.0, -30.0))
S.text("水系", xg, yg, "海拉斯集水区界", 7.8, "cjk", fill=C["ink"], anchor="middle", halo=2.2)

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", X0, 52, "海拉斯", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", X0 + text_width("海拉斯", 30, "cjk_b", 3) + 18, 52, "盆地地形与水系图 · 2100 年 3 月", 14, "cjk", fill=C["ink2"])
S.text("图名", X0, 72, "HELLAS BASIN  ·  TOPOGRAPHY AND HYDROGRAPHY  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
RX = SW - 48
S.text("图名", RX, 46, f"兰伯特等积方位投影 · 中心 {abs(LAT_C):g}°S {LON_C:g}°E  ·  火星 2000 参考球  R = 3,396.19 km", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 60, f"等高线间距 {CONTOUR_STEP:,} m，每 {INDEX_STEP:,} m 加粗；水道与集水区按 MOLA 地形推算", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", RX, 74, "海岸线测绘于 2100 年 3 月　海拉斯海仍在上涨，本图岸线逐年失效", 8.2, "cjk", fill=C["alert"], anchor="end")

# ── 右栏 ───────────────────────────────────────────────────────────
LY = Y0 + 8
S.text("图例", LX, LY, "图例", 11.5, "cjk_b", weight="bold")
items = [("other", "城镇（独立 / 混杂）"), ("station", "车站"), ("rail", "铁路支线"), ("peak", "火山（MOLA 峰顶）"),
         ("coast", "海岸线（−7,000 m）"), ("future", "预测岸线 −6,000 / −5,000 m"), ("river", "径流水道（按地形推算）"),
         ("divide", "海拉斯集水区界"), ("contour", "等高线 1,000 m"), ("index", "计曲线 2,000 m"),
         ("bathy", "等深线 1,000 m"), ("tz", "时区界（正典）"), ("veg", "草场 / 已绿化带（沿水推算）"), ("star", "☆ 仅见于正典地图")]
for i, (k, t_) in enumerate(items):
    col, row = i % 2, i // 2
    x = LX + col*150; y = LY + 24 + row*19
    if k == "other": S.add("图例", M.symbol("other", x+8, y-3.5, 2.6))
    elif k == "station": S.add("图例", f'<rect x="{x+5.8:.1f}" y="{y-5.7:.1f}" width="4.4" height="4.4" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')
    elif k == "rail": S.add("图例", M.rail_svg([(x-1, y-3.5), (x+19, y-3.5)], "支线"))
    elif k == "peak": S.add("图例", M.peak_svg(x+8, y-3.5, 0.9))
    elif k == "coast": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{C["coast"]}" stroke-width="0.9"/>')
    elif k == "future": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{FUTURE_C}" stroke-width="0.8" stroke-dasharray="4 2.5"/>')
    elif k == "river": S.add("图例", f'<path d="M{x},{y-2} q5,-5 9,-1 t9,-2" fill="none" stroke="{RIVER_C}" stroke-width="0.8"/>')
    elif k == "divide": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{C["ink"]}" stroke-width="0.9" stroke-dasharray="6 2 1.2 2"/>')
    elif k == "contour": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{M.CONTOUR}" stroke-width="0.35" opacity="0.7"/>')
    elif k == "index": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{M.CONTOUR}" stroke-width="0.7" opacity="0.8"/>')
    elif k == "bathy": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{C["coast"]}" stroke-width="0.45" opacity="0.7"/>')
    elif k == "tz": S.add("图例", f'<path d="M{x},{y-3.5} h18" stroke="{TZ_C}" stroke-width="0.9" stroke-dasharray="7 2.5 1.5 2.5"/>')
    elif k in ("crop", "veg", "aqua"): M.landuse_legend(S, "图例", x, y, {"crop": "农田", "veg": "草场", "aqua": "水产"}[k])
    S.text("图例", x+(25 if k != "star" else 0), y, t_, 8.4, "cjk")

yd = LY + 24 + 8*19 + 16
S.text("图例", LX, yd, "海拉斯海数据", 11.5, "cjk_b", weight="bold")
rows = [("水面高程", f"{M.fmt_m(LV)} m（火星最低处，坑底 {M.fmt_m(basin_min)} m）"),
        ("面积", f"{sea_area/1e4:,.1f} 万 km²  ≈ 福建省"),
        ("东西宽", f"{ext_km:,.0f} km ≈ {ext_km/1.609:,.0f} 英里（正典：只有几百英里）"),
        ("最深 / 平均", f"{sea_max_depth:,.0f} m / {vol*1e3/sea_area:,.0f} m"),
        ("水量", f"{vol/1e4:,.1f} 万 km³"),
        ("集水区", f"{catch_area/1e4:,.0f} 万 km² = 全火星 {catch_area/MARS_AREA:.0%}（正典：15% 以上）"),
        ("涨到 −6,000 m", f"{fut_area[-6000]/1e4:,.0f} 万 km²  ≈ 新疆（166 万）"),
        ("涨到 −5,000 m", f"{fut_area[-5000]/1e4:,.0f} 万 km²  ≈ 地中海的 80%")]
for i, (a_, b_) in enumerate(rows):
    yy = yd + 22 + i*16
    S.text("图例", LX, yy, a_, 8.6, "cjk", fill=C["ink2"])
    S.text("图例", LX + 78, yy, b_, 8.6, "cjk")

yh = yd + 22 + len(rows)*16 + 20
M.hypso_bar(S, "图例", LX, yh + 8, 270, -8000, 4000, 4000, "hyp", title="高程（m）")
ys_ = yh + 54
M.scale_bar(S, "图例", LX, ys_ + 12, SCALE, 250, 4, title=f"比例尺（图幅中心处）")
S.text("图例", LX, ys_ + 40, "等积投影：图内任何一块面积都可以直接比；图框四角方向略有变形。", 7.8, "cjk", fill=C["ink2"])

yn = ys_ + 66
S.text("图例", LX, yn, "注", 9.5, "cjk_b", weight="bold")
notes = ["· 正典：海拉斯是全火星最低点，正被四周排下来的水填满，22 世纪某个时候",
         "　会成为自给自足的海洋；现在「只有几百英里宽，不封冻时挤满冰山」。",
         "· 正典：环海有以美、欧、南美人为主的定居点；2078 年一名矿工在海边",
         "　的勘探坑里发现化石，此后古生物学家云集，人均科学家数量仅次于",
         "　尼克斯奥林匹卡。定居点没有名字和位置，本图只标聚落带。",
         "· 水道与集水区：把 MOLA 地形上的洼地填平后按最陡方向汇流算出，",
         "　表示降水会往哪里流，不代表常年有水。集水区界在图外的部分见索引图。",
         f"　真实地形上集水区占全火星 {catch_area/MARS_AREA:.0%}，正典说「15% 以上」，略有出入。",
         "· 时区界（正典）：60°E 是叙尔蒂斯时区与阿拉伯时区的界线，绕开海拉斯海",
         "　让整个海在叙尔蒂斯时区；绕行的具体走向为示意。",
         "· 道城：正典 p20 图画在海东岸；真实地形上道谷河口离 −7,000 m 的水面",
         f"　{float(PLACES['dao_city']['离水_km']):,.0f} km，但只比海面高 {float(PLACES['dao_city']['MOLA高程_m']) - LV:,.0f} m——海面涨到 "
         f"{M.fmt_m(float(PLACES['dao_city']['MOLA高程_m']))} m 水就到城下。",
         "· 海拉斯支线：正典只说「有支线通往海拉斯」，接轨点与走向为推定。"]
y4 = M.note_lines(S, "图例", LX, yn + 18, notes, size=8.2, lh=13.5)
M.index_map(S, "图例", LX, y4 + 30, 270, "海拉斯区域图")
# 索引图上补画集水区的整体范围
ix, iy, ik = LX, y4 + 30, 270/360
S.add("图例", f'<path d="{" ".join(M.path_d(ix + e[:, 0]*ik, iy + (90-e[:, 1])*ik, close=True) for e, _ in catch_rings)}" '
              f'fill="none" stroke="{C["ink"]}" stroke-width="0.7" stroke-dasharray="3 1.2 0.8 1.2"/>')
S.text("图例", ix, iy + 135 + 20, "虚线：海拉斯集水区", 6.8, "cjk", fill=C["ink2"])

S.text("出处", X0, SH-22, "底图：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接）；多向晕渲（四光源 225–360°）× 天空可见度；陆地色调：MGS TES 反照率（USGS 7.4 km 拼接）；等高线由 64 px/度重采样高程平滑后提取；"
       "水道与集水区按 16 px/度高程 D8 汇流算得。地貌名：IAU 行星地名库。城镇、时区与铁路：GURPS Transhuman Space《In The Well》。",
       7.0, "cjk", fill=C["ink3"])

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
