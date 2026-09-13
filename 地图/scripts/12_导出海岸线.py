#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 11_ 标定出的三海掩膜转成矢量海岸线。

产出（都在 产出/ 下）：
  海岸线_2100.geojson   经纬度（东经，火星行星中心纬度），拖进任何 GIS 都能看
  海岸线_2100.gpkg      带正确火星坐标系的 GeoPackage —— 拖进 QGIS 用这个
  海岸线_多级海侵.geojson 一组不同海平面的岸线，用来画地球化进度

运行：  ./.venv/bin/python scripts/12_导出海岸线.py
"""
import json, math, pathlib, subprocess
import numpy as np
from affine import Affine
from rasterio import features
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from scipy import ndimage

HERE    = pathlib.Path(__file__).resolve().parent
MAP_DIR = HERE.parent
OUT     = MAP_DIR / "产出"; OUT.mkdir(exist_ok=True)
R       = 3396190.0
MARS_PROJ = "+proj=longlat +R=3396190 +no_defs"      # 火星 2000 球体，东经

z = np.load(OUT / "三海掩膜.npz")
PPD = int(z["ppd"])
LEV = {"borealis": int(z["level_borealis"]), "hellas": int(z["level_hellas"]),
       "marineris": int(z["level_marineris"])}
NAME = {"borealis": "北方海 Borealis Sea", "hellas": "海拉斯海 Hellas Sea",
        "marineris": "水手峡谷海 Marineris Sea"}
# 像元 → 经纬度：左上角 (−180°E, 90°N)，每像元 1/PPD 度
TF = Affine(1/PPD, 0, -180, 0, -1/PPD, 90)

# 岸线平滑：DEM 是栅格，直接转矢量会得到锯齿。
# 0.06° ≈ 3.6 km，对一张全球图来说远小于线宽，但足以去掉台阶。
SIMPLIFY = 0.06
MIN_KM2  = {"borealis": 2000, "hellas": 500, "marineris": 200}   # 小于此的岛/湖丢掉

def vectorize(mask, min_km2, simplify=SIMPLIFY):
    """掩膜 → 简化后的多边形列表（经纬度）。"""
    # 先填掉小孔（单像元的"岛"多半是 DEM 噪声），再转矢量
    m = ndimage.binary_closing(mask, np.ones((3, 3), bool))
    polys = []
    for geom, v in features.shapes(m.astype(np.uint8), mask=m, transform=TF):
        g = shape(geom)
        # 纬度加权的粗略面积：1 平方度在赤道约 3562 km²
        km2 = g.area * (math.pi*R/180/1e3)**2 * math.cos(math.radians(g.centroid.y))
        if km2 < min_km2: continue
        g = g.simplify(simplify, preserve_topology=True)
        if not g.is_empty: polys.append((g, km2))
    polys.sort(key=lambda t: -t[1])
    return polys

feats = []
print("矢量化三海（简化容差 %.2f° ≈ %.1f km）" % (SIMPLIFY, SIMPLIFY*math.pi*R/180/1e3))
for key in ("borealis", "hellas", "marineris"):
    polys = vectorize(z[key], MIN_KM2[key])
    tot = sum(a for _, a in polys)
    print(f"  {NAME[key]:<26s} 海平面 {LEV[key]:>6d} m   {len(polys):>3d} 个多边形   "
          f"{tot/1e4:>7.1f} 万 km²   顶点 {sum(len(g.exterior.coords) for g,_ in polys):>5d}")
    for g, a in polys:
        feats.append({"type": "Feature",
                      "properties": {"sea": key, "name": NAME[key],
                                     "level_m": LEV[key], "area_km2": round(a, 1)},
                      "geometry": mapping(g)})

gj = {"type": "FeatureCollection",
      "crs_note": "火星 2000 球体 R=3396190 m，东经，行星中心纬度。"
                  "GeoJSON 规范假定地球 WGS84，这里是行星科学界的通用惯例用法。",
      "features": feats}
p = OUT / "海岸线_2100.geojson"
p.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
print(f"\n→ {p.name}  {p.stat().st_size/1024:.0f} KB")

# ── 转 GeoPackage，打上真正的火星坐标系（用 flatpak 里的 ogr2ogr）────────
gpkg = OUT / "海岸线_2100.gpkg"
gpkg.unlink(missing_ok=True)
r = subprocess.run([str(MAP_DIR/"bin"/"ogr2ogr"), "-f", "GPKG", "-a_srs", MARS_PROJ,
                    "-nln", "coastline_2100", str(gpkg), str(p)],
                   capture_output=True, text=True)
if r.returncode == 0 and gpkg.exists():
    print(f"→ {gpkg.name}  {gpkg.stat().st_size/1024:.0f} KB   坐标系已打成 {MARS_PROJ}")
else:
    print("ogr2ogr 失败：", (r.stderr or r.stdout)[-400:])

# ── 海侵序列：正典说北方海在涨，这组线就是「地球化进度条」──────────────
print("\n海侵序列（北方海，连通填充）")
dem = np.load(MAP_DIR / f"DEM/dem_{PPD}ppd_min.npy")
def borealis_at(level):
    lab, n = ndimage.label(dem < level, structure=np.ones((3, 3), bool))
    if not n: return np.zeros_like(dem, bool)
    top = lab[:int(60*PPD)]; sz = np.bincount(top.ravel()); sz[0] = 0
    return lab == int(np.argmax(sz))
seq = []
for L in (-4500, -4200, -3900, -3600, -3000, -2400, -2000):
    sea = borealis_at(L)
    polys = vectorize(sea, 5000, simplify=0.10)
    a = sum(x for _, x in polys)
    print(f"  {L:>6d} m   {a/1e4:>7.1f} 万 km²   {len(polys):>2d} 个多边形"
          + ("   ← 2100 年（11_ 标定值）" if L == LEV["borealis"] else ""))
    for g, x in polys:
        seq.append({"type": "Feature",
                    "properties": {"level_m": L, "area_km2": round(x, 1)},
                    "geometry": mapping(g)})
q = OUT / "海岸线_多级海侵.geojson"
q.write_text(json.dumps({"type": "FeatureCollection", "features": seq}, ensure_ascii=False),
             encoding="utf-8")
print(f"\n→ {q.name}  {q.stat().st_size/1024:.0f} KB")
print("\n这组线可以直接当「地球化进度」用：一张图叠七条岸线，就是从 2050 到 2150 的火星。")
