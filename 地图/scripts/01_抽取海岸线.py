#!/usr/bin/env python3
"""从 In The Well p22 原图抽出水体掩膜 → potrace 矢量化。

灰度分层（实测）：
  水体        43-150   （西侧诺克提斯谷地最深约 60，Lake Eos 最浅约 115）
  陆地       155-185
  标签白底   195-255   黑字 0-40

流程（顺序很重要）：
  1. 取 42-150 灰度带
  2. 减去「近白区域膨胀 13px」——杀掉标签框及其灰色光晕
  3. 轻开运算去毛刺
  4. 连通域面积筛选，只留 >= 3000 px 的块  ← 必须在闭运算之前，
     否则闭运算会把标签框残留的细环膨胀成实心矩形
  5. 轻闭运算，回填水面上被标签挖掉的缺口
"""
from PIL import Image, ImageFilter
from collections import deque
import numpy as np, pathlib

HERE     = pathlib.Path(__file__).resolve().parent
MAP_DIR  = HERE.parent
OUT      = MAP_DIR / "产出"
OUT.mkdir(exist_ok=True)
SRC      = MAP_DIR.parent / "TS/Transhuman Space In The Well - Marineris Sea Region Map (p22).png"
# 图框按「整度数边界」定义，使抽出的路径能和经纬网严格对齐：
#   标度 21.81 px/deg；120°W 在 x=132.2；赤道在 y=179.5
#   120°W→30°W, 5°N→25°S  ⇒  1963×655 px = 90°×30°
FRAME    = (132, 70, 2095, 725)
MIN_AREA = 900                      # 连通域最小保留面积（px）。3000 会误删诺克提斯西侧的细谷地

a    = np.array(Image.open(SRC).convert("L"))
crop = a[FRAME[1]:FRAME[3], FRAME[0]:FRAME[2]]

# 1+2) 水体带减去近白膨胀区
nw      = Image.fromarray((crop >= 195).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(13))
exclude = np.array(nw) > 127
mask    = (crop >= 42) & (crop <= 150) & ~exclude

# 3) 轻开运算
m    = Image.fromarray(mask.astype(np.uint8) * 255)
m    = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
mask = np.array(m) > 127

# 4) 连通域面积筛选（8 邻域 BFS）
H, W    = mask.shape
seen    = np.zeros((H, W), bool)
keep    = np.zeros((H, W), bool)
kept, dropped = [], 0
nbr     = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
for sy, sx in zip(*np.nonzero(mask)):
    if seen[sy, sx]:
        continue
    q, comp = deque([(sy, sx)]), []
    seen[sy, sx] = True
    while q:
        y, x = q.popleft(); comp.append((y, x))
        for dy, dx in nbr:
            ny, nx = y+dy, x+dx
            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    if len(comp) >= MIN_AREA:
        ys, xs = zip(*comp); keep[list(ys), list(xs)] = True; kept.append(len(comp))
    else:
        dropped += 1
print(f"连通域：保留 {len(kept)} 块 {sorted(kept, reverse=True)[:8]}…，剔除 {dropped} 块小块")

# 5) 轻闭运算 + 高斯平滑
#    形态学用的是方形核，会留下直角锯齿和标签挖出的方形缺口；
#    模糊后重新二值化，把这些方角磨圆，potrace 出来的海岸线才自然。
m   = Image.fromarray(keep.astype(np.uint8) * 255)
m   = m.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
m   = m.filter(ImageFilter.GaussianBlur(3.2))
out = (np.array(m) > 118).astype(np.uint8) * 255

print(f"图框 {crop.shape[1]}×{crop.shape[0]} px   水体占比 {100*(out>127).sum()/out.size:.2f}%")
Image.fromarray(out).save(OUT / "water_mask.png")
Image.fromarray(255 - out).save(OUT / "water_mask_inv.pbm")     # potrace: 黑=前景

rgb  = np.stack([crop]*3, -1).astype(np.uint8)
edge = np.array(Image.fromarray(out).filter(ImageFilter.FIND_EDGES)) > 40
rgb[edge] = [255, 40, 40]
Image.fromarray(rgb).save(OUT / "preview_叠加检查.png")
print(f"→ {OUT/'water_mask.png'} / {OUT/'water_mask_inv.pbm'} / {OUT/'preview_叠加检查.png'}")
