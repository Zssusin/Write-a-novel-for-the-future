#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地形剖面图（2100 年 3 月）—— 三条真实 MOLA 剖面，同一张图上：
  A–A′ 水手峡谷纵剖面：诺克提斯迷宫 → Ius 船闸 → 水手峡谷海 → Capri 坝 → 克律塞湾。沿谷底走（最小代价路径）
  B–B′ 塔西斯剖面：亚马逊湾 → Liangzhen → 奥林匹斯山顶 → 尼克斯奥林匹卡 → 新上海 → 故乡 → 海源城。大圆折线
  C–C′ 南北剖面：沿 318°E 从北极到南极，经新阿姆斯特丹、Capri 坝、罗宾逊城、阿吉尔盆地
风格与系列图一致；剖面按分层设色填色，水体按水面高程填蓝。全矢量（位置图除外）。

数据：DEM/dem_32ppd_avg.npy、产出/三海掩膜.npz、数据/火星地点.csv、数据/IAU
产出：产出/地形剖面图_2100.svg  产出/地形剖面图_2100.png（3 倍，印刷用）
运行：./.venv/bin/python scripts/33_地形剖面图.py
"""
import math, subprocess, sys
import numpy as np
from scipy import ndimage
from skimage.graph import route_through_array
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, text_width

NAME = "地形剖面图_2100"
SW = 1848
STEP = 2.0                                          # 剖面采样间距 km
BREATH = 5*1609.344
BREATH_C = "#7B3F98"
PX0, PX1, PH = 150.0, SW - 116.0, 220.0              # 剖面绘图区左右边与高度

D = M.load_dem32_avg()
Z = M.load_masks()
PL = {r["id"]: r for r in M.load_places()}
PEAKS = {r["山"]: r for r in M.load_peaks()}
IAU = M.load_iau()
WATER = [("borealis", int(Z["level_borealis"]), "北方海"), ("hellas", int(Z["level_hellas"]), "海拉斯海"),
         ("marineris_ius", int(Z["level_ius"]), "Ius 段"), ("marineris_mid", int(Z["level_marineris"]), "水手峡谷海"),
         ("marineris_eos", int(Z["level_eos"]), "厄俄斯湖")]

def pt(pid): return float(PL[pid]["纬度"]), float(PL[pid]["东经"])
def iau(n): return float(IAU[n]["center_lat"]), float(IAU[n]["center_lon"]) % 360

# ── 路径 ───────────────────────────────────────────────────────────
def gc(p, q):
    """两点间大圆，按约 1 km 取点。"""
    def v(la, lo): la, lo = math.radians(la), math.radians(lo); return np.array([math.cos(la)*math.cos(lo), math.cos(la)*math.sin(lo), math.sin(la)])
    a, b = v(*p), v(*q); om = math.acos(max(-1.0, min(1.0, float(a @ b))))
    n = max(2, int(om*M.R/1e3))
    t = np.linspace(0, 1, n)[:, None]
    w = (np.sin((1-t)*om)*a + np.sin(t*om)*b)/math.sin(om)
    return np.degrees(np.arcsin(w[:, 2])), np.degrees(np.arctan2(w[:, 1], w[:, 0])) % 360

def polyline(points):
    la, lo = zip(*[gc(p, q) for p, q in zip(points[:-1], points[1:])])
    return np.concatenate(la), np.concatenate(lo)

def thalweg(points, lon0, lon1, lat0, lat1):
    """沿谷底的最小代价路径：代价随高程指数增长，所以会贴着最低处走。"""
    c0, r0 = int(((lon0+180) % 360)*32), int((90-lat0)*32)             # 不跨 180°E 的窗口
    win = D[r0:int((90-lat1)*32), c0:c0 + int((lon1-lon0)*32)].astype(np.float64)
    cost = np.exp((win - win.min())/700.0)
    rc = lambda p: (int((lat0-p[0])*32), int((p[1]-lon0)*32))
    path = []
    for p, q in zip(points[:-1], points[1:]):
        seg, _ = route_through_array(cost, rc(p), rc(q), fully_connected=True, geometric=True)
        path += seg if not path else seg[1:]
    r, c = np.array(path, float).T
    la = ndimage.uniform_filter1d(lat0 - (r+0.5)/32, 9, mode="nearest")
    lo = ndimage.uniform_filter1d(lon0 + (c+0.5)/32, 9, mode="nearest")
    return la, lo

def build(la, lo):
    lo = np.degrees(np.unwrap(np.radians(lo)))
    seg = M.hav_km(la[:-1], lo[:-1], la[1:], lo[1:]); cum = np.r_[0, np.cumsum(seg)]
    s = np.arange(0, cum[-1], STEP)
    la, lo = np.interp(s, cum, la), np.interp(s, cum, lo) % 360
    z = M.sample_lonlat(D, 32, lo, la, order=1).astype(float)
    wl = np.full(z.shape, np.nan); wname = np.full(z.shape, "", object)
    for k, lv, nm in WATER:
        m = M.sample_lonlat(Z[k], 32, lo, la, order=0).astype(bool)
        m = ndimage.binary_closing(m, np.ones(5, bool)) & (z < lv)
        wl[m] = lv; wname[m] = nm
    return dict(s=s, la=la, lo=lo, z=z, wl=wl, wname=wname)

print("剖面 A：谷底路径 …")
PA = build(*thalweg([(-7.0, 262.0), pt("ius_locks_w"), pt("ius_locks_e"), pt("capri_dam"), (22.0, 320.0)], 250, 335, 30, -22))
PB = build(*polyline([(26.5, 204.0), pt("liangzhen"), (float(PEAKS["Olympus Mons"]["峰顶纬度"]), float(PEAKS["Olympus Mons"]["峰顶东经"])),
                      pt("nix_olympica"), pt("new_shanghai"), pt("guxiang"), pt("haiyuan")]))
latc = np.linspace(89.99, -89.99, 20000)
PC = build(latc, np.full_like(latc, 318.0))
for k, p in (("A", PA), ("B", PB), ("C", PC)):
    print(f"  {k}: {p['s'][-1]:,.0f} km  最高 {p['z'].max():,.0f} m  最低 {p['z'].min():,.0f} m")

# ── 版面 ───────────────────────────────────────────────────────────
TOP0 = 560
GAPP = 350
SH = int(TOP0 + 3*GAPP - 40)
S = SVG(SW, SH, "火星地形剖面图 · 2100 年 3 月")

def draw(key, pr, top, title, zstep, dstep, feats, towns_max_km, geo_axis, water_labels=True):
    s, z, wl = pr["s"], pr["z"], pr["wl"]
    L = s[-1]
    zmin = math.floor((min(z.min(), np.nanmin(wl) if np.isfinite(wl).any() else z.min()) - 300)/zstep)*zstep
    zmax = math.ceil((z.max() + 1200)/zstep)*zstep
    xo = lambda d: PX0 + (PX1-PX0)*np.asarray(d)/L
    yo = lambda h: top + PH*(zmax - np.asarray(h))/(zmax - zmin)
    ve = (L/(PX1-PX0))/((zmax-zmin)/1e3/PH)
    pre = f"p{key}"
    pl = Placer((PX0+2, top-30, PX1-2, top+PH-2))

    # 标题行
    S.add("剖面", f'<rect x="{PX0-92}" y="{top-49}" width="22" height="22" fill="{C["ink"]}"/>')
    S.text("剖面", PX0-81, top-32.5, key, 14, "lat_b", fill="#FFFFFF", anchor="middle", weight="bold")
    S.text("剖面", PX0-62, top-32, title, 15, "cjk_b", weight="bold")
    S.text("剖面", PX0-62 + text_width(title, 15, "cjk_b") + 14, top-32,
           f"全长 {L:,.0f} km  ·  垂直夸大约 {ve:,.0f} 倍  ·  最高 {z.max():,.0f} m  ·  最低 {z.min():,.0f} m", 9, "cjk", fill=C["ink2"])
    S.text("剖面", PX0, top-8, key, 11, "lat_b", weight="bold"); S.text("剖面", PX1, top-8, key + "′", 11, "lat_b", weight="bold", anchor="end")
    pl.block(PX0, top-20, PX0+14, top); pl.block(PX1-18, top-20, PX1, top)

    # 高程网格
    g = []
    h = zmin
    while h <= zmax:
        y = float(yo(h))
        g.append(f'<line x1="{PX0}" y1="{y:.1f}" x2="{PX1}" y2="{y:.1f}"/>')
        lab = f"{h/1000:+g}".replace("+0", "0").replace("-", "−")
        S.text("剖面", PX0-7, y+3, lab, 7.6, "lat", anchor="end"); S.text("剖面", PX1+7, y+3, lab, 7.6, "lat")
        h += zstep
    S.add("剖面", f'<g stroke="{C["grat"]}" stroke-width="0.35" opacity="0.2">{"".join(g)}</g>')
    S.add("剖面", f'<text x="{PX0-36:.1f}" y="{top+PH/2:.1f}" transform="rotate(-90 {PX0-36:.1f} {top+PH/2:.1f})" font-family="{M.FAM_CJK}" '
                  f'font-size="8.4" fill="{C["ink2"]}" text-anchor="middle">高程（km）</text>')

    # 地形：按高程分层设色的竖向渐变
    hs = np.linspace(zmax, zmin, 40); cols = M.ramp(hs, M.HYPSO)*0.93
    stops = "".join(f'<stop offset="{i/39:.3f}" stop-color="rgb({int(c[0])},{int(c[1])},{int(c[2])})"/>' for i, c in enumerate(cols))
    S.add("剖面", f'<linearGradient id="{pre}g" gradientUnits="userSpaceOnUse" x1="0" y1="{yo(zmax):.1f}" x2="0" y2="{yo(zmin):.1f}">{stops}</linearGradient>')
    X, Y = xo(s), yo(z)
    ground = M.path_d(X, Y)
    S.add("剖面", f'<path d="{ground} L{PX1:.1f},{top+PH:.1f} L{PX0:.1f},{top+PH:.1f} Z" fill="url(#{pre}g)"/>')

    # 水体
    wet = np.isfinite(wl)
    lab_runs = []
    for sl in ndimage.find_objects(ndimage.label(wet)[0]):
        i0, i1 = sl[0].start, sl[0].stop
        if i1 - i0 < 2: continue
        lv = wl[i0]
        d = M.path_d(X[i0:i1], np.full(i1-i0, float(yo(lv))))
        back = M.path_d(X[i0:i1][::-1], Y[i0:i1][::-1]).replace("M", "L", 1)
        S.add("剖面", f'<path d="{d} {back} Z" fill="rgb(190,218,238)"/>')
        S.add("剖面", f'<path d="{d}" fill="none" stroke="{C["coast"]}" stroke-width="0.9"/>')
        lab_runs.append((i0, i1, lv, pr["wname"][i0]))
    S.add("剖面", f'<path d="{ground}" fill="none" stroke="{C["ink"]}" stroke-width="0.75" stroke-linejoin="round"/>')

    # 参考线
    if zmin < 0 < zmax:
        y = float(yo(0)); S.add("剖面", f'<line x1="{PX0}" y1="{y:.1f}" x2="{PX1}" y2="{y:.1f}" stroke="{C["ink2"]}" stroke-width="0.5" stroke-dasharray="1.5 2"/>')
    if zmin < BREATH < zmax:
        y = float(yo(BREATH))
        S.add("剖面", f'<line x1="{PX0}" y1="{y:.1f}" x2="{PX1}" y2="{y:.1f}" stroke="{BREATH_C}" stroke-width="0.9" stroke-dasharray="5 2.2"/>')
        t_ = "呼吸线 8,047 m（正典：5 英里以上无法呼吸）"
        w = text_width(t_, 8, "cjk")
        S.text("剖面", PX1-6, y-4, t_, 8, "cjk", fill=BREATH_C, anchor="end", halo=2.2)
        pl.block(PX1-6-w, y-13, PX1-6, y)

    S.add("剖面", f'<rect x="{PX0}" y="{top}" width="{PX1-PX0:.1f}" height="{PH}" fill="none" stroke="{C["frame"]}" stroke-width="0.9"/>')

    # 下沿：距离
    t = []
    d = 0.0
    while d <= L + 1e-6:
        x = float(xo(d)); major = abs(d/dstep - round(d/dstep)) < 1e-6
        t.append(f'<line x1="{x:.1f}" y1="{top+PH}" x2="{x:.1f}" y2="{top+PH+(6 if major else 3)}"/>')
        if major: S.text("剖面", x, top+PH+16, f"{d:,.0f}", 7.6, "lat", anchor="middle")
        d += dstep/5
    S.text("剖面", PX1, top+PH+28, "距 " + key + " 点（km）", 8, "cjk", fill=C["ink2"], anchor="end")
    # 上沿：经度或纬度
    vals = pr["lo"] if geo_axis == "lon" else pr["la"]
    step = 10
    cells = np.floor((np.degrees(np.unwrap(np.radians(vals))) if geo_axis == "lon" else vals)/step)
    for i in np.nonzero(np.diff(cells))[0]:
        x = float(xo(pr["s"][i+1]))
        v = round(((vals[i] + vals[i+1])/2)/step)*step if geo_axis == "lat" else round(vals[i+1]/step)*step % 360
        t.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top-4}"/>')
        lab = (f"{v:g}°E" if geo_axis == "lon" else ("0°" if v == 0 else f"{abs(v):g}°{'N' if v > 0 else 'S'}"))
        S.text("剖面", x, top-7, lab, 6.8, "lat", fill=C["ink2"], anchor="middle")
        pl.block(x-10, top-14, x+10, top)
    S.add("剖面", f'<g stroke="{C["frame"]}" stroke-width="0.6">{"".join(t)}</g>')

    # 水面注记
    if water_labels:
        best = {}
        for run in lab_runs:
            if run[3] not in best or run[1]-run[0] > best[run[3]][1]-best[run[3]][0]: best[run[3]] = run
        for i0, i1, lv, nm in best.values():
            if (i1-i0)*STEP < 90: continue
            xm = float(xo(s[(i0+i1)//2])); y = float(yo(lv)) + 11
            txt = f"{nm} {M.fmt_m(lv)} m"; w = text_width(txt, 7.6, "cjk")
            if w > float(xo(s[i1-1]) - xo(s[i0]))*1.6: txt = nm; w = text_width(txt, 7.6, "cjk")
            box = (xm-w/2, y-8, xm+w/2, y+2)
            if pl.free(box, 0.5):
                S.text("剖面", xm, y, txt, 7.6, "cjk", fill=C["water_label"], anchor="middle", halo=2); pl.block(*box)

    # 地貌注记：放在附近最高地面的上方
    for nm, where in feats:
        i = where if isinstance(where, int) else int(np.argmin(M.hav_km(where[0], where[1], pr["la"], pr["lo"])))
        x = float(xo(s[i])); j0, j1 = max(0, i-15), min(len(s), i+16)
        yg = float(yo(z[j0:j1].max()))
        w = text_width(nm, 8.4, "cjk")
        for dy in (8, 20, 32, 44, 56):
            y = yg - dy
            box = (x-w/2, y-9, x+w/2, y+2)
            if y - 9 > top - 28 and pl.free(box, 1):
                S.text("剖面", x, y, nm, 8.4, "cjk", fill="#666666", anchor="middle", halo=2.2); pl.block(*box)
                break

    # 聚落：投到剖面上，符号画在它自己的高程
    near = []
    for r in PL.values():
        if r["类别"] not in ("城市", "城镇", "遗址", "军事", "闸坝"): continue
        dist = M.hav_km(float(r["纬度"]), float(r["东经"]), pr["la"], pr["lo"]); i = int(np.argmin(dist))
        if dist[i] <= towns_max_km: near.append((r, i, float(dist[i])))
    half = {}
    for r, i, dd in sorted(near, key=lambda t: (t[0]["等级"], t[2])):
        x, y = float(xo(s[i])), float(yo(float(r["MOLA高程_m"])))
        if r["类别"] == "闸坝":
            S.add("剖面", f'<rect x="{x-1.3:.1f}" y="{y-6:.1f}" width="2.6" height="12" fill="{C["alert"]}"/>'); pl.block(x-2, y-6, x+2, y+6)
            half[r["id"]] = 6
        else:
            rad = {"1": 3.2, "2": 2.7, "3": 2.2}[r["等级"]]
            S.add("剖面", M.symbol(M.faction_kind(r["阵营"]), x, y, rad, major=r["等级"] == "1"))
            half[r["id"]] = rad + (2.4 if r["等级"] == "1" else 0) + 1
            pl.block(x-half[r["id"]], y-half[r["id"]], x+half[r["id"]], y+half[r["id"]])
    for r, i, dd in sorted(near, key=lambda t: (t[0]["等级"], t[2])):
        x, y = float(xo(s[i])), float(yo(float(r["MOLA高程_m"])))
        nm = r["中文名"].replace("船闸群（西闸）", "船闸（西）").replace("船闸群（东闸）", "船闸（东）")
        nm = (nm if "船闸（" in nm else nm.split("（")[0].replace("群", "")) + (" ☆" if r["正典"] == "仅地图" else "")
        if r["类别"] == "闸坝": nm = nm.replace("峡谷大坝", "坝")
        zs = 9 if r["等级"] == "1" else 8
        w = text_width(nm, zs, "cjk_b" if r["等级"] == "1" else "cjk")
        for extra in (3.5, 12, 22):                                    # 挤的地方把注记推远一点再试
            got = pl.place(x, y, w, zs*1.2, gap=half[r["id"]] + extra, order=("N", "NE", "NW", "E", "W", "SE", "SW", "S"))
            if got: break
        if got:
            S.text("剖面", got[0], got[1]+zs, nm, zs, "cjk_b" if r["等级"] == "1" else "cjk",
                   fill=C["alert"] if r["类别"] == "闸坝" else C["ink"], halo=2.2, weight="bold" if r["等级"] == "1" else "normal")
        else:
            print(f"   {key} 没放下：{nm}")
    return dict(zmin=zmin, zmax=zmax, ve=ve)

FA = [("诺克提斯迷宫", iau("Noctis Labyrinthus")), ("伊乌斯峡谷", iau("Ius Chasma")), ("美拉斯峡谷", iau("Melas Chasma")),
      ("科普来特斯峡谷", iau("Coprates Chasma")), ("厄俄斯峡谷", iau("Eos Chasma")), ("西穆德谷", iau("Simud Valles")),
      ("克律塞平原", (22.0, 320.0))]
def at(pr, lat, lon): return int(np.argmin(M.hav_km(lat, lon, pr["la"], pr["lo"])))
iO = at(PB, 17.34, 226.55)
W30 = 30                                                            # 60 km 窗口
rise60 = PB["z"][W30:iO] - PB["z"][:iO-W30]
iScarp = int(np.argmax(rise60)); SCARP = float(rise60[iScarp])
FB = [("亚马逊湾", (26.5, 204.0)), ("奥林匹斯断崖", iScarp + W30//2), ("奥林匹斯山", (17.34, 226.55)),
      ("帕弗尼斯山", (1.48, 247.04)), ("诺克提斯迷宫", iau("Noctis Labyrinthus"))]
FC = [("北极冰盖", (87.3, 318.0)), ("北方海", (60.0, 318.0)), ("克律塞湾", (30.0, 318.0)), ("赞西高地", (3.0, 318.0)),
      ("珍珠高地", (-28.0, 318.0)), ("阿吉尔盆地", (-49.8, 318.0)), ("南方高地", (-68.0, 318.0)), ("南极高原", (-85.0, 318.0))]
print("绘制 …")
IA = draw("A", PA, TOP0, "水手峡谷纵剖面（沿谷底）", 2000, 500, FA, 70, "lon")
IB = draw("B", PB, TOP0 + GAPP, "塔西斯剖面：亚马逊湾—奥林匹斯山—新上海—海源城", 5000, 500, FB, 40, "lon")
IC = draw("C", PC, TOP0 + 2*GAPP, "南北剖面：沿 318°E 从北极到南极", 2000, 1000, FC, 70, "lat")

# ── 位置图 ─────────────────────────────────────────────────────────
LX, LY, LW = 84.0, 150.0, 640.0
LHh, k = LW/2, LW/360
S.text("位置图", LX, LY-10, "剖面位置", 11.5, "cjk_b", weight="bold")
S.add("位置图", f'<image x="{LX}" y="{LY}" width="{LW}" height="{LHh}" preserveAspectRatio="none" href="{M.png_data_uri(M.thumb_rgb(), quality=90)}"/>')
g = "".join(f'<line x1="{LX+lo*k:.1f}" y1="{LY}" x2="{LX+lo*k:.1f}" y2="{LY+LHh}"/>' for lo in range(30, 360, 30)) + \
    "".join(f'<line x1="{LX}" y1="{LY+(90-la)*k:.1f}" x2="{LX+LW}" y2="{LY+(90-la)*k:.1f}"/>' for la in range(-60, 90, 30))
S.add("位置图", f'<g stroke="{C["grat"]}" stroke-width="0.3" opacity="0.3">{g}</g>')
S.add("位置图", f'<rect x="{LX}" y="{LY}" width="{LW}" height="{LHh}" fill="none" stroke="{C["frame"]}" stroke-width="0.8"/>')
for lo in range(0, 361, 60): S.text("位置图", LX+lo*k, LY+LHh+11, f"{lo}°E", 7, "lat", fill=C["ink2"], anchor="middle")
for la in (60, 30, 0, -30, -60):
    S.text("位置图", LX-5, LY+(90-la)*k+3, "0°" if la == 0 else f"{abs(la)}°{'N' if la > 0 else 'S'}", 7, "lat", fill=C["ink2"], anchor="end")
for key, pr in (("A", PA), ("B", PB), ("C", PC)):
    xs, ys = LX + pr["lo"]*k, LY + (90 - pr["la"])*k
    S.add("位置图", f'<path d="{M.path_d(xs, ys)}" fill="none" stroke="#FFFFFF" stroke-width="3.2" opacity="0.85"/>'
                    f'<path d="{M.path_d(xs, ys)}" fill="none" stroke="{C["alert"]}" stroke-width="1.4"/>')
    OFF = {"A": (-4, 14), "A′": (10, 0), "B": (-10, 0), "B′": (6, 14), "C": (9, -2), "C′": (9, 8)}
    for (xx, yy), lab in (((xs[0], ys[0]), key), ((xs[-1], ys[-1]), key + "′")):
        dx, dy = OFF[lab]
        S.add("位置图", f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="2.2" fill="{C["alert"]}"/>')
        S.text("位置图", xx+dx, yy+dy+4, lab, 10, "lat_b", fill=C["alert"], anchor="middle", weight="bold", halo=2.4)

# ── 右侧：读图要点（数字全部从剖面上量）──────────────────────────────
TX = LX + LW + 70
S.text("要点", TX, LY-10, "读图要点", 11.5, "cjk_b", weight="bold")
iN = at(PB, *pt("nix_olympica")); iS = at(PB, *pt("new_shanghai"))
sea_b = np.nonzero(np.isfinite(PB["wl"]))[0]
iShore = int(sea_b.max()) if len(sea_b) else 0
rise = PB["z"][iO] - Z["level_borealis"]
slope = math.degrees(math.atan((PB["z"][iO] - PB["z"][iN])/1e3/(PB["s"][iN] - PB["s"][iO])))
north = PC["z"][(PC["la"] > 5) & (PC["la"] < 60)].mean(); south = PC["z"][(PC["la"] < -5) & (PC["la"] > -60)].mean()
ia = at(PC, -49.8, 318.0); argyre = PC["z"][max(0, ia-150):ia+150].min()
floorA = PA["z"][(PA["lo"] > 283) & (PA["lo"] < 318)].min()
rimA = PA["z"][:60].max()
lines = [
    ("A", f"峡谷从诺克提斯迷宫的高原（约 +{rimA/1e3:.1f} km）一路降到谷底 {floorA:,.0f} m，"),
    ("", "　剖面上三级水面清楚可见：Ius 段 −3,300 m 高出中段 500 m，靠两座船闸拦住；"),
    ("", "　Capri 坝下就是北方海的克律塞湾南支，坝上坝下水面同为 −3,700 m。"),
    ("B", f"从亚马逊湾海面到奥林匹斯山顶，高差 {rise/1e3:.1f} km，水平距离只有 {PB['s'][iO]-PB['s'][iShore]:,.0f} km。"),
    ("", f"　山顶到尼克斯奥林匹卡 {PB['s'][iN]-PB['s'][iO]:,.0f} km，平均坡度只有 {slope:.1f}°——火星的巨山是缓坡，"),
    ("", f"　站在山坡上看不出自己在山上；真正陡的是山脚的断崖，剖面上 60 km 内拔起 {SCARP/1e3:.1f} km。"),
    ("", f"　新上海（{float(PL['new_shanghai']['MOLA高程_m']):,.0f} m）比尼克斯奥林匹卡高 {(float(PL['new_shanghai']['MOLA高程_m']) - float(PL['nix_olympica']['MOLA高程_m']))/1e3:.1f} km，远在呼吸线以上。"),
    ("C", f"北半球低、南半球高：沿这条经线，5–60°N 平均 {north:,.0f} m，5–60°S 平均 {south:,.0f} m，"),
    ("", f"　相差 {(south-north)/1e3:.1f} km——北方海能存在，靠的就是这道「南北二分」。阿吉尔盆地底 {argyre:,.0f} m，没有水。"),
    ("注", "剖面的垂直方向都做了夸大（每条标出倍数），真实比例下这些起伏几乎是一条平线。"),
    ("", "　聚落符号画在它自己的高程上，离剖面线远的（如崖顶城镇）会浮在谷底之上。"),
]
y = LY + 12
for tag, t_ in lines:
    if tag:
        y += 8
        if tag in "ABC":
            S.add("要点", f'<rect x="{TX}" y="{y-10}" width="14" height="14" fill="{C["ink"]}"/>')
            S.text("要点", TX+7, y+1.2, tag, 9, "lat_b", fill="#FFFFFF", anchor="middle", weight="bold")
        else:
            S.text("要点", TX, y, tag, 9.4, "cjk_b", weight="bold")
    S.text("要点", TX + 22 + (9*1.0 if t_.startswith("　") else 0), y, t_.lstrip("　"), 9.2, "cjk", fill=C["ink"] if tag else C["ink2"])
    y += 16
y += 14
S.text("要点", TX, y, "图例", 9.6, "cjk_b", weight="bold")
lg = [("water", "水体（按推算水面高程）"), ("breath", "呼吸线 8,047 m"), ("datum", "0 m 火星大地水准面"),
      ("dam", "闸 / 坝"), ("cn", "锈色中国"), ("us", "火星联邦（美）"), ("other", "独立 / 其他"), ("corp", "企业城邦")]
for i, (kk, t_) in enumerate(lg):
    xx = TX + (i % 4)*236; yy = y + 20 + (i // 4)*19
    if kk == "water": S.add("要点", f'<rect x="{xx}" y="{yy-9}" width="18" height="10" fill="rgb(190,218,238)" stroke="{C["coast"]}" stroke-width="0.6"/>')
    elif kk == "breath": S.add("要点", f'<path d="M{xx},{yy-4} h18" stroke="{BREATH_C}" stroke-width="1" stroke-dasharray="5 2.2"/>')
    elif kk == "datum": S.add("要点", f'<path d="M{xx},{yy-4} h18" stroke="{C["ink2"]}" stroke-width="0.6" stroke-dasharray="1.5 2"/>')
    elif kk == "dam": S.add("要点", f'<rect x="{xx+7.7}" y="{yy-9}" width="2.6" height="10" fill="{C["alert"]}"/>')
    else: S.add("要点", M.symbol(kk, xx+9, yy-4, 3.0))
    S.text("要点", xx+26, yy, t_, 8.6, "cjk")

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", 84, 52, "地形剖面", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", 84 + text_width("地形剖面", 30, "cjk_b", 3) + 18, 52, "水手峡谷 · 塔西斯 · 南北纵贯 · 2100 年 3 月", 14, "cjk", fill=C["ink2"])
S.text("图名", 84, 72, "MARS  ·  TOPOGRAPHIC PROFILES  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
S.text("图名", SW-84, 46, "高程取自 MOLA 数字高程模型（32 px/度），剖面每 2 km 采样一次", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", SW-84, 60, "A 线为沿谷底的最低路径；B 线为大圆折线，转折于各城镇；C 线为 318°E 经线", 8.2, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", SW-84, 74, "水面高程为按真实地形推算的值（2100 年 3 月）", 8.2, "cjk", fill=C["alert"], anchor="end")
S.text("出处", 84, SH-18, "高程：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接）。地貌名：IAU 行星地名库。"
       "城镇与工程：GURPS Transhuman Space《In The Well》，位置按正典给出的地理关系在真实地形上重新确定。", 7.0, "cjk", fill=C["ink3"])

svg = M.OUT/f"{NAME}.svg"; S.save(svg)
png = M.OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
