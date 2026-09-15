#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2100 年土地利用：农田、草场（已绿化带）、水产养殖、城区 —— 按真实地形算出来，不手画。

思路
  1. 适宜度 S = f(高程) × f(纬度) × f(坡度) × f(水)：高程代气压（Ge'gyai 5,119 m 还能种果树，6,500 m 以上为 0），
     纬度代温度（±25° 内满分，±65° 为 0），水 = 离海/湖距离 与 离河道距离 取大者。河道用 MOLA 填洼 + D8 汇流算，
     窗口 236–336°E × 32°N–24°S（水手峡谷、赞西、克律塞、诺克提斯），其余地区只看离海距离。
  2. 农田：总量 12,000 km²（2.5e6 人 × 地球 0.19 ha/人 ≈ 4,750 km²，正典说火星是外太阳系粮仓、出口食物，取 2.5 倍），
     按正典点名的农区分配配额（赞西谷地「大规模农业」最多，Chester 周边「大量农场」，诺克提斯湿谷，克律塞、亚马逊、
     伊利瑟姆沿岸「一些农业」，海拉斯沿岸，大瑟提斯以北庄园），每区取适宜度最高的格子直到配额满。
  3. 草场：适宜度放宽后的连片带——水手峡谷海边的「草场牧群」（ITW 牲畜条）、湿谷里的「绿意」、沿岸带。
  4. 水产：红湖（因斯布鲁克陨坑湖，海带养殖）取湖面；海拉斯、北方海沿岸的季节性水产不画面。
  5. 城区：按推定人口 / 密度算面积，穹顶城按正典尺寸摆穹顶（新上海六穹顶围绕电梯基座，一号在北、俯瞰火山口）。
     只有大比例尺的城区图画得出来；区域图上城区比符号还小，不画。

数据：DEM/dem_32ppd_avg.npy、产出/三海掩膜.npz、数据/火星地点.csv
产出：产出/土地利用_2100.geojson（多边形：class = 农田 / 草场 / 水产 / 城区，附 region、area_km2）
      产出/土地利用_2100_统计.md
运行：./.venv/bin/python scripts/22_土地利用.py
"""
import json, math, sys
import numpy as np
from scipy import ndimage
from skimage.morphology import reconstruction
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M

PPD = 32
POP_2100 = 2_500_000
CROP_TOTAL = 12_000                      # km²
CH_ACC = 30_000                          # 汇流面积 ≥ 这个数（km²）算常年河（3,000 会把每条小冲沟都算上，草场带铺满赞西）
Z = M.load_masks()
LV = {k: int(Z[f"level_{k}"]) for k in ("borealis", "hellas", "marineris", "ius", "eos", "innsbruck", "mutch")}

print("读 DEM …")
D = M.load_dem32_avg().astype(np.float32)
H, W = D.shape
lat = 90 - (np.arange(H) + 0.5)/PPD
lon = -180 + (np.arange(W) + 0.5)/PPD
cosl = np.cos(np.radians(lat))[:, None]
dy_km = M.KMPD/PPD
cell = dy_km*dy_km*cosl*np.ones((1, W), np.float32)                   # km²
water = (Z["borealis"] | Z["hellas"] | Z["marineris_ius"] | Z["marineris_mid"] | Z["marineris_eos"]
         | Z["lake_innsbruck"] | Z["lake_mutch"])

# ── 因子 ─────────────────────────────────────────────────────────────
def f_elev(z, mid=3800.0, width=900.0):  # 高程 → 气压因子：logistic，3,800 m 处 0.5，6,500 m 以上 ≈ 0（Ge'gyai 5,119 m ≈ 0.19）
    return (1/(1 + np.exp((z - mid)/width))).astype(np.float32)
def f_lat(la, mid=45.0, width=8.0):       # 纬度 → 温度因子：±25° ≈ 0.92，±45° = 0.5，±65° ≈ 0.08
    return (1/(1 + np.exp((np.abs(la) - mid)/width))).astype(np.float32)

print("坡度、离水距离 …")
gy, gx = np.gradient(D)
slope = np.degrees(np.arctan(np.hypot(gx/(dy_km*1000*np.maximum(cosl, 0.05)), gy/(dy_km*1000))))
del gx, gy
f_slope_crop = np.exp(-(slope/3.0)**2).astype(np.float32)                    # 3° 降到 0.37，6° ≈ 0.02
f_slope_veg = np.exp(-(slope/8.0)**2).astype(np.float32)
# 离海/湖距离：16 px/度上算 EDT（各向同性近似，单位取南北向格长），再放大
w16 = water.reshape(H//2, 2, W//2, 2).any(axis=(1, 3))
d16 = ndimage.distance_transform_edt(~w16)*(M.KMPD/16)
d_sea = np.repeat(np.repeat(d16, 2, 0), 2, 1).astype(np.float32); del d16, w16

# 离城镇距离（农场围着市场和车站长）：16 px/度 EDT
PLACES = {r["id"]: r for r in M.load_places()}
town16 = np.zeros((H//2, W//2), bool)
for r in PLACES.values():
    if r["类别"] in ("城市", "城镇", "军事", "区域", "庄园"):
        rr, cc = int((90 - float(r["纬度"]))*16), int(((float(r["东经"]) + 180) % 360)*16)
        town16[min(rr, H//2-1), min(cc, W//2-1)] = True
d16 = ndimage.distance_transform_edt(~town16)*(M.KMPD/16)
d_town = np.repeat(np.repeat(d16, 2, 0), 2, 1).astype(np.float32); del d16, town16
f_town = (0.35 + 0.65*np.exp(-d_town/150.0)).astype(np.float32)

# ── 河道：填洼 + D8 汇流（窗口 236–336°E × 32°N–24°S）────────────────────
print("河道：填洼、D8 汇流 …")
HLON0, HLON1, HLAT0, HLAT1 = 236, 336, 32, -24
r0, r1 = int((90 - HLAT0)*PPD), int((90 - HLAT1)*PPD); c0, c1 = int(((HLON0 + 180) % 360)*PPD), int(((HLON1 + 180) % 360)*PPD)
demw = D[r0:r1, c0:c1].astype(np.float64); seaw = water[r0:r1, c0:c1]
HH, HW = demw.shape
h_lat = lat[r0:r1]; h_cell = cell[r0:r1, c0:c1].astype(np.float64)
outlet = seaw.copy(); outlet[0, :] = outlet[-1, :] = True; outlet[:, 0] = outlet[:, -1] = True
filled = reconstruction(np.where(outlet, demw, demw.max() + 1.0), demw, method="erosion")
NB = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
dx_km = dy_km*np.maximum(np.cos(np.radians(h_lat)), 0.02)[:, None]
pad = np.pad(filled, 1, mode="edge")
best = np.full(filled.shape, -1, np.int8); bestdrop = np.zeros(filled.shape)
for k, (di, dj) in enumerate(NB):
    nb = pad[1+di:1+di+HH, 1+dj:1+dj+HW]
    dist = dy_km if dj == 0 else (dx_km if di == 0 else np.hypot(dx_km, dy_km))
    drop = (filled - nb)/dist
    better = drop > bestdrop; best[better] = k; bestdrop[better] = drop[better]
best[outlet] = -1
resolved = (best >= 0) | outlet
for _ in range(400):
    un = ~resolved
    if not un.any(): break
    pres = np.pad(resolved, 1, mode="constant"); changed = False
    for k, (di, dj) in enumerate(NB):
        cand = un & (pad[1+di:1+di+HH, 1+dj:1+dj+HW] == filled) & pres[1+di:1+di+HH, 1+dj:1+dj+HW]
        if cand.any(): best[cand] = k; un &= ~cand; changed = True
    resolved = (best >= 0) | outlet
    if not changed: break
idx = np.arange(filled.size).reshape(filled.shape); down = idx.copy()
for k, (di, dj) in enumerate(NB):
    rr, cc = np.nonzero(best == k)
    down[rr, cc] = idx[np.clip(rr+di, 0, HH-1), np.clip(cc+dj, 0, HW-1)]
down = down.ravel(); N = down.size
acc = h_cell.ravel().copy()
indeg = np.bincount(down, minlength=N); selfloop = down == np.arange(N); indeg[selfloop] -= 1
frontier = np.nonzero(indeg == 0)[0]
while frontier.size:
    m = ~selfloop[frontier]; src, tgt = frontier[m], down[frontier[m]]
    np.add.at(acc, tgt, acc[src]); np.subtract.at(indeg, tgt, 1)
    frontier = np.unique(tgt[indeg[tgt] == 0])
acc = acc.reshape(filled.shape)
valley = (demw - ndimage.uniform_filter(demw, 15)) < -60          # 真谷地：比 28 km 邻域平均低 60 m 以上
channel = (acc >= CH_ACC) & ~seaw & valley
d_riv = np.full(D.shape, 1e4, np.float32)
d_riv[r0:r1, c0:c1] = ndimage.distance_transform_edt(~channel)*dy_km
print(f"  河道格 {int(channel.sum()):,}（只保留切入谷地的），最大汇流 {acc.max()/1e4:,.0f} 万 km²")
del filled, pad, best, bestdrop, resolved, idx, down, acc, indeg, demw

# ── 适宜度 ───────────────────────────────────────────────────────────
print("适宜度 …")
f_water_crop = np.maximum(np.exp(-d_sea/35.0), np.exp(-d_riv/12.0)).astype(np.float32)
f_water_veg = np.maximum(np.exp(-d_sea/22.0), np.exp(-d_riv/10.0)).astype(np.float32)
LAT2 = np.broadcast_to(lat[:, None], D.shape)
S_crop = f_elev(D)*f_lat(LAT2)*f_slope_crop*f_water_crop*f_town
S_dry = f_elev(D)*f_lat(LAT2)*f_slope_crop*f_town                        # 不看水：井灌 / 运冰的庄园用
S_veg = f_elev(D, mid=4200.0)*f_lat(LAT2, mid=36.0, width=6.0)*f_slope_veg*f_water_veg
S_crop[water] = 0; S_veg[water] = 0

# ── 农田：按区配额 ──────────────────────────────────────────────────────
REGIONS = [  # (名称, lon0, lon1, lat_s, lat_n, 权重, 正典依据)
    ("赞西谷地", 300, 326, -5, 12, 0.32, "赞西「相对肥沃，谷地里有大规模农业」ITW p.24"),
    ("俄斐高原 · Chester", 295, 307, -12.5, -8, 0.12, "Chester 周边「大量农场」，粮食在此装车 ITW p.25"),
    ("水手峡谷沿岸", 278, 322, -18, -4, 0.14, "坎多尔、梅拉斯、科普拉特斯、厄俄斯湖岸；红湖水产 ITW p.22–25"),
    ("诺克提斯迷宫", 250, 268, -12, -2, 0.06, "湿谷「满是绿意」、中国栖息地、Ge'gyai 果园 ITW p.22–23"),
    ("克律塞湾沿岸", 305, 336, 12, 30, 0.10, "北方海岸「一些农业和季节性水产」ITW p.26"),
    ("阿西达利亚 · 滕比岸", 285, 305, 22, 36, 0.03, "同上；Sharona"),
    ("亚马逊湾沿岸", 190, 216, 20, 33, 0.04, "同上；Liangzhen、大分"),
    ("伊利瑟姆 · 秘鲁沿岸", 128, 162, 17, 37, 0.09, "秘鲁殖民地核心区、莫约班巴、冥河城 ITW p.27"),
    ("海拉斯沿岸", 48, 76, -37, -25, 0.06, "海拉斯海沿岸聚落带 ITW p.27"),
    ("大瑟提斯以北庄园", 62, 72, 16, 23, 0.02, "富豪「数千英亩精心造景的土地」，井灌与运冰，不靠地表水 ITW p.47"),
    ("其他零星", None, None, None, None, 0.02, "全球其余高适宜度地点"),
]
crop = np.zeros(D.shape, bool)
stats = []
def box(lon0, lon1, lat_s, lat_n):
    L = (lon + 180) % 360 - 180
    a = lon0 - 360 if lon0 > 180 else lon0; b = lon1 - 360 if lon1 > 180 else lon1
    if a > b: cm = (L >= a) | (L <= b)
    else: cm = (L >= a) & (L <= b)
    rm = (lat >= lat_s) & (lat <= lat_n)
    return rm[:, None] & cm[None, :]
for name, lo0, lo1, la_s, la_n, wgt, src in REGIONS:
    quota = CROP_TOTAL*wgt
    sel = box(lo0, lo1, la_s, la_n) if lo0 is not None else ~crop
    sc = np.where(sel & ~crop, S_dry if "庄园" in name else S_crop, 0)
    order = np.argsort(sc, axis=None)[::-1]
    cum = np.cumsum(cell.ravel()[order]); n = int(np.searchsorted(cum, quota)) + 1
    take = order[:n]; take = take[sc.ravel()[take] > 0.05]
    m = np.zeros(D.size, bool); m[take] = True; m = m.reshape(D.shape)
    m = ndimage.binary_closing(m, np.ones((3, 3), bool)) & ~water & sel if lo0 is not None else m
    crop |= m
    stats.append((name, float((cell*m).sum()), float(sc.ravel()[take].min()) if take.size else 0, src))
crop_area = float((cell*crop).sum())

# ── 草场 / 已绿化带 ──────────────────────────────────────────────────────
veg = (S_veg >= 0.40) & ~crop & ~water
veg = ndimage.binary_opening(veg, np.ones((2, 2), bool))
veg_area = float((cell*veg).sum())
print(f"  草场 {veg_area/1e4:,.0f} 万 km²：临海 {float((cell*(veg & (d_sea < d_riv))).sum())/1e4:,.0f} 万，沿河 {float((cell*(veg & (d_riv <= d_sea))).sum())/1e4:,.0f} 万")

# ── 水产：红湖 ───────────────────────────────────────────────────────────
# 三海掩膜里的 lake_innsbruck 是空的（11_ 的坑湖填充在这个坑没成功），这里直接按坑底填：坑心 320.036°E 6.391°S，直径 59 km（IAU）
ri, ci = int((90 + 6.391)*PPD), int(((320.036 + 180) % 360)*PPD)
sub = D[ri-16:ri+16, ci-16:ci+16]
yy, xx = np.mgrid[-16:16, -16:16]; inside = np.hypot(yy, xx*math.cos(math.radians(-6.4))) <= 25/dy_km
floor = float(sub[inside].min())
lake = inside & (sub < floor + 150)
lab, _ = ndimage.label(lake); lake = lab == lab[np.unravel_index(np.argmin(np.where(inside, sub, 1e9)), sub.shape)]
aqua = np.zeros(D.shape, bool); aqua[ri-16:ri+16, ci-16:ci+16] = lake
aqua_area = float((cell*aqua).sum())
print(f"  红湖：坑底 {floor:,.0f} m，水面 {floor+150:,.0f} m，面积 {aqua_area:,.0f} km²")

# ── 城区（推定人口）──────────────────────────────────────────────────────
# 人口：正典只给了全火星 250 万与新上海「约 4%」，其余按城市等级、正典描述推定；剩下约 150 万散在栖息地、农场、矿站。
URBAN = {  # id: (人口, 密度 人/km², 形态)
    "new_shanghai": (100_000, None, "domes6"), "port_lowell": (180_000, 4500, "open"), "haiyuan": (120_000, 5000, "terrace"),
    "robinson": (90_000, 4500, "open"), "nix_olympica": (40_000, None, "dome1"), "santo_tomas": (25_000, 2000, "open"),
    "zhigansk": (35_000, 3500, "open"), "moyobamba": (40_000, 4000, "open"), "stygis": (40_000, 4000, "open"),
    "hanggin_qi": (15_000, 3000, "open"), "bako": (12_000, 3000, "open"), "harbin": (12_000, 3000, "open"),
    "red_lake": (15_000, 3000, "open"), "wudu": (15_000, 3500, "open"), "chester": (8_000, 2000, "open"),
    "sharona": (8_000, 3000, "open"), "liangzhen": (12_000, 3000, "open"), "anchorage": (6_000, 3000, "open"),
    "ge_gyai": (6_000, 2000, "open"), "fort_meier": (5_000, 2500, "open"), "vlore": (5_000, 3000, "open"),
    "fortuna": (4_000, 3000, "open"), "timbuktu": (4_000, 3000, "open"), "new_amsterdam": (4_000, 3000, "open"),
    "rockwood": (4_000, 3000, "open"), "nantong": (5_000, 3000, "open"), "aralqi": (5_000, 3000, "open"),
    "rizhao": (4_000, 3000, "open"), "heze": (4_000, 3000, "open"), "as_sulaymi": (6_000, 3000, "open"),
    "urumqi": (5_000, 3000, "open"), "oita": (4_000, 3000, "open"), "shibetsu": (3_000, 3000, "open"),
    "dayville": (3_000, 3000, "open"), "christiana": (3_000, 3000, "open"), "clarke": (3_000, 3000, "open"),
    "ica_nova": (5_000, 3000, "open"), "dao_city": (5_000, 3000, "open"),
}
def circle(lon0, lat0, r_km, n=48):
    dlat = r_km/M.KMPD; dlon = dlat/max(math.cos(math.radians(lat0)), 0.05)
    return [[round(lon0 + dlon*math.cos(t), 5), round(lat0 + dlat*math.sin(t), 5)] for t in np.linspace(0, 2*math.pi, n, endpoint=False)]
urban_feats = []
for pid, (pop, dens, shape_) in URBAN.items():
    r = PLACES[pid]; lo, la = float(r["东经"]), float(r["纬度"])
    if shape_ == "domes6":         # 六个直径 >1 英里的穹顶围绕电梯基座；一号在北缘俯瞰火山口；七号在建；穹顶外临建区
        e = PLACES["elevator"]; elo, ela = float(e["东经"]), float(e["纬度"])
        R_ring, r_dome = 2.6, 0.9
        for i in range(7):
            t = math.radians(90 - i*360/6) if i < 6 else math.radians(90 - 6.5*360/6)
            dlat = R_ring/M.KMPD; dlon = dlat/math.cos(math.radians(ela))
            c = (elo + dlon*math.cos(t)*(1 if i < 6 else 1.9), ela + dlat*math.sin(t)*(1 if i < 6 else 1.9))
            urban_feats.append({"type": "Feature", "properties": {"class": "城区", "name": r["中文名"], "part": f"{i+1} 号穹顶" + ("（在建）" if i == 6 else ""),
                                "pop": pop if i == 0 else 0, "area_km2": round(math.pi*r_dome**2, 2), "kind": "dome" if i < 6 else "dome_uc"},
                                "geometry": {"type": "Polygon", "coordinates": [circle(c[0], c[1], r_dome)]}})
        # 临建区：穹顶环外东、南侧的一圈扇环（正典：城市「以临建方式向外扩张」，东郊在缆索坠落路径上）
        r_in, r_out = 3.7, 5.3; a0, a1 = math.radians(-160), math.radians(30)
        dlat = 1/M.KMPD; dlon = dlat/math.cos(math.radians(ela))
        arc_o = [[round(elo + dlon*r_out*math.cos(t), 5), round(ela + dlat*r_out*math.sin(t), 5)] for t in np.linspace(a0, a1, 40)]
        arc_i = [[round(elo + dlon*r_in*math.cos(t), 5), round(ela + dlat*r_in*math.sin(t), 5)] for t in np.linspace(a1, a0, 40)]
        sprawl_area = 0.5*(r_out**2 - r_in**2)*(a1 - a0)
        urban_feats.append({"type": "Feature", "properties": {"class": "城区", "name": r["中文名"], "part": "穹顶外临建区", "pop": 0, "area_km2": round(sprawl_area, 1), "kind": "sprawl"},
                            "geometry": {"type": "Polygon", "coordinates": [arc_o + arc_i + arc_o[:1]]}})
        continue
    if shape_ == "dome1":
        urban_feats.append({"type": "Feature", "properties": {"class": "城区", "name": r["中文名"], "part": "主穹顶（直径 1 英里）", "pop": pop, "area_km2": round(math.pi*0.8**2, 2), "kind": "dome"},
                            "geometry": {"type": "Polygon", "coordinates": [circle(lo, la, 0.8)]}})
        for k in range(4):
            t = math.radians(200 + k*40); dlat = 1.6/M.KMPD; dlon = dlat/math.cos(math.radians(la))
            urban_feats.append({"type": "Feature", "properties": {"class": "城区", "name": r["中文名"], "part": "附属穹顶", "pop": 0, "area_km2": 0.2, "kind": "dome"},
                                "geometry": {"type": "Polygon", "coordinates": [circle(lo + dlon*math.cos(t), la + dlat*math.sin(t), 0.25, 24)]}})
        continue
    area = pop/dens
    urban_feats.append({"type": "Feature", "properties": {"class": "城区", "name": r["中文名"], "part": "", "pop": pop, "area_km2": round(area, 1), "kind": shape_},
                        "geometry": {"type": "Polygon", "coordinates": [circle(lo, la, math.sqrt(area/math.pi))]}})
urban_pop = sum(v[0] for v in URBAN.values())

# ── 导出 ─────────────────────────────────────────────────────────────────
print("矢量化 …")
feats = []
def add_rings(mask, cls, min_px=3, simplify=0.02):
    n = 0
    for lon_left in (-180.0,):
        for ext, holes in M.mask_rings(mask, PPD, lon_left=lon_left, lat_top=90.0, min_px=min_px, simplify=simplify, smooth=1):
            ext = np.vstack([ext, ext[:1]]); holes = [np.vstack([h, h[:1]]) for h in holes]      # mask_rings 平滑后首尾差一点，闭合
            poly = [ext.tolist()] + [h.tolist() for h in holes]
            xs = ext[:, 0]; ys = ext[:, 1]
            a = abs(float(np.sum(xs[:-1]*ys[1:] - xs[1:]*ys[:-1]))/2)*M.KMPD*M.KMPD*math.cos(math.radians(float(ys.mean())))
            feats.append({"type": "Feature", "properties": {"class": cls, "area_km2": round(a, 1)}, "geometry": {"type": "Polygon", "coordinates": poly}})
            n += 1
    return n
n_crop = add_rings(crop, "农田", min_px=2)
n_veg = add_rings(veg, "草场", min_px=12, simplify=0.03)
n_aq = add_rings(aqua, "水产", min_px=2)
feats += urban_feats
json.dump({"type": "FeatureCollection", "features": feats}, open(M.OUT/"土地利用_2100.geojson", "w", encoding="utf-8"), ensure_ascii=False)
print(f"→ 土地利用_2100.geojson  农田 {n_crop} 块 · 草场 {n_veg} 块 · 水产 {n_aq} 块 · 城区 {len(urban_feats)} 块")

# 统计
CN = [("新疆", 166e4), ("西藏", 123e4), ("内蒙古", 118e4), ("青海", 72e4), ("四川", 48.6e4), ("黑龙江", 47.3e4), ("甘肃", 42.6e4),
      ("云南", 39.4e4), ("广西", 23.8e4), ("湖南", 21.2e4), ("陕西", 20.6e4), ("河北", 18.8e4), ("广东", 18.0e4), ("山东", 15.8e4),
      ("河南", 16.7e4), ("辽宁", 14.8e4), ("福建", 12.4e4), ("江苏", 10.7e4), ("浙江", 10.6e4), ("重庆", 8.2e4), ("宁夏", 6.6e4),
      ("台湾", 3.6e4), ("海南", 3.5e4), ("北京", 1.64e4), ("天津", 1.19e4), ("上海", 6340)]
def cn_ref(a):
    nm, v = min(CN, key=lambda t: abs(math.log(a/t[1])))
    r = a/v
    return f"{nm}" if 0.9 < r < 1.1 else f"{nm}的 {r:.1f} 倍" if r >= 1.1 else f"{nm}的 {r*10:.0f} 成"
lines = ["# 2100 年土地利用统计", "", f"由 `scripts/22_土地利用.py` 生成；面积按 32 px/度格网统计。", "",
         "| 类别 | 面积 | 对照 |", "|---|---|---|",
         f"| 农田 | {crop_area:,.0f} km² | ≈ {cn_ref(crop_area)}；地球 0.19 ha/人 × 250 万人 = {POP_2100*0.19/100:,.0f} km²，正典说火星出口食物，取 {CROP_TOTAL/(POP_2100*0.19/100):.1f} 倍 |",
         f"| 草场 / 已绿化带 | {veg_area/1e4:,.0f} 万 km² | ≈ {cn_ref(veg_area)}；水手峡谷海边的草场牧群、湿谷绿意、沿岸带 |",
         f"| 水产（红湖） | {aqua_area:,.0f} km² | 因斯布鲁克陨坑湖，海带养殖 |",
         f"| 城区 | {sum(f['properties']['area_km2'] for f in urban_feats):,.0f} km² | {len(URBAN)} 座城镇，推定城镇人口 {urban_pop/1e4:,.0f} 万，其余 {(POP_2100-urban_pop)/1e4:,.0f} 万散在栖息地、农场、矿站 |",
         "", "## 农田分区", "", "| 农区 | 面积 km² | 配额 | 取用格最低适宜度（满分 1） | 正典依据 |", "|---|---|---|---|---|"]
for (name, a, smin, src), (_, _, _, _, _, wgt, _) in zip(stats, REGIONS):
    lines.append(f"| {name} | {a:,.0f} | {wgt:.0%} | {smin:.2f} | {src} |")
lines += ["", "## 城区推定", "", "| 城镇 | 推定人口 | 面积 km² | 形态 |", "|---|---|---|---|"]
for pid, (pop, dens, shape_) in sorted(URBAN.items(), key=lambda t: -t[1][0]):
    a = sum(f["properties"]["area_km2"] for f in urban_feats if f["properties"]["name"] == PLACES[pid]["中文名"])
    lines.append(f"| {PLACES[pid]['中文名']} | {pop:,} | {a:.1f} | {'六穹顶 + 临建区（正典）' if shape_ == 'domes6' else '一英里穹顶 + 附属穹顶（正典）' if shape_ == 'dome1' else '沿坑壁梯田式（正典）' if shape_ == 'terrace' else f'敞开式，{dens:,} 人/km²'} |")
(M.OUT/"土地利用_2100_统计.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines[4:12]))
