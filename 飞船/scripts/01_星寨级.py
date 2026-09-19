#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星寨级空间支配载具识别图 —— 系列图第一张飞船技术图。
右舷侧视图、俯视图（散热翼展开）、前视图、纵剖空间分配，全部同比例；参照物 054A 型护卫舰。

数据：GURPS Transhuman Space《Spacecraft of the Solar System》p.35–36（星寨级）、
      《In The Well》p.107（正阳级 AKV）、核心书 p.173–189（设计规则：1 格 = 500 立方英尺）。
      TS 只给船体形状与总尺寸、散热翼尺寸、机库内径、模块清单和各面装甲；部件沿船身的位置按正典对同代
      SDV-90 的描述排（机库与舰桥在前、燃料罐居中、驱动在尾，TS p.192）。
产出：飞船/产出/飞船识别图_星寨级.svg  飞船/产出/飞船识别图_星寨级.png（3 倍）
运行：在项目根目录 地图/.venv/bin/python 飞船/scripts/01_星寨级.py
      字体、配色、SVG 工具借用 地图/scripts/制图公共.py，不读任何地形数据。
"""
import math, pathlib, subprocess, sys
SHIP_DIR = pathlib.Path(__file__).resolve().parents[1]                 # 飞船/
OUT = SHIP_DIR / "产出"
sys.path.insert(0, str(SHIP_DIR.parent / "地图" / "scripts"))
import 制图公共 as M
from 制图公共 import C, SVG, text_width

NAME = "飞船识别图_星寨级"
SW, SH = 1848, 1685
FT = 0.3048
SPACE_M3 = 500*FT**3                                   # 1 格 = 500 cf = 14.16 m³

# ── 船（米）──────────────────────────────────────────────────────────
L, R = 350*FT, 30*FT                                   # 106.7 m × 半径 9.14 m
WING = 141*FT                                          # 散热翼 43 × 43 m
X_FWD, X_TANK, X_DRV = 1.5, 22.0, 96.0                 # 艏板 | 前段 | 燃料段 | 驱动段
NOZ = 11.5                                             # 磁喷管长度
WING_X0 = X_DRV - WING - 2                             # 散热翼沿船身位置（靠近驱动）
HANGAR = (55*FT, 20*FT)                                # 机库门 16.8 × 6.1 m
AKV_L, AKV_W = 37.5*FT, 10*FT                          # 正阳 AKV 11.4 × 3.0 m
PB_L = 300*FT                                          # 粒子束 91.4 m
SPACES = dict(hull=2016, tanks=1500, drive=200, hangar=55, bays=36, reactor=20.5, quarters=4*4+6*2, misc=40)

# ── 版面 ──────────────────────────────────────────────────────────
S_PX = 7.5                                             # 屏幕单位 / 米
X0 = 132                                               # 艏在屏幕上的 x
YA = 262                                               # 侧视图轴线
YSEC = 430                                             # 纵剖条
YREF = 722                                             # 参照物水线
YB = 1202                                              # 俯视图轴线
FX, FY = 1330, 250                                     # 前视图圆心
INK, INK2, INK3 = C["ink"], C["ink2"], C["ink3"]
HULL_F, ARMOR_F, RAD_F, DARK_F = "#F3F3F1", "#CFCFCB", "#FAFAF8", "#B9B9B5"
S = SVG(SW, SH, "星寨级空间支配载具 · 识别图")

def px(xm): return X0 + xm*S_PX
def rect(layer, x, y, w, h, fill="none", stroke=INK, sw=0.8, extra=""):
    S.add(layer, f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{extra}/>')
def line(layer, x1, y1, x2, y2, stroke=INK, sw=0.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.add(layer, f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" stroke="{stroke}" stroke-width="{sw}" fill="none"{d}/>')
def circ(layer, x, y, r, fill="none", stroke=INK, sw=0.7):
    S.add(layer, f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def path(layer, d, fill="none", stroke=INK, sw=0.8, extra=""):
    S.add(layer, f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"{extra}/>')
def hatch(layer, x, y, w, h, step=4.2, sw=0.35, stroke=INK3):
    """斜线阴影，裁在矩形内。"""
    gid = f"h{int(x)}_{int(y)}"
    S.add(layer, f'<clipPath id="{gid}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/></clipPath>')
    d = "".join(f"M{x+i:.1f},{y:.1f} l{-h:.1f},{h:.1f} " for i in [k*step for k in range(int((w+h)/step)+2)])
    S.add(layer, f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" clip-path="url(#{gid})"/>')

def dim(layer, x1, y1, x2, y2, label, off=0, size=8.2, side="above"):
    """尺寸线：两端短界线 + 斜刻度，文字在线上方。"""
    vert = abs(x2-x1) < abs(y2-y1)
    if vert:
        line(layer, x1-4, y1, x1+4, y1, sw=0.5); line(layer, x2-4, y2, x2+4, y2, sw=0.5)
        line(layer, x1, y1, x2, y2, sw=0.5)
        for yy in (y1, y2): line(layer, x1-2.5, yy+2.5, x1+2.5, yy-2.5, sw=0.7)
        S.add(layer, f'<text x="{x1-5:.1f}" y="{(y1+y2)/2:.1f}" font-family="{M.FAM_LAT}" font-size="{size}" fill="{INK}" '
                     f'text-anchor="middle" transform="rotate(-90 {x1-5:.1f} {(y1+y2)/2:.1f})">{M.esc(label)}</text>')
    else:
        line(layer, x1, y1-4, x1, y1+4, sw=0.5); line(layer, x2, y2-4, x2, y2+4, sw=0.5)
        line(layer, x1, y1, x2, y2, sw=0.5)
        for xx in (x1, x2): line(layer, xx-2.5, y1+2.5, xx+2.5, y1-2.5, sw=0.7)
        S.text(layer, (x1+x2)/2, y1 - 3 if side == "above" else y1 + size + 2, label, size, "lat", anchor="middle")

def callout(layer, n, x, y, tx, ty):
    """编号泡 + 引线（引线端点在部件上）。"""
    line(layer, x, y, tx, ty, sw=0.5)
    circ(layer, tx, ty, 6.2, fill="#FFFFFF", sw=0.7)
    S.text(layer, tx, ty+3, str(n), 7.6, "lat_b", anchor="middle", weight="bold")

def view_title(layer, key, x, y, title, sub=""):
    S.add(layer, f'<rect x="{x}" y="{y-14}" width="18" height="18" fill="{INK}"/>')
    S.text(layer, x+9, y, key, 11, "lat_b", fill="#FFFFFF", anchor="middle", weight="bold")
    S.text(layer, x+26, y, title, 12.5, "cjk_b", weight="bold")
    if sub: S.text(layer, x+26 + text_width(title, 12.5, "cjk_b") + 10, y, sub, 8.6, "cjk", fill=INK2)

# ── 共用部件：船身轮廓（侧视 / 俯视共用，y 为屏幕轴线）──────────────────
def hull_outline(layer, yc, top_view):
    r = R*S_PX
    # 主体
    rect(layer, px(0), yc-r, L*S_PX, 2*r, fill=HULL_F, sw=0.9)
    # 艏板：外凸 1.5 m 的厚装甲，实色
    d = f"M{px(0):.1f},{yc-r:.1f} A{1.5*S_PX:.1f},{r:.1f} 0 0 0 {px(0):.1f},{yc+r:.1f} Z"
    path(layer, d, fill=ARMOR_F, sw=0.9)
    rect(layer, px(0), yc-r, X_FWD*S_PX, 2*r, fill=ARMOR_F, sw=0.0)
    line(layer, px(X_FWD), yc-r, px(X_FWD), yc+r, sw=0.9)
    # 分段线
    for xm in (X_TANK, X_DRV): line(layer, px(xm), yc-r, px(xm), yc+r, sw=0.7)
    # 燃料段外壳 = 船体散热板：纵向细线 + 每 10 m 一道环肋
    x0, x1 = px(X_TANK), px(X_DRV)
    rect(layer, x0, yc-r, x1-x0, 2*r, fill=RAD_F, sw=0.0)
    for k in range(1, 12):
        yy = yc - r + 2*r*k/12
        line(layer, x0+3, yy, x1-3, yy, stroke=INK3, sw=0.3)
    for xm in range(int(X_TANK)+8, int(X_DRV)-2, 10):
        line(layer, px(xm), yc-r, px(xm), yc+r, stroke=INK2, sw=0.4)
    # 驱动段：深一点，环肋密
    rect(layer, px(X_DRV), yc-r, (L-X_DRV)*S_PX, 2*r, fill=DARK_F, sw=0.0)
    for xm in (X_DRV+3, X_DRV+6, X_DRV+9): line(layer, px(xm), yc-r, px(xm), yc+r, stroke=INK2, sw=0.4)
    rect(layer, px(0), yc-r, L*S_PX, 2*r, fill="none", sw=0.9)
    # 磁喷管：从 0.75R 张到 1.2R
    r0, r1 = 0.78*r, 1.18*r
    d = (f"M{px(L):.1f},{yc-r0:.1f} L{px(L+NOZ):.1f},{yc-r1:.1f} L{px(L+NOZ):.1f},{yc+r1:.1f} "
         f"L{px(L):.1f},{yc+r0:.1f} Z")
    path(layer, d, fill="#E4E4E1", sw=0.9)
    for k in range(1, 6):
        t = k/6; xx = px(L + NOZ*t); rr = r0 + (r1-r0)*t
        line(layer, xx, yc-rr, xx, yc+rr, stroke=INK2, sw=0.35)
    line(layer, px(L+NOZ), yc-r1, px(L+NOZ), yc+r1, sw=1.4)
    # 姿态推进器组：驱动段前缘四组，侧视/俯视各见两组
    for sgn in (-1, 1):
        rect(layer, px(X_DRV-2.5), yc + sgn*r - (0 if sgn < 0 else 4.5), 2.0*S_PX, 4.5, fill=DARK_F, sw=0.6)
        rect(layer, px(X_DRV-2.5), yc + sgn*(r+2.6) - 1.3, 2.0*S_PX, 2.6, fill=INK, sw=0)
    # 出入口（对接环）×2：前段上下；俯视时只见轮廓
    for sgn in (-1, 1):
        yy = yc + sgn*r
        if not top_view:
            rect(layer, px(24.5), yy - (5.5 if sgn < 0 else 0), 3.2*S_PX, 5.5, fill=HULL_F, sw=0.7)
        else:
            rect(layer, px(24.5), yy-3.2*S_PX/2, 3.2*S_PX, 3.2*S_PX, fill="none", sw=0.5, extra=' stroke-dasharray="1.5 1.5"')

def towers(layer, yc, top_view):
    """重激光塔 ×6（可缩回，3 上 3 下）、轻激光 ×8（4 左 4 右，固定泡）、艉轻激光 ×2。
    侧视：塔在上下缘，轻激光泡在轴线上。俯视：塔投影成轴线上的方块，轻激光泡在左右缘。"""
    r = R*S_PX
    heavy = [(30, -1), (42, 1), (55, -1), (67, 1), (80, -1), (91, 1)]
    light = [28, 48, 68, 88]
    for xm, sgn in heavy:
        if not top_view:
            yy = yc + sgn*r
            rect(layer, px(xm)-1.1*S_PX, yy - (2.6*S_PX if sgn < 0 else 0), 2.2*S_PX, 2.6*S_PX, fill=HULL_F, sw=0.8)
            rect(layer, px(xm)-0.55*S_PX, yy - (3.4*S_PX if sgn < 0 else 2.6*S_PX), 1.1*S_PX, 0.8*S_PX, fill=INK, sw=0)
        else:
            rect(layer, px(xm)-1.1*S_PX, yc-1.1*S_PX, 2.2*S_PX, 2.2*S_PX, fill="#FFFFFF", sw=0.8)
            circ(layer, px(xm), yc, 0.55*S_PX, fill=INK, sw=0)
    for xm in light:
        if not top_view:
            circ(layer, px(xm), yc, 1.0*S_PX, fill="#FFFFFF", sw=0.7); circ(layer, px(xm), yc, 0.35*S_PX, fill=INK, sw=0)
        else:
            for sgn in (-1, 1):
                yy = yc + sgn*r
                path(layer, f"M{px(xm)-1.0*S_PX:.1f},{yy:.1f} A{1.0*S_PX:.1f},{0.55*S_PX:.1f} 0 0 {1 if sgn<0 else 0} {px(xm)+1.0*S_PX:.1f},{yy:.1f} Z",
                     fill="#FFFFFF", sw=0.7)
    # 艉轻激光 ×2：驱动段前缘，左右
    for sgn in (-1, 1):
        if top_view:
            yy = yc + sgn*r
            path(layer, f"M{px(X_DRV+1)-0.9*S_PX:.1f},{yy:.1f} A{0.9*S_PX:.1f},{0.5*S_PX:.1f} 0 0 {1 if sgn<0 else 0} {px(X_DRV+1)+0.9*S_PX:.1f},{yy:.1f} Z",
                 fill="#FFFFFF", sw=0.7)
    if not top_view:
        circ(layer, px(X_DRV+1), yc, 0.9*S_PX, fill="#FFFFFF", sw=0.7); circ(layer, px(X_DRV+1), yc, 0.3*S_PX, fill=INK, sw=0)

def sensors(layer, yc, top_view):
    """艏部传感器：大型被动阵列 ×2（上下，长条）、中型雷达 ×2（左右，圆泡）、中型雷达激光 ×3。"""
    r = R*S_PX
    if not top_view:
        for sgn in (-1, 1):                                    # PESA 上下
            yy = yc + sgn*r
            path(layer, f"M{px(3.0):.1f},{yy:.1f} A{2.0*S_PX:.1f},{0.8*S_PX:.1f} 0 0 {1 if sgn<0 else 0} {px(7.0):.1f},{yy:.1f} Z", fill="#FFFFFF", sw=0.7)
        circ(layer, px(5.0), yc, 1.3*S_PX, fill="#FFFFFF", sw=0.7)                       # 右舷雷达
        circ(layer, px(5.0), yc, 0.4*S_PX, fill="none", sw=0.5)
        for yy in (yc - 0.55*r, yc + 0.55*r): circ(layer, px(9.0), yy, 0.7*S_PX, fill=INK, sw=0)   # 雷达激光
    else:
        for sgn in (-1, 1):                                    # 俯视：雷达在左右缘，PESA 投影为轴线长条
            yy = yc + sgn*r
            path(layer, f"M{px(5.0)-1.3*S_PX:.1f},{yy:.1f} A{1.3*S_PX:.1f},{0.7*S_PX:.1f} 0 0 {1 if sgn<0 else 0} {px(5.0)+1.3*S_PX:.1f},{yy:.1f} Z", fill="#FFFFFF", sw=0.7)
        rect(layer, px(3.0), yc-0.8*S_PX, 4.0*S_PX, 1.6*S_PX, fill="#FFFFFF", sw=0.7)
        circ(layer, px(9.0), yc, 0.7*S_PX, fill=INK, sw=0)

def akv_bays(layer, yc, top_view):
    """正阳级 AKV 发射舱 ×6，每舷 3；侧视见右舷 3 扇门，俯视见左右缘的舱盖线。"""
    r = R*S_PX
    xs = (X_FWD+1.5, X_FWD+1.5+AKV_L+1.0, X_FWD+1.5+2*(AKV_L+1.0))
    xs = (2.5, 8.5, 14.5)                                  # 门长 5.6 m（AKV 横放 3 m 宽，纵放 11.4 m 太长，按 6 格 = 85 m³ 舱室横排）
    for xm in xs:
        if not top_view:
            rect(layer, px(xm), yc - 0.62*r, 5.6*S_PX, 1.24*r, fill="#FFFFFF", sw=0.8)
            line(layer, px(xm)+5.6*S_PX/2, yc-0.62*r, px(xm)+5.6*S_PX/2, yc+0.62*r, stroke=INK2, sw=0.4)
        else:
            for sgn in (-1, 1):
                yy = yc + sgn*r
                rect(layer, px(xm), yy - (1.6 if sgn < 0 else 0), 5.6*S_PX, 1.6, fill=INK, sw=0)

def hangar(layer, yc, top_view):
    """机库门 16.8 × 6.1 m，在背部；俯视见门，侧视见门框凸缘。"""
    r = R*S_PX
    if top_view:
        x, w = px(3.0), HANGAR[0]*S_PX; h = HANGAR[1]*S_PX
        rect(layer, x, yc-h/2, w, h, fill="#FFFFFF", sw=0.8)
        line(layer, x, yc, x+w, yc, stroke=INK2, sw=0.45, dash="3 2")
    else:
        rect(layer, px(3.0), yc - r - 2.2, HANGAR[0]*S_PX, 2.2, fill="#FFFFFF", sw=0.6)

def wings_top(layer, yc):
    """散热翼 ×2，展开；管路横纹，根部铰链。"""
    r = R*S_PX
    x, w = px(WING_X0), WING*S_PX
    for sgn in (-1, 1):
        y0 = yc + sgn*(r + 0.8*S_PX)
        y1 = y0 + sgn*WING*S_PX
        ya, yb = min(y0, y1), max(y0, y1)
        rect(layer, x, ya, w, yb-ya, fill="#FFFFFF", sw=0.9)
        for k in range(1, 22):
            yy = ya + (yb-ya)*k/22
            line(layer, x+2, yy, x+w-2, yy, stroke=INK3, sw=0.3)
        for k in (1, 2, 3):
            xx = x + w*k/4
            line(layer, xx, ya, xx, yb, stroke=INK2, sw=0.45)
        # 铰链座 ×3
        for k in (0.12, 0.5, 0.88):
            xx = x + w*k
            rect(layer, xx-1.2*S_PX, yc + sgn*r - (0.8*S_PX if sgn < 0 else 0), 2.4*S_PX, 0.8*S_PX, fill=INK, sw=0)

# ── A · 右舷侧视图 ────────────────────────────────────────────────
LA = "A侧视"
view_title(LA, "A", 84, 118, "右舷侧视图", "散热翼在船身两侧，本图中侧对视线，只见铰链座")
hull_outline(LA, YA, False)
# 散热翼铰链座（侧视）
for k in (0.12, 0.5, 0.88):
    xx = px(WING_X0) + WING*S_PX*k
    rect(LA, xx-1.2*S_PX, YA-0.4*S_PX, 2.4*S_PX, 0.8*S_PX, fill=INK, sw=0)
line(LA, px(WING_X0), YA, px(WING_X0+WING), YA, stroke=INK2, sw=0.5, dash="4 2")
towers(LA, YA, False); sensors(LA, YA, False); akv_bays(LA, YA, False); hangar(LA, YA, False)
# 尺寸
rA = R*S_PX
dim(LA, px(0), YA-rA-42, px(L), YA-rA-42, "106.7 m（350 ft）")
dim(LA, px(L), YA-rA-42, px(L+NOZ), YA-rA-42, f"{NOZ:.0f} m", size=7.4)
dim(LA, px(L+NOZ)+22, YA-rA, px(L+NOZ)+22, YA+rA, "18.3 m")
dim(LA, px(X_TANK), YA+rA+46, px(X_DRV), YA+rA+46, "燃料段 74 m", side="below")
# 图注
callout(LA, 1, px(0.3), YA-rA*0.55, px(0)-30, YA-rA-4)
callout(LA, 3, px(5.0), YA-rA-6, px(9), YA-rA-30)
callout(LA, 5, px(11), YA-rA-2, px(20), YA-rA-30)
callout(LA, 6, px(11.3), YA+rA*0.62, px(14), YA+rA+22)
callout(LA, 7, px(26), YA+rA+5, px(30), YA+rA+22)
callout(LA, 8, px(55), YA-rA-2.6*S_PX, px(55), YA-rA-40)
callout(LA, 9, px(68), YA, px(68)+16, YA+rA+22)
callout(LA, 10, px(85), YA+rA*0.5, px(85), YA+rA+22)
callout(LA, 13, px(L+NOZ*0.5), YA-rA*0.95, px(L+NOZ*0.5), YA-rA-30)
callout(LA, 14, px(X_DRV-1.5), YA+rA+3, px(X_DRV-1.5)+6, YA+rA+22)
S.text(LA, px(0), YA+rA+64, "艏", 9, "cjk_b", weight="bold", anchor="middle")
S.text(LA, px(L+NOZ), YA+rA+64, "艉", 9, "cjk_b", weight="bold", anchor="middle")

# ── 纵剖空间分配（与侧视图同 x 比例）─────────────────────────────────
LS = "纵剖"
h = 26
S.text(LS, 84, YSEC-8, "纵剖 · 内部空间分配", 9.6, "cjk_b", weight="bold")
S.text(LS, 84 + text_width("纵剖 · 内部空间分配", 9.6, "cjk_b") + 10, YSEC-8,
       f"船体 {SPACES['hull']:,} 格 × 14.2 m³ = {SPACES['hull']*SPACE_M3/1e3:,.1f} 万 m³；1 格 = 500 立方英尺", 8, "cjk", fill=INK2)
segs = [(0, X_FWD, ARMOR_F, ""), (X_FWD, X_TANK, HULL_F, ""),
        (X_TANK, X_DRV, RAD_F, f"核弹丸燃料罐 1,500 格 · 18,000 t · 船体 {SPACES['tanks']/SPACES['hull']*100:.0f}%"),
        (X_DRV, L, DARK_F, "驱动 200 格")]
for x0m, x1m, f, t in segs:
    rect(LS, px(x0m), YSEC, (x1m-x0m)*S_PX, h, fill=f, sw=0.7)
    if t: S.text(LS, px((x0m+x1m)/2), YSEC+h/2+3, t, 7.6, "cjk", anchor="middle")
if True:
    hatch(LS, px(0), YSEC, X_FWD*S_PX, h)
# 粒子束：贯穿前 91.4 m 的一根管
rect(LS, px(0.6), YSEC+h+6, PB_L*S_PX, 4, fill=INK, sw=0)
S.text(LS, px(PB_L)+6, YSEC+h+13.5, f"旧式粒子束加速器 {PB_L:.0f} m（300 ft），前向，射口在艏板中心", 7.6, "cjk", fill=INK2)
S.text(LS, px(X_FWD)+2, YSEC+h+13.5, "▶", 6, "lat", fill=INK)
S.text(LS, px((X_FWD+X_TANK)/2), YSEC+h/2+3, "前段 20.5 m", 7.6, "cjk", anchor="middle")
line(LS, px(X_TANK)-20, YSEC+h, px(X_TANK)-20, YSEC+h+30, sw=0.5)
S.text(LS, px(X_TANK)-14, YSEC+h+34, "前段：指挥舰桥（重型风暴掩体）· 机库 55 格 · AKV 舱 6 × 6 格 · 居住 4 舱室 + 6 通铺 · 手术室 · 新式裂变堆 80 MW（20.5 格）", 7.6, "cjk", fill=INK2)
callout(LS, 4, px(6), YSEC+4, px(0)-30, YSEC+13)
callout(LS, 12, px(85), YSEC, px(85), YSEC-16)

# ── 参照物：054A 型护卫舰，同比例 ────────────────────────────────────
LR = "参照"
S.text(LR, 84, YREF-200, "同比例参照", 9.6, "cjk_b", weight="bold")
S.text(LR, 84 + text_width("同比例参照", 9.6, "cjk_b") + 10, YREF-200, "054A 型护卫舰，长 134 m，桅顶高约 25 m；艏前小人高 1.7 m", 8, "cjk", fill=INK2)
fl = 134*S_PX; fx = px(0)
pts = [(0.03, 0), (1.0, 0), (1.0, 5.0), (0.80, 5.0), (0.80, 10.0), (0.62, 10.0), (0.62, 5.2), (0.52, 5.2), (0.52, 11.5),
       (0.47, 11.5), (0.47, 5.2), (0.44, 5.2), (0.44, 12.5), (0.405, 12.5), (0.405, 25.0), (0.395, 25.0), (0.395, 12.5),
       (0.30, 12.5), (0.30, 5.5), (0.21, 5.5), (0.21, 7.8), (0.175, 7.8), (0.175, 5.8), (0.0, 7.2)]
d = "M" + " L".join(f"{fx+fl*x:.1f},{YREF-z*S_PX:.1f}" for x, z in pts) + " Z"
path(LR, d, fill="#E9E9E6", sw=0.7)
line(LR, fx, YREF, fx+fl, YREF, stroke=C["water_label"], sw=1.0)
S.text(LR, fx+fl-6, YREF-5*S_PX-5, "054A", 8.6, "lat_b", weight="bold", anchor="end")
# 小人：1.7 m
hx, hy = fx-26, YREF
line(LR, hx, hy, hx, hy-1.7*S_PX*0.62, sw=1.0); circ(LR, hx, hy-1.7*S_PX*0.82, 1.7*S_PX*0.18, fill=INK, sw=0)
line(LR, hx-3, hy-1.7*S_PX*0.62, hx+3, hy-1.7*S_PX*0.62, sw=1.0)
S.text(LR, hx+8, hy-2, "1.7 m", 7.2, "lat", fill=INK2)

# ── B · 前视图（散热翼截断）与 AKV ─────────────────────────────────
LF = "B前视"
view_title(LF, "B", 1180, 118, "前视图", "散热翼展开、截断表示；实际每侧伸出 43 m")
rf = R*S_PX
circ(LF, FX, FY, rf, fill=ARMOR_F, sw=1.0)
S.add(LF, f'<clipPath id="hfront"><circle cx="{FX:.1f}" cy="{FY:.1f}" r="{rf:.1f}"/></clipPath>')
S.add(LF, '<path d="' + "".join(f"M{FX-rf+i:.1f},{FY-rf:.1f} l{-2*rf:.1f},{2*rf:.1f} " for i in [k*5 for k in range(int(4*rf/5)+2)])
      + f'" stroke="{INK3}" stroke-width="0.3" clip-path="url(#hfront)"/>')
circ(LF, FX, FY, rf, fill="none", sw=1.0)
circ(LF, FX, FY, rf*0.55, fill="none", sw=0.5)                       # 艏板分块
circ(LF, FX, FY, 1.4*S_PX, fill="#FFFFFF", sw=0.9); circ(LF, FX, FY, 0.5*S_PX, fill=INK, sw=0)   # 粒子束射口
for a in (45, 135, 225, 315):                                        # 重激光 ×4 前向
    ax, ay = FX + rf*0.72*math.cos(math.radians(a)), FY + rf*0.72*math.sin(math.radians(a))
    circ(LF, ax, ay, 0.9*S_PX, fill="#FFFFFF", sw=0.8); circ(LF, ax, ay, 0.35*S_PX, fill=INK, sw=0)
# 外缘部件：塔（上下）、雷达泡（左右）、PESA（上下长条）、机库门缘（上）
for sgn in (-1, 1):
    rect(LF, FX-1.1*S_PX, FY + sgn*rf - (2.6*S_PX if sgn < 0 else 0), 2.2*S_PX, 2.6*S_PX, fill=HULL_F, sw=0.8)
for sgn in (-1, 1):
    xx = FX + sgn*rf
    path(LF, f"M{xx:.1f},{FY-1.3*S_PX:.1f} A{0.7*S_PX:.1f},{1.3*S_PX:.1f} 0 0 {0 if sgn<0 else 1} {xx:.1f},{FY+1.3*S_PX:.1f} Z", fill="#FFFFFF", sw=0.7)
    # 散热翼：从船侧伸出 12 m 后截断
    wx0 = xx + sgn*0.8*S_PX; wx1 = wx0 + sgn*12*S_PX
    rect(LF, min(wx0, wx1), FY-1.6, abs(wx1-wx0), 3.2, fill="#FFFFFF", sw=0.8)
    zx = wx1
    path(LF, f"M{zx:.1f},{FY-7:.1f} l{sgn*3:.1f},4 l{-sgn*6:.1f},6 l{sgn*3:.1f},4", stroke="#FFFFFF", sw=3)
    path(LF, f"M{zx:.1f},{FY-7:.1f} l{sgn*3:.1f},4 l{-sgn*6:.1f},6 l{sgn*3:.1f},4", sw=0.8)
    rect(LF, min(wx0, wx1), FY-1.6, abs(wx1-wx0), 3.2, fill="none", sw=0.8)
dim(LF, FX+rf+14*S_PX+16, FY-rf, FX+rf+14*S_PX+16, FY+rf, "18.3 m（60 ft）")
callout(LF, 2, FX + rf*0.72*math.cos(math.radians(315)) + 5, FY + rf*0.72*math.sin(math.radians(315)) - 5, FX+rf+8, FY-rf-14)
callout(LF, 11, FX-rf-9*S_PX, FY+2, FX-rf-9*S_PX, FY+rf+24)
S.text(LF, FX, FY+rf+14*S_PX-30, "船体截面：圆柱，无自旋舱，全程微重力", 7.8, "cjk", anchor="middle", fill=INK2)

# 正阳级 AKV，同比例，放在前视图右侧
ax0, ay0 = 1590, 335
S.text(LF, ax0, ay0-64, "正阳级 AKV（舰载 6 架）", 9.6, "cjk_b", weight="bold")
S.text(LF, ax0, ay0-51, f"{AKV_L:.1f} × {AKV_W:.1f} m · 150 t · 0.21 G · 同比例", 8, "cjk", fill=INK2)
rect(LF, ax0, ay0-AKV_W*S_PX/2, AKV_L*S_PX, AKV_W*S_PX, fill=HULL_F, sw=0.8)
rect(LF, ax0, ay0-AKV_W*S_PX/2, 0.9*S_PX, AKV_W*S_PX, fill=ARMOR_F, sw=0.8)              # 艏装甲 cDR 60
for sgn in (-1, 1):                                                                       # 小散热翼 4.9 × 4.9 m
    y0 = ay0 + sgn*AKV_W*S_PX/2; y1 = y0 + sgn*4.9*S_PX
    rect(LF, ax0+AKV_L*S_PX*0.55, min(y0, y1), 4.9*S_PX, abs(y1-y0), fill="#FFFFFF", sw=0.7)
circ(LF, ax0+2.2*S_PX, ay0, 0.5*S_PX, fill=INK, sw=0)                                     # 线圈炮口（前向）
path(LF, f"M{ax0+AKV_L*S_PX:.1f},{ay0-AKV_W*S_PX*0.35:.1f} l{2.2*S_PX:.1f},{-AKV_W*S_PX*0.15:.1f} l0,{AKV_W*S_PX:.1f} l{-2.2*S_PX:.1f},{-AKV_W*S_PX*0.15:.1f} Z", fill="#E4E4E1", sw=0.8)
S.text(LF, ax0, ay0+62, "钨弹丸包或 X 射线激光弹包各一，", 7.8, "cjk", fill=INK2)
S.text(LF, ax0, ay0+75, "比美军掠食者多带一包备用弹药。", 7.8, "cjk", fill=INK2)

# ── C · 俯视图（散热翼展开）───────────────────────────────────────
LT = "C俯视"
view_title(LT, "C", 84, YB - WING*S_PX - R*S_PX - 56, "俯视图", "巡航状态，散热翼展开；战斗时收拢以免被激光烧穿")
wings_top(LT, YB)
hull_outline(LT, YB, True)
towers(LT, YB, True); sensors(LT, YB, True); akv_bays(LT, YB, True); hangar(LT, YB, True)
rt = R*S_PX
wtop = YB - rt - 0.8*S_PX - WING*S_PX; wbot = YB + rt + 0.8*S_PX + WING*S_PX
dim(LT, px(L+NOZ)+22, wtop, px(L+NOZ)+22, wbot, f"翼展 {2*WING + 2*R + 1.6:.0f} m")
dim(LT, px(WING_X0), wbot+22, px(WING_X0+WING), wbot+22, f"{WING:.0f} m（141 ft）", side="below")
dim(LT, px(WING_X0)-24, YB - rt - 0.8*S_PX, px(WING_X0)-24, wtop, f"{WING:.0f} m")
S.text(LT, px(0)-14, YB - rt - 0.8*S_PX - WING*S_PX/2, "左舷", 9, "cjk_b", weight="bold", anchor="end")
S.text(LT, px(0)-14, YB + rt + 0.8*S_PX + WING*S_PX/2, "右舷", 9, "cjk_b", weight="bold", anchor="end")
callout(LT, 5, px(11.4), YB-1, px(20), YB-rt-46)
callout(LT, 6, px(11.3), YB+rt+1, px(14), YB+rt+40)
callout(LT, 8, px(55), YB-2, px(48), YB-rt-46)
callout(LT, 9, px(48), YB+rt-1, px(40), YB+rt+40)
callout(LT, 11, px(WING_X0+WING*0.6), YB-rt-0.8*S_PX-WING*S_PX*0.5, px(WING_X0+WING*0.6)+40, YB-rt-0.8*S_PX-WING*S_PX*0.5-40)
callout(LT, 10, px(40), YB+rt*0.4, px(30), YB+rt+40)

# ── 图注（编号说明）────────────────────────────────────────────────
LN = "图注"
NX, NY = 1180, 1095
S.text(LN, NX, NY, "图注", 9.6, "cjk_b", weight="bold")
S.text(LN, NX + text_width("图注", 9.6, "cjk_b") + 10, NY, "编号见三视图与纵剖", 8, "cjk", fill=INK2)
notes = [
    (1, "重装甲艏板：cDR 65，侧面 15、艉部 5。永远把这一面对着敌人；被两个方向夹住就得选一个"),
    (2, "重激光 ×4（10 MJ，前向固定）；中心是粒子束射口。粒子束供电时六门重激光塔不能同时开火"),
    (3, "传感器组：大型被动阵列 ×2、中型雷达 ×2、中型雷达激光 ×3。被动阵列十万英里外就能看见任何热的船"),
    (4, "指挥舰桥（旧式），内置，套在重型风暴掩体里（cPF 1,000）；另一处轻掩体罩着陆战队座舱"),
    (5, "机库门 16.8 × 6.1 m，机库 55 格，常载 500 t 的备用 AKV 或陆战队装备"),
    (6, "正阳级 AKV 发射舱 ×6，每舷 3，每舱 6 格 85 m³"),
    (7, "大型出入口 ×2（对接环），背腹各一"),
    (8, "重激光塔 ×6（10 MJ，可缩回），3 背 3 腹交错，塔式安装可以向前后射击"),
    (9, "轻激光 ×8（2.5 MJ，固定泡），每舷 4；艉部另有 2，对付尾追的 AKV"),
    (10, "船体散热板 6,500 m²，覆盖燃料段整个外壳（正典：70 ksf 船体散热器）"),
    (11, "折叠散热翼 ×2，43 × 43 m，共 3,700 m²。展开时是全舰最大、最软的目标"),
    (12, "燃料段：核弹丸 1,500 格、18,000 t，占船体 74%。满载 31,224 t 里 58% 是燃料"),
    (13, "高比冲聚变脉冲驱动，200 格；磁喷管。0.04 G，可连续点火 187.5 小时，ΔV 82.5 英里/秒（133 km/s）"),
    (14, "姿态控制推进器组 ×4，随驱动附送；船可以独立于航向转动，这是「侧击靠数量」的物理根源"),
]
col_w = 584
cy = NY + 22
for n, t in notes:
    circ(LN, NX+6, cy-3, 6.2, fill="#FFFFFF", sw=0.7)
    S.text(LN, NX+6, cy, str(n), 7.6, "lat_b", anchor="middle", weight="bold")
    if text_width(t, 8.2, "cjk") > col_w - 24:
        k = len(t)//2
        cut = max(t.rfind("，", 0, k+10), t.rfind("；", 0, k+10), t.rfind("。", 0, k+10))
        cut = cut+1 if cut > 0 else k
        S.text(LN, NX+18, cy, t[:cut], 8.2, "cjk"); S.text(LN, NX+18, cy+12, t[cut:], 8.2, "cjk")
        cy += 30
    else:
        S.text(LN, NX+18, cy, t, 8.2, "cjk"); cy += 18

# ── 主要参数（右栏）──────────────────────────────────────────────
LP = "参数"
PX, PY = 1180, 560
S.text(LP, PX, PY, "主要参数", 11, "cjk_b", weight="bold")
S.text(LP, PX + text_width("主要参数", 11, "cjk_b") + 10, PY, "数值照抄正典，英制换算成公制", 8, "cjk", fill=INK2)
rows = [
    ("舰级", "星寨级（Xingzhai，「星」）空间支配载具"),
    ("设计 / 建造", "MAST 2073 年立项；原型「久星号」2086 年成；2088 年起量产"),
    ("数量", "20 艘（2100 年）；预计服役至 2120 年以后"),
    ("隶属", "人民解放军海军太空部队深空舰队主力；母港火卫一"),
    ("船体", f"圆柱 {L:.1f} m × 直径 {2*R:.1f} m，碳复合材料特重框架，智能船体"),
    ("装甲", "金属基复合材料；cDR 前 65 / 侧 15 / 后 5；变色蒙皮"),
    ("质量", "空重 11,768 t · 战斗 22,224 t · 满载 31,224 t"),
    ("载荷", "1,456 t（含 6 架 AKV 与 500 t 舰载物资）"),
    ("动力", "高比冲聚变脉冲驱动 200 格；新式裂变堆 80 MW"),
    ("性能", "0.04 G · 点火 187.5 h · ΔV 82.5 mps（133 km/s）"),
    ("散热", "船体 70 ksf + 折叠翼 40 ksf；需求 105 ksf"),
    ("武器", "重激光 10 MJ：6 塔（侧）+ 4（前）；轻激光 2.5 MJ：8（侧）+ 2（后）"),
    ("", f"旧式粒子束 {PB_L:.0f} m（前）；正阳级 AKV × 6"),
    ("传感器", "中型雷达激光 × 3 · 大型被动阵列 × 2 · 中型雷达 × 2"),
    ("乘员", "舰长、领航、飞行员、2 武器官、20 工程师、3 军医；多为赛博壳"),
    ("搭载", "24 名动力甲陆战队（第 67 太空步兵师）"),
    ("居住", "4 舱室 + 6 通铺 + 座舱；无自旋舱，全员微重力适应"),
    ("造价", "9.27 亿美元（2100 年美元）"),
    ("维护", "每 1.32 小时一次检查，每天 73 工时"),
    ("同代对手", "美军 DFS-3 天使级 114 m · 欧盟 SDV-90 114 m · 法国柯尼斯堡级球形 29 m"),
]
yy = PY + 22
for k, v in rows:
    if k: S.text(LP, PX, yy, k, 8.4, "cjk_b", weight="bold", fill=INK2)
    S.text(LP, PX+72, yy, v, 8.4, "cjk")
    yy += 17
line(LP, PX, PY+8, PX+584, PY+8, sw=0.6)
line(LP, PX, yy-9, PX+584, yy-9, sw=0.6)

# 要点
yy += 14
S.text(LP, PX, yy, "读图要点", 9.6, "cjk_b", weight="bold"); yy += 6
pts = [
    "· 这是一根装了引擎的油罐：船体四分之三是燃料，人住的地方不到一成。0.04 G 的加速度",
    "　意味着离开火卫一去地球，要连续点火一个星期。",
    "· 装甲只在艏板上。TS 的太空战因此像地中海桨帆船：把鼻子对准敌人，用数量绕到对方侧面。",
    "· 散热翼展开时翼展超过船长，是被激光优先烧的部位；收拢后靠船体散热板撑，撑不了太久。",
    "· 部件位置是按正典对 SDV 通用布局的描述排的，正典没有给出本级的图。",
    "· 2198 年：火卫一若还留着星寨级，它们已服役一百一十年，火卫一船厂是唯一能修它们的地方。",
]
yy = M.note_lines(S, LP, PX, yy+12, pts, size=8.2, lh=14)

# ── 图名 ───────────────────────────────────────────────────────────
S.text("图名", 84, 52, "星寨级", 30, "cjk_b", weight="bold", spacing=3)
S.text("图名", 84 + text_width("星寨级", 30, "cjk_b", 3) + 18, 52, "空间支配载具 · 人民解放军海军太空部队 · 深空舰队 · 火卫一", 14, "cjk", fill=INK2)
S.text("图名", 84, 72, "XINGZHAI-CLASS SPACE DOMINANCE VEHICLE  ·  PLAN-SF DEEP SPACE FLEET  ·  RECOGNITION DRAWING  ·  2100", 8.4, "lat", fill=INK2, spacing=1.6)
S.text("图名", SW-84, 46, "比例 1 : 7.5 屏幕单位/米，三视图与参照物同比例", 8.2, "cjk", fill=INK2, anchor="end")
S.text("图名", SW-84, 60, "尺寸、质量、模块清单取自正典；部件排布为本图推定", 8.2, "cjk", fill=C["alert"], anchor="end")
S.text("图名", SW-84, 74, "飞船识别图 · 第 1 号", 8.2, "cjk", fill=INK2, anchor="end")
S.text("出处", 84, SH-18, "数据：GURPS Transhuman Space《Spacecraft of the Solar System》p.35–36（星寨级）、《In The Well》p.107（正阳级 AKV）、核心书 p.173–203（设计与战斗规则）。"
       "参照物：054A 型护卫舰公开尺寸。1 格 = 500 立方英尺 = 14.16 m³。", 7.0, "cjk", fill=INK3)

svg = OUT/f"{NAME}.svg"; S.save(svg)
png = OUT/f"{NAME}.png"
subprocess.run(["rsvg-convert", "-z", "3", "-o", str(png), str(svg)], check=True)
print("→", svg, png)
