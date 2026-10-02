"""
Experiment 22: a new supplementary figure for the figures-only page - denoised-output
closeups for Convergence and Fireplace Room, 2D CDF vs CodecLeafAlias (AliasCtu), at the 2
regions per scene where the DENOISED FLIP difference between them is largest (i.e. where our
technique's cleaner input gives the denoiser the biggest advantage) - not the same regions
used elsewhere in this experiment, which were picked from the NOISY renders.

FLIP is computed here with NVIDIA's own official flip_evaluator Python package (pip installed
this session - the reference implementation of the published FLIP metric, same metric this
whole project already reports; the earlier heatmaps in results/experiment8/renders/ were
produced by Falcor's own FLIPPass render-graph node instead, which is why the absolute mean
values won't match exactly - both implement the same metric, just via different code paths
and possibly different default viewing-condition parameters. Region selection only needs
INTERNAL consistency (same computation for both techniques), so this doesn't affect its
validity - flagged here for transparency, not hidden).

Region search: same CropSize (128) and displayed UpscaleTo (500) as figures_only_restir_v9's
closeups (the "previous figure" the request refers to), searched over a 1920x1080 grid,
scored by mean(FLIP_2dcdf - FLIP_ours) in the window (positive = our technique wins), with
the same brightness/variance sanity filters used everywhere else in this experiment, and a
minimum center-to-center distance so the 2 regions per scene land in genuinely different
spots.

Output: a 2-row x 8-column grid.
  Row 1 (denoised color): 2D CDF/Ours x Convergence-A/B x Fireplace-A/B
  Row 2 (FLIP heatmap, same 8 regions/techniques, magma-colored)
"""
import os
import glob
import numpy as np
import cv2
import flip_evaluator as flip
from PIL import Image, ImageDraw, ImageFont

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LIBERTINE_BOLD = r"C:\Users\Jose\AppData\Local\Programs\MiKTeX\fonts\opentype\public\libertine\LinLibertine_RB.otf"
LIBERTINE_REGULAR = r"C:\Users\Jose\AppData\Local\Programs\MiKTeX\fonts\opentype\public\libertine\LinLibertine_R.otf"
group_font = ImageFont.truetype(LIBERTINE_BOLD, 36)
cell_font = ImageFont.truetype(LIBERTINE_BOLD, 38)
row_font = ImageFont.truetype(LIBERTINE_BOLD, 40)

CROP_SIZE = 128
UPSCALE_TO = 500
MIN_DIST = 180
SCAN_STRIDE = 12
MARGIN = int(CROP_SIZE * 0.6)

# v2: the first version's automatic search found both Convergence regions on plain wall (no
# object content) - real FLIP-difference peaks, but visually uninteresting. Convergence's
# search is now restricted to a bounding box around the 3x3 sphere cluster + corner mirror
# panels (read off the reference render directly), with a much higher variance floor, so it
# can only land on object surfaces. Fireplace Room's regions were fine as-is, so they're
# pinned via MANUAL_REGIONS to the exact same spot as before instead of re-searching.
SEARCH_BOUNDS = {
    "convergence": (380, 260, 1350, 980),  # x0, y0, x1, y1 - the sphere cluster area
    "fireplace_room": None,
}
VARIANCE_FLOOR = {
    "convergence": 500,
    "fireplace_room": 120,
}
MANUAL_REGIONS = {
    "fireplace_room": [(1492, 208), (1264, 532)],
}

SCENES = {
    "convergence": {"ref_glob": "results/quality_weyl/convergence/reference.ToneMapper.dst.*.png"},
    "fireplace_room": {"ref_glob": "results/quality_weyl/fireplace_room/reference.ToneMapper.dst.*.png"},
}
TECH_DIRS = {"Cdf2D": "Cdf2D", "Ours": "AliasCtu"}
TECH_NAMES = {"Cdf2D": "2D CDF", "Ours": "CodecLeafAlias"}


def load01(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return im


def find_regions(scene):
    ref_path = glob.glob(os.path.join(REPO, SCENES[scene]["ref_glob"]))[0]
    ref = load01(ref_path)
    H, W, _ = ref.shape

    denoised = {}
    flip_raw = {}
    for key, dirtech in TECH_DIRS.items():
        p = os.path.join(REPO, "results", "experiment8", "renders", f"{scene}_{dirtech}", "denoised.ToneMapper.dst.4.png")
        denoised[key] = load01(p)
        errmap, _, _ = flip.evaluate(ref, denoised[key], "LDR", applyMagma=False)
        flip_raw[key] = errmap[..., 0]

    def score_at(x0, y0):
        cdf_flip = flip_raw["Cdf2D"][y0:y0 + CROP_SIZE, x0:x0 + CROP_SIZE].mean()
        ours_flip = flip_raw["Ours"][y0:y0 + CROP_SIZE, x0:x0 + CROP_SIZE].mean()
        return cdf_flip - ours_flip, cdf_flip, ours_flip

    if scene in MANUAL_REGIONS:
        chosen = []
        for x0, y0 in MANUAL_REGIONS[scene]:
            score, cdf_flip, ours_flip = score_at(x0, y0)
            chosen.append((score, x0, y0, cdf_flip, ours_flip))
            print(f"[{scene}] region {len(chosen)} (MANUAL, unchanged from before): x={x0} y={y0} "
                  f"cdfFLIP={cdf_flip:.4f} oursFLIP={ours_flip:.4f} score={score:.4f}")
        return denoised, flip_raw, chosen

    ref_gray = ref.mean(axis=2)
    bounds = SEARCH_BOUNDS.get(scene)
    x_lo, y_lo = (bounds[0], bounds[1]) if bounds else (MARGIN, MARGIN)
    x_hi = (bounds[2] - CROP_SIZE) if bounds else (W - CROP_SIZE - MARGIN)
    y_hi = (bounds[3] - CROP_SIZE) if bounds else (H - CROP_SIZE - MARGIN)
    var_floor = VARIANCE_FLOOR.get(scene, 120)

    candidates = []
    for y0 in range(y_lo, y_hi, SCAN_STRIDE):
        for x0 in range(x_lo, x_hi, SCAN_STRIDE):
            patch = ref_gray[y0:y0 + CROP_SIZE, x0:x0 + CROP_SIZE]
            bright = patch.mean() * 255
            var = patch.var() * (255 ** 2)
            if bright < 8 or var < var_floor:
                continue
            score, cdf_flip, ours_flip = score_at(x0, y0)
            candidates.append((score, x0, y0, cdf_flip, ours_flip))

    candidates.sort(key=lambda c: c[0], reverse=True)
    chosen = []
    for c in candidates:
        score, x0, y0 = c[0], c[1], c[2]
        if any(np.hypot(x0 - cx, y0 - cy) < MIN_DIST for _, cx, cy, *_ in chosen):
            continue
        chosen.append(c)
        print(f"[{scene}] region {len(chosen)}: x={x0} y={y0} cdfFLIP={c[3]:.4f} oursFLIP={c[4]:.4f} score={score:.4f}")
        if len(chosen) == 2:
            break

    return denoised, flip_raw, chosen


def crop_upscale(arr01, x0, y0):
    crop = arr01[y0:y0 + CROP_SIZE, x0:x0 + CROP_SIZE]
    im = Image.fromarray((np.clip(crop, 0, 1) * 255).astype(np.uint8))
    return im.resize((UPSCALE_TO, UPSCALE_TO), Image.NEAREST)


def magma_colorize(errmap01):
    import matplotlib
    norm = np.clip(errmap01, 0, 1)
    colored = matplotlib.colormaps["magma"](norm)[..., :3]
    return colored


def draw_outlined(draw, text, font, xy, fill=(255, 255, 255)):
    x, y = xy
    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def draw_outlined_centered(draw, text, font, xy, fill=(255, 255, 255)):
    """Same outlined-white-on-black-shadow style, but horizontally centered on x."""
    cx, y = xy
    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
        draw.text((cx + dx, y + dy), text, font=font, fill=(0, 0, 0), anchor="ma")
    draw.text((cx, y), text, font=font, fill=fill, anchor="ma")


scene_data = {scene: find_regions(scene) for scene in SCENES}

# Layout: 8 columns (Cdf2D/Ours x ConvA/ConvB/FireA/FireB), 2 rows (denoised color, FLIP)
COLUMN_ORDER = []
for scene, label in [("convergence", "Convergence"), ("fireplace_room", "Fireplace Room")]:
    for closeup_idx in [0, 1]:
        for tech in ["Cdf2D", "Ours"]:
            COLUMN_ORDER.append((scene, label, closeup_idx, tech))

GROUP_HEADER_H = 60
CELL_LABEL_PAD = 8
ROW_LABEL_W = 74
GAP = 4
n_cols = len(COLUMN_ORDER)
cell_w = UPSCALE_TO
total_w = ROW_LABEL_W + n_cols * cell_w + (n_cols - 1) * GAP
total_h = GROUP_HEADER_H + 2 * UPSCALE_TO + GAP

final = Image.new("RGB", (total_w, total_h), (255, 255, 255))
draw = ImageDraw.Draw(final)

# Group headers (span 2 columns each)
group_labels = ["Convergence #1", "Convergence #2", "Fireplace Room #1", "Fireplace Room #2"]
for gi, glabel in enumerate(group_labels):
    x0 = ROW_LABEL_W + gi * 2 * (cell_w + GAP)
    x1 = x0 + 2 * cell_w + GAP
    draw.text(((x0 + x1) / 2, GROUP_HEADER_H / 2), glabel, font=group_font, fill=(0, 0, 0), anchor="mm")

for ci, (scene, label, closeup_idx, tech) in enumerate(COLUMN_ORDER):
    denoised, flip_raw, chosen = scene_data[scene]
    score, x0, y0, cdf_flip, ours_flip = chosen[closeup_idx]

    color_crop = crop_upscale(denoised[tech], x0, y0)
    flip_map = flip_raw[tech][y0:y0 + CROP_SIZE, x0:x0 + CROP_SIZE]
    flip_colored = magma_colorize(flip_map)
    flip_crop = Image.fromarray((flip_colored * 255).astype(np.uint8)).resize((UPSCALE_TO, UPSCALE_TO), Image.NEAREST)

    cell_x = ROW_LABEL_W + ci * (cell_w + GAP)
    final.paste(color_crop, (cell_x, GROUP_HEADER_H))
    final.paste(flip_crop, (cell_x, GROUP_HEADER_H + UPSCALE_TO + GAP))

    # v2: bigger, horizontally-centered label at the top of each cell (no more per-cell
    # colored border - see the group-level black border drawn below instead)
    for row_y in [GROUP_HEADER_H, GROUP_HEADER_H + UPSCALE_TO + GAP]:
        cx = cell_x + cell_w / 2
        draw_outlined_centered(draw, TECH_NAMES[tech], cell_font, (cx, row_y + CELL_LABEL_PAD))

# One big black border grouping each set's 2 columns x 2 rows (denoised + FLIP, 2D CDF + Ours)
GROUP_BORDER_W = 10
for gi in range(len(group_labels)):
    gx0 = ROW_LABEL_W + gi * 2 * (cell_w + GAP)
    gx1 = gx0 + 2 * cell_w + GAP
    gy0 = GROUP_HEADER_H
    gy1 = GROUP_HEADER_H + 2 * UPSCALE_TO + GAP
    draw.rectangle([gx0, gy0, gx1, gy1], outline=(0, 0, 0), width=GROUP_BORDER_W)

# Rotated row labels
for ri, rlabel in enumerate(["Denoised", "FLIP"]):
    txt_img = Image.new("RGBA", (UPSCALE_TO, ROW_LABEL_W), (255, 255, 255, 0))
    tdraw = ImageDraw.Draw(txt_img)
    bbox = tdraw.textbbox((0, 0), rlabel, font=row_font)
    tw = bbox[2] - bbox[0]
    tdraw.text(((UPSCALE_TO - tw) / 2 - bbox[0], (ROW_LABEL_W - (bbox[3] - bbox[1])) / 2 - bbox[1]),
                rlabel, font=row_font, fill=(0, 0, 0, 255))
    rotated = txt_img.rotate(90, expand=True)
    row_y = GROUP_HEADER_H + ri * (UPSCALE_TO + GAP)
    final.paste(rotated, (0, row_y), rotated)

out_path = os.path.join(OUT_DIR, "denoised_flip_grid.png")
final.save(out_path)
print("Saved", out_path, final.size)
