# -*- coding: utf-8 -*-
"""
2100 年火星系列地图共用的制图工具。风格：白纸、MOLA 晕渲 + 低饱和分层设色、浅蓝水面、
细黑经纬网、无底框的干净注记——仿 USGS/NASA 行星地形图（如 I-2782 火星地形图）的做法。

除底图晕渲是嵌入的位图外，海岸线、经纬网、铁路、符号、全部文字都是真矢量。
"""
import base64, csv, io, json, math, pathlib
import numpy as np
from PIL import Image, ImageFont
from scipy import ndimage
from rasterio import features
from affine import Affine
from shapely.geometry import shape

HERE    = pathlib.Path(__file__).resolve().parent
MAP_DIR = HERE.parent
OUT     = MAP_DIR / "产出"
DATA    = MAP_DIR / "数据"
R       = 3396190.0
KMPD    = 2*math.pi*R/1e3/360

# ── 字体 ───────────────────────────────────────────────────────────
FONT_FILES = {
    "lat":   "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf",
    "lat_i": "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Italic.ttf",
    "lat_b": "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf",
    "cjk":   "/usr/share/fonts/fandol/FandolHei-Regular.otf",
    "cjk_b": "/usr/share/fonts/fandol/FandolHei-Bold.otf",
}
FAM_LAT = "Liberation Sans, Helvetica, Arial, sans-serif"
FAM_CJK = "FandolHei, Noto Sans CJK SC, Liberation Sans, sans-serif"
_fcache = {}
def text_width(s, size, kind="cjk", spacing=0.0):
    """用真实字体量字宽（SVG 用户单位）。
    坑：FAM_CJK 把 FandolHei 排第一，它自带西文字形，渲染器整串都用它画，所以中文注记里的数字、
    「·」（FandolHei 里是全角宽）也得按 FandolHei 量，不能按 Liberation 量。"""
    if kind not in _fcache: _fcache[kind] = ImageFont.truetype(FONT_FILES[kind], 100)
    f = _fcache[kind]
    return sum(f.getlength(ch)*size/100 + spacing for ch in s) - (spacing if s else 0)

# ── 配色 ───────────────────────────────────────────────────────────
C = dict(paper="#FFFFFF", ink="#1A1A1A", ink2="#5C5C5C", ink3="#8A8A8A",
         grat="#1A1A1A", water_label="#3F6D96", coast="#4F7FA8",
         rail="#262626", alert="#B3261E", frame="#1A1A1A")

# 陆地分层设色：刻意低饱和，让晕渲和注记当主角
HYPSO = [(-8500, (228, 230, 224)), (-5000, (238, 237, 231)), (-2500, (244, 241, 233)),
         (0, (244, 237, 224)), (3000, (238, 228, 210)), (7000, (229, 216, 196)),
         (12000, (218, 205, 188)), (17000, (229, 222, 214)), (22000, (251, 250, 247))]
# 水深：浅处接近纸白，深处中蓝
BATHY = [(0, (216, 233, 245)), (800, (196, 221, 239)), (2500, (165, 199, 228)), (5000, (136, 176, 212))]

def ramp(values, stops):
    xs = np.array([s[0] for s in stops], float)
    out = np.empty(values.shape + (3,), np.float32)
    for i in range(3):
        out[..., i] = np.interp(values, xs, [s[1][i] for s in stops])
    return out

def shade(dem, dx_m, dy_m, zfac=2.2, az=315, alt=40):
    """晕渲 0–1。dx_m / dy_m：像元东西、南北方向的真实尺寸（米，可以是按行广播的数组）。
    zfac 适度夸张，火星地势大，别太重。"""
    gy, gx = np.gradient(dem.astype(np.float32))
    dzdx, dzdy = gx/dx_m*zfac, -gy/dy_m*zfac
    slope = np.arctan(np.hypot(dzdx, dzdy)); aspect = np.arctan2(dzdy, -dzdx)
    zen, azr = math.radians(90-alt), math.radians(360-az+90)
    return np.clip(np.cos(zen)*np.cos(slope) + np.sin(zen)*np.sin(slope)*np.cos(azr-aspect), 0, 1)

def colorize(dem, hs, water_masks=(), water_levels=()):
    """陆地：分层设色 × 晕渲；水面：水深色，淡淡透出海底地形。"""
    rgb = ramp(dem, HYPSO) * (0.80 + 0.26*hs[..., None])
    for m, lvl in zip(water_masks, water_levels):
        depth = np.clip(lvl - dem, 0, None)
        wc = ramp(depth, BATHY) * (0.95 + 0.06*hs[..., None])
        rgb = np.where(m[..., None], wc, rgb)
    return np.clip(rgb, 0, 255).astype(np.uint8)

def relief_rgb(dem, water_masks, water_levels, ppd, lat_top=90.0, zfac=2.2):
    """等距圆柱排布的 dem + 若干 (掩膜, 水面高程) → RGB。"""
    lats = lat_top - (np.arange(dem.shape[0]) + 0.5)/ppd
    dyk = KMPD*1000/ppd
    cl = np.maximum(np.cos(np.radians(lats)), 0.05)[:, None]
    return colorize(dem, shade(dem, dyk*cl, dyk, zfac), water_masks, water_levels)

def png_data_uri(rgb, quality=None):
    buf = io.BytesIO()
    im = Image.fromarray(rgb)
    if quality: im.save(buf, "JPEG", quality=quality, optimize=True, subsampling=0); mime = "jpeg"
    else:       im.save(buf, "PNG", optimize=True); mime = "png"
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode()

# ── 投影 ───────────────────────────────────────────────────────────
class Equirect:
    """等距圆柱。lon0/lon1 为东经（可跨 360），lat0 > lat1。"""
    def __init__(self, lon0, lon1, lat0, lat1, x0, y0, ppd):
        self.lon0, self.lon1, self.lat0, self.lat1 = lon0, lon1, lat0, lat1
        self.x0, self.y0, self.ppd = x0, y0, ppd
        self.w, self.h = (lon1-lon0)*ppd, (lat0-lat1)*ppd
    def unwrap(self, lon):
        # 已在 [lon0, lon0+360] 内的不取模：图幅东边线上的点（恰好 lon0+360）取模会被甩回西边线，
        # 海岸线会拉出横贯全图的直线
        L = np.asarray(lon, float)
        return np.where((L < self.lon0) | (L > self.lon0 + 360), self.lon0 + ((L - self.lon0) % 360), L)
    def xy(self, lon, lat):
        return self.x0 + (self.unwrap(lon)-self.lon0)*self.ppd, self.y0 + (self.lat0-np.asarray(lat))*self.ppd
    def inside(self, lon, lat, pad=0):
        L = self.unwrap(lon)
        return (self.lon0-pad <= L <= self.lon1+pad) and (self.lat1-pad <= lat <= self.lat0+pad)

class Mollweide:
    def __init__(self, lon0, cx, cy, rx):
        self.lon0, self.cx, self.cy, self.rx, self.ry = lon0, cx, cy, rx, rx/2
    def _theta(self, lat):
        lat = np.radians(np.asarray(lat, float)); t = lat.copy()
        target = np.pi*np.sin(lat)
        for _ in range(30):
            f = 2*t + np.sin(2*t) - target
            fp = 2 + 2*np.cos(2*t)
            t = np.where(np.abs(fp) > 1e-9, t - f/np.where(np.abs(fp) > 1e-9, fp, 1), t)
        return t
    def xy(self, lon, lat):
        # 已经在 [lon0−180, lon0+180] 内的经度不取模：接缝上的点（恰好 ±180°）取模会被甩到另一侧，
        # 从滚动过的全球掩膜矢量化出来的海岸线正好有大量这样的点。
        d = np.asarray(lon, float) - self.lon0
        d = np.where((d < -180) | (d > 180), ((d + 180) % 360) - 180, d)
        lam = np.radians(d)
        th = self._theta(lat)
        return self.cx + self.rx*lam*np.cos(th)/np.pi, self.cy - self.ry*np.sin(th)
    def inverse(self, x, y):
        dx, dy = (x - self.cx)/self.rx, (y - self.cy)/self.ry
        inside = dx**2 + dy**2 <= 1.0
        th = np.arcsin(np.clip(-dy, -1, 1))
        lat = np.degrees(np.arcsin(np.clip((2*th + np.sin(2*th))/np.pi, -1, 1)))
        lon = self.lon0 + np.degrees(np.pi*dx/np.maximum(np.cos(th), 1e-9))
        return lon % 360, lat, inside & (np.abs(np.pi*dx/np.maximum(np.cos(th), 1e-9)) <= np.pi)
    def seam_lon(self): return (self.lon0 + 180) % 360

class Mercator(Equirect):
    """球面墨卡托（区域图用，USGS 火星 1:500 万分幅在 ±30° 内也用它）。ppd：赤道上每度的屏幕单位。
    经纬网仍是直角网格，所以 Equirect 的 unwrap / inside 和直角图廓函数都能直接用。"""
    def __init__(self, lon0, lon1, lat0, lat1, x0, y0, ppd):
        super().__init__(lon0, lon1, lat0, lat1, x0, y0, ppd)
        self.k = ppd*180/math.pi
        self.ytop = self._y(lat0)
        self.h = self.ytop - self._y(lat1)
    def _y(self, lat):
        return self.k*np.log(np.tan(np.pi/4 + np.radians(np.asarray(lat, float))/2))
    def xy(self, lon, lat):
        return self.x0 + (self.unwrap(lon)-self.lon0)*self.ppd, self.y0 + self.ytop - self._y(lat)
    def lat_of(self, y):
        m = (self.ytop - (np.asarray(y, float) - self.y0))/self.k
        return np.degrees(2*np.arctan(np.exp(m)) - np.pi/2)
    def km_per_unit(self, lat):
        return KMPD*math.cos(math.radians(lat))/self.ppd

class Azimuthal:
    """球面方位投影（极区图、同比例尺对比图、地球仪）。
    kind="laea" 兰伯特等积方位；kind="ortho" 正射。scale：屏幕单位/千米。
    北极心（lat0=90）时 lon0 那条经线朝正下方，东经逆时针增加，与 USGS 火星极区图一致。"""
    def __init__(self, lat0, lon0, cx, cy, scale, radius_km=R/1e3, kind="laea"):
        self.lat0, self.lon0, self.cx, self.cy, self.scale = lat0, lon0, cx, cy, scale
        self.Rk, self.kind = radius_km, kind
        self.s1, self.c1 = math.sin(math.radians(lat0)), math.cos(math.radians(lat0))
    def _fwd(self, lon, lat):
        lam = np.radians(np.asarray(lon, float) - self.lon0); phi = np.radians(np.asarray(lat, float))
        cosc = self.s1*np.sin(phi) + self.c1*np.cos(phi)*np.cos(lam)
        k = np.sqrt(2/np.maximum(1 + cosc, 1e-12)) if self.kind == "laea" else 1.0
        x = self.Rk*k*np.cos(phi)*np.sin(lam)
        y = self.Rk*k*(self.c1*np.sin(phi) - self.s1*np.cos(phi)*np.cos(lam))
        return x, y, cosc
    def xy(self, lon, lat):
        x, y, _ = self._fwd(lon, lat)
        return self.cx + x*self.scale, self.cy - y*self.scale
    def visible(self, lon, lat):
        return self._fwd(lon, lat)[2] >= 0
    def inverse(self, X, Y):
        x = (np.asarray(X, float) - self.cx)/self.scale; y = (self.cy - np.asarray(Y, float))/self.scale
        rho = np.hypot(x, y)
        if self.kind == "laea":
            ok = rho <= 2*self.Rk; c = 2*np.arcsin(np.clip(rho/(2*self.Rk), 0, 1))
        else:
            ok = rho <= self.Rk; c = np.arcsin(np.clip(rho/self.Rk, 0, 1))
        sc, cc, rs = np.sin(c), np.cos(c), np.where(rho > 0, rho, 1.0)
        phi = np.arcsin(np.clip(cc*self.s1 + y*sc*self.c1/rs, -1, 1))
        lam = np.arctan2(x*sc, rs*self.c1*cc - y*self.s1*sc)
        return (self.lon0 + np.degrees(lam)) % 360, np.degrees(phi), ok
    def radius_of(self, lat_edge):
        """北极心 / 南极心时，纬线 lat_edge 的屏幕半径。"""
        c = math.radians(90 - abs(lat_edge))
        return self.scale*self.Rk*(2*math.sin(c/2) if self.kind == "laea" else math.sin(c))

class Identity:
    """坐标已经是屏幕坐标时，给 rings_to_path 用。"""
    def xy(self, x, y): return np.asarray(x), np.asarray(y)

# ── 数据 ───────────────────────────────────────────────────────────
def load_masks():
    return np.load(OUT/"三海掩膜.npz")

def load_dem32():
    return np.load(MAP_DIR/"DEM/dem_32ppd_min.npy")

def load_dem32_avg():
    """32 px/度 全球高程，平均重采样（晕渲、剖面、面积统计用；min 版只给水体连通用）。没有就现场生成。"""
    p = MAP_DIR/"DEM/dem_32ppd_avg.npy"
    if not p.exists():
        import rasterio
        from rasterio.enums import Resampling
        with rasterio.open(MAP_DIR/"DEM/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif") as ds:
            np.save(p, ds.read(1, out_shape=(5760, 11520), resampling=Resampling.average).astype(np.float32))
    return np.load(p)

def sample_lonlat(arr, ppd, lon, lat, order=1):
    """按经纬度采样全球栅格（第 0 列 = −180°E，第 0 行 = 90°N），经度首尾相接。掩膜用 order=0。"""
    a = np.concatenate([arr[:, -2:], arr, arr[:, :2]], axis=1)
    if a.dtype == bool: a = a.astype(np.uint8)
    lon, lat = np.broadcast_arrays(np.asarray(lon, float), np.asarray(lat, float))
    col = ((np.atleast_1d(lon) + 180) % 360)*ppd - 0.5 + 2
    row = (90 - np.atleast_1d(lat))*ppd - 0.5
    return ndimage.map_coordinates(a, [row, col], order=order, mode="nearest").reshape(lon.shape)

def load_places():
    return list(csv.DictReader(open(DATA/"火星地点.csv", encoding="utf-8-sig")))

def load_peaks():
    return list(csv.DictReader(open(DATA/"火星山峰.csv", encoding="utf-8-sig")))

def load_infra():
    return json.load(open(OUT/"基础设施_2100.geojson", encoding="utf-8"))["features"]

def load_iau():
    return {r["clean_name"]: r for r in csv.DictReader(open(DATA/"IAU/火星IAU地名.csv", encoding="utf-8"))}

def faction_kind(f):
    if "锈色中国" in f: return "cn"
    if "联邦" in f or "美" in f: return "us"
    if "企业" in f: return "corp"
    if f.startswith("独立"): return "ind"
    if f in ("—", "", "火星百万富翁") or "区域" in f: return "none"
    return "other"

# ── 掩膜 → 海岸线 ───────────────────────────────────────────────────
def mask_rings(mask, ppd, lon_left=-180.0, lat_top=90.0, min_px=12, simplify=None, smooth=2, transform=None):
    """栅格掩膜 → [(外环, [内环…]), …]，坐标为 (东经, 纬度)。
    lon_left：掩膜第 0 列对应的经度（全球掩膜先 np.roll 到接缝在两侧，再传进来）。
    transform：掩膜已经在投影后的屏幕网格上时，传像元→屏幕的 Affine，输出就是屏幕坐标（配 Identity 画）。"""
    tf = transform or Affine(1/ppd, 0, lon_left, 0, -1/ppd, lat_top)
    m = ndimage.binary_opening(mask, np.ones((2, 2), bool)) if min_px else mask
    out = []
    for geom, v in features.shapes(m.astype(np.uint8), mask=m, transform=tf):
        g = shape(geom)
        if g.area*ppd*ppd < min_px: continue
        if simplify: g = g.simplify(simplify, preserve_topology=True)
        def sm(coords):
            pts = np.array(coords)
            for _ in range(smooth):                               # Chaikin 平滑，去掉栅格台阶
                p, q = pts[:-1], pts[1:]
                pts = np.vstack([np.column_stack([0.75*p+0.25*q, 0.25*p+0.75*q]).reshape(-1, 2), pts[:1]])
            return pts
        ext = sm(g.exterior.coords)
        holes = [sm(h.coords) for h in g.interiors if len(h.coords) > 6]
        out.append((ext, holes))
    return out

def rings_to_path(rings, proj, close=True, seam_jump=None):
    parts = []
    for ext, holes in rings:
        for ring in [ext] + holes:
            x, y = proj.xy(ring[:, 0], ring[:, 1])
            parts.append("M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y)) + (" Z" if close else ""))
    return " ".join(parts)

# ── SVG 输出 ────────────────────────────────────────────────────────
def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class SVG:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.layers = {}
        self.order = []
    def layer(self, name):
        if name not in self.layers: self.layers[name] = []; self.order.append(name)
        return self.layers[name]
    def add(self, name, s): self.layer(name).append(s)
    def text(self, name, x, y, s, size, kind="cjk", fill=None, anchor="start", spacing=0,
             halo=0.0, italic=False, weight="normal", opacity=1.0):
        fam = FAM_CJK if "cjk" in kind else FAM_LAT
        st = ' font-style="italic"' if italic else ""
        h = (f' stroke="#FFFFFF" stroke-width="{halo:.2f}" stroke-linejoin="round" paint-order="stroke"'
             if halo else "")
        ls = f' letter-spacing="{spacing:.2f}"' if spacing else ""
        op = f' opacity="{opacity}"' if opacity != 1 else ""
        self.add(name, f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FAM_CJK if "cjk" in kind else FAM_LAT}" '
                       f'font-size="{size:.2f}" font-weight="{weight}"{st}{ls}{h}{op} fill="{fill or C["ink"]}" '
                       f'text-anchor="{anchor}">{esc(s)}</text>')
    def save(self, path):
        body = "\n".join(f'<g id="{n}">\n' + "\n".join(self.layers[n]) + "\n</g>" for n in self.order)
        path.write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'
            f'<title>{esc(self.title)}</title>\n<rect width="100%" height="100%" fill="{C["paper"]}"/>\n{body}\n</svg>\n',
            encoding="utf-8")

# ── 注记避让 ───────────────────────────────────────────────────────
class Placer:
    """贪心避让：按优先级依次放，每个注记试 8 个方位，取第一个不与已占区域重叠的。"""
    def __init__(self, bounds):
        self.boxes = []
        self.bounds = bounds                                       # (x0, y0, x1, y1) 注记必须在内
    def block(self, x0, y0, x1, y1): self.boxes.append((x0, y0, x1, y1))
    def free(self, b, pad=1.5):
        x0, y0, x1, y1 = b
        bx0, by0, bx1, by1 = self.bounds
        if x0 < bx0 or y0 < by0 or x1 > bx1 or y1 > by1: return False
        return all(x1+pad < a0 or x0-pad > a1 or y1+pad < b0 or y0-pad > b1 for a0, b0, a1, b1 in self.boxes)
    def place(self, x, y, w, h, gap, order=("E", "W", "NE", "SE", "NW", "SW", "N", "S")):
        """返回 (文字左下角 x, 基线 y, anchor) 或 None。h 为总行高（含第二行）。"""
        cand = {"E": (x+gap, y-h/2), "W": (x-gap-w, y-h/2), "NE": (x+gap*0.7, y-gap*0.7-h),
                "SE": (x+gap*0.7, y+gap*0.7), "NW": (x-gap*0.7-w, y-gap*0.7-h), "SW": (x-gap*0.7-w, y+gap*0.7),
                "N": (x-w/2, y-gap-h), "S": (x-w/2, y+gap)}
        for k in order:
            bx, by = cand[k]
            b = (bx, by, bx+w, by+h)
            if self.free(b):
                self.boxes.append(b); return bx, by, k
        return None

# ── 高分辨率 DEM 与水面细化（区域图用）─────────────────────────────
def read_dem_window(lon0, lon1, lat0, lat1, ppd_out):
    """从原始 463 m DEM 读 [lon0, lon1] × [lat1, lat0]（东经，不跨 0°），重采样到 ppd_out。"""
    import rasterio
    from rasterio.windows import Window
    from rasterio.enums import Resampling
    ds = rasterio.open(MAP_DIR/"DEM/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif")
    PF = 128
    c0 = int(((lon0+180) % 360)*PF); r0 = int((90-lat0)*PF)
    w, h = int((lon1-lon0)*PF), int((lat0-lat1)*PF)
    ow, oh = int(round((lon1-lon0)*ppd_out)), int(round((lat0-lat1)*ppd_out))
    a = ds.read(1, window=Window(c0, r0, w, h), out_shape=(oh, ow), resampling=Resampling.bilinear).astype(np.float32)
    a[a < -30000] = np.nan
    return np.where(np.isfinite(a), a, np.nanmin(a))

def refine_water(mask32, level, dem_hr, ppd_hr, lon0, lat0):
    """把 32 px/度 的水体掩膜细化到高分辨率：只在原掩膜附近、且高程低于水面的像元算水。
    水位与连通关系完全沿用 32 px/度 的标定结果，只是岸线更细。"""
    f = ppd_hr // 32
    r0 = int((90-lat0)*32); c0 = int(((lon0+180) % 360)*32)
    hh, ww = dem_hr.shape[0]//f + 1, dem_hr.shape[1]//f + 1
    sub = mask32[r0:r0+hh][:, np.arange(c0, c0+ww) % mask32.shape[1]]
    up = np.repeat(np.repeat(sub, f, 0), f, 1)[:dem_hr.shape[0], :dem_hr.shape[1]]
    up = ndimage.binary_dilation(up, np.ones((2*f+1, 2*f+1), bool))
    return up & (dem_hr < level)

# ── 符号 ───────────────────────────────────────────────────────────
def symbol(kind, x, y, r, major=False):
    """阵营用形状区分（黑白印刷也能读）；主要城市外加一圈。"""
    s = []
    if major: s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+2.4:.2f}" fill="none" stroke="{C["ink"]}" stroke-width="0.8"/>')
    if kind == "cn":
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{C["ink"]}"/>')
    elif kind == "us":
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="1.2"/>')
    elif kind == "corp":
        d = r*1.35
        s.append(f'<path d="M{x:.1f},{y-d:.1f} L{x+d:.1f},{y:.1f} L{x:.1f},{y+d:.1f} L{x-d:.1f},{y:.1f} Z" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="1.2"/>')
    else:
        d = r*0.9
        s.append(f'<rect x="{x-d:.1f}" y="{y-d:.1f}" width="{2*d:.1f}" height="{2*d:.1f}" fill="{C["ink"]}"/>')
    return "".join(s)

def rail_svg(pts_xy, kind):
    """铁路：黑线 + 横枕（经典铁路符号，用虚线描边实现）；未通车段画灰色虚线。"""
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_xy)
    if kind == "未通车":
        return f'<path d="{d}" fill="none" stroke="{C["ink2"]}" stroke-width="1.0" stroke-dasharray="4 3"/>'
    w = 0.9 if kind != "支线" else 0.7
    return (f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="{w+1.6:.1f}" stroke-linejoin="round" opacity="0.8"/>'
            f'<path d="{d}" fill="none" stroke="{C["rail"]}" stroke-width="{w}" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="none" stroke="{C["rail"]}" stroke-width="{3.4 if kind != "支线" else 2.8}" stroke-dasharray="0.7 6.3"/>')

def path_d(x, y, close=False, nd=1):
    return "M" + " L".join(f"{a:.{nd}f},{b:.{nd}f}" for a, b in zip(x, y)) + (" Z" if close else "")

def peak_svg(x, y, s=1.0):
    return f'<path d="M{x:.1f},{y-3.6*s:.1f} L{x+3.4*s:.1f},{y+2.4*s:.1f} L{x-3.4*s:.1f},{y+2.4*s:.1f} Z" fill="{C["ink"]}"/>'

# ── 等高线 ─────────────────────────────────────────────────────────
CONTOUR = "#8A6A4A"
def contour_lines(dem, level, to_xy, sigma=1.2, min_len=12, tol=0.35):
    """dem 栅格 → 一个高程的等值线 [(N, 2) 屏幕坐标]。to_xy(行, 列) → (x, y)；先高斯平滑去噪，再按屏幕单位简化。
    同一块 dem 要取很多个高程时，先自己平滑好再传 sigma=0，省得重复算。"""
    from skimage import measure
    from shapely.geometry import LineString
    sm = ndimage.gaussian_filter(dem.astype(np.float64), sigma) if sigma else dem
    out = []
    for c in measure.find_contours(sm, level):
        x, y = to_xy(c[:, 0], c[:, 1])
        ls = LineString(np.column_stack([x, y]))
        if ls.length < min_len: continue
        out.append(np.asarray(ls.simplify(tol).coords))
    return out

def contour_paths(dem, levels, to_xy, sigma=1.2, min_len=12, tol=0.35):
    """dem 栅格 → {高程: SVG path d}。"""
    sm = ndimage.gaussian_filter(dem.astype(np.float64), sigma) if sigma else dem.astype(np.float64)
    out = {}
    for lv in levels:
        lines = contour_lines(sm, lv, to_xy, 0, min_len, tol)
        if lines: out[lv] = " ".join(path_d(p[:, 0], p[:, 1]) for p in lines)
    return out

def label_contours(S, placer, lines_by_level, size=6.4, every=340, layer="等高线注记", fmt=None, color=None):
    """计曲线注记：沿线找直一点、又没压到别的注记的地方，数字顺着线写、字头朝上。返回注了几处。
    fmt(level) → 文字；color 默认等高线棕。"""
    n = 0
    color = color or CONTOUR
    for lv, lines in lines_by_level.items():
        s_txt = fmt(lv) if fmt else f"{lv}"
        tw = text_width(s_txt, size, "lat")
        for p in lines:
            seg = np.hypot(*np.diff(p, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
            if cum[-1] < 140: continue
            s = 70.0
            while s < cum[-1] - 70:
                a, b = s - 16, s + 16
                xa, ya = np.interp(a, cum, p[:, 0]), np.interp(a, cum, p[:, 1])
                xb, yb = np.interp(b, cum, p[:, 0]), np.interp(b, cum, p[:, 1])
                if math.hypot(xb-xa, yb-ya) < 0.93*32: s += 18; continue
                ang = math.degrees(math.atan2(yb-ya, xb-xa))
                if ang > 90: ang -= 180
                if ang < -90: ang += 180
                xc, yc = (xa+xb)/2, (ya+yb)/2
                ca, sa = abs(math.cos(math.radians(ang))), abs(math.sin(math.radians(ang)))
                hw, hh = tw/2*ca + 4*sa, tw/2*sa + 4*ca
                box = (xc-hw, yc-hh, xc+hw, yc+hh)
                if placer.free(box, pad=3):
                    placer.block(*box)
                    S.add(layer, f'<text x="{xc:.1f}" y="{yc:.1f}" transform="rotate({ang:.1f} {xc:.1f} {yc:.1f})" '
                                 f'font-family="{FAM_LAT}" font-size="{size}" fill="{color}" text-anchor="middle" dominant-baseline="central" '
                                 f'stroke="#FFFFFF" stroke-width="2.2" stroke-linejoin="round" paint-order="stroke">{s_txt}</text>')
                    n += 1
                    s += every
                else:
                    s += 18
    return n

# ── 直角经纬网图廓（等距圆柱、墨卡托）───────────────────────────────
def graticule_rect(S, proj, major, minor, label_every, tick=True, size=8.5):
    x0, y0, x1, y1 = proj.x0, proj.y0, proj.x0+proj.w, proj.y0+proj.h
    g = []
    lon = math.ceil(proj.lon0/major)*major
    while lon <= proj.lon1:
        x, _ = proj.xy(lon, 0)
        g.append(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}"/>')
        lon += major
    lat = math.ceil(proj.lat1/major)*major
    while lat <= proj.lat0:
        _, y = proj.xy(proj.lon0, lat)
        g.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}"/>')
        lat += major
    S.add("经纬网", f'<g stroke="{C["grat"]}" stroke-width="0.35" opacity="0.28">' + "".join(g) + "</g>")
    t = []
    if tick:
        lon = math.ceil(proj.lon0/minor)*minor
        while lon <= proj.lon1 + 1e-9:
            x, _ = proj.xy(lon, 0); L = 6 if abs(lon/major - round(lon/major)) < 1e-9 else 3
            t.append(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y0-L:.1f}"/><line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y1+L:.1f}"/>')
            lon += minor
        lat = math.ceil(proj.lat1/minor)*minor
        while lat <= proj.lat0 + 1e-9:
            _, y = proj.xy(proj.lon0, lat); L = 6 if abs(lat/major - round(lat/major)) < 1e-9 else 3
            t.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0-L:.1f}" y2="{y:.1f}"/><line x1="{x1:.1f}" y1="{y:.1f}" x2="{x1+L:.1f}" y2="{y:.1f}"/>')
            lat += minor
    S.add("图廓", f'<g stroke="{C["frame"]}" stroke-width="0.6">' + "".join(t) + "</g>")
    S.add("图廓", f'<rect x="{x0}" y="{y0}" width="{proj.w:.1f}" height="{proj.h:.1f}" fill="none" stroke="{C["frame"]}" stroke-width="1.0"/>')
    lon = math.ceil(proj.lon0/label_every)*label_every
    while lon <= proj.lon1 + 1e-9:
        x, _ = proj.xy(lon, 0)
        S.text("图廓", x, y0-9, f"{lon % 360:g}°E", size, "lat", anchor="middle")
        S.text("图廓", x, y1+9+size*0.8, f"{(360-lon) % 360:g}°W", size, "lat", fill=C["ink2"], anchor="middle")
        lon += label_every
    lat = math.ceil(proj.lat1/label_every)*label_every
    while lat <= proj.lat0 + 1e-9:
        _, y = proj.xy(proj.lon0, lat)
        s = "0°" if lat == 0 else f"{abs(lat):g}°{'N' if lat > 0 else 'S'}"
        S.text("图廓", x0-9, y+size*0.35, s, size, "lat", anchor="end")
        S.text("图廓", x1+9, y+size*0.35, s, size, "lat", anchor="start")
        lat += label_every

# ── 矩形图框里的曲线经纬网（方位投影区域图）────────────────────────
def graticule_frame(S, P, x0, y0, w, h, step=10, tick_step=2, size=8.5, clip_id="clipMap"):
    """经纬线按投影画成曲线，裁到矩形图框里；与四条边相交处打刻度，整 step 度的注度数。"""
    from shapely.geometry import LineString, box as sbox
    frame = sbox(x0, y0, x0+w, y0+h)
    edges = {"top": LineString([(x0, y0), (x0+w, y0)]), "bottom": LineString([(x0, y0+h), (x0+w, y0+h)]),
             "left": LineString([(x0, y0), (x0, y0+h)]), "right": LineString([(x0+w, y0), (x0+w, y0+h)])}
    from shapely.geometry import MultiLineString
    def curve(kind, v):
        """一条经线 / 纬线的屏幕折线。方位投影里经过对跖点的线会跳成一条贯穿图幅的直线
        （中央经线的对跖经线正好压在中央经线上，刻度和注记就会印两遍），所以按段长把跳段切掉。"""
        if kind == "lon":
            lat = np.linspace(-89.9, 89.9, 721); lon = np.full_like(lat, float(v))
        else:
            lon = np.linspace(0, 360, 1441); lat = np.full_like(lon, float(v))
        x, y = P.xy(lon, lat)
        pts = np.column_stack([x, y])
        seg = np.hypot(*np.diff(pts, axis=0).T)
        ok_ = seg <= 8*np.median(seg)
        runs, cur = [], [0]
        for i, good in enumerate(ok_):
            if good: cur.append(i+1)
            else:
                if len(cur) > 1: runs.append(pts[cur])
                cur = [i+1]
        if len(cur) > 1: runs.append(pts[cur])
        return MultiLineString([r for r in runs]) if len(runs) != 1 else LineString(runs[0])
    g, ticks = [], []
    for kind, vals in (("lon", range(0, 360, tick_step)), ("lat", range(-80, 90, tick_step))):
        for v in vals:
            major = v % step == 0
            ln = curve(kind, v)
            if not ln.intersects(frame): continue
            if major:
                seg = ln.intersection(frame)
                for part in getattr(seg, "geoms", [seg]):
                    if part.geom_type == "LineString" and part.length > 0:
                        c = np.asarray(part.coords); g.append(path_d(c[:, 0], c[:, 1]))
            for e, ed in edges.items():
                hit = ln.intersection(ed)
                for pt in getattr(hit, "geoms", [hit]):
                    if pt.is_empty or pt.geom_type != "Point": continue
                    X, Y = pt.x, pt.y
                    L = 6 if major else 3
                    if e == "top":    ticks.append(f'<line x1="{X:.1f}" y1="{Y:.1f}" x2="{X:.1f}" y2="{Y-L:.1f}"/>')
                    if e == "bottom": ticks.append(f'<line x1="{X:.1f}" y1="{Y:.1f}" x2="{X:.1f}" y2="{Y+L:.1f}"/>')
                    if e == "left":   ticks.append(f'<line x1="{X:.1f}" y1="{Y:.1f}" x2="{X-L:.1f}" y2="{Y:.1f}"/>')
                    if e == "right":  ticks.append(f'<line x1="{X:.1f}" y1="{Y:.1f}" x2="{X+L:.1f}" y2="{Y:.1f}"/>')
                    # 经度只在上下边注字、纬度只在左右边注字，免得两种标注在同一条边上撞车
                    if not major or (kind == "lon") != (e in ("top", "bottom")): continue
                    if kind == "lon":
                        lab, lab2 = f"{v % 360}°E", f"{(360 - v) % 360}°W"
                    else:
                        lab, lab2 = ("0°" if v == 0 else f"{abs(v)}°{'N' if v > 0 else 'S'}"), None
                    if e in ("top", "bottom"):
                        yy = Y - 9 if e == "top" else Y + 9 + size*0.8
                        S.text("图廓", X, yy, lab, size, "lat", anchor="middle")
                        if lab2: S.text("图廓", X, yy + (-size*1.05 if e == "top" else size*1.05), lab2, size*0.8, "lat", fill=C["ink2"], anchor="middle")
                    else:
                        S.text("图廓", X - 9 if e == "left" else X + 9, Y + size*0.35, lab, size, "lat", anchor="end" if e == "left" else "start")
    S.add("经纬网", f'<path d="{" ".join(g)}" fill="none" stroke="{C["grat"]}" stroke-width="0.35" opacity="0.28" clip-path="url(#{clip_id})"/>')
    S.add("图廓", f'<g stroke="{C["frame"]}" stroke-width="0.6">' + "".join(ticks) + "</g>")
    S.add("图廓", f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" stroke="{C["frame"]}" stroke-width="1.0"/>')

def sample_window(arr, ppd, lon_left, lat_top, lon, lat, order=1):
    """按经纬度采样一块局部栅格（第 0 列 = lon_left，第 0 行 = lat_top，不跨 0°/360°）。"""
    col = (np.asarray(lon, float) - lon_left)*ppd - 0.5
    row = (lat_top - np.asarray(lat, float))*ppd - 0.5
    return ndimage.map_coordinates(arr, [row, col], order=order, mode="nearest")

# ── 图例部件 ───────────────────────────────────────────────────────
def scale_bar(S, layer, x, y, units_per_km, step_km, n, size=7.2, h=4.5, title=None):
    """黑白相间的比例尺。units_per_km：屏幕单位/千米。"""
    if title: S.text(layer, x, y-8, title, 9.5, "cjk_b", weight="bold")
    seg = step_km*units_per_km
    for i in range(n):
        S.add(layer, f'<rect x="{x+i*seg:.1f}" y="{y:.1f}" width="{seg:.1f}" height="{h}" '
                     f'fill="{C["ink"] if i % 2 == 0 else "#FFFFFF"}" stroke="{C["ink"]}" stroke-width="0.5"/>')
        S.text(layer, x+i*seg, y+h+size+3, f"{i*step_km:,}", size, "lat", anchor="middle")
    S.text(layer, x+n*seg, y+h+size+3, f"{n*step_km:,} km", size, "lat", anchor="middle")

def hypso_bar(S, layer, x, y, w, vmin, vmax, step, gid, h=8, size=6.8, title=None):
    if title: S.text(layer, x, y-6, title, 9.5, "cjk_b", weight="bold")
    vals = np.linspace(vmin, vmax, 160); cols = ramp(vals, HYPSO)
    stops = "".join(f'<stop offset="{i/159:.3f}" stop-color="rgb({int(c[0])},{int(c[1])},{int(c[2])})"/>' for i, c in enumerate(cols))
    S.add(layer, f'<linearGradient id="{gid}">{stops}</linearGradient><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gid})" stroke="{C["ink"]}" stroke-width="0.5"/>')
    v = vmin
    while v <= vmax:
        xx = x + (v-vmin)/(vmax-vmin)*w
        S.add(layer, f'<line x1="{xx:.1f}" y1="{y+h}" x2="{xx:.1f}" y2="{y+h+3}" stroke="{C["ink"]}" stroke-width="0.5"/>')
        S.text(layer, xx, y+h+size+5, f"{v:+,}".replace("+0", "0").replace("-", "−"), size, "lat", anchor="middle")
        v += step

# ── 图幅索引（系列图共用）──────────────────────────────────────────
SHEETS = [("水手峡谷战区图", ("box", 238, 334, 5, -20)), ("塔西斯区域图", ("box", 192, 272, 32, -22)),
          ("北方海极区图", ("cap", 5)), ("海拉斯区域图", ("laea", -39.0, 70.0, 0.40, 1400, 1000))]
_thumb = {}
def thumb_rgb():
    """4 px/度的全火星晕渲小图，0–360°E 排布（索引图、位置图用）。"""
    if "rgb" not in _thumb:
        d, Z, f = load_dem32_avg(), load_masks(), 8
        dd = d.reshape(5760//f, f, 11520//f, f).mean(axis=(1, 3))
        ms = [Z[k].reshape(5760//f, f, 11520//f, f).mean(axis=(1, 3)) > 0.4 for k in ("borealis", "hellas", "marineris")]
        lv = [int(Z["level_borealis"]), int(Z["level_hellas"]), int(Z["level_marineris"])]
        _thumb["rgb"] = np.roll(relief_rgb(dd, ms, lv, 32//f, zfac=6.0), -180*(32//f), axis=1)
    return _thumb["rgb"]

def index_map(S, layer, x, y, w, current):
    """全火星小图（等距圆柱 0–360°E），框出本系列各图幅的范围，本图用红框。"""
    h, k = w/2, w/360
    S.text(layer, x, y-8, "图幅索引", 9.5, "cjk_b", weight="bold")
    S.add(layer, f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="none" href="{png_data_uri(thumb_rgb(), quality=88)}"/>')
    g = "".join(f'<line x1="{x+lo*k:.1f}" y1="{y}" x2="{x+lo*k:.1f}" y2="{y+h}"/>' for lo in (90, 180, 270)) + \
        "".join(f'<line x1="{x}" y1="{y+(90-la)*k:.1f}" x2="{x+w}" y2="{y+(90-la)*k:.1f}"/>' for la in (-45, 0, 45))
    S.add(layer, f'<g stroke="{C["grat"]}" stroke-width="0.3" opacity="0.3">{g}</g>')
    S.add(layer, f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{C["frame"]}" stroke-width="0.7"/>')
    for lo in (0, 90, 180, 270, 360):
        S.text(layer, x+lo*k, y+h+9, f"{lo}°E", 6.2, "lat", fill=C["ink2"], anchor="middle")
    for name, fp in SHEETS:
        cur = name == current
        st = (f'stroke="{C["alert"]}" stroke-width="1.4"' if cur else f'stroke="{C["ink"]}" stroke-width="0.6" stroke-dasharray="2.5 1.5"')
        if fp[0] == "laea":                                            # 方位投影图幅：把矩形图框逆投影回经纬度，画成曲边框
            _, la0, lo0, sc, fw, fh = fp
            A = Azimuthal(la0, lo0, fw/2, fh/2, sc)
            t = np.linspace(0, 1, 40)
            ex = np.r_[t*fw, np.full(40, fw), (1-t)*fw, np.zeros(40)]; ey = np.r_[np.zeros(40), t*fh, np.full(40, fh), (1-t)*fh]
            lon, lat, _ = A.inverse(ex, ey)
            S.add(layer, f'<path d="{path_d(x+lon*k, y+(90-lat)*k, close=True)}" fill="none" {st}/>')
            bx, by, bh = float(x+lon.min()*k), float(y+(90-lat.max())*k), 0
        elif fp[0] == "box":
            _, lo0, lo1, la0, la1 = fp
            bx, by, bw, bh = x+lo0*k, y+(90-la0)*k, (lo1-lo0)*k, (la0-la1)*k
            S.add(layer, f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="none" {st}/>')
        else:
            bx, by, bw, bh = x, y, w, (90-fp[1])*k
            S.add(layer, f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="none" {st}/>')
        S.text(layer, bx+2.5, by+(8 if fp[0] != "cap" else bh-3), name.replace("图", "") if not cur else "本图", 6.4, "cjk",
               fill=C["alert"] if cur else C["ink"], halo=1.8)

def note_lines(S, layer, x, y, lines, size=8.6, lh=15, fill=None):
    """说明文字。以全角空格开头的行是上一条的续行，缩进对齐「· 」——
    渲染器会吞掉行首空白（连全角空格也吞），所以缩进只能挪 x。"""
    for i, s in enumerate(lines):
        ind = s.startswith("　")
        S.text(layer, x + (size*1.33 if ind else 0), y + i*lh, s.lstrip("　 "), size, "cjk", fill=fill or C["ink2"])
    return y + len(lines)*lh

def hav_km(lat1, lon1, lat2, lon2):
    """球面大圆距离（km），参数可以是数组。"""
    p1, p2 = np.radians(lat1), np.radians(lat2); dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin((p2-p1)/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R/1e3*np.arcsin(np.sqrt(np.clip(a, 0, 1)))

def fmt_m(v):
    return f"{v:+,.0f}".replace("+", "").replace("-", "−") if v < 0 else f"{v:,.0f}"

def split_line(coords, proj, max_jump_deg=1.0):
    """GeoJSON 折线（±180 经度）→ 按跳变与投影接缝切段。
    坑：等距圆柱把经度折算到 [lon0, lon0+360)，一段折线跨过图框西边线时，前一点被折到图的最东边，
    不断开就会画出一条横贯全图的直线。"""
    unwrap = getattr(proj, "unwrap", None)
    segs, cur, prev = [], [], None
    for lo, la in coords:
        lo = lo % 360
        seam = unwrap is not None and prev is not None and abs(float(unwrap(lo)) - float(unwrap(prev[0]))) > 180
        if prev is not None and (seam or abs(((lo-prev[0]+180) % 360)-180) > max_jump_deg):
            if len(cur) > 1: segs.append(cur)
            cur = []
        cur.append((lo, la)); prev = (lo, la)
    if len(cur) > 1: segs.append(cur)
    return segs
