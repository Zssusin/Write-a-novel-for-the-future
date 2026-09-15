#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新上海城区图（2100 年 3 月）—— 帕弗尼斯山火山口南缘，太空电梯基座与六个穹顶。大比例尺（1 km ≈ 77 屏幕单位，
PNG 约 4.3 m/px），底图是真实轨道影像 MRO CTX 5 m（NASA Trek 瓦片，缓存在 DEM/CTX缓存/），等高线 MOLA 128 px/度。

城区几何来自 产出/土地利用_2100.geojson（22_ 按正典生成：六个直径 1.8 km 的穹顶围绕电梯基座、一号在北缘压在火山口
壁顶、七号在建、穹顶外东南侧临建区）。右栏另有一张同范围的 2198 年小图：电梯被切后坠落缆索砸毁东侧（【已定 H】），
哪几个穹顶毁、哪几个存活是建议，改 STATE_2198 即可。

数据：DEM/CTX缓存（缺瓦片联网取）、DEM 原始 MOLA、产出/土地利用_2100.geojson、数据/火星地点.csv、产出/基础设施_2100.geojson
产出：产出/新上海城区图_2100.svg / .png（3 倍）
运行：./.venv/bin/python scripts/39_新上海城区图.py
"""
import json, math, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Equirect, text_width

NAME = "新上海城区图_2100"
CACHE = M.MAP_DIR/"DEM"/"CTX缓存"; CACHE.mkdir(exist_ok=True)
TILE_URL = "https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{r}/{c}"
KMPD = M.KMPD
PLACES = {r["id"]: r for r in M.load_places()}
BASE = (float(PLACES["elevator"]["东经"]), float(PLACES["elevator"]["纬度"]))            # 电梯基座
STATION = (float(PLACES["new_shanghai"]["东经"]), float(PLACES["new_shanghai"]["纬度"]))  # 车站 / 城市符号点（坑沿最高处）
CITY_Z = float(PLACES["new_shanghai"]["MOLA高程_m"])
BREATH = 5*1609.344

DOME_FN = {1: "行政 · 小楚总部 · 移民局", 2: "商业 / 工业", 3: "住宅（上层）", 4: "住宅（中层）· 各族裔区",
           5: "住宅（下层）+ 商业", 6: "娱乐 · 日本区", 7: "在建 · 2102 年完工"}
DOME_NUM = {1: "一号", 2: "二号", 3: "三号", 4: "四号", 5: "五号", 6: "六号", 7: "七号"}
# 2198：东侧毁于坠落缆索（【已定 H】：东侧穹顶与城外临建区毁，西侧存活）。一号（北，行政）重创后封闭是建议。
STATE_2198 = {1: "重创 · 封闭", 2: "毁", 3: "毁", 4: "存活 · 应急气闸", 5: "存活", 6: "存活", 7: "毁（未完工）"}

# ── 版面 ───────────────────────────────────────────────────────────
UPK = 77.0                                     # 屏幕单位 / km
W_KM, H_KM = 16.0, 15.6
X0, Y0 = 84.0, 118.0
MW, MH = W_KM*UPK, H_KM*UPK
PPD = UPK*KMPD
LON0, LON1 = BASE[0] - 8.0/KMPD, BASE[0] + 8.0/KMPD
LAT0 = BASE[1] + 5.6/KMPD; LAT1 = LAT0 - H_KM/KMPD
P = Equirect(LON0, LON1, LAT0, LAT1, X0, Y0, PPD)
RX = X0 + MW + 44; RW = 1848 - 40 - RX
P2 = Equirect(LON0, LON1, LAT0, LAT1, RX, Y0, RW/(W_KM/KMPD))
SW, SH = 1848, int(Y0 + MH + 62)
S = SVG(SW, SH, "新上海城区图 · 2100 年 3 月")
for n in ("底图", "等高线", "铁路", "城区", "注记", "图廓", "图例", "图名", "出处"): S.layer(n)
placer = Placer((P.x0 + 2, P.y0 + 2, P.x0 + P.w - 2, P.y0 + P.h - 2))

# ── 底图：CTX 影像 ────────────────────────────────────────────────────
def tile_res(z): return 0.3515625/2**z
def fetch(z, r, c):
    f = CACHE/f"z{z}_{r}_{c}.png"
    if not f.exists() or f.stat().st_size < 1000:
        subprocess.run(["curl", "-sS", "--max-time", "60", "-A", "Mozilla/5.0", "-o", str(f), TILE_URL.format(z=z, r=r, c=c)])
    return f
def mosaic(z, lon0, lon1, lat0, lat1):
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
def flatten(img, sig, lo=200, hi=241, gain=1.05):
    mu = ndimage.gaussian_filter(img, sig); hp = img - mu
    sd = np.sqrt(ndimage.gaussian_filter(hp**2, sig)) + 2.0
    z = np.clip(hp/sd*gain, -2.5, 2.5)
    return lo + (z + 2.5)/5*(hi - lo)

print("CTX 影像（zoom 12，约 5 m/px）…")
Z12 = 12
img, res, org = mosaic(Z12, LON0 - 360 - 0.01, LON1 - 360 + 0.01, LAT0 + 0.01, LAT1 - 0.01)
img = flatten(img, 90)                                                # σ 90 px ≈ 450 m：去拼接块的明暗差，留地表纹理
SS = 3
def panel_gray(proj, ss):
    nw, nh = int(round(proj.w*ss)), int(round(proj.h*ss))
    lon = proj.lon0 + (np.arange(nw) + 0.5)/(proj.ppd*ss) - 360
    lat = proj.lat0 - (np.arange(nh) + 0.5)/(proj.ppd*ss)
    col = (lon - org[0])/res - 0.5; row = (org[1] - lat)/res - 0.5
    g = ndimage.map_coordinates(img, np.meshgrid(row, col, indexing="ij"), order=1, mode="nearest")
    rgb = np.stack([g, g*0.992, g*0.972], -1)                          # 微暖
    return np.clip(rgb, 0, 255).astype(np.uint8)
main_rgb = panel_gray(P, SS)
S.add("底图", f'<clipPath id="clipMain"><rect x="{P.x0}" y="{P.y0}" width="{P.w:.1f}" height="{P.h:.1f}"/></clipPath>')
S.add("底图", f'<image x="{P.x0}" y="{P.y0}" width="{P.w:.1f}" height="{P.h:.1f}" preserveAspectRatio="none" href="{M.png_data_uri(main_rgb, quality=88)}"/>')
S.add("底图", f'<clipPath id="clip2"><rect x="{P2.x0}" y="{P2.y0}" width="{P2.w:.1f}" height="{P2.h:.1f}"/></clipPath>')
small = np.asarray(Image.fromarray(main_rgb).resize((int(P2.w*2), int(P2.h*2)), Image.LANCZOS))
small = np.clip(small.astype(np.float32)*0.35 + 255*0.65, 0, 255).astype(np.uint8)   # 小图底图更淡
S.add("底图", f'<image x="{P2.x0}" y="{P2.y0}" width="{P2.w:.1f}" height="{P2.h:.1f}" preserveAspectRatio="none" href="{M.png_data_uri(small, quality=85)}"/>')
del img

# ── 等高线：MOLA 128 px/度 ──────────────────────────────────────────
print("等高线 …")
d = M.read_dem_window(LON0 - 0.06, LON1 + 0.06, LAT0 + 0.06, LAT1 - 0.06, 128)
sm = ndimage.gaussian_filter(d.astype(np.float64), 1.0)
to_xy = lambda rr, cc: P.xy(LON0 - 0.06 + (cc + 0.5)/128, LAT0 + 0.06 - (rr + 0.5)/128)
levels = list(range(9000, 14100, 100))
lines = {lv: M.contour_lines(sm, lv, to_xy, sigma=0, min_len=30, tol=0.6) for lv in levels}
thin = " ".join(M.path_d(p[:, 0], p[:, 1]) for lv, ls in lines.items() if lv % 500 for p in ls)
index = " ".join(M.path_d(p[:, 0], p[:, 1]) for lv, ls in lines.items() if lv % 500 == 0 for p in ls)
S.add("等高线", f'<path d="{thin}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.35" opacity="0.6" clip-path="url(#clipMain)"/>')
S.add("等高线", f'<path d="{index}" fill="none" stroke="{M.CONTOUR}" stroke-width="0.75" opacity="0.8" clip-path="url(#clipMain)"/>')
print(f"  图内 MOLA 高程 {sm.min():,.0f} – {sm.max():,.0f} m")

# ── 城区几何 ─────────────────────────────────────────────────────────
LU = [f for f in M.load_landuse() if f["properties"]["class"] == "城区" and f["properties"]["name"] == "新上海"]
domes, sprawl = {}, None
for f in LU:
    pr = f["properties"]; ring = np.asarray(f["geometry"]["coordinates"][0], float)
    if pr["kind"] in ("dome", "dome_uc"):
        n = int(pr["part"].split(" ")[0]); c = ring.mean(axis=0)
        domes[n] = dict(lon=float(c[0]), lat=float(c[1]), r_km=math.sqrt(pr["area_km2"]/math.pi), uc=pr["kind"] == "dome_uc")
    elif pr["kind"] == "sprawl": sprawl = ring
assert len(domes) == 7 and sprawl is not None, "土地利用_2100.geojson 里没有新上海的穹顶，先跑 22_土地利用.py"

def dome_svg(proj, n, dm, state=None, size_scale=1.0):
    x, y = proj.xy(dm["lon"], dm["lat"]); r = dm["r_km"]*proj.ppd/KMPD
    dead = state in ("毁", "毁（未完工）"); hurt = state and state.startswith("重创")
    out = []
    if dm["uc"] and not state:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="none" stroke="{C["ink"]}" stroke-width="0.9" stroke-dasharray="4 2.2"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*0.9:.1f}" fill="#FFFFFF" fill-opacity="0.35" stroke="{C["ink2"]}" stroke-width="0.4" stroke-dasharray="2 2"/>')
    elif dead:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="url(#ruin)" stroke="{C["alert"]}" stroke-width="0.9"' + (' stroke-dasharray="4 2.2"' if dm["uc"] else "") + '/>')
    else:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#F6F2EA" fill-opacity="0.92" stroke="{C["ink"]}" stroke-width="{1.1*size_scale:.2f}"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*0.86:.1f}" fill="none" stroke="{C["ink3"]}" stroke-width="0.45"/>')
        if hurt: out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+2.2:.1f}" fill="none" stroke="{C["alert"]}" stroke-width="1.2" stroke-dasharray="5 2.5"/>')
    return "\n".join(out), x, y, r

def gates_svg(proj, w=4.0):
    """相邻穹顶间的巨型闸门：环上按方位角排序，相邻两圆最近点之间画短粗段。"""
    ring = sorted([n for n in domes if n <= 6], key=lambda n: math.atan2(domes[n]["lat"] - BASE[1], domes[n]["lon"] - BASE[0]))
    out = []
    for a, b in zip(ring, ring[1:] + ring[:1]):
        xa, ya = proj.xy(domes[a]["lon"], domes[a]["lat"]); xb, yb = proj.xy(domes[b]["lon"], domes[b]["lat"])
        ra, rb = domes[a]["r_km"]*proj.ppd/KMPD, domes[b]["r_km"]*proj.ppd/KMPD
        dx, dy = xb - xa, yb - ya; L = math.hypot(dx, dy); ux, uy = dx/L, dy/L
        p, q = (xa + ux*ra*0.97, ya + uy*ra*0.97), (xb - ux*rb*0.97, yb - uy*rb*0.97)
        out.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="{C["ink"]}" stroke-width="{w:.1f}"/>')
        out.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="#FFFFFF" stroke-width="{w*0.35:.1f}"/>')
    return "\n".join(out)

def base_svg(proj, big=True):
    x, y = proj.xy(*BASE); u = proj.ppd/KMPD                            # 单位/km
    out = [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{1.9*u:.1f}" fill="none" stroke="{C["ink2"]}" stroke-width="0.6" stroke-dasharray="3 3"/>',     # 地下城区范围
           f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{1.5*u:.1f}" fill="url(#yard)" stroke="none"/>',                                             # 无压仓库、装卸场
           f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.55*u:.1f}" fill="#FFFFFF"/>',
           f'<rect x="{x-0.35*u:.1f}" y="{y-0.35*u:.1f}" width="{0.7*u:.1f}" height="{0.7*u:.1f}" fill="{C["ink2"]}" stroke="{C["ink"]}" stroke-width="0.8"/>',
           f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.16*u:.1f}" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.8"/>',
           f'<path d="M{x-0.16*u:.1f},{y:.1f} h{0.32*u:.1f} M{x:.1f},{y-0.16*u:.1f} v{0.32*u:.1f}" stroke="{C["ink"]}" stroke-width="0.8"/>']
    return "\n".join(out), x, y, u

S.add("城区", f'<pattern id="yard" width="3.4" height="3.4" patternUnits="userSpaceOnUse"><rect x="0.6" y="0.6" width="1.6" height="1.6" fill="{C["ink3"]}" opacity="0.75"/></pattern>'
              f'<pattern id="sprawl" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="{C["ink3"]}" stroke-width="0.8"/></pattern>'
              f'<pattern id="ruin" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><line x1="0" y1="0" x2="0" y2="4" stroke="{C["alert"]}" stroke-width="1.1"/></pattern>')

def draw_city(proj, clip, states=None, big=True):
    g = [f'<g clip-path="url(#{clip})">']
    # 临建区
    x, y = proj.xy(sprawl[:, 0], sprawl[:, 1])
    g.append(f'<path d="{M.path_d(x, y, close=True)}" fill="url(#sprawl)" fill-opacity="0.8" stroke="{C["ink2"]}" stroke-width="0.7" stroke-dasharray="2.5 1.8"/>')
    if states:   # 2198：东半临建区毁
        bx, _ = proj.xy(*BASE)
        xe = np.where(x >= bx - 0.3*proj.ppd/KMPD, x, bx - 0.3*proj.ppd/KMPD)
        g.append(f'<path d="{M.path_d(xe, y, close=True)}" fill="url(#ruin)" fill-opacity="0.9" stroke="none"/>')
    b, bx, by, u = base_svg(proj, big); g.append(b)
    g.append(gates_svg(proj, 4.0 if big else 2.2))
    for n in sorted(domes):
        d_, x, y, r = dome_svg(proj, n, domes[n], states.get(n) if states else None, 1.0 if big else 0.7); g.append(d_)
    if states:   # 坠落缆索：从基座向东砸过去
        w = 0.45*u
        g.append(f'<path d="M{bx:.1f},{by-w/2:.1f} L{proj.x0+proj.w+5:.1f},{by-w/2+0.9*u:.1f} L{proj.x0+proj.w+5:.1f},{by+w/2+0.9*u:.1f} L{bx:.1f},{by+w/2:.1f} Z" fill="{C["alert"]}" fill-opacity="0.35" stroke="{C["alert"]}" stroke-width="0.7"/>')
    g.append("</g>")
    S.add("城区", "\n".join(g))
    return bx, by, u

bx, by, u = draw_city(P, "clipMain")
draw_city(P2, "clip2", STATE_2198, big=False)

# ── 铁路（赤道铁路、两条支线、站到基座的货运线）───────────────────────
INFRA = M.load_infra()
for f in INFRA:
    if f["geometry"]["type"] != "LineString": continue
    pts = [(lo % 360, la) for lo, la in f["geometry"]["coordinates"]]
    near = [(lo, la) for lo, la in pts if LON0 - 0.15 <= lo <= LON1 + 0.15 and LAT1 - 0.15 <= la <= LAT0 + 0.15]
    if len(near) < 2: continue
    # 20_ 的布线是 32 px/度（1.85 km 格）上的最小代价路径，在这个比例尺下只是示意；穿过穹顶环的顶点丢掉，
    # 被切断的线从车站沿临建区东缘绕出去再接上
    sx_, sy_ = P.xy(*STATION)
    far = [(lo, la) for lo, la in near if M.hav_km(la, lo, BASE[1], BASE[0]) > 5.8]
    if len(far) < len(near):
        xy0 = [tuple(map(float, P.xy(lo, la))) for lo, la in far]
        if not xy0: continue
        side = 1 if np.mean([q[0] for q in xy0]) > bx else -1
        det1, det2 = (bx + side*6.4*u, sy_ - 1.2*u), (bx + side*6.4*u, by + 1.6*u)   # 站 → 沿线东行 → 贴临建区外缘北上 → 接回原线
        xy0.sort(key=lambda q: math.hypot(q[0]-det2[0], q[1]-det2[1]))
        pts_xy = [(sx_, sy_), det1, det2] + xy0
    else:
        pts_xy = [tuple(map(float, P.xy(lo, la))) for lo, la in near]
    xy = M.chaikin(pts_xy, 3)
    S.add("铁路", f'<g clip-path="url(#clipMain)">' + M.rail_svg([tuple(p) for p in xy], f["properties"]["kind"]) + "</g>")
sx, sy = P.xy(*STATION)
# 货运线：车站 → 从四号与三号之间的闸门下方以隧道进入 → 基座装卸场。环内一段画成隧道（虚线）
freight = M.chaikin([(sx, sy), (sx + 0.5*u, sy - 3.2*u), (bx + 1.5*u, by + 3.6*u), (bx + 1.25*u, by + 2.25*u), (bx + 0.7*u, by + 1.3*u)], 3)
outer = [tuple(p) for p in freight if math.hypot(p[0]-bx, p[1]-by) > 3.45*u]
inner = [tuple(p) for p in freight if math.hypot(p[0]-bx, p[1]-by) <= 3.55*u]
S.add("铁路", f'<g clip-path="url(#clipMain)">' + M.rail_svg(outer, "支线") + "</g>")
S.add("铁路", f'<path d="{M.path_d([q[0] for q in inner], [q[1] for q in inner])}" fill="none" stroke="{C["ink"]}" stroke-width="1.1" stroke-dasharray="3 2.2" clip-path="url(#clipMain)"/>')
S.add("铁路", f'<rect x="{sx-4:.1f}" y="{sy-4:.1f}" width="8" height="8" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="1.1"/>')

# ── 注记 ─────────────────────────────────────────────────────────────
def halo_text(layer, x, y, s, size, kind="cjk", fill=None, anchor="start", weight="normal", spacing=0):
    S.text(layer, x, y, s, size, kind, fill=fill, anchor=anchor, halo=2.6, weight=weight, spacing=spacing)
for n, dm in domes.items():
    x, y = P.xy(dm["lon"], dm["lat"]); r = dm["r_km"]*UPK
    halo_text("注记", x, y - 2, DOME_NUM[n], 15, "cjk_b", weight="bold", anchor="middle", spacing=2)
    halo_text("注记", x, y + 11, DOME_FN[n], 7.4, "cjk", fill=C["ink2"], anchor="middle")
    placer.block(x - r, y - r, x + r, y + r)
halo_text("注记", bx + 0.75*u, by - 0.62*u, "太空电梯基座", 11, "cjk_b", weight="bold")
halo_text("注记", bx + 0.75*u, by - 0.62*u + 10, "缆索 → 火卫二 · 2083 年建成 · 地面站建筑群", 7.2, "cjk", fill=C["ink2"])
halo_text("注记", bx, by + 0.8*u, "无压仓库 · 装卸场", 7.4, "cjk", fill=C["ink2"], anchor="middle")
halo_text("注记", bx, by + 0.8*u + 9, "（敞露于大气）", 7.0, "cjk", fill=C["ink2"], anchor="middle")
halo_text("注记", bx + 1.7*u, by + 3.15*u, "货运线 · 闸门下隧道", 7.0, "cjk", fill=C["ink2"])
sxm, sym = P.xy(float(sprawl[:, 0].mean()), float(sprawl[:, 1].mean()))
halo_text("注记", bx + 3.0*u, by + 4.9*u, "城外临建区 · 东郊", 9.5, "cjk_b", weight="bold")
halo_text("注记", bx + 3.0*u, by + 4.9*u + 10, "增压模块与集装箱住区，「以临建方式向外扩张」（正典）", 7.2, "cjk", fill=C["ink2"])
halo_text("注记", sx + 7, sy + 4, "新上海站 · 赤道铁路", 9, "cjk_b", weight="bold")
halo_text("注记", sx + 7, sy + 14, f"坑沿最高处 · {CITY_Z:,.0f} m", 7.2, "cjk", fill=C["ink2"])
# 火山口壁顶、坑底
xr, yr = P.xy(BASE[0] - 5.5/KMPD, LAT0 - 1.2/KMPD)
halo_text("注记", xr, yr, "帕弗尼斯山火山口", 11, "cjk", fill="#707070", spacing=2.5)
halo_text("注记", xr, yr + 10, "PAVONIS MONS CALDERA · 坑底 ≈ 9,300 m，比一号穹顶低 4,100 m（正典「三英里」）", 7, "lat_i", fill="#707070")
placer.block(xr, yr - 12, xr + 300, yr + 14)
n_lab = M.label_contours(S, placer, {lv: ls for lv, ls in lines.items() if lv % 500 == 0}, size=6.6, every=260, layer="等高线", fmt=lambda v: f"{v:,}")
print(f"  计曲线注记 {n_lab} 处")
# 2198 小图注记
for n, dm in domes.items():
    x, y = P2.xy(dm["lon"], dm["lat"])
    st = STATE_2198[n]; col = C["alert"] if ("毁" in st or "重创" in st) else C["ink"]
    S.text("注记", x, y + 3, DOME_NUM[n][0], 8.5, "cjk_b", fill=col, anchor="middle", halo=2, weight="bold")
b2x, b2y = P2.xy(*BASE)
S.text("注记", P2.x0 + P2.w - 6, b2y + 0.9*P2.ppd/KMPD + 14, "坠落缆索 →", 8, "cjk_b", fill=C["alert"], anchor="end", halo=2, weight="bold")

# ── 图廓、经纬刻度、比例尺 ───────────────────────────────────────────
def frame(proj, step, size, label=True):
    x0, y0, x1, y1 = proj.x0, proj.y0, proj.x0 + proj.w, proj.y0 + proj.h
    S.add("图廓", f'<rect x="{x0}" y="{y0}" width="{proj.w:.1f}" height="{proj.h:.1f}" fill="none" stroke="{C["frame"]}" stroke-width="1"/>')
    lo = math.ceil(proj.lon0/step)*step
    while lo <= proj.lon1 + 1e-9:
        x, _ = proj.xy(lo, proj.lat0)
        S.add("图廓", f'<path d="M{x:.1f},{y0} v-5 M{x:.1f},{y1} v5" stroke="{C["frame"]}" stroke-width="0.8"/>')
        S.add("图廓", f'<path d="M{x:.1f},{y0} V{y1}" stroke="{C["grat"]}" stroke-width="0.35" opacity="0.28"/>')
        if label:
            S.text("图廓", x, y0 - 8, f"{lo:.2f}°E", size, "lat", anchor="middle"); S.text("图廓", x, y1 + 14, f"{360-lo:.2f}°W", size, "lat", anchor="middle", fill=C["ink2"])
        lo += step
    la = math.ceil(proj.lat1/step)*step
    while la <= proj.lat0 + 1e-9:
        _, y = proj.xy(proj.lon0, la)
        S.add("图廓", f'<path d="M{x0},{y:.1f} h-5 M{x1},{y:.1f} h5" stroke="{C["frame"]}" stroke-width="0.8"/>')
        S.add("图廓", f'<path d="M{x0},{y:.1f} H{x1}" stroke="{C["grat"]}" stroke-width="0.35" opacity="0.28"/>')
        if label:
            t = f"{abs(la):.2f}°{'N' if la >= 0 else 'S'}" if abs(la) > 1e-9 else "0°"
            S.text("图廓", x0 - 8, y + 3, t, size, "lat", anchor="end"); S.text("图廓", x1 + 8, y + 3, t, size, "lat")
        la += step
frame(P, 0.05, 8.2); frame(P2, 0.1, 6.5, label=False)
M.scale_bar(S, "图廓", P.x0 + 16, P.y0 + P.h - 22, UPK, 1, 5, size=7.4, h=5, title=None)
S.text("图廓", P.x0 + 16 + 5*UPK + 8, P.y0 + P.h - 18, "km", 7.4, "lat")
S.text("图廓", P2.x0, P2.y0 - 8, "2198 年 · 电梯坠落之后（同范围）", 9.5, "cjk_b", weight="bold")

# ── 图名、图例、说明 ─────────────────────────────────────────────────
S.text("图名", X0, 52, "新上海", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", X0 + text_width("新上海", 30, "cjk_b", 3) + 18, 52, "电梯基座与六穹顶 · 城区图 · 2100 年 3 月", 14, "cjk", fill=C["ink2"])
S.text("图名", X0, 72, "NEW SHANGHAI · ELEVATOR BASE AND THE SIX DOMES · MARCH 2100", 8.5, "lat", fill=C["ink3"], spacing=1.6)
S.text("图名", SW - 40, 40, f"等距圆柱投影 · 1 km = {UPK:.0f} 单位（PNG 约 4.3 m/px） · 火星 2000 参考球 R = 3,396.19 km", 7.6, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", SW - 40, 54, f"全图海拔 {sm.min():,.0f}–{sm.max():,.0f} m，均在呼吸线（{BREATH:,.0f} m）以上：城外任何地方都不能呼吸", 7.6, "cjk", fill=C["ink2"], anchor="end")
S.text("图名", SW - 40, 74, "穹顶尺寸、功能、临建区为正典；穹顶的具体方位与 2198 年毁损分布为推定", 8.2, "cjk", fill=C["alert"], anchor="end")

LX, LY = RX, P2.y0 + P2.h + 34
S.text("图例", LX, LY, "图例", 11.5, "cjk_b", weight="bold")
items = [("dome", "穹顶（直径 1.8 km，正典「逾一英里」）"), ("uc", "在建穹顶（挡土环已铺好）"), ("gate", "穹顶间巨型闸门（兼应急气闸）"),
         ("base", "电梯基座 · 地面站建筑群"), ("yard", "无压仓库 · 装卸场"), ("ug", "地下城区范围"),
         ("sprawl", "城外临建区"), ("rail", "赤道铁路 / 支线 · 车站"), ("contour", "等高线 100 m · 计曲线 500 m"),
         ("ruin", "2198：毁于坠落缆索"), ("hurt", "2198：重创、封闭")]
for i, (k, t) in enumerate(items):
    y = LY + 22 + i*18; x = LX
    if k == "dome": S.add("图例", f'<circle cx="{x+9}" cy="{y-3.5}" r="6.5" fill="#F6F2EA" stroke="{C["ink"]}" stroke-width="1"/><circle cx="{x+9}" cy="{y-3.5}" r="5.5" fill="none" stroke="{C["ink3"]}" stroke-width="0.45"/>')
    elif k == "uc": S.add("图例", f'<circle cx="{x+9}" cy="{y-3.5}" r="6.5" fill="none" stroke="{C["ink"]}" stroke-width="0.9" stroke-dasharray="3 2"/>')
    elif k == "gate": S.add("图例", f'<line x1="{x+1}" y1="{y-3.5}" x2="{x+17}" y2="{y-3.5}" stroke="{C["ink"]}" stroke-width="4"/><line x1="{x+1}" y1="{y-3.5}" x2="{x+17}" y2="{y-3.5}" stroke="#FFFFFF" stroke-width="1.4"/>')
    elif k == "base": S.add("图例", f'<rect x="{x+3.5}" y="{y-9}" width="11" height="11" fill="{C["ink2"]}" stroke="{C["ink"]}" stroke-width="0.8"/><circle cx="{x+9}" cy="{y-3.5}" r="2.6" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.8"/>')
    elif k == "yard": S.add("图例", f'<rect x="{x}" y="{y-9}" width="18" height="11" fill="url(#yard)"/>')
    elif k == "ug": S.add("图例", f'<circle cx="{x+9}" cy="{y-3.5}" r="6.5" fill="none" stroke="{C["ink2"]}" stroke-width="0.6" stroke-dasharray="3 3"/>')
    elif k == "sprawl": S.add("图例", f'<rect x="{x}" y="{y-9}" width="18" height="11" fill="url(#sprawl)" stroke="{C["ink2"]}" stroke-width="0.7" stroke-dasharray="2.5 1.8"/>')
    elif k == "rail": S.add("图例", M.rail_svg([(x-1, y-3.5), (x+12, y-3.5)], "干线") + f'<rect x="{x+13}" y="{y-7}" width="6" height="6" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="0.9"/>')
    elif k == "contour": S.add("图例", f'<path d="M{x},{y-5.5} h18" stroke="{M.CONTOUR}" stroke-width="0.35" opacity="0.7"/><path d="M{x},{y-1.5} h18" stroke="{M.CONTOUR}" stroke-width="0.75" opacity="0.8"/>')
    elif k == "ruin": S.add("图例", f'<circle cx="{x+9}" cy="{y-3.5}" r="6.5" fill="url(#ruin)" stroke="{C["alert"]}" stroke-width="0.9"/>')
    elif k == "hurt": S.add("图例", f'<circle cx="{x+9}" cy="{y-3.5}" r="6.5" fill="#F6F2EA" stroke="{C["ink"]}" stroke-width="1"/><circle cx="{x+9}" cy="{y-3.5}" r="8.3" fill="none" stroke="{C["alert"]}" stroke-width="1.1" stroke-dasharray="4 2"/>')
    S.text("图例", x + 26, y, t, 8.4, "cjk")

yn = LY + 22 + len(items)*18 + 14
S.text("图例", LX, yn, "新上海数据", 11.5, "cjk_b", weight="bold")
rows = [("位置", "帕弗尼斯山火山口南缘（正典「海拔 11 英里」）"), ("海拔", f"{CITY_Z:,.0f} m · 呼吸线以上 {CITY_Z-BREATH:,.0f} m"),
        ("人口", "约 10 万，全火星 4%（正典）；每天还有人从电梯下来"), ("穹顶", "六座，直径逾一英里；七号 2102 年完工（正典）"),
        ("一号北缘", "压在火山口壁顶（MOLA）：向下 4,100 m 到坑底"), ("2198", "缆索坠落砸毁东侧；西侧靠闸门封住存活")]
for i, (a, b) in enumerate(rows):
    y = yn + 20 + i*15
    S.text("图例", LX, y, a, 8.2, "cjk", fill=C["ink2"]); S.text("图例", LX + 58, y, b, 8.2, "cjk")
yq = yn + 20 + len(rows)*15 + 12
S.text("图例", LX, yq, "注", 11.5, "cjk_b", weight="bold")
notes = ["· 底图是今天的帕弗尼斯山（MRO CTX 5 m 轨道影像），书里 2100 年的城市画在它上面。",
         "· 穹顶围绕基座的方位、临建区落在东南、地下城区半径、货运线，都是推定，",
         "　 正典只给了「六个穹顶围绕基座」「一号北缘俯瞰火山口」「二三号之间建七号」。",
         "· 一号北缘要能「向下看三英里到火山口底」，所以整个环被放在壁顶后退 0.9 km 处；",
         "　 电梯基座据此定在 0.13°N，比《火星坐标对照表》旧值北移 5 km。",
         "· 2198：正典给了物理——最接近地面的几英里缆索不会烧毁，「新上海及其东郊会严重受损」。",
         "　 哪几个穹顶毁、哪几个存活是建议（改脚本里的 STATE_2198）。"]
M.note_lines(S, "图例", LX, yq + 18, notes, size=7.8, lh=13.5)
S.text("出处", X0, SH - 22, "底图：MRO CTX 5 m 全球拼接（Caltech Murray Lab；NASA Trek / astro.arcgis.com 瓦片，局部对比归一化压成浅色）；等高线：MGS MOLA 463 m（128 px/度重采样，σ=1 平滑）；"
                          "城区：GURPS Transhuman Space《In The Well》p.21、27，几何由 22_土地利用.py 生成。", 6.8, "cjk", fill=C["ink3"])

# ── 输出 ─────────────────────────────────────────────────────────────
svg = M.OUT/f"{NAME}.svg"; png = M.OUT/f"{NAME}.png"
S.save(svg)
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB   {SW}×{SH}")
