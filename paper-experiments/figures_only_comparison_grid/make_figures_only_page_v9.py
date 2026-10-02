"""
Experiment 22 (separate document, still does not replace/delete figures_only_page.png,
results_section.tex, or any earlier figures_only_restir_v2-v8/final.png iteration): v9 - a
correction of what v8's "twice as big" experiment should have meant. v8 doubled UpscaleTo
(the DISPLAY size), which barely changed anything because the closeup block always gets
rescaled to match the full-frame photo's height regardless of its native size. What was
actually wanted: double the SOURCE crop SQUARE (CropSize 64 -> 128, centered on the exact
same point v7 used), while keeping the DISPLAY size the same (UpscaleTo still 500) - i.e. the
same-size closeup box now shows twice as much of the image around that point (more context,
"zoomed out" a bit) instead of the box itself growing. The marker square drawn on the
full-frame photo is correspondingly twice as big too, still centered on the same point.

Since make_comparison_figure_v2.ps1's region search assigns a NEW best point every time it
re-scans (and a 128px window scores differently than a 64px one), the exact v7 center points
were preserved deliberately via -ManualRegions (X,Y = v7's old top-left + 32, i.e. the true
center, minus the new half-size 64) rather than letting it re-search.

Source panels are saved as two files per scene again (v9_<scene>.png = full-frame,
v9_<scene>_closeups.png = the closeup grid), same as v8, since cellW is now tied to UpscaleTo
rather than a fixed W/4 (a v8-era change) and no longer happens to equal the source width.
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import os

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LIBERTINE_BOLD = r"C:\Users\Jose\AppData\Local\Programs\MiKTeX\fonts\opentype\public\libertine\LinLibertine_RB.otf"
scene_font = ImageFont.truetype(LIBERTINE_BOLD, 54)

PANELS = [
    ("v9_fireplace_room.png", "Fireplace Room", os.path.join(REPO, "quadlight", "fireplace", "4k", "frame_00082.hdr")),
    ("v9_phonehand.png", "Phone", os.path.join(REPO, "quadlight", "colors", "frame_00987.hdr")),
    ("v9_convergence.png", "Convergence", os.path.join(REPO, "quadlight", "cave", "frame_00221.hdr")),
]

GAP = 8                    # gap between full-frame block and closeup grid
SCENE_GAP = 5              # gap between scene rows (tight, ReSTIR-style)
SIDE_LABEL_W = 68          # width reserved for the rotated scene-name label
HDR_INSET_MARGIN = 12
HDR_INSET_BORDER = 4
HDR_INSET_EXPOSURE = 3.0
HDR_INSET_FRACTION = 0.20
HDR_INSET_TOP = 100


def load_hdr_thumbnail(path, target_h):
    im = cv2.imread(path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float64)
    im = im * HDR_INSET_EXPOSURE
    mapped = im / (1.0 + im)
    mapped = np.clip(mapped, 0, 1) ** (1 / 2.2)
    pil = Image.fromarray((mapped * 255).astype(np.uint8))
    w = int(round(pil.width * target_h / pil.height))
    return pil.resize((w, target_h), Image.LANCZOS)


def build_panel(fname, hdr_path):
    top_block = Image.open(os.path.join(OUT_DIR, fname)).convert("RGB")
    closeups_path = os.path.join(OUT_DIR, fname.replace(".png", "_closeups.png"))
    bottom_block = Image.open(closeups_path).convert("RGB")

    scale = top_block.height / bottom_block.height
    new_w = int(round(bottom_block.width * scale))
    bottom_block = bottom_block.resize((new_w, top_block.height), Image.LANCZOS)

    panel_w = top_block.width + GAP + bottom_block.width
    panel_h = top_block.height
    panel = Image.new("RGB", (panel_w, panel_h), (255, 255, 255))
    panel.paste(top_block, (0, 0))
    panel.paste(bottom_block, (top_block.width + GAP, 0))

    draw = ImageDraw.Draw(panel)
    inset_h = int(top_block.height * HDR_INSET_FRACTION)
    thumb = load_hdr_thumbnail(hdr_path, inset_h)
    tx, ty = HDR_INSET_MARGIN, HDR_INSET_TOP
    draw.rectangle(
        [tx - HDR_INSET_BORDER, ty - HDR_INSET_BORDER,
         tx + thumb.width + HDR_INSET_BORDER, ty + thumb.height + HDR_INSET_BORDER],
        fill=(255, 255, 255),
    )
    panel.paste(thumb, (tx, ty))
    draw.rectangle([tx, ty, tx + thumb.width, ty + thumb.height], outline=(0, 0, 0), width=2)

    return panel


panels = [build_panel(fname, hdr_path) for fname, _, hdr_path in PANELS]
content_w = max(p.width for p in panels)
W = SIDE_LABEL_W + content_w
total_h = sum(p.height for p in panels) + SCENE_GAP * (len(panels) - 1)

final = Image.new("RGB", (W, total_h), (255, 255, 255))
draw = ImageDraw.Draw(final)
y = 0
for (fname, label, hdr_path), panel in zip(PANELS, panels):
    final.paste(panel, (SIDE_LABEL_W, y))
    txt_img = Image.new("RGBA", (panel.height, SIDE_LABEL_W), (255, 255, 255, 0))
    tdraw = ImageDraw.Draw(txt_img)
    bbox = tdraw.textbbox((0, 0), label, font=scene_font)
    tw = bbox[2] - bbox[0]
    tdraw.text(((panel.height - tw) / 2 - bbox[0], (SIDE_LABEL_W - (bbox[3] - bbox[1])) / 2 - bbox[1]),
                label, font=scene_font, fill=(0, 0, 0, 255))
    rotated = txt_img.rotate(90, expand=True)
    final.paste(rotated, (0, y), rotated)
    y += panel.height + SCENE_GAP

out_path = os.path.join(OUT_DIR, "figures_only_restir_v9.png")
final.save(out_path)
print("Saved", out_path, final.size)
