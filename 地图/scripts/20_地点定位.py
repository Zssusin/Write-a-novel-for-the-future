#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 数据/地点规则.csv 里的每条「定位规则」落到真实 MOLA 地形上，并生成赤道铁路。

为什么要这一步：旧坐标大多是从 In The Well 的 p22 示意图上量的，而那张图把整条峡谷
画偏了约 3°、把厄俄斯湖画偏了 5–7°。照搬到真实地形上，船闸落在四千米高的台地上、
铁路压在水面上。这里改成「保留正典给的关系（北岸 / 南岸 / 哪条支湖 / 哪个陨坑），
在真实地形上重新找到那个位置」。

输入：数据/地点规则.csv  数据/IAU/火星IAU地名.csv  产出/三海掩膜.npz  DEM/…463m.tif
产出：数据/火星地点.csv          ← 坐标表的唯一数据源（对照表 md、所有地图都读它）
      产出/地点_2100.geojson
      产出/基础设施_2100.geojson  ← 赤道铁路（干线/支线/桥段）、车站、闸坝
运行：./.venv/bin/python scripts/20_地点定位.py
"""
import csv, json, math, pathlib
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy import ndimage
from skimage.morphology import reconstruction
from skimage.graph import route_through_array

HERE    = pathlib.Path(__file__).resolve().parent
MAP_DIR = HERE.parent
OUT     = MAP_DIR / "产出"
DATA    = MAP_DIR / "数据"
R       = 3396190.0
KMPD    = 2*math.pi*R/1e3/360            # 赤道上 1° ≈ 59.27 km
ST3     = np.ones((3, 3), bool)

# ── 数据载入 ───────────────────────────────────────────────────────
IAU = {r["clean_name"]: r for r in csv.DictReader(open(DATA/"IAU/火星IAU地名.csv", encoding="utf-8"))}
Z   = np.load(OUT/"三海掩膜.npz")
P   = int(Z["ppd"])
MASK = {k: Z[k] for k in ("borealis", "hellas", "marineris", "marineris_ius", "marineris_mid",
                          "marineris_eos", "lake_innsbruck", "lake_mutch")}
LEVEL = {"borealis": int(Z["level_borealis"]), "hellas": int(Z["level_hellas"]),
         "marineris_ius": int(Z["level_ius"]), "marineris_mid": int(Z["level_marineris"]),
         "marineris_eos": int(Z["level_eos"]), "lake_mutch": int(Z["level_mutch"])}
WATER_NAMES = {"borealis": "北方海", "hellas": "海拉斯海", "marineris_ius": "水手峡谷海·Ius 段",
               "marineris_mid": "水手峡谷海·中段", "marineris_eos": "厄俄斯湖", "lake_mutch": "Mutch 陨坑湖"}
ALLWATER = np.zeros_like(MASK["borealis"])
for k in WATER_NAMES: ALLWATER |= MASK[k]
H, W = ALLWATER.shape
DEM32 = np.load(MAP_DIR/"DEM/dem_32ppd_min.npy")
DS    = rasterio.open(MAP_DIR/"DEM/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif")
PF    = 128                                           # 原始 DEM 分辨率 px/度

DIRS = {"N": (1, 0), "S": (-1, 0), "E": (0, 1), "W": (0, -1),
        "NE": (1, 1), "NW": (1, -1), "SE": (-1, 1), "SW": (-1, -1)}

def lon360(x): return x % 360.0
def m_rc(lat, lon): return min(max(int((90-lat)*P), 0), H-1), int(((lon+180) % 360)*P) % W
def m_ll(r, c):     return 90-(r+0.5)/P, lon360((c+0.5)/P-180)

def move(lat, lon, d, km):
    dy, dx = DIRS[d]; n = math.hypot(dy, dx)
    return (lat + km/KMPD*dy/n,
            lon360(lon + km/(KMPD*max(math.cos(math.radians(lat)), 0.05))*dx/n))

def gdist(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(((lon2-lon1+180) % 360)-180)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R/1e3*math.asin(math.sqrt(min(a, 1)))

# ── 原始 463 m DEM 窗口读取 ────────────────────────────────────────
def fr_window(lat, lon, half):
    l = ((lon+180) % 360)-180
    r, c, h = int((90-lat)*PF), int((l+180)*PF), int(half*PF)
    r0, r1 = max(r-h, 0), min(r+h, DS.height)
    a = DS.read(1, window=Window(c-h, r0, 2*h, r1-r0), boundless=True, fill_value=-32768).astype(np.float32)
    a[a == -32768] = np.nan
    return a, r0, c-h
def fr_ll(r0, c0, i, j): return 90-(r0+i+0.5)/PF, lon360((c0+j+0.5)/PF-180)
def fr_elev(lat, lon):
    a, _, _ = fr_window(lat, lon, 1/PF)
    return float(np.nanmean(a)) if np.isfinite(a).any() else float("nan")

# ── 各条规则 ───────────────────────────────────────────────────────
def iau(name):
    r = IAU[name]; return float(r["center_lat"]), lon360(float(r["center_lon"]))

def iau_edge(name, d):
    lat, lon = iau(name); return move(lat, lon, d, float(IAU[name]["diameter"])/2)

def summit(name):
    r = IAU[name]
    la0, la1 = float(r["min_lat"]), float(r["max_lat"])
    lo0, lo1 = float(r["min_lon"]), float(r["max_lon"])
    a, r0, c0 = fr_window((la0+la1)/2, (lo0+lo1)/2, max(la1-la0, lo1-lo0)/2)
    i, j = np.unravel_index(np.nanargmax(a), a.shape)
    return fr_ll(r0, c0, i, j)

def _caldera(name):
    """山顶火山口 = 山体中心附近「深度 × 面积」最大的封闭洼地（形态学填洼后深度 > 300 m）。
    两个坑：① 窗口要以 IAU 山体中心为心（以最高点为心时，Olympus 的火山口会被挤到窗口边上）；
           ② 找不到候选时绝不能退回标号 0 —— 那是整个窗口的背景。"""
    lat, lon = iau(name)
    a, r0, c0 = fr_window(lat, lon, 1.5)
    a = np.where(np.isfinite(a), a, np.nanmin(a)).astype(np.float64)   # float32 会让 skimage 的重建算错
    seed = a.copy(); seed[1:-1, 1:-1] = a.max()
    depth = reconstruction(seed, a, method="erosion") - a
    lab, n = ndimage.label(depth > 300, structure=ST3)
    cy, cx = a.shape[0]/2, a.shape[1]/2
    best, score = None, 0.0
    for k in range(1, n+1):
        m = lab == k
        ii, jj = np.nonzero(m)
        off = math.hypot(ii.mean()-cy, jj.mean()-cx)/cy          # 0 = 窗口中心，1 = 边缘
        s = depth[m].sum() * max(0.0, 1.0-off)
        if s > score: best, score = k, s
    if best is None: raise ValueError(f"{name} 附近没找到火山口")
    m = lab == best
    ii, jj = np.nonzero(m)
    return a, r0, c0, m, ii.mean(), jj.mean()

def caldera(name):
    a, r0, c0, m, ci, cj = _caldera(name)
    return fr_ll(r0, c0, ci, cj)

def caldera_rim(name, d):
    """从火山口中心沿方位走出洼地，继续走到高程不再上升处 = 坑缘。"""
    a, r0, c0, m, ci, cj = _caldera(name)
    dy, dx = DIRS[d]; n = math.hypot(dy, dx)
    i, j = ci, cj; left = False; best = (-1e9, ci, cj); since = 0
    for _ in range(4000):
        i -= dy/n*0.5; j += dx/n*0.5
        ii, jj = int(round(i)), int(round(j))
        if not (0 <= ii < a.shape[0] and 0 <= jj < a.shape[1]): break
        if not left:
            left = not m[ii, jj]; continue
        if a[ii, jj] > best[0]: best, since = (a[ii, jj], ii, jj), 0
        else:
            since += 1
            if since > 30: break                             # 约 7 km 不再上升
    return fr_ll(r0, c0, best[1], best[2])

def scarp_top(name, d):
    """从山心沿方位出发，找「20 km 内落差最大」的一段，取其上沿 = 崖顶。"""
    lat0, lon0 = iau(name)
    rad = float(IAU[name]["diameter"])/2
    step = 0.5
    ks = np.arange(0, rad*1.6, step)
    pts = [move(lat0, lon0, d, k) for k in ks]
    a, r0, c0 = fr_window(lat0, lon0, rad*1.7/KMPD)
    el = []
    for la, lo in pts:
        i = int((90-la)*PF) - r0; j = int((((lo+180) % 360))*PF) - c0
        el.append(a[i, j] if 0 <= i < a.shape[0] and 0 <= j < a.shape[1] else np.nan)
    el = np.convolve(np.nan_to_num(np.array(el), nan=np.nanmin(el)), np.ones(9)/9, mode="same")
    win = int(20/step)
    drop = el[:-win] - el[win:]
    drop[ks[:-win] < rad*0.4] = -1e9                         # 只在山体外缘找
    k = int(np.argmax(drop))
    return pts[max(k-2, 0)]

def floor_(lat, lon, rad_km):
    a, r0, c0 = fr_window(lat, lon, rad_km/KMPD)
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    cy, cx = a.shape[0]/2, a.shape[1]/2
    dist = np.hypot((yy-cy)/PF*KMPD, (xx-cx)/PF*KMPD*math.cos(math.radians(lat)))
    a = np.where(dist <= rad_km, a, np.nan)
    i, j = np.unravel_index(np.nanargmin(a), a.shape)
    return fr_ll(r0, c0, i, j)

def shore(mask_name, side, lat, lon, maxkm=1600):
    """离 (lat, lon) 最近、且水在指定一侧的岸线点。点本身必须在陆地上。"""
    mk = MASK[mask_name]
    r, c = m_rc(lat, lon); h = int(maxkm/KMPD*P)
    top, bot = max(r-h, 0), min(r+h, H)
    cols = np.arange(c-h, c+h) % W
    sub  = mk[top:bot][:, cols]
    land = ~ALLWATER[top:bot][:, cols]
    cand = land & ndimage.binary_dilation(sub, ST3)
    if side != "ANY":
        dy, dx = DIRS[side]
        wet = np.zeros_like(sub)
        for k in (1, 2, 3):                                  # 水在岸侧的反方向 1–3 格内
            wet |= np.roll(np.roll(sub, -dy*k, axis=0), dx*k, axis=1)
        cand &= wet
    rr, cc = np.nonzero(cand)
    if not len(rr): raise ValueError(f"{mask_name} 在 {lat:.1f},{lon:.1f} 附近 {maxkm} km 内找不到 {side} 岸")
    d = np.hypot((rr-(r-top))*KMPD/P, (cc-h)*KMPD/P*math.cos(math.radians(lat)))
    k = int(np.argmin(d))
    return m_ll(top+rr[k], (c-h+cc[k]) % W)

def comps(mk):
    lab, n = ndimage.label(mk, structure=ST3)
    return lab, n

def closest_pair(A, B):
    """两块水体最近的一对像元的中点（闸坝址）。只在两者外包框里算。"""
    rows = np.nonzero((A | B).any(1))[0]; cols = np.nonzero((A | B).any(0))[0]
    r0, r1, c0, c1 = rows.min()-5, rows.max()+6, cols.min()-5, cols.max()+6
    a, b = A[r0:r1, c0:c1], B[r0:r1, c0:c1]
    lat_mid = 90-(r0+r1)/2/P
    dist, (ir, ic) = ndimage.distance_transform_edt(~a, sampling=(1, math.cos(math.radians(lat_mid))), return_indices=True)
    br, bc = np.nonzero(b)
    k = int(np.argmin(dist[br, bc]))
    pr, pc = br[k], bc[k]; qr, qc = ir[pr, pc], ic[pr, pc]
    return m_ll(r0+(pr+qr)/2, c0+(pc+qc)/2)

def gap_west(mask_name):
    lab, n = comps(MASK[mask_name])
    sz = np.bincount(lab.ravel()); sz[0] = 0
    main = lab == int(np.argmax(sz))
    cmain = np.nonzero(main)[1].mean()
    rest = np.zeros_like(main)
    for k in range(1, n+1):
        if k != int(np.argmax(sz)) and np.nonzero(lab == k)[1].mean() < cmain: rest |= lab == k
    return closest_pair(main, rest)

def cutface(mask_name, lonE, which):
    mk = MASK[mask_name]; c = m_rc(0, lonE)[1]
    for cc in range(c, c-40, -1):                            # 截断面往西最后一列有水的
        rows = np.nonzero(mk[:, cc])[0]
        if len(rows): break
    runs = np.split(rows, np.nonzero(np.diff(rows) > 3)[0]+1)
    run = runs[0] if which == "north" else runs[-1]
    return m_ll(run.mean(), cc)

def centroid(mask_name, box=None):
    mk = MASK[mask_name]
    if box:                                                  # 只取框内的水（坎多尔湖、Hebes 这类支湖）
        la0, la1, lo0, lo1 = box
        sel = np.zeros_like(mk)
        r0, r1 = m_rc(la1, 0)[0], m_rc(la0, 0)[0]
        c0, c1 = m_rc(0, lo0)[1], m_rc(0, lo1)[1]
        sel[r0:r1, c0:c1] = True; mk = mk & sel
    rr, cc = np.nonzero(mk)
    return m_ll(rr.mean(), cc.mean())

def gap_end(a_name, b_name):
    """A、B 两块水体最近的那一对像元里，属于 A 的那一端（运河两头的船闸）。"""
    A, B = MASK[a_name], MASK[b_name]
    rows = np.nonzero((A | B).any(1))[0]; cols = np.nonzero((A | B).any(0))[0]
    r0, r1, c0, c1 = rows.min()-5, rows.max()+6, cols.min()-5, cols.max()+6
    a, b = A[r0:r1, c0:c1], B[r0:r1, c0:c1]
    lat_mid = 90-(r0+r1)/2/P
    dist = ndimage.distance_transform_edt(~b, sampling=(1, math.cos(math.radians(lat_mid))))
    ar, ac = np.nonzero(a)
    k = int(np.argmin(dist[ar, ac]))
    return m_ll(r0+ar[k], c0+ac[k])

def rim(mask_name, side, lat, lon, max_km=120):
    """先吸附到岸，再沿岸侧方向往外走，直到 10 km 内爬升不足 150 m —— 峡谷崖顶。"""
    la, lo = shore(mask_name, side, lat, lon)
    prev = fr_elev(la, lo); walked = 0
    while walked < max_km:
        la2, lo2 = move(la, lo, side, 10); z = fr_elev(la2, lo2)
        if z - prev < 150 and walked >= 20: break
        la, lo, prev, walked = la2, lo2, z, walked + 10
    return la, lo

# ── 逐条解析 ───────────────────────────────────────────────────────
rules = list(csv.DictReader(open(DATA/"地点规则.csv", encoding="utf-8-sig")))
POS = {}
METHOD_ZH = {"iau": "IAU 官方中心", "iau_edge": "IAU 地貌边缘", "summit": "MOLA 峰顶", "caldera": "MOLA 火山口",
             "caldera_rim": "MOLA 火山口缘", "scarp_top": "MOLA 崖顶", "floor": "MOLA 谷底", "map": "正典图目测",
             "point": "精确坐标", "shore": "真实岸线吸附", "inland": "岸线 + 距离", "wet_snap": "正典图位置（落水则吸附到岸）",
             "near": "相对定位", "ref_shore": "相对闸坝的岸线吸附", "gap": "水体阶梯处", "gap_west": "水体阶梯处",
             "cutface": "水库出口", "centroid": "水体质心", "orbital": "轨道",
             "gap_end": "运河端点（两级水面之间）", "rim": "峡谷崖顶"}
def ll(s): a, b = s.split(";"); return float(a), lon360(float(b))

def resolve(rule):
    kind, *args = rule.split(":")
    if kind == "iau":        return iau(args[0])
    if kind == "iau_edge":   return iau_edge(args[0], args[1])
    if kind == "summit":     return summit(args[0])
    if kind == "caldera":    return caldera(args[0])
    if kind == "caldera_rim":return caldera_rim(args[0], args[1])
    if kind == "scarp_top":  return scarp_top(args[0], args[1])
    if kind in ("map", "point"): return ll(args[0])
    if kind == "floor":      la, lo, rk = args[0].split(";"); return floor_(float(la), lon360(float(lo)), float(rk))
    if kind == "shore":      return shore(args[0], args[1], *ll(args[2]))
    if kind == "inland":     return move(*shore(args[0], args[1], *ll(args[2])), args[1], float(args[3]))
    if kind == "wet_snap":
        la, lo = ll(args[1])
        return shore(args[0], "ANY", la, lo) if MASK[args[0]][m_rc(la, lo)] else (la, lo)
    if kind == "near":       la, lo = POS[args[0]]; return move(la, lo, args[1], float(args[2]))
    if kind == "ref_shore":  la, lo = POS[args[2]]; return shore(args[0], args[1], la+0.2, lon360(lo+float(args[3])))
    if kind == "gap":        return closest_pair(MASK[args[0]], MASK[args[1]])
    if kind == "gap_west":   return gap_west(args[0])
    if kind == "cutface":    return cutface(args[0], float(args[1]), args[2])
    if kind == "centroid":   return centroid(args[0], tuple(float(x) for x in args[1].split(";")) if len(args) > 1 else None)
    if kind == "gap_end":    return gap_end(args[0], args[1])
    if kind == "rim":        return rim(args[0], args[1], *ll(args[2]))
    raise ValueError(kind)

def nearest_water(lat, lon):
    r, c = m_rc(lat, lon)
    for k in WATER_NAMES:
        if MASK[k][r, c]: return WATER_NAMES[k], 0.0, True
    best = ("—", float("inf"))
    h = int(1500/KMPD*P)
    top = max(r-h, 0); cols = np.arange(c-h, c+h) % W
    for k, zh in WATER_NAMES.items():
        sub = MASK[k][top:r+h][:, cols]
        rr, cc = np.nonzero(sub)
        if not len(rr): continue
        d = np.hypot((rr-(r-top))*KMPD/P, (cc-h)*KMPD/P*math.cos(math.radians(lat))).min()
        if d < best[1]: best = (zh, float(d))
    return best[0], best[1], False

rows_out, feats = [], []
print(f"{'id':<16s}{'纬度':>8s}{'东经':>9s}{'高程':>8s}  {'最近水体':<16s}{'离岸':>8s}{'较旧坐标偏移':>12s}  方法")
for rr_ in rules:
    kind = rr_["规则"].split(":")[0]
    lat, lon = resolve(rr_["规则"])
    POS[rr_["id"]] = (lat, lon)
    z = fr_elev(lat, lon)
    wname, wd, inwater = nearest_water(lat, lon)
    shift = gdist(lat, lon, float(rr_["旧纬度"]), float(rr_["旧东经"])) if rr_["旧纬度"].strip() else None
    status = f"水上（{wname}）" if inwater else "陆地"
    rows_out.append({
        "id": rr_["id"], "中文名": rr_["中文名"], "英文名": rr_["英文名"], "类别": rr_["类别"], "阵营": rr_["阵营"],
        "等级": rr_["等级"], "正典": rr_["正典"], "纬度": f"{lat:.3f}", "东经": f"{lon:.3f}", "西经": f"{(360-lon) % 360:.3f}",
        "SpaceEngine": f"GoTo {{ Lat {lat:.3f} Lon {((lon+180) % 360)-180:.3f} HeightKm 0 }}",
        "MOLA高程_m": f"{z:.0f}", "2100状态": status, "最近水体": wname,
        "离水_km": "0" if inwater else (f"{wd:.0f}" if wd < 1e9 else ">1500"),
        "定位方法": METHOD_ZH[kind], "规则": rr_["规则"], "依附": rr_["依附"], "正典描述": rr_["正典描述"],
        "出处": rr_["出处"], "旧纬度": rr_["旧纬度"], "旧东经": rr_["旧东经"],
        "较旧坐标偏移_km": f"{shift:.0f}" if shift is not None else ""})
    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(((lon+180) % 360)-180, 4), round(lat, 4)]},
                  "properties": {k: rows_out[-1][k] for k in ("id", "中文名", "英文名", "类别", "阵营", "等级", "正典", "MOLA高程_m", "2100状态")}})
    print(f"{rr_['id']:<16s}{lat:>8.2f}{lon:>9.2f}{z:>8.0f}  {wname:<16s}{('水上' if inwater else f'{wd:.0f} km'):>8s}"
          f"{(f'{shift:.0f} km' if shift is not None else ''):>12s}  {METHOD_ZH[kind]}")

with open(DATA/"火星地点.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0])); w.writeheader(); w.writerows(rows_out)
(OUT/"地点_2100.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")
print(f"\n→ 数据/火星地点.csv  {len(rows_out)} 条    → 产出/地点_2100.geojson")

# ── 山峰表（MOLA 峰顶实测）─────────────────────────────────────────
PEAKS = ["Olympus Mons", "Ascraeus Mons", "Arsia Mons", "Pavonis Mons", "Elysium Mons", "Alba Mons",
         "Uranius Mons", "Ceraunius Tholus", "Hecates Tholus", "Albor Tholus", "Tharsis Tholus", "Apollinaris Mons"]
with open(DATA/"火星山峰.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["山", "IAU中心纬度", "IAU中心东经", "峰顶纬度", "峰顶东经", "峰顶MOLA高程_m", "基底直径_km", "SpaceEngine"])
    for n in PEAKS:
        la, lo = summit(n); z = fr_elev(la, lo); cla, clo = iau(n)
        w.writerow([n, f"{cla:.3f}", f"{clo:.3f}", f"{la:.3f}", f"{lo:.3f}", f"{z:.0f}", IAU[n]["diameter"][:6],
                    f"GoTo {{ Lat {la:.3f} Lon {((lo+180) % 360)-180:.3f} HeightKm 0 }}"])
print("→ 数据/火星山峰.csv")

# ═══ 赤道铁路：最小代价路径 ═══════════════════════════════════════════
# 正典（ITW p.27）：大部分路段略偏赤道以南；水手峡谷一带沿海的北岸走；最后一段在
# Escalante 合龙，2100 年 7 月下旬通车。图面日期 2100 年 3 月 → Escalante 处留缺口。
# 做法：站点之间在 32 px/度 格网上跑最小代价路径。陆地代价随坡度上升；水面代价很高但有限，
# 这样实在绕不过去的窄水面会被「架桥」跨过（桥段单独标出），而不是整条路线失败。
SLOPE = np.hypot(*np.gradient(DEM32.astype(np.float32)))            # m / 格
WATER_COST = 40.0
def route(a, b, pad=3.0, prefer_lat=None):
    (la1, lo1), (la2, lo2) = a, b
    dlo = ((lo2-lo1+180) % 360)-180
    lat_top, lat_bot = max(la1, la2)+pad, min(la1, la2)-pad
    lon_w = lo1 + min(0, dlo) - pad
    ncols = int((abs(dlo)+2*pad)*P); nrows = int((lat_top-lat_bot)*P)
    r0 = int((90-lat_top)*P); c0 = int(((lon_w+180) % 360)*P)
    cols = np.arange(c0, c0+ncols) % W
    wet  = ALLWATER[r0:r0+nrows][:, cols]
    cost = 1.0 + np.clip(SLOPE[r0:r0+nrows][:, cols]/400.0, 0, 6)
    if prefer_lat is not None:                                        # 赤道段：偏离「略南于赤道」的纬度要加价
        lats = 90-(np.arange(r0, r0+nrows)+0.5)/P
        cost += 0.08*np.abs(lats-prefer_lat)[:, None]
    cost[wet] = WATER_COST
    s = (int((90-la1)*P)-r0, int((((lo1-lon_w) % 360))*P))
    e = (int((90-la2)*P)-r0, int((((lo2-lon_w) % 360))*P))
    path, _ = route_through_array(cost, s, e, fully_connected=True, geometric=True)
    out = []
    for i, j in path:
        la, lo = m_ll(r0+i, cols[j]); out.append((la, lo, bool(wet[i, j])))
    return out

def simplify(pts, every=3):
    keep = [p for k, p in enumerate(pts) if k % every == 0 or k == len(pts)-1 or p[2] != pts[max(k-1, 0)][2]]
    return keep

S = POS
EQ = -1.5                                                             # 「略偏赤道以南」
ESC = S["escalante"]
# 干线站点顺序（自 Escalante 以东绕行一圈回到 Escalante 以西）
chain = [("escalante", None), ((EQ, 135.0), EQ), ((EQ, 160.0), EQ), ((EQ, 185.0), EQ), ((EQ, 210.0), EQ),
         ((EQ, 232.0), EQ), ("new_shanghai", None), ("guxiang", None), ("hanggin_qi", None),
         ("port_lowell", None), ("vlore", None), ("chester", None), ("robinson", None),
         ((EQ, 336.0), EQ), ((EQ, 355.0), EQ), ((EQ, 15.0), EQ), ((EQ, 40.0), EQ), ((EQ, 65.0), EQ),
         ((EQ, 90.0), EQ), ((EQ, 108.0), EQ), ("escalante", None)]
pts_chain = [(S[x] if isinstance(x, str) else x, p) for x, p in chain]
trunk = []
for (a, _), (b, pref) in zip(pts_chain[:-1], pts_chain[1:]):
    seg = route(a, b, prefer_lat=pref if pref is not None else None)
    trunk.extend(seg if not trunk else seg[1:])
# Escalante 缺口：美国承建的最后一段，2100 年 7 月合龙 —— 从站点往东留 2.5°
GAP_E = 2.5
def in_gap(lo): return 0 < ((lo-ESC[1]) % 360) < GAP_E
built = [p for p in trunk if not in_gap(p[1])]
gap   = [p for p in trunk if in_gap(p[1])]

def split_runs(pts):
    """按「连续 + 桥/非桥」切成多段折线。"""
    runs, cur = [], [pts[0]]
    for p, q in zip(pts[:-1], pts[1:]):
        jump = gdist(p[0], p[1], q[0], q[1]) > 10
        if jump or q[2] != p[2]:
            if not jump: cur.append(q)
            runs.append(cur); cur = [q]
        else: cur.append(q)
    runs.append(cur)
    return [r for r in runs if len(r) > 1]

spurs = {"尼克斯奥林匹卡支线": route(S["nix_olympica"], (EQ, 226.2), prefer_lat=None),
         "Ascraeus 支线": route(S["new_shanghai"], S["aralqi"]),
         "Arsia 支线": route(S["new_shanghai"], (-6.6, 241.6)),
         "海源城支线": route(S["guxiang"], S["haiyuan"]),
         # 正典（ITW p.27）：支线通往尼克斯奥林匹卡、海拉斯、两极。海拉斯支线从干线正北接到海拉斯海北岸聚落带；
         # 接轨点正典没说，取聚落带正北的干线上。盆地壁陡，窗口放宽到 ±6° 让它能绕开陨坑。
         "海拉斯支线": route((EQ, 61.0), S["hellas_shore"], pad=6.0)}
gf = []
def line(pts, props):
    gf.append({"type": "Feature", "properties": props,
               "geometry": {"type": "LineString",
                            "coordinates": [[round(((lo+180) % 360)-180, 4), round(la, 4)] for la, lo, _ in pts]}})
for run in split_runs(simplify(built)):
    line(run, {"kind": "桥" if run[1][2] else "干线", "name": "赤道铁路"})
for run in split_runs(gap):
    line(run, {"kind": "未通车", "name": "赤道铁路 Escalante 段（2100 年 7 月合龙）"})
for n, pts in spurs.items():
    for run in split_runs(simplify(pts)):
        line(run, {"kind": "桥" if run[1][2] else "支线", "name": n})
for sid in ("new_shanghai", "guxiang", "hanggin_qi", "port_lowell", "vlore", "chester", "robinson", "escalante", "nix_olympica", "haiyuan", "aralqi",
            "hellas_shore"):
    la, lo = S[sid]
    gf.append({"type": "Feature", "properties": {"kind": "车站", "id": sid},
               "geometry": {"type": "Point", "coordinates": [round(((lo+180) % 360)-180, 4), round(la, 4)]}})
for sid in ("ius_locks_w", "ius_locks_e", "capri_dam", "eos_dam"):
    la, lo = S[sid]
    gf.append({"type": "Feature", "properties": {"kind": "闸坝", "id": sid},
               "geometry": {"type": "Point", "coordinates": [round(((lo+180) % 360)-180, 4), round(la, 4)]}})
(OUT/"基础设施_2100.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": gf}, ensure_ascii=False), encoding="utf-8")

def length(pts): return sum(gdist(p[0], p[1], q[0], q[1]) for p, q in zip(pts[:-1], pts[1:]))
bridges = [r for r in split_runs(built) if r[1][2]]
print(f"\n赤道铁路：已建 {length(built):,.0f} km ｜ Escalante 未通车段 {length(gap):,.0f} km ｜ 桥段 {len(bridges)} 处，共 {sum(length(b) for b in bridges):,.0f} km")
for b in bridges:
    print(f"   桥：{b[0][0]:+.2f},{b[0][1]:.2f} → {b[-1][0]:+.2f},{b[-1][1]:.2f}  {length(b):.0f} km")
for n, pts in spurs.items():
    print(f"   {n}：{length(pts):,.0f} km")
print("→ 产出/基础设施_2100.geojson")
