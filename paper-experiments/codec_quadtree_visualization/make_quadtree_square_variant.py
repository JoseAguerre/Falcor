"""
One-off variant of make_quadtree_figures.py for a single request: redo
quadtree_hdr_cinema_frame_00232_black with SQUARE leaves instead of the native-16:9-
aspect leaves the real QuadLightBudgetLeafAliasSampler::build() produces (every split
there bisects both width and height together, so every leaf keeps the source image's own
aspect ratio - that's what the other 30 images in this experiment faithfully reproduce).

To get square leaves, the construction itself has to change: the source is embedded in a
SQUARE canvas (side = max(w,h) = 1920, the 1080-tall frame centered with zero-luminance
padding above/below) before running the identical best-first/variance*area/leaf-budget
algorithm. Since every split of a square still bisects both axes equally, every resulting
leaf is square by construction. The zero-luminance padding rows contribute no variance, so
the algorithm naturally spends almost no budget there. Leaves are clipped back to the
original 1920x1080 window before drawing (a handful of large leaves straddling the padding
boundary will appear cut off at the top/bottom edge - expected, not a bug).

This is a one-off exploration, not a replacement for the faithful port in
make_quadtree_figures.py - the real GPU sampler does NOT do this padding, so this output
should not be described as "how BudgetLeafAlias actually builds its tree", only as a
square-leaf stylistic alternative for this one figure.
"""
import heapq
import os
import cv2
import numpy as np

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.join(REPO, r"results\experiment19")

LUM_R, LUM_G, LUM_B = 0.2126, 0.7152, 0.0722
LEAF_BUDGET = 4000

FAMILY, FRAME_NAME, SCENE = "hdr", "frame_00232.hdr", "cinema"


def build_quadtree(luminance, side, budget):
    """Same algorithm as make_quadtree_figures.py's build_quadtree, run on a square
    (side x side) canvas so every split bisects equal width/height -> square leaves."""
    lum64 = luminance.astype(np.float64)
    sat = np.zeros((side + 1, side + 1), dtype=np.float64)
    satsq = np.zeros((side + 1, side + 1), dtype=np.float64)
    sat[1:, 1:] = np.cumsum(np.cumsum(lum64, axis=0), axis=1)
    satsq[1:, 1:] = np.cumsum(np.cumsum(lum64 * lum64, axis=0), axis=1)

    def query(x0, y0, x1, y1):
        s = sat[y1, x1] - sat[y0, x1] - sat[y1, x0] + sat[y0, x0]
        ssq = satsq[y1, x1] - satsq[y0, x1] - satsq[y1, x0] + satsq[y0, x0]
        return s, ssq

    pq = []
    counter = 0
    final_leaves = []

    def consider(x0, y0, x1, y1):
        nonlocal counter
        s, ssq = query(x0, y0, x1, y1)
        area = float(x1 - x0) * float(y1 - y0)
        mean = s / area if area > 0.0 else 0.0
        variance = max(0.0, ssq / area - mean * mean)
        can_split = (x1 - x0) > 1 and (y1 - y0) > 1 and variance > 0.0
        if can_split:
            counter += 1
            heapq.heappush(pq, (-(variance * area), counter, x0, y0, x1, y1))
        else:
            final_leaves.append((x0, y0, x1, y1))

    consider(0, 0, side, side)

    while pq and (len(final_leaves) + len(pq) + 3 <= budget):
        _, _, x0, y0, x1, y1 = heapq.heappop(pq)
        xm = x0 + (x1 - x0) // 2
        ym = y0 + (y1 - y0) // 2
        consider(x0, y0, xm, ym)
        consider(xm, y0, x1, ym)
        consider(x0, ym, xm, y1)
        consider(xm, ym, x1, y1)

    while pq:
        _, _, x0, y0, x1, y1 = heapq.heappop(pq)
        final_leaves.append((x0, y0, x1, y1))

    return final_leaves


def load_hdr_rgb(path):
    img = cv2.imread(path, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
    if img is None:
        raise FileNotFoundError(path)
    return img[:, :, ::-1].copy()


def tonemap_for_display(rgb):
    lum = LUM_R * rgb[..., 0] + LUM_G * rgb[..., 1] + LUM_B * rgb[..., 2]
    p99 = np.percentile(lum, 99.0)
    exposure = 1.0 / max(p99, 1e-6)
    x = rgb * exposure
    x = x / (1.0 + x)
    x = np.clip(x, 0.0, 1.0) ** (1.0 / 2.2)
    return (x * 255.0 + 0.5).astype(np.uint8)


path = os.path.join(REPO, "quadlight", FAMILY, FRAME_NAME)
rgb = load_hdr_rgb(path)
h, w = rgb.shape[:2]
luminance = (LUM_R * rgb[..., 0] + LUM_G * rgb[..., 1] + LUM_B * rgb[..., 2]).astype(np.float32)

side = max(w, h)  # 1920
pad_top = (side - h) // 2  # 420
pad_luminance = np.zeros((side, side), dtype=np.float32)
pad_luminance[pad_top:pad_top + h, 0:w] = luminance

leaves_padded = build_quadtree(pad_luminance, side, LEAF_BUDGET)

# Clip leaves back to the original w x h window (shifted by -pad_top in y), dropping any
# that fall entirely in the padding band.
leaves = []
for (x0, y0, x1, y1) in leaves_padded:
    cy0, cy1 = y0 - pad_top, y1 - pad_top
    cx0, cx1 = x0, x1
    cy0c, cy1c = max(0, cy0), min(h, cy1)
    cx0c, cx1c = max(0, cx0), min(w, cx1)
    if cx1c > cx0c and cy1c > cy0c:
        leaves.append((cx0c, cy0c, cx1c, cy1c))

display = tonemap_for_display(rgb)
bgr = display[:, :, ::-1].copy()
BLACK = (0, 0, 0)
for (x0, y0, x1, y1) in leaves:
    cv2.rectangle(bgr, (x0, y0), (x1 - 1, y1 - 1), BLACK, 1, lineType=cv2.LINE_AA)
overlaid_rgb = bgr[:, :, ::-1]

out_name = f"quadtree_{FAMILY}_{SCENE}_{os.path.splitext(FRAME_NAME)[0]}_black_squareleaves.png"
out_path = os.path.join(OUT_DIR, out_name)
cv2.imwrite(out_path, overlaid_rgb[:, :, ::-1])
print(f"square-leaf variant: {len(leaves)} leaves visible in-frame ({len(leaves_padded)} total incl. padding) -> {out_name}")
