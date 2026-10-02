"""
Experiment 19: for each quadlight "family" (the video-frame folders under quadlight/),
build the exact variance-driven, budget-limited quadtree that
QuadLightBudgetLeafAliasSampler::build() constructs at leafBudget=4000 (as used by
"BudgetLeafAlias4000" everywhere else in this project), and draw its leaf boundaries over
the source frame.

This is a faithful line-for-line port of the real construction algorithm in
Source/Falcor/Rendering/Lights/QuadLightBudgetLeafAliasSampler.cpp's build() (read
directly, not guessed): a summed-area table over per-texel luminance for O(1) rect
mean/variance queries, then best-first greedy refinement - at each step split whichever
pending rect currently contributes the most total squared error (variance * area) to the
piecewise-constant approximation - until the leaf budget is spent. Luminance weights are
Rec.709 (0.2126 R + 0.7152 G + 0.0722 B) on the raw linear HDR values, matching
QuadLightLuminance.cpp exactly.

One representative frame per family, chosen to be the exact frame each official paperscene
actually uses (grep'd from paperscenes/*/*.pyscene) wherever a family is used by one of the
5 official scenes; "scientist" isn't used by any official scene, so an arbitrary mid-sequence
frame is used for it instead.

No new Mogwai renders - this only reads .hdr frames already on disk and does CPU-side image
processing.
"""
import heapq
import os
import cv2
import numpy as np

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.join(REPO, r"results\experiment19")
os.makedirs(OUT_DIR, exist_ok=True)

LUM_R, LUM_G, LUM_B = 0.2126, 0.7152, 0.0722
LEAF_BUDGET = 4000

# (family, frame filename, which official scene uses it - for the caption/filename)
FAMILIES = [
    ("road",          "frame_00150.hdr", "rover"),
    ("hdr",           "frame_00232.hdr", "cinema"),
    ("cave",          "frame_00221.hdr", "convergence"),
    ("fireplace/4k",  "frame_00082.hdr", "fireplace_room"),
    ("colors",        "frame_00987.hdr", "phonehand"),
    ("scientist",     "frame_00106.hdr", "unused_extra_family"),
]


def build_quadtree(luminance, w, h, budget):
    """Exact port of QuadLightBudgetLeafAliasSampler::build()'s quadtree construction."""
    lum64 = luminance.astype(np.float64)
    sat = np.zeros((h + 1, w + 1), dtype=np.float64)
    satsq = np.zeros((h + 1, w + 1), dtype=np.float64)
    csum = np.cumsum(np.cumsum(lum64, axis=0), axis=1)
    csumsq = np.cumsum(np.cumsum(lum64 * lum64, axis=0), axis=1)
    sat[1:, 1:] = csum
    satsq[1:, 1:] = csumsq

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

    consider(0, 0, w, h)

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
    img = cv2.imread(path, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)  # float32 BGR
    if img is None:
        raise FileNotFoundError(path)
    return img[:, :, ::-1].copy()  # -> RGB


def tonemap_for_display(rgb):
    """Simple, content-agnostic display tonemap: per-image auto-exposure to the 99th
    luminance percentile, Reinhard, gamma 2.2 - just for legible visualization, not a
    physically-authoritative tonemap (the real renderer's own ToneMapper is unrelated to
    quadtree construction, which operates on linear luminance regardless of display)."""
    lum = LUM_R * rgb[..., 0] + LUM_G * rgb[..., 1] + LUM_B * rgb[..., 2]
    p99 = np.percentile(lum, 99.0)
    exposure = 1.0 / max(p99, 1e-6)
    x = rgb * exposure
    x = x / (1.0 + x)  # Reinhard
    x = np.clip(x, 0.0, 1.0) ** (1.0 / 2.2)
    return (x * 255.0 + 0.5).astype(np.uint8)


LINE_COLOR_BGR = (255, 255, 0)  # cyan, opaque - reads clearly against nearly any content
LINE_THICKNESS = 1


def draw_leaves(display_rgb_u8, leaves, color_bgr, thickness=1):
    bgr = display_rgb_u8[:, :, ::-1].copy()  # cv2 draws in BGR
    for (x0, y0, x1, y1) in leaves:
        cv2.rectangle(bgr, (x0, y0), (x1 - 1, y1 - 1), color_bgr, thickness, lineType=cv2.LINE_AA)
    return bgr[:, :, ::-1]  # back to RGB


# 5 candidate line colors/thicknesses to compare per image, stored as (name, BGR, thickness).
# A spread of cool/neutral/warm and light/dark choices so at least one reads well regardless
# of a given frame's own palette (e.g. white disappears on the cinema sky, black disappears
# on the fireplace/cave darks - that's expected, it's why there are 5 to pick from).
LINE_VARIANTS = [
    ("cyan",  (255, 255, 0), 1),   # the original choice from the first pass
    ("white", (255, 255, 255), 1),
    ("black", (0, 0, 0), 1),
    ("red",   (40, 40, 255), 1),
    ("lime",  (0, 255, 140), 1),
]

for family, frame_name, scene in FAMILIES:
    path = os.path.join(REPO, "quadlight", family, frame_name)
    rgb = load_hdr_rgb(path)
    h, w = rgb.shape[:2]
    luminance = (LUM_R * rgb[..., 0] + LUM_G * rgb[..., 1] + LUM_B * rgb[..., 2]).astype(np.float32)

    leaves = build_quadtree(luminance, w, h, LEAF_BUDGET)
    display = tonemap_for_display(rgb)

    safe_family = family.replace("/", "_")
    base_name = f"quadtree_{safe_family}_{scene}_{os.path.splitext(frame_name)[0]}"
    for color_name, color_bgr, thickness in LINE_VARIANTS:
        overlaid = draw_leaves(display, leaves, color_bgr, thickness)
        out_name = f"{base_name}_{color_name}.png"
        out_path = os.path.join(OUT_DIR, out_name)
        cv2.imwrite(out_path, overlaid[:, :, ::-1])  # cv2.imwrite expects BGR
    print(f"{family:14s} {frame_name:18s} -> {len(leaves):5d} leaves -> {base_name}_*.png (x{len(LINE_VARIANTS)})")
