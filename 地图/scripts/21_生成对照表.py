#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 数据/火星地点.csv、数据/火星山峰.csv、产出/基础设施_2100.geojson 渲染成 Markdown 表格，
写回 火星坐标对照表.md 里 <!-- AUTO:名字 --> … <!-- /AUTO:名字 --> 之间的位置。
正文说明是手写的，不会被覆盖；只有标记之间的表会刷新。

运行：./.venv/bin/python scripts/21_生成对照表.py
"""
import csv, json, math, pathlib, re

HERE    = pathlib.Path(__file__).resolve().parent
MAP_DIR = HERE.parent
ROOT    = MAP_DIR.parent
MD      = ROOT / "设定" / "火星坐标对照表.md"
R       = 3396190.0

rows = {r["id"]: r for r in csv.DictReader(open(MAP_DIR/"数据/火星地点.csv", encoding="utf-8-sig"))}

GROUPS = {
 "地点_战区设施": ["ius_locks_w", "ius_locks_e", "capri_dam", "eos_dam"],
 "地点_战区城镇": ["haiyuan", "hanggin_qi", "harbin", "bako", "port_lowell", "vlore", "santo_tomas", "fortuna",
                 "chester", "robinson", "anchorage", "plymouth", "burroughs", "red_lake", "fort_meier", "timbuktu", "nantong"],
 "地点_战区水体": ["lake_tithonium", "lake_candor", "hebes_lake", "lake_eos", "mutch_lake", "gangis", "echus_river", "noctis"],
 "地点_塔西斯":   ["new_shanghai", "elevator", "nix_olympica", "univ_mars", "zeus_resort", "zeus_caldera", "aralqi", "rizhao",
                 "heze", "as_sulaymi", "urumqi", "ge_gyai", "wudu", "guxiang", "liangzhen", "oita"],
 "地点_克律塞":   ["zhigansk", "sharona", "new_amsterdam", "rockwood", "viking1", "sagan", "shibetsu", "dayville", "christiana", "kasei"],
 "地点_东半球":   ["peru_core", "moyobamba", "stygis", "ica_nova", "albor_home", "clarke", "escalante", "syrtis_estates",
                 "syrtis_desert", "hellas_shore", "dao_city"],
 "地点_两极":     ["north_cap", "olympia_undae", "south_cap", "argyre", "schiaparelli"],
}
used = {i for g in GROUPS.values() for i in g}
missing = [i for i in rows if i not in used]
if missing: raise SystemExit(f"这些地点没分组：{missing}")

def fmt_int(s):
    try: return f"{int(float(s)):+,}".replace("+", "+").replace("-", "−")
    except ValueError: return s

def status(r):
    if r["2100状态"].startswith("水上"): return f"水上 · {r['最近水体']}"
    d = r["离水_km"]
    if d in ("", ">1500") or r["最近水体"] == "—": return "内陆（1,500 km 内无水）"
    d = int(float(d))
    return f"岸边 · {r['最近水体']}" if d <= 5 else f"离{r['最近水体']} {d:,} km"

def name(r):
    n = f"{r['中文名']}"
    if r["英文名"] and r["英文名"] not in r["中文名"]: n += f"<br><sub>{r['英文名']}</sub>"
    if r["等级"] == "1": n = f"**{n}**"
    if r["正典"] == "仅地图": n += " ☆"
    return n

def table(ids):
    out = ["| 地点 | 阵营 | 纬度 | 东经<br>（西经） | MOLA 高程 | 2100 年 | 定位依据 | SpaceEngine |",
           "|---|---|---:|---:|---:|---|---|---|"]
    for i in ids:
        r = rows[i]
        lat = float(r["纬度"]); lon = float(r["东经"])
        out.append(f"| {name(r)} | {r['阵营']} | {abs(lat):.2f}°{'N' if lat >= 0 else 'S'} | {lon:.2f}<br>（{float(r['西经']):.2f}°W） "
                   f"| {fmt_int(r['MOLA高程_m'])} m | {status(r)} | {r['定位方法']}：{r['依附']} | `{r['SpaceEngine']}` |")
    return "\n".join(out)

blocks = {k: table(v) for k, v in GROUPS.items()}

# 山峰
pk = list(csv.DictReader(open(MAP_DIR/"数据/火星山峰.csv", encoding="utf-8-sig")))
t = ["| 山 | 峰顶纬度 | 峰顶东经 | 峰顶高程（MOLA 实测） | 基底直径 | SpaceEngine |", "|---|---:|---:|---:|---:|---|"]
for r in pk:
    la = float(r["峰顶纬度"])
    t.append(f"| {r['山']} | {abs(la):.2f}°{'N' if la >= 0 else 'S'} | {float(r['峰顶东经']):.2f} | {fmt_int(r['峰顶MOLA高程_m'])} m "
             f"| {float(r['基底直径_km']):,.0f} km | `{r['SpaceEngine']}` |")
blocks["山峰"] = "\n".join(t)

# 旧坐标偏移
sh = [r for r in rows.values() if r["较旧坐标偏移_km"]]
sh.sort(key=lambda r: -float(r["较旧坐标偏移_km"]))
t = ["| 地点 | 旧坐标 | 新坐标 | 偏移 | 新定位依据 |", "|---|---:|---:|---:|---|"]
for r in sh[:25]:
    t.append(f"| {r['中文名']} | {float(r['旧纬度']):+.1f}, {float(r['旧东经']):.1f}E | {float(r['纬度']):+.2f}, {float(r['东经']):.2f}E "
             f"| **{float(r['较旧坐标偏移_km']):,.0f} km** | {r['定位方法']} |")
blocks["偏移"] = "\n".join(t)

# 铁路
gj = json.load(open(MAP_DIR/"产出/基础设施_2100.geojson", encoding="utf-8"))
def gdist(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2); dl = math.radians(lo2-lo1)
    x = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R/1e3*math.asin(math.sqrt(min(x, 1)))
L = {}
for f in gj["features"]:
    if f["geometry"]["type"] != "LineString": continue
    c = f["geometry"]["coordinates"]
    key = (f["properties"]["kind"], f["properties"]["name"])
    L[key] = L.get(key, 0) + sum(gdist(a, b) for a, b in zip(c[:-1], c[1:]))
trunk = sum(v for (k, n), v in L.items() if n == "赤道铁路" and k in ("干线", "桥"))
bridge = sum(v for (k, n), v in L.items() if k == "桥")
gap = sum(v for (k, n), v in L.items() if k == "未通车")
t = ["| 线路 | 长度 | 说明 |", "|---|---:|---|",
     f"| 赤道铁路干线（已通车） | {trunk:,.0f} km | 含桥段 {bridge:,.0f} km |",
     f"| Escalante 未通车段 | {gap:,.0f} km | 美国承建的最后一段，2100 年 7 月下旬合龙 |"]
for (k, n), v in sorted(L.items(), key=lambda x: x[0][1]):
    if n != "赤道铁路" and k != "未通车" and k == "支线":
        t.append(f"| {n} | {v:,.0f} km | |")
blocks["铁路"] = "\n".join(t)

md = MD.read_text(encoding="utf-8")
n_done = 0
for k, v in blocks.items():
    pat = re.compile(rf"(<!-- AUTO:{k} -->).*?(<!-- /AUTO:{k} -->)", re.S)
    md, n = pat.subn(lambda m: m.group(1) + "\n" + v + "\n" + m.group(2), md)
    if n == 0: print(f"  ⚠ 对照表里没有标记 AUTO:{k}")
    n_done += n
MD.write_text(md, encoding="utf-8")
print(f"已刷新 {n_done} 个表 → {MD.name}（地点 {len(rows)} 条，山峰 {len(pk)} 座）")
