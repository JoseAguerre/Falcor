"""
Teaser v2 (see make_teaser.py history / chat for v1). Two scene panels side by side
(rover | cinema), each a 4-way diagonal-band technique comparison (Random / 2D CDF / Ours /
Reference) with white divider lines and white bold serif labels overlaid directly on the
image, LEFT-aligned per band. Below each panel: a single tightly-packed row of 8 small
closeups (2 marker regions x 4 techniques), borderless, with the technique name overlaid
inside each thumbnail (top-left) instead of a separate label row.

"Ours" is relabeled for the teaser only (display name, not the underlying technique):
BudgetLeafAlias4000 -> "BudgetLeafAlias" (rover), AliasCtu -> "CodecLeafAlias" (cinema) -
this is a presentation choice for the teaser, the actual rendered/measured technique behind
each is unchanged (see results/experiment17/SUMMARY.md and results/quality_summary_weyl.json
for the real technique names and numbers).

Inputs (already-rendered, no new Mogwai renders):
  rover:  results/experiment17/quality_v3/{Random,Cdf2D,BudgetLeafAlias4000}.ToneMapper.dst.1.png
          + reference.ToneMapper.dst.8000.png
  cinema: results/quality_weyl/cinema/{Random,Cdf2D,AliasCtu}.ToneMapper.dst.1.png
          + reference.ToneMapper.dst.1224.png
Output: results/experiment17/teaser.png
"""
from PIL import Image, ImageDraw, ImageFont
import os

REPO = r"C:\Users\Jose\Desktop\Falcor"
SS = 2  # supersample factor for smoother diagonal lines / text

W, H = 1920, 1080
DIAG_SHIFT = 220
CROP = 50
DIVIDER_W = 5 * SS
MARKER_W = 4 * SS
MARKER_COLORS = [(255, 235, 0), (0, 220, 255)]  # region A (yellow), region B (cyan)

FONT_MAIN = 46 * SS
FONT_CLOSEUP = 34 * SS

# Single row of 8 closeups per panel: 2 regions x 4 techniques, with a small uniform margin
# between every thumbnail (7 gaps across the row).
N_PER_REGION = 4
THUMB_GAP = 10
CELL_W = (W - THUMB_GAP * 7) // 8
CELL_H = CELL_W  # square thumbnails, matching the 1:1 source crop
ROW_TOP_MARGIN = 18  # separates the closeup row from the main image above

def font(size, bold_path=r"C:\Windows\Fonts\georgiab.ttf"):
    try:
        return ImageFont.truetype(bold_path, size)
    except Exception:
        return ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", size)

def boundaries_at(y):
    t = y / (H - 1)
    shift = (t - 0.5) * DIAG_SHIFT
    b1 = max(0, min(W, int(W / 4 + shift)))
    b2 = max(0, min(W, int(W / 2 + shift)))
    b3 = max(0, min(W, int(W * 3 / 4 + shift)))
    return b1, b2, b3

def draw_label_stroke(draw, xy, text, f, fill=(255, 255, 255), stroke=(0, 0, 0), sw=2):
    draw.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)

def build_panel(scene_dir, ours_file_label, ours_display_name, ref_name, regions):
    rand_im = Image.open(os.path.join(scene_dir, "Random.ToneMapper.dst.1.png")).convert("RGB")
    cdf_im = Image.open(os.path.join(scene_dir, "Cdf2D.ToneMapper.dst.1.png")).convert("RGB")
    ours_im = Image.open(os.path.join(scene_dir, f"{ours_file_label}.ToneMapper.dst.1.png")).convert("RGB")
    ref_im = Image.open(os.path.join(scene_dir, ref_name)).convert("RGB")
    imgs = [rand_im, cdf_im, ours_im, ref_im]
    names = ["Random", "2D CDF", ours_display_name, "Reference"]

    # --- diagonal composite at supersampled res for smooth divider lines ---
    comp = Image.new("RGB", (W * SS, H * SS))
    up_imgs = [im.resize((W * SS, H * SS), Image.LANCZOS) for im in imgs]
    for y in range(H * SS):
        y0 = y // SS
        b1, b2, b3 = boundaries_at(y0)
        b1, b2, b3 = b1 * SS, b2 * SS, b3 * SS
        row = Image.new("RGB", (W * SS, 1))
        if b1 > 0: row.paste(up_imgs[0].crop((0, y, b1, y + 1)), (0, 0))
        if b2 > b1: row.paste(up_imgs[1].crop((b1, y, b2, y + 1)), (b1, 0))
        if b3 > b2: row.paste(up_imgs[2].crop((b2, y, b3, y + 1)), (b2, 0))
        if W * SS > b3: row.paste(up_imgs[3].crop((b3, y, W * SS, y + 1)), (b3, 0))
        comp.paste(row, (0, y))

    draw = ImageDraw.Draw(comp)
    top_b1, top_b2, top_b3 = boundaries_at(0)
    bot_b1, bot_b2, bot_b3 = boundaries_at(H - 1)
    for (tb, bb) in [(top_b1, bot_b1), (top_b2, bot_b2), (top_b3, bot_b3)]:
        draw.line([(tb * SS, 0), (bb * SS, H * SS)], fill=(255, 255, 255), width=DIVIDER_W)

    # White bold serif labels, centered in the space between each band's dividers (using
    # this row's own boundaries, at the vertical height where the text sits).
    f = font(FONT_MAIN)
    margin_top = 16 * SS
    label_y_px = margin_top // SS
    lb1, lb2, lb3 = boundaries_at(label_y_px)
    spans = [(0, lb1), (lb1, lb2), (lb2, lb3), (lb3, W)]
    for name, (x0, x1) in zip(names, spans):
        cx = ((x0 + x1) / 2) * SS
        bbox = draw.textbbox((0, 0), name, font=f)
        tw = bbox[2] - bbox[0]
        draw_label_stroke(draw, (cx - tw / 2, margin_top), name, f, sw=max(1, SS))

    # Marker squares (one per region, color-coded to match the closeup row's group order)
    for (mx, my), color in zip(regions, MARKER_COLORS):
        draw.rectangle([mx * SS, my * SS, (mx + CROP) * SS, (my + CROP) * SS],
                        outline=color, width=MARKER_W)

    comp = comp.resize((W, H), Image.LANCZOS)

    # --- closeup row: 2 regions x 4 techniques = 8 borderless thumbnails on a white
    # background, small margin between every thumbnail, technique name overlaid centered
    # horizontally near the TOP of each thumbnail (not vertically centered), all at ONE
    # fixed size shared across every label (sized to fit "BudgetLeafAlias", the longest) ---
    row_img = Image.new("RGB", (W, CELL_H), (255, 255, 255))
    row_img_ss = row_img.resize((W * SS, CELL_H * SS), Image.NEAREST)
    rdraw = ImageDraw.Draw(row_img_ss)
    max_text_w = CELL_W * SS - 16 * SS  # leave a little padding inside the thumbnail

    # Fixed size for every closeup label, determined once from the longest label so nothing
    # overflows its cell - all labels render at this same size, not auto-fit per-label.
    fit_size = FONT_CLOSEUP
    fc = font(fit_size)
    bbox = rdraw.textbbox((0, 0), "BudgetLeafAlias", font=fc)
    while (bbox[2] - bbox[0]) > max_text_w and fit_size > 10 * SS:
        fit_size -= 2 * SS
        fc = font(fit_size)
        bbox = rdraw.textbbox((0, 0), "BudgetLeafAlias", font=fc)
    top_pad = 8 * SS

    x_cursor = 0
    for region_i, (mx, my) in enumerate(regions):
        for i, (im, name) in enumerate(zip(imgs, names)):
            crop = im.crop((mx, my, mx + CROP, my + CROP)).resize((CELL_W * SS, CELL_H * SS), Image.NEAREST)
            row_img_ss.paste(crop, (x_cursor * SS, 0))
            bbox = rdraw.textbbox((0, 0), name, font=fc)
            tw = bbox[2] - bbox[0]
            tx = x_cursor * SS + (CELL_W * SS - tw) / 2
            ty = top_pad - bbox[1]
            draw_label_stroke(rdraw, (tx, ty), name, fc, sw=max(1, SS))
            x_cursor += CELL_W + THUMB_GAP

    row_img = row_img_ss.resize((W, CELL_H), Image.LANCZOS)
    return comp, row_img

# All 4 already-picked from prior figures - none invented fresh. Ordered left-to-right to
# match where their marker squares actually fall in the main image (leftmost square's 4
# crops first), so the closeup row reads left-to-right the same way the markers do:
#   rover:  cyan (x=865, left) then magenta (x=1190, right) - from figure_rover_newcam_v5.png
#   cinema: yellow (x=208, left) then magenta (x=1168, right) - from figure_cinema.png
rover_regions = [(865, 610), (1190, 475)]
cinema_regions = [(208, 692), (1168, 592)]

rover_comp, rover_row = build_panel(
    os.path.join(REPO, r"results\experiment17\quality_v3"),
    "BudgetLeafAlias4000", "BudgetLeafAlias", "reference.ToneMapper.dst.8000.png",
    rover_regions)

cinema_comp, cinema_row = build_panel(
    os.path.join(REPO, r"results\quality_weyl\cinema"),
    "AliasCtu", "CodecLeafAlias", "reference.ToneMapper.dst.1224.png",
    cinema_regions)

GAP = 10
top_h = H
bottom_h = rover_row.height
final_w = W * 2 + GAP
final_h = top_h + ROW_TOP_MARGIN + bottom_h
final = Image.new("RGB", (final_w, final_h), (255, 255, 255))
final.paste(rover_comp, (0, 0))
final.paste(cinema_comp, (W + GAP, 0))
final.paste(rover_row, (0, top_h + ROW_TOP_MARGIN))
final.paste(cinema_row, (W + GAP, top_h + ROW_TOP_MARGIN))

out_path = os.path.join(REPO, r"results\experiment17\teaser.png")
final.save(out_path)
print("Saved", out_path, final.size)
