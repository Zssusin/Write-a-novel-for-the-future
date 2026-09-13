#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火星全图（2100 年 3 月）两张：
  火星全图_摩尔威德_2100   卷首图。等积投影，中心 280°E，塔西斯与水手峡谷居中
  火星全图_等距圆柱_2100   写作参考图。0–360°E，10° 经纬网，上标东经下标西经
风格与 30_ 战区图一致。除晕渲外全矢量。
运行：./.venv/bin/python scripts/31_火星全图.py
"""
import math, subprocess, sys
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import 制图公共 as M
from 制图公共 import C, SVG, Placer, Equirect, Mollweide, text_width

Z = M.load_masks()
WATER = [("borealis", int(Z["level_borealis"])), ("hellas", int(Z["level_hellas"])),
         ("marineris_ius", int(Z["level_ius"])), ("marineris_mid", int(Z["level_marineris"])),
         ("marineris_eos", int(Z["level_eos"])), ("lake_mutch", int(Z["level_mutch"]))]
PLACES = M.load_places()
PID = {r["id"]: r for r in PLACES}
PEAKS = {r["山"]: r for r in M.load_peaks()}
INFRA = M.load_infra()

# ── 全球晕渲（16 px/度，东经 −180…180 排布）──────────────────────────
print("全球晕渲 …")
d32 = M.load_dem32().astype(np.float32)
d32[d32 > 30000] = np.nan
d16 = np.nanmean(d32.reshape(2880, 2, 5760, 2), axis=(1, 3))
m16 = {k: Z[k].reshape(2880, 2, 5760, 2).any(axis=(1, 3)) for k, _ in WATER}
RGB16 = M.relief_rgb(d16, [m16[k] for k, _ in WATER], [v for _, v in WATER], 16, zfac=5.0)

SEAS = [("北方海", "BOREALIS SEA", 66.0, 150.0, 15, 5), ("北方海", "BOREALIS SEA", 66.0, 320.0, 15, 5),
        ("克律塞湾", "CHRYSE BAY", 30.0, 322.0, 10.5, 3), ("亚马逊湾", "AMAZONIS BAY", 31.0, 196.0, 10.5, 3),
        ("Adamas 湾", "ADAMAS BAY", 44.0, 118.0, 10, 2), ("海拉斯海", "HELLAS SEA", -44.5, 62.0, 10.5, 2),
        ("水手峡谷海", "MARINERIS SEA", -18.8, 296.0, 9.5, 2)]
REGIONS = [("塔西斯", "THARSIS", 8.0, 262.0), ("伊利瑟姆", "ELYSIUM", 4.0, 158.0), ("阿拉伯高地", "ARABIA TERRA", 22.0, 8.0),
           ("大瑟提斯", "SYRTIS MAJOR", 7.0, 70.0), ("伊希斯平原", "ISIDIS PLANITIA", 15.0, 91.0),
           ("阿吉尔盆地", "ARGYRE PLANITIA", -50.0, 317.0), ("塞壬高地", "TERRA SIRENUM", -41.0, 206.0),
           ("辛梅里亚高地", "TERRA CIMMERIA", -32.0, 146.0), ("普罗米修斯高地", "PROMETHEI TERRA", -52.0, 118.0),
           ("赫斯珀里亚高原", "HESPERIA PLANUM", -20.0, 110.0), ("诺亚高地", "NOACHIS TERRA", -45.0, 350.0),
           ("珍珠高地", "MARGARITIFER TERRA", -6.0, 336.0), ("赞西高地", "XANTHE TERRA", 5.0, 305.0),
           ("滕比高地", "TEMPE TERRA", 41.0, 287.0), ("南极高原", "PLANUM AUSTRALE", -82.0, 180.0),
           ("北极冰盖", "PLANUM BOREUM", 84.5, 30.0), ("诺克提斯迷宫", "NOCTIS LABYRINTHUS", -5.0, 258.5),
           ("代达利亚高原", "DAEDALIA PLANUM", -22.0, 232.0)]
PEAK_ZH = {"Olympus Mons": "奥林匹斯山", "Ascraeus Mons": "艾斯克雷尔斯山", "Pavonis Mons": "帕弗尼斯山",
           "Arsia Mons": "阿尔西亚山", "Elysium Mons": "伊利瑟姆山", "Alba Mons": "阿尔巴山"}
POINT_CATS = {"城市", "城镇", "遗址", "军事"}

def coast_rings(seam_lon):
    """全球掩膜滚动到「接缝在两侧」后矢量化。"""
    shift = int(((seam_lon + 180) % 360)*32)
    out = []
    for k, _ in WATER:
        m = np.roll(Z[k], -shift, axis=1)
        out += M.mask_rings(m, 32, lon_left=seam_lon if seam_lon <= 180 else seam_lon-360, lat_top=90,
                            min_px=40, simplify=0.06, smooth=2)
    return out

def render(kind):
    SW, SH = 1848, 1100
    S = SVG(SW, SH, "火星全图 · 2100 年 3 月")
    if kind == "moll":
        P = Mollweide(280.0, 924.0, 548.0, 820.0)
        inside_map = lambda x, y: ((x-P.cx)/P.rx)**2 + ((y-P.cy)/P.ry)**2 <= 0.985
        MX0, MY0, MX1, MY1 = P.cx-P.rx, P.cy-P.ry, P.cx+P.rx, P.cy+P.ry
        seam = P.seam_lon()
    else:
        P = Equirect(0.0, 360.0, 90.0, -90.0, 84.0, 124.0, 1680/360)
        inside_map = lambda x, y: P.x0 <= x <= P.x0+P.w and P.y0 <= y <= P.y0+P.h
        MX0, MY0, MX1, MY1 = P.x0, P.y0, P.x0+P.w, P.y0+P.h
        seam = 0.0

    # 底图
    W3, H3 = int((MX1-MX0)*3), int((MY1-MY0)*3)
    if kind == "moll":
        yy, xx = np.mgrid[0:H3, 0:W3].astype(np.float32)
        lon, lat, ok = P.inverse(MX0 + (xx+0.5)/3, MY0 + (yy+0.5)/3)
        col = ((lon + 180) % 360)*16 - 0.5; row = (90 - lat)*16 - 0.5
        out = np.full((H3, W3, 3), 255, np.uint8)
        for ch in range(3):
            v = ndimage.map_coordinates(RGB16[..., ch].astype(np.float32), [row[ok], col[ok]], order=1, mode="wrap")
            out[..., ch][ok] = np.clip(v, 0, 255).astype(np.uint8)
        S.add("底图", f'<image x="{MX0}" y="{MY0}" width="{MX1-MX0}" height="{MY1-MY0}" preserveAspectRatio="none" href="{M.png_data_uri(out, quality=90)}"/>')
        S.add("底图", f'<clipPath id="clipMap"><ellipse cx="{P.cx}" cy="{P.cy}" rx="{P.rx}" ry="{P.ry}"/></clipPath>')
    else:
        rgb = np.roll(RGB16, -180*16, axis=1)                         # 改成 0…360°E 排布
        out = np.array(Image.fromarray(rgb).resize((W3, H3), Image.LANCZOS))
        S.add("底图", f'<image x="{MX0}" y="{MY0}" width="{MX1-MX0}" height="{MY1-MY0}" preserveAspectRatio="none" href="{M.png_data_uri(out, quality=90)}"/>')
        S.add("底图", f'<clipPath id="clipMap"><rect x="{MX0}" y="{MY0}" width="{MX1-MX0}" height="{MY1-MY0}"/></clipPath>')

    # 海岸线
    rings = coast_rings(seam)
    if kind == "equi":                                               # 等距圆柱：经度搬到 0…360
        rings = [(np.column_stack([e[:, 0] % 360 if False else e[:, 0], e[:, 1]]), h) for e, h in rings]
    S.add("海岸线", f'<path d="{M.rings_to_path(rings, P)}" fill="none" stroke="{C["coast"]}" stroke-width="0.55" stroke-linejoin="round" clip-path="url(#clipMap)"/>')

    # 经纬网
    g = []
    if kind == "moll":
        for lo in range(0, 360, 30):
            la = np.linspace(-90, 90, 181); x, y = P.xy(np.full_like(la, lo), la)
            g.append("M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y)))
        for la in range(-75, 76, 15):
            lo = np.linspace(P.lon0-179.999, P.lon0+179.999, 361); x, y = P.xy(lo, np.full_like(lo, la))
            g.append("M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y)))
        S.add("经纬网", f'<path d="{" ".join(g)}" fill="none" stroke="{C["grat"]}" stroke-width="0.35" opacity="0.28"/>')
        S.add("图廓", f'<ellipse cx="{P.cx}" cy="{P.cy}" rx="{P.rx}" ry="{P.ry}" fill="none" stroke="{C["frame"]}" stroke-width="1.0"/>')
        for la in range(-75, 76, 15):
            x, y = P.xy(P.lon0-179.999, la); x2, _ = P.xy(P.lon0+179.999, la)
            s = "0°" if la == 0 else f"{abs(la)}°{'N' if la > 0 else 'S'}"
            S.text("图廓", x-7, y+3, s, 8, "lat", anchor="end", fill=C["ink2"])
            S.text("图廓", x2+7, y+3, s, 8, "lat", anchor="start", fill=C["ink2"])
        for lo in range(0, 360, 30):
            x, y = P.xy(lo, 0)
            if abs(((lo-P.lon0+180) % 360)-180) > 170: continue
            S.text("图廓", x+2.5, y-3.5, f"{lo}°E", 7.2, "lat", fill=C["ink2"], halo=2)
    else:
        for lo in range(0, 361, 10):
            x, _ = P.xy(lo, 0) if lo < 360 else (P.x0+P.w, 0)
            g.append(f'<line x1="{x:.1f}" y1="{MY0}" x2="{x:.1f}" y2="{MY1}"/>')
        for la in range(-80, 81, 10):
            _, y = P.xy(0, la); g.append(f'<line x1="{MX0}" y1="{y:.1f}" x2="{MX1}" y2="{y:.1f}"/>')
        S.add("经纬网", f'<g stroke="{C["grat"]}" stroke-width="0.35" opacity="0.26">' + "".join(g) + "</g>")
        t = []
        for lo in range(0, 361, 5):
            x = P.x0 + lo*P.ppd; L = 6 if lo % 30 == 0 else (4 if lo % 10 == 0 else 2.5)
            t.append(f'<line x1="{x:.1f}" y1="{MY0}" x2="{x:.1f}" y2="{MY0-L}"/><line x1="{x:.1f}" y1="{MY1}" x2="{x:.1f}" y2="{MY1+L}"/>')
            if lo % 30 == 0:
                S.text("图廓", x, MY0-9, f"{lo}°E", 8.5, "lat", anchor="middle")
                S.text("图廓", x, MY1+17, f"{(360-lo) % 360}°W", 8.5, "lat", anchor="middle", fill=C["ink2"])
        for la in range(-90, 91, 5):
            y = P.y0 + (90-la)*P.ppd; L = 6 if la % 30 == 0 else (4 if la % 10 == 0 else 2.5)
            t.append(f'<line x1="{MX0}" y1="{y:.1f}" x2="{MX0-L}" y2="{y:.1f}"/><line x1="{MX1}" y1="{y:.1f}" x2="{MX1+L}" y2="{y:.1f}"/>')
            if la % 30 == 0:
                s = "0°" if la == 0 else f"{abs(la)}°{'N' if la > 0 else 'S'}"
                S.text("图廓", MX0-9, y+3, s, 8.5, "lat", anchor="end"); S.text("图廓", MX1+9, y+3, s, 8.5, "lat")
        S.add("图廓", f'<g stroke="{C["frame"]}" stroke-width="0.6">' + "".join(t) + "</g>")
        S.add("图廓", f'<rect x="{MX0}" y="{MY0}" width="{MX1-MX0}" height="{MY1-MY0}" fill="none" stroke="{C["frame"]}" stroke-width="1.0"/>')

    # 战区图范围
    lo_ = np.r_[np.linspace(238, 334, 40), np.full(20, 334.0), np.linspace(334, 238, 40), np.full(20, 238.0)]
    la_ = np.r_[np.full(40, 5.0), np.linspace(5, -20, 20), np.full(40, -20.0), np.linspace(-20, 5, 20)]
    x, y = P.xy(lo_, la_)
    S.add("图框标注", '<path d="M' + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y)) + f' Z" fill="none" stroke="{C["ink"]}" stroke-width="0.6" stroke-dasharray="3 2"/>')

    class EPlacer(Placer):
        def free(self, b, pad=1.5):
            x0, y0, x1, y1 = b
            if not all(inside_map(xx, yy) for xx, yy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))): return False
            return super().free(b, pad)
    pl = EPlacer((MX0, MY0, MX1, MY1))
    bx, by = P.xy(334, 5)
    S.text("图框标注", float(bx)+3, float(by)-3, "战区图范围", 7, "cjk", fill=C["ink2"], halo=2)
    pl.block(float(bx), float(by)-10, float(bx)+42, float(by))

    # 铁路
    for f in INFRA:
        if f["geometry"]["type"] != "LineString": continue
        for seg in M.split_line(f["geometry"]["coordinates"], P if kind == "equi" else P, max_jump_deg=1.0):
            lons = np.array([p[0] for p in seg]); lats = np.array([p[1] for p in seg])
            if kind == "moll":                                         # 摩尔威德接缝也要断
                d = ((lons - P.lon0 + 180) % 360) - 180
                cut = np.nonzero(np.abs(np.diff(d)) > 180)[0]
                parts = np.split(np.arange(len(lons)), cut+1)
            else:
                parts = [np.arange(len(lons))]
            for idx in parts:
                if len(idx) < 2: continue
                x, y = P.xy(lons[idx], lats[idx])
                S.add("铁路", f'<g clip-path="url(#clipMap)">' + M.rail_svg(list(zip(x, y)), f["properties"]["kind"]).replace("3.4", "2.6").replace("0.7 6.3", "0.6 4.4") + "</g>")

    # 闸坝（全球尺度只画符号）
    for k in ("ius_locks_w", "ius_locks_e", "capri_dam", "eos_dam"):
        x, y = P.xy(float(PID[k]["东经"]), float(PID[k]["纬度"]))
        S.add("闸坝", f'<rect x="{x-0.9:.1f}" y="{y-3:.1f}" width="1.8" height="6" fill="{C["alert"]}"/>')

    # 符号
    pts = []
    for r in PLACES:
        if r["类别"] not in POINT_CATS: continue
        x, y = P.xy(float(r["东经"]), float(r["纬度"]))
        x, y = float(x), float(y)
        if not inside_map(x, y): continue
        rad = {"1": 2.8, "2": 2.3, "3": 1.8}[r["等级"]]
        S.add("符号", M.symbol(M.faction_kind(r["阵营"]), x, y, rad, major=r["等级"] == "1"))
        br = rad + (2.4 if r["等级"] == "1" else 0) + 0.6
        pl.block(x-br, y-br, x+br, y+br)
        pts.append((r, x, y, br))
    for n, zh in PEAK_ZH.items():
        pk = PEAKS[n]; x, y = P.xy(float(pk["峰顶东经"]), float(pk["峰顶纬度"])); x, y = float(x), float(y)
        S.add("符号", f'<path d="M{x:.1f},{y-3.2:.1f} L{x+3:.1f},{y+2.1:.1f} L{x-3:.1f},{y+2.1:.1f} Z" fill="{C["ink"]}"/>')
        pl.block(x-3.5, y-3.5, x+3.5, y+2.5)

    def put_town(r, x, y, br, gap_extra=2.0):
        tier = r["等级"]; star = " ☆" if r["正典"] == "仅地图" else ""
        zs = {"1": 9.6, "2": 8.2, "3": 7.2}[tier]
        s = r["中文名"].split("（")[0].replace("维京公园·海盗 1 号着陆点", "维京公园") + star
        w = text_width(s, zs, "cjk_b" if tier == "1" else "cjk")
        got = pl.place(x, y, w, zs*1.15, gap=br+gap_extra)
        if got: S.text("城镇注记", got[0], got[1]+zs*0.98, s, zs, "cjk_b" if tier == "1" else "cjk", halo=2.1, weight="bold" if tier == "1" else "normal")
        return bool(got)

    def put_area(x, y, zh, en, zs, es, fill, sp):
        """面状注记：以给定位置为中心，上下左右小范围挪动找空位；实在没有就不放。"""
        wz = text_width(zh, zs, "cjk", sp); we = text_width(en, es, "lat_i", 0.8); w = max(wz, we)
        for dx, dy in ((0, 0), (0, -9), (0, 9), (-14, 0), (14, 0), (0, -18), (0, 18), (-28, 0), (28, 0),
                       (-28, -18), (28, -18), (-28, 18), (28, 18), (-42, 0), (42, 0), (0, -27), (0, 27)):   # 大地貌（如诺克提斯迷宫）允许挪远些
            box = (x+dx-w/2, y+dy-zs, x+dx+w/2, y+dy+es*1.6)
            if pl.free(box):
                pl.block(*box)
                S.text("面状注记", x+dx, y+dy, zh, zs, "cjk", fill=fill, anchor="middle", spacing=sp, halo=2.4)
                S.text("面状注记", x+dx, y+dy+es*1.35, en, es, "lat_i", fill=fill, anchor="middle", spacing=0.8, halo=2, italic=True)
                return True
        return False

    def put_peak(n, zh):
        pk = PEAKS[n]; x, y = P.xy(float(pk["峰顶东经"]), float(pk["峰顶纬度"])); x, y = float(x), float(y)
        e = f"{int(float(pk['峰顶MOLA高程_m'])):,} m"
        w = max(text_width(zh, 7.6, "cjk"), text_width(e, 6.2, "lat"))
        for gap in (5, 9):
            got = pl.place(x, y, w, 15.5, gap=gap)
            if got:
                S.text("城镇注记", got[0], got[1]+7.4, zh, 7.6, "cjk", halo=2)
                S.text("城镇注记", got[0], got[1]+14.6, e, 6.2, "lat", fill=C["ink2"], halo=2)
                return True
        return False

    miss = []
    order = sorted(pts, key=lambda t: (t[0]["等级"], t[0]["id"]))
    for r, x, y, br in order:                                          # ① 主要城市
        if r["等级"] == "1" and not put_town(r, x, y, br): miss.append(r)
    for zh, en, la, lo, zs, sp in SEAS:                                # ② 水体
        x, y = P.xy(lo, la)
        if not put_area(float(x), float(y), zh, en, zs, 6.4, C["water_label"], sp): print("   水体注记没放下：", zh)
    for n, zh in PEAK_ZH.items():                                      # ③ 山峰
        if not put_peak(n, zh): print("   山峰注记没放下：", zh)
    for zh, en, la, lo in REGIONS:                                     # ④ 地貌
        x, y = P.xy(lo, la)
        if not put_area(float(x), float(y), zh, en, 8.6, 5.6, "#707070", 1.8): print("   地貌注记没放下：", zh)
    for r, x, y, br in order:                                          # ⑤ 其余城镇
        if r["等级"] != "1" and not put_town(r, x, y, br): miss.append(r)
    still = []
    for r in miss:                                                     # ⑥ 放不下的加大间距再试两轮
        _, x, y, br = next(p for p in pts if p[0] is r)
        if not (put_town(r, x, y, br, gap_extra=6.0) or put_town(r, x, y, br, gap_extra=11.0)): still.append(r["中文名"])
    if still: print(f"  {kind}：没放下 {len(still)} 个城镇注记：", "、".join(still))

    # 图名
    S.text("图名", 84, 52, "火星", 30, "cjk_b", weight="bold", spacing=4)
    S.text("图名", 84 + text_width("火星", 30, "cjk_b", 4) + 18, 52,
           "地形与水系全图 · 2100 年 3 月" + ("（参考图）" if kind == "equi" else ""), 14, "cjk", fill=C["ink2"])
    S.text("图名", 84, 72, "MARS  ·  TOPOGRAPHY AND HYDROGRAPHY  ·  MARCH 2100", 8.4, "lat", fill=C["ink2"], spacing=1.6)
    RX = SW - 84
    S.text("图名", RX, 46, ("摩尔威德等积投影 · 中央经线 280°E" if kind == "moll" else "等距圆柱投影 · 0–360°E") + "  ·  火星 2000 参考球  R = 3,396.19 km", 8.2, "cjk", fill=C["ink2"], anchor="end")
    S.text("图名", RX, 60, "面积比例处处正确，距离与方向在边缘变形" if kind == "moll" else "经度：上沿东经，下沿西经（正典地图用西经）", 8.2, "cjk", fill=C["ink2"], anchor="end")
    S.text("图名", RX, 74, "海岸线测绘于 2100 年 3 月　北方海仍在上涨，本图岸线逐年失效", 8.2, "cjk", fill=C["alert"], anchor="end")

    # 图例（底部一行）
    LY = SH - 118 if kind == "moll" else MY1 + 42
    LX = 84
    items = [("cn", "锈色中国"), ("us", "火星联邦（美）"), ("corp", "企业城邦"), ("other", "独立 / 其他"),
             ("major", "主要城市"), ("dam", "闸 / 坝"), ("rail", "赤道铁路及支线"), ("gap", "未通车段（7 月合龙）"), ("peak", "山峰")]
    S.text("图例", LX, LY, "图例", 10.5, "cjk_b", weight="bold")
    for i, (k, t) in enumerate(items):
        col, row = i % 3, i // 3
        x = LX + col*150; y = LY + 20 + row*19
        if k in ("cn", "us", "corp", "other"): S.add("图例", M.symbol(k, x+8, y-3.5, 2.8))
        elif k == "major": S.add("图例", M.symbol("cn", x+8, y-3.5, 2.8, major=True))
        elif k == "dam": S.add("图例", f'<rect x="{x+7:.1f}" y="{y-7.5:.1f}" width="2" height="8" fill="{C["alert"]}"/>')
        elif k == "rail": S.add("图例", M.rail_svg([(x, y-3.5), (x+17, y-3.5)], "干线"))
        elif k == "gap": S.add("图例", M.rail_svg([(x, y-3.5), (x+17, y-3.5)], "未通车"))
        elif k == "peak": S.add("图例", f'<path d="M{x+8:.1f},{y-7:.1f} L{x+11:.1f},{y-1.5:.1f} L{x+5:.1f},{y-1.5:.1f} Z" fill="{C["ink"]}"/>')
        S.text("图例", x+24, y, t, 8.6, "cjk")
    L2 = LX + 480
    S.text("图例", L2, LY, "水面高程", 10.5, "cjk_b", weight="bold")
    for i, t in enumerate(["北方海 −3,700 m　　海拉斯海 −7,000 m　　Mutch 陨坑湖 +862 m",
                           "水手峡谷海：Ius 段 −3,300 m　中段 −3,800 m　厄俄斯湖 −3,700 m",
                           "☆ 仅见于正典地图　　正典未划定中美边界，本图不画国界"]):
        S.text("图例", L2, LY+20+i*15, t, 8.6, "cjk", fill=C["ink2"])
    L3 = LX + 1000; BW = 300
    S.text("图例", L3, LY, "高程（m）", 10.5, "cjk_b", weight="bold")
    vals = np.linspace(-8000, 20000, 160); cols = M.ramp(vals, M.HYPSO)
    stops = "".join(f'<stop offset="{i/159:.3f}" stop-color="rgb({int(c[0])},{int(c[1])},{int(c[2])})"/>' for i, c in enumerate(cols))
    S.add("图例", f'<linearGradient id="hyp{kind}">{stops}</linearGradient><rect x="{L3}" y="{LY+10}" width="{BW}" height="8" fill="url(#hyp{kind})" stroke="{C["ink"]}" stroke-width="0.5"/>')
    for v in range(-8000, 20001, 4000):
        x = L3 + (v+8000)/28000*BW
        S.add("图例", f'<line x1="{x:.1f}" y1="{LY+18}" x2="{x:.1f}" y2="{LY+21}" stroke="{C["ink"]}" stroke-width="0.5"/>')
        S.text("图例", x, LY+30, f"{v:+,}".replace("+0", "0").replace("-", "−"), 6.8, "lat", anchor="middle")
    if kind == "equi":
        kpu = M.KMPD/P.ppd
        S.text("图例", L3, LY+50, "比例尺（赤道处）", 9, "cjk_b", weight="bold")
        for i in range(4):
            x = L3 + i*500/kpu
            S.add("图例", f'<rect x="{x:.1f}" y="{LY+56}" width="{500/kpu:.1f}" height="4" fill="{C["ink"] if i % 2 == 0 else "#FFFFFF"}" stroke="{C["ink"]}" stroke-width="0.5"/>')
            S.text("图例", x, LY+70, f"{i*500:,}", 6.8, "lat", anchor="middle")
        S.text("图例", L3 + 2000/kpu, LY+70, "2,000 km", 6.8, "lat", anchor="middle")
    S.text("出处", 84, SH-22, "底图：MGS MOLA 463 m 数字高程模型（NASA GSFC · USGS Astrogeology 拼接）。地貌名：IAU 行星地名库。"
           "城镇、工程与铁路：GURPS Transhuman Space《In The Well》，位置按正典给出的地理关系在真实地形上重新确定。水位为推算值，见《火星坐标对照表》第 7 节。",
           7.0, "cjk", fill=C["ink3"])

    name = "火星全图_摩尔威德_2100" if kind == "moll" else "火星全图_等距圆柱_2100"
    svg = M.OUT/f"{name}.svg"; S.save(svg)
    png = M.OUT/f"{name}.png"
    subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
    print(f"→ {svg.name} {svg.stat().st_size/1e6:.1f} MB  ·  {png.name} {png.stat().st_size/1e6:.1f} MB")

render("moll")
render("equi")
