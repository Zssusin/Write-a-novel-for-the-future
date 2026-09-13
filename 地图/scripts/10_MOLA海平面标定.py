#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用真实 MOLA 地形标定「2100 年火星海平面」。

火星坐标对照表.md 第 6 节里的海平面高程是我从正典文字反推的，没有经过地形验证。
这个脚本拿真实 DEM 去检验它：把候选海平面代进去，看淹没结果是否与正典的几条
硬约束一致（维京公园此刻还干着、北极冰盖露出海面、Argyre 无水……）。

运行：  ./.venv/bin/python scripts/10_MOLA海平面标定.py
"""
import math, pathlib
import numpy as np
import rasterio
from rasterio.windows import Window

MAP_DIR = pathlib.Path(__file__).resolve().parent.parent
DEM     = MAP_DIR / "DEM/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
R       = 3396190.0                      # 火星参考球半径 m（IAU 2000，与 DEM 的 CRS 一致）
NODATA= -32768
AREA  = 4*math.pi*R**2 / 1e6           # 火星总表面积 km²

ds  = rasterio.open(DEM)
PPD = ds.width / 360.0                 # 128 px/deg

def probe(lonE, lat):
    """单点高程。DEM 跨 −180…180°E，所以经度先归一化。"""
    lon = ((lonE + 180) % 360) - 180
    r, c = ds.index(math.radians(lon)*R, math.radians(lat)*R)
    r = min(max(r, 0), ds.height-1); c = min(max(c, 0), ds.width-1)
    return int(ds.read(1, window=Window(c, r, 1, 1))[0, 0])

# ── 正典硬约束：这些点在 2100 年是干的还是湿的，书里写死了 ──────────────
#    (地名, 东经, 纬度, 正典状态, 出处)
CANON = [
 ("维京公园 Viking Park",      312.03,  22.48, "干", "正在修堤防海；几十年内才会被淹"),
 ("北极冰盖 Planum Boreum",      0.00,  87.00, "干", "冰盖露出海面，只有一圈窄黑沙滩"),
 ("Acidalia Planitia 中部",    340.00,  45.00, "干", "p19 图上仍是陆地"),
 ("Argyre Planitia 底",        316.00, -50.00, "干", "正典明说 Argyre 是干的"),
 ("Vastitas Borealis 深处",    240.00,  70.00, "湿", "北方海主体"),
 ("Utopia Planitia 深处",      110.00,  45.00, "湿", "Adamas 湾"),
 ("Isidis Planitia 中心",       88.00,  13.00, "干", "p20 图上是陆地"),
]

print("="*74)
print("一、DEM 自检（拿已知真值对表）")
print("="*74)
print(f"  尺寸 {ds.width}×{ds.height}  {PPD:g} px/度  {ds.res[0]:.2f} m/px  dtype {ds.dtypes[0]}")
for n, lo, la, known in [("Viking 1 着陆点", 312.03, 22.48, -3627),
                         ("北极冰盖顶",         0.00, 89.50, -2000)]:
    v = probe(lo, la)
    print(f"  {n:<16s} DEM {v:>7d} m   已知 {known:>7d} m   差 {v-known:+d} m")

print()
print("="*74)
print("二、正典硬约束点的真实高程")
print("="*74)
for n, lo, la, st, src in CANON:
    print(f"  {n:<26s} {lo:6.1f}°E {la:+6.1f}°  {probe(lo,la):>7d} m   正典：{st}  （{src}）")

# ── 阈值扫描：一遍流式读盘，同时统计所有候选海平面 ────────────────────
LEVELS = list(range(-5200, -1799, 200))
flood  = {L: 0.0 for L in LEVELS}      # 按面积权重累计的淹没量
total  = 0.0                            # 全球有效像元的面积权重总和
print()
print("="*74)
print("三、阈值扫描（按 cos(纬度) 加权，得到真实表面积占比）")
print("="*74)
STRIP = 1024                            # 按行带流式读盘，避免一次吃下 2.1 GB
for r0 in range(0, ds.height, STRIP):
    h    = min(STRIP, ds.height - r0)
    a    = ds.read(1, window=Window(0, r0, ds.width, h))
    lat  = 90.0 - (np.arange(r0, r0 + h) + 0.5) / PPD
    w    = np.cos(np.radians(lat))[:, None]   # 等距圆柱下像元真实面积 ∝ cos(lat)
    valid = a != NODATA
    total += float((valid * w).sum())
    for L in LEVELS:
        flood[L] += float((((a < L) & valid) * w).sum())

print(f"  {'海平面':>9s}{'淹没占比':>10s}{'淹没面积':>14s}   备注")
for L in LEVELS:
    f = flood[L] / total
    print(f"  {L:>7d} m{f*100:9.2f}%{f*AREA/1e6:12.2f} 亿 km²")
print(f"\n  （地球海洋占 70.8%。火星总表面积 {AREA/1e6:.2f} 亿 km²，约等于地球陆地面积）")
