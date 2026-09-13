#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2100 年火星三个海：连通性填充 + 海平面精标定。

为什么不能用单一阈值（10_ 脚本暴露的问题）：
  Argyre 盆底低到 −5243 m，任何能灌满北方海的阈值都会把它一起灌满，
  而正典明说 Argyre 是干的。因为 Argyre 是内流封闭盆地，与北方低地不连通。
解法：阈值只定义「低于水面的洼地」，再从各海自己的种子点做连通填充。
  好处是真实地形天然就把三个海分开了 —— 北方海、海拉斯海、水手峡谷海
  在地形上互不连通，正好对应正典的三个海。

两个踩过的坑（都写在注释里，别重犯）：
  ① 降采样必须取最小值，不能取平均：平均会抹平窄海峡，海被切成孤立湖。
  ② 种子不能取「北半球最低点」—— 那是 Lyot 陨坑（50.6°N/29.2°E，−7032 m），
     一个孤立深坑，直到 −3600 m 才与北方低地连通。要取「北纬 30° 以北最大连通域」。

运行：  ./.venv/bin/python scripts/11_三海连通填充.py
"""
import math, pathlib
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy import ndimage

HERE    = pathlib.Path(__file__).resolve().parent
MAP_DIR = HERE.parent
OUT     = MAP_DIR / "产出"; OUT.mkdir(exist_ok=True)
DEM     = MAP_DIR / "DEM/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
R       = 3396190.0
NODATA  = -32768
AREA    = 4*math.pi*R**2 / 1e6          # 火星总表面积 km² = 1.45 亿
YI      = 1e8                           # 「亿」
OUT_PPD = 32                            # 11520×5760，做全球图足够

# ── 读 DEM 并降采样 ────────────────────────────────────────────────
ds = rasterio.open(DEM)
F  = int(round(ds.width/360.0) // OUT_PPD)
H, W = ds.height//F, ds.width//F
cache = MAP_DIR / f"DEM/dem_{OUT_PPD}ppd_min.npy"
if cache.exists():
    dem = np.load(cache)
else:
    print(f"降采样 {ds.width}×{ds.height} → {W}×{H}（{OUT_PPD} px/度，取最小值）")
    dem = np.empty((H, W), np.int16)
    STRIP = 512*F
    for r0 in range(0, ds.height, STRIP):
        h = min(STRIP, ds.height-r0); h -= h % F
        if h <= 0: break
        a = ds.read(1, window=Window(0, r0, ds.width, h)).astype(np.int16)
        a = np.where(a == NODATA, 32767, a)       # nodata 当高地，别参与填充
        dem[r0//F:r0//F+h//F] = a.reshape(h//F, F, W, F).min(axis=(1, 3))
    np.save(cache, dem)
print(f"DEM {W}×{H} @ {OUT_PPD} px/度   高程 {dem[dem<30000].min()} … {dem[dem<30000].max()} m")

wcos  = np.cos(np.radians(90.0 - (np.arange(H)+0.5)/OUT_PPD))[:, None]
WTOT  = float(wcos.sum())*W
def km2(mask): return float((mask*wcos).sum())/WTOT * AREA
def rc(lonE, lat):
    return int((90-lat)*OUT_PPD), int((((lonE+180) % 360))*OUT_PPD)

def basins(level):
    """阈值 + 经度环绕的连通标号。返回 (标号图, 各标号面积权重)。"""
    lab, n = ndimage.label(dem < level, structure=np.ones((3, 3), bool))
    if n:
        # 等距圆柱在 ±180° 首尾相接，把跨缝的标号并起来
        a, b = lab[:, 0], lab[:, -1]
        j = (a > 0) & (b > 0)
        if j.any():
            parent = np.arange(n+1)
            def find(x):
                while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
                return x
            for u, v in zip(a[j], b[j]):
                ru, rv = find(u), find(v)
                if ru != rv: parent[max(ru, rv)] = min(ru, rv)
            lab = np.array([find(i) for i in range(n+1)])[lab]
    return lab

def deepest(lat0, lat1, lon0, lon1):
    """在给定经纬度框里找最深点，当作该海的种子。
    别硬编码种子坐标 —— 我第一版写死 Hellas 在 (70.5°E, −42.4°S)，
    那一点只有 −6035 m，比海平面还高，填充直接返回空集。"""
    nz = lambda d: ((d + 180) % 360) - 180     # 经度框也要归一化到 −180…180
    r0, r1 = int((90-lat1)*OUT_PPD), int((90-lat0)*OUT_PPD)
    c0, c1 = int((nz(lon0)+180)*OUT_PPD), int((nz(lon1)+180)*OUT_PPD)
    sub = dem[r0:r1, c0:c1]
    dr, dc = np.unravel_index(np.argmin(sub), sub.shape)
    return (r0+dr, c0+dc), int(sub[dr, dc])

def by_seed(lab, rowcol):
    k = lab[rowcol]
    return (lab == k) if k > 0 else np.zeros_like(lab, bool)

def borealis(lab):
    """北纬 30° 以北面积最大的连通域 = 北方海（避开 Lyot 陨坑那类孤立深坑）。"""
    top = lab[:int(60*OUT_PPD)]                   # 90°N…30°N
    sz  = np.bincount(top.ravel()); sz[0] = 0
    return (lab == int(np.argmax(sz))) if sz.max() else np.zeros_like(lab, bool)

# ── 北方海海平面：正典自相矛盾，由作者裁定 ─────────────────────────────
# 第一版我用「Vastitas Borealis 必须被淹」这条判据得出 −3900 m —— 那条是我自己的推断，不是正典。
# 把正典原文里所有关于北方海的可检验陈述摆在一起，真实地形上它们分成互斥的两组：
#   甲组（海小）：面积「略小于地中海两倍」、「一条地峡把赞西高地与极冠连接起来」、
#                p19 图上 Dayville 所在的 Acidalia 是陆地                  → 需要 ≤ −4500 m
#   乙组（岸低）：Zhigansk「赞西北部，北方海畔」、New Amsterdam「Shalbatan 河口」、
#                Liangzhen「奥林匹斯以西的北方海岸」、p19 图上的克律塞湾与亚马逊湾、
#                维京公园「正在修堤防海」                                  → 需要约 −3700 m
# 原因：p19 把克律塞湾画成伸到赤道的窄长海湾，同时让更低的 Acidalia 保持干燥 —— 真实地形上做不到。
# 2026-09-12 作者裁定：取乙组，−3700 m（保住正典里人住的海岸）。改回甲组只需改下面这个数。
BOREALIS_LEVEL = -3700
MED_KM2 = 2.51e6

def borealis_all(level, min_km2=2e4):
    """北方海 = 与北纬 30° 以北水面相连的所有水块（去掉 < 2 万 km² 的孤立陨坑）。"""
    lab = basins(level)
    ids = np.unique(lab[:int(60*OUT_PPD)]); ids = ids[ids > 0]
    if not len(ids): return np.zeros_like(lab, bool)
    area = ndimage.sum(np.broadcast_to(wcos, lab.shape), lab, ids) / WTOT * AREA   # 一次算完各块面积
    return np.isin(lab, ids[area >= min_km2])

def isthmus(sea):
    """从赞西高地北缘 (310°E, 18°N) 只走陆地能否到达北纬 84° —— 正典说的地峡是否存在。"""
    lab, _ = ndimage.label(~sea, structure=np.ones((3, 3), bool))
    k = lab[rc(310, 18)]
    return k > 0 and k in set(np.unique(lab[:int(6*OUT_PPD)]))

def shore_km(sea, lonE, lat, maxkm=1500):
    """点到最近岸线的距离（km）；点在水里时量到最近的陆地。"""
    kmpd = 2*math.pi*R/1e3/360
    r, c = rc(lonE, lat); h = int(maxkm/kmpd*OUT_PPD)
    top = max(r-h, 0)
    sub = np.take(sea[top:r+h], range(c-h, c+h), axis=1, mode="wrap")
    st3 = np.ones((3, 3), bool)
    coast = (ndimage.binary_dilation(sub, st3) & ~sub) if not sea[r, c] else (sub & ndimage.binary_dilation(~sub, st3))
    rr, cc = np.nonzero(coast)
    if not len(rr): return float("inf")
    return float(np.hypot((rr-(r-top))*kmpd/OUT_PPD, (cc-h)*kmpd/OUT_PPD*math.cos(math.radians(lat))).min())

print()
print("="*110)
print("一、北方海水位记分卡（正典陈述逐条检验；乙组城镇离岸 ≤150 km 算满足）")
print("="*110)
TOWNS = [("Zhigansk", 311.0, 19.0), ("NewAmst.", 317.9, 15.7), ("Liangzhen", 212.0, 25.0), ("Clarke", 139.7, 48.2)]
print(f"{'海平面':>8s}{'×地中海':>8s}{'地峡':>5s}{'Dayville干':>10s}{'维京公园':>9s} " + "".join(f"{n:>11s}" for n, *_ in TOWNS))
for L in (-4700, -4500, -4300, -4100, -3900, -3700):
    sea = borealis_all(L)
    ds = [shore_km(sea, lo, la) for _, lo, la in TOWNS]
    vk_h = int(dem[rc(311.813, 22.697)]) - L
    print(f"{L:>6d} m{km2(sea)/MED_KM2:>7.1f}×{'有' if isthmus(sea) else '无':>4s}{'干' if not sea[rc(337, 40)] else '淹':>9s}"
          f"{('高出 %d m' % vk_h) if vk_h > 0 else '淹没':>10s} "
          + "".join(f"{('✓' if d <= 150 else '✗') + ('%5.0f km' % d if d < 1e4 else ' 远'):>11s}" for d in ds)
          + ("   ← 采用" if L == BOREALIS_LEVEL else ""))
LB = BOREALIS_LEVEL

# ── 三个海各自落定 ────────────────────────────────────────────────
# 海拉斯海：标定为 −7000 m（东西宽 747 km ≈ 464 英里，符合正典「几百英里宽」）
LH = -7000

# 水手峡谷海：正典明确指出它是自西向东阶梯分布、带巨型船闸和大坝的人工阶梯水体
# 门槛高程 −3607 m（低于此门槛不会漫入北方海）
LM_ius = -3300                         # 西段（Ius 闸上，顺塔西斯隆起缓降）
LM_mid = -3800                         # 中段（Melas / Candor / Coprates 主湖区）
LM_eos = -3700                         # 东段（Capri / Eos 坝前水库，受双大坝拦蓄）
LM = LM_mid

print()
print("="*96)
print("二、三个海（真实地形 + 正典闸坝阶梯分段标定）")
print("="*96)
sea_b  = borealis_all(LB)
sh, zh = deepest(-55, -30,  50, 100)           # Hellas 盆地框内最深点
sa, za = deepest(-58, -38, 300, 340)           # Argyre 盆地框内最深点
sea_h  = by_seed(basins(LH), sh)
sea_a  = by_seed(basins(LB), sa)                # 正典说 Argyre 是干的，看它会不会被灌

# 水手峡谷分段阶梯填充
# ── 每段 = 该段峡谷范围内「所有」低于本段水面的洼地，而不是只取一个种子所在的那块 ──
# 为什么：Ius 峡谷底崎岖，−3300 m 下是 8 块互不连通的小盆；Candor、Hebes 在 −3800 m 下
# 也和 Melas 不连通。只取一个种子，会把正典明写有水的 Ius 段、坎多尔湖、Hebes 统统漏掉
# （Gemini 版的 15_ 在渲染时临时补了 Candor/Hebes，这里收回到唯一数据源）。
# 水位数字不变；段界框取 IAU 官方峡谷范围（数据/IAU/火星IAU地名.csv 的 min/max_lat/lon）。
print("  ▶ 水手峡谷三段阶梯水库体系：")
def box_mask(level, boxes, min_px=30):
    """boxes: [(南纬, 北纬, 西界°E, 东界°E), …]；返回框内所有 < level 的洼地（去掉碎点）。"""
    m = np.zeros_like(dem, bool)
    below = dem < level
    for la0, la1, lo0, lo1 in boxes:
        r0, r1 = int((90-la1)*OUT_PPD), int((90-la0)*OUT_PPD)
        c0, c1 = rc(lo0, 0)[1], rc(lo1, 0)[1]
        m[r0:r1, c0:c1] |= below[r0:r1, c0:c1]
    lab, n = ndimage.label(m, structure=np.ones((3, 3), bool))
    sz = np.bincount(lab.ravel()); sz[0] = 0
    return np.isin(lab, np.where(sz >= min_px)[0])

# 1. 西段 Ius（Ius Chasma 官方范围，东界截在 Ius 船闸处 283.5°E）
sea_ius = box_mask(LM_ius, [(-10.0, -5.7, 268.5, 283.5)])
# 2. 中段：Melas + Coprates 主槽，外加坎多尔湖（Candor+Ophir）与 Hebes 湖
#    Ganges Chasma 不在内 —— 正典里它是 Gangis River（河），不是湖
sea_mid = box_mask(LM_mid, [(-14.0, -7.2, 283.5, 291.9),     # Melas
                            (-16.3, -10.3, 291.0, 313.0),    # Coprates
                            (-9.2, -2.8, 283.5, 296.0),      # Candor + Ophir → 坎多尔湖
                            (-2.2, 0.2, 281.4, 286.7)])      # Hebes
sea_mid &= ~sea_ius
# 3. 东段 Lake Eos：种子所在连通域，截在 318°E（两座坝所在的出口面）
se, ze = deepest(-17, -12, 313, 318)
sea_eos = by_seed(basins(LM_eos), se)
sea_eos[:, rc(318.0, 0)[1]:] = False
sea_eos &= ~(sea_ius | sea_mid)

# 4. 两个正典陨坑湖：蓄水到坑内溢流口以下 20 m（规则明确，不另设水位）
def crater_lake(lat, lonE, diameter_km, freeboard=20):
    """陨坑湖：从坑心附近的最低点起注水，直到溢出坑缘，水面取溢流口以下 freeboard 米。
    种子必须取坑内（坑心 0.3 个半径以内），不能取窗口最低点 —— 窗口会带进坑外更低的地形。"""
    kmpd = 2*math.pi*R/1e3/360
    rad  = diameter_km/2/kmpd                        # 坑半径（度）
    win  = rad*1.8
    r0, r1 = int((90-lat-win)*OUT_PPD), int((90-lat+win)*OUT_PPD)
    c0, c1 = rc(lonE-win, 0)[1], rc(lonE+win, 0)[1]
    sub = dem[r0:r1, c0:c1].astype(np.int32)
    yy, xx = np.mgrid[0:sub.shape[0], 0:sub.shape[1]]
    cy, cx = (sub.shape[0]-1)/2, (sub.shape[1]-1)/2
    inner = (yy-cy)**2 + (xx-cx)**2 <= (0.3*rad*OUT_PPD)**2
    seed = np.unravel_index(np.argmin(np.where(inner, sub, 10**6)), sub.shape)
    floor = int(sub[seed]); spill = None
    for L in range(floor+10, floor+6000, 10):
        lab, _ = ndimage.label(sub < L, structure=np.ones((3, 3), bool))
        rr, cc = np.where(lab == lab[seed])
        if rr.min() == 0 or cc.min() == 0 or rr.max() == sub.shape[0]-1 or cc.max() == sub.shape[1]-1:
            spill = L - 10; break
    lvl = spill - freeboard
    lab, _ = ndimage.label(sub < lvl, structure=np.ones((3, 3), bool))
    m = np.zeros_like(dem, bool)
    if lab[seed] > 0:
        m[r0:r1, c0:c1] = lab == lab[seed]
    return m, lvl, floor
lake_innsbruck, LV_inn, fl_inn = crater_lake(-6.391, 320.036, 59.0)   # Red Lake 所在（ITW p.25）
lake_mutch,     LV_mut, fl_mut = crater_lake(0.595, 304.793, 198.8)   # p22 图上画作湖
print(f"    - Innsbruck 陨坑湖（红湖）   坑底 {fl_inn} m  水面 {LV_inn} m  面积 {km2(lake_innsbruck):,.0f} km²")
print(f"    - Mutch 陨坑湖              坑底 {fl_mut} m  水面 {LV_mut} m  面积 {km2(lake_mutch):,.0f} km²")

sea_m = sea_ius | sea_mid | sea_eos

kmpd = 2*math.pi*R/1e3/360
for seg_name, s, lvl in [
    ("水手峡谷 · 西段 (Ius 闸上)", sea_ius, LM_ius),
    ("水手峡谷 · 中段 (Melas-Coprates 湖)", sea_mid, LM_mid),
    ("水手峡谷 · 东段 (Eos 坝前水库)", sea_eos, LM_eos),
]:
    rs, cs = np.where(s)
    ew = (cs.max()-cs.min())/OUT_PPD * kmpd * math.cos(math.radians(90-rs.mean()/OUT_PPD))
    print(f"    - {seg_name:<28s} 水面 {lvl:>6d} m   宽 {ew:>5.0f} km   "
          f"经度跨 {((cs.min()/OUT_PPD-180)%360):.1f}°E…{((cs.max()/OUT_PPD-180)%360):.1f}°E")

print(f"\n  种子：Hellas {zh} m · Lake Eos {ze} m · Argyre {za} m")

for n, s, L in [("北方海 Borealis Sea", sea_b, LB), ("海拉斯海 Hellas Sea", sea_h, LH),
                ("水手峡谷海 Marineris Sea (全线)", sea_m, LM)]:
    if not s.any():
        print(f"  {n:<26s} 海平面 {L:>6d} m   ← 空集，种子点比海平面高，检查种子框"); continue
    rs, cs = np.where(s)
    ew = (cs.max()-cs.min())/OUT_PPD * kmpd * math.cos(math.radians(90-rs.mean()/OUT_PPD))
    ns = (rs.max()-rs.min())/OUT_PPD * kmpd
    print(f"  {n:<26s} 标称基准 {L:>6d} m   面积 {km2(s)/YI:6.3f} 亿km² ({km2(s)/AREA*100:4.1f}%)"
          f"   纬度 {90-rs.max()/OUT_PPD:+.0f}…{90-rs.min()/OUT_PPD:+.0f}°"
          f"   跨度 {ew:.0f}×{ns:.0f} km ({ew/1.609:.0f}×{ns/1.609:.0f} 英里)")
aa = km2(sea_a)
print(f"  {'Argyre（正典：无水）':<26s} 海平面 {LB:>6d} m   " +
      ("与北方海不连通，自动保持干燥 ✓" if aa == 0 else
       f"却被灌了 {aa/YI:.3f} 亿km² ← 得在成图时手工排除"))

# ── 维京公园：正典说那里正在修堤，算算水面离它多远 ──────────────────
r, c = rc(312.03, 22.48)
dist = ndimage.distance_transform_edt(~sea_b)[r, c] / OUT_PPD * kmpd
print()
print("="*96)
print("三、维京公园：正典写它「此刻正在修堤防海」—— 真实地形给出的数字")
print("="*96)
print(f"  园区地面 −3620 m，海面 {LB} m  →  高出水面 {-3620-LB:+d} m")
print(f"  到岸线水平距离 约 {dist:.0f} km")
print(f"  正典说几十年内会被淹到「近一英里深」→ 届时海平面约 {-3620+1600:+d} m")
print(f"  也就是说这条堤要拦的是 {(-3620+1600)-LB:+d} m 的海侵。它拦不住。")

np.savez_compressed(OUT / "三海掩膜.npz", borealis=sea_b, hellas=sea_h, marineris=sea_m,
                    ppd=OUT_PPD, level_borealis=LB, level_hellas=LH, level_marineris=LM,
                    level_ius=LM_ius, level_eos=LM_eos,
                    # 分段与陨坑湖（20_ 地点定位、15_ 战区图用）
                    marineris_ius=sea_ius, marineris_mid=sea_mid, marineris_eos=sea_eos,
                    lake_innsbruck=lake_innsbruck, lake_mutch=lake_mutch,
                    level_innsbruck=LV_inn, level_mutch=LV_mut)
print(f"\n掩膜已存 → {OUT / '三海掩膜.npz'}（{W}×{H} @ {OUT_PPD} px/度）")
