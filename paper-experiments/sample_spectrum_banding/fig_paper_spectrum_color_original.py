"""
Revised paper figure per feedback: only the "bad" (informative) case - hdr_4000 - not
scientist_4000 (where the artifact is masked by the image's own strong density feature);
color instead of grayscale; the actual texture shown behind the point-set crops; and a 4th
column for the raw QMC input sequence (unwarped Halton (u,v)) before any method warps it.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import cv2

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TAG = "hdr_4000"
TEXTURE_PATH = os.path.join(OUT_DIR, "..", "..", "quadlight", "hdr", "frame_00180.hdr")

METHOD_KEYS = [
    ("Input\n(QMC seq.)", None, None),
    ("2D CDF", "x_cdf", "y_cdf"),
    ("Alias\n(per-pixel)", "x_alias", "y_alias"),
    ("BudgetLeaf\nAlias", "x_bla", "y_bla"),
]

TITLE_FONTSIZE = 16.7  # empirically calibrated against measured cap-height of matching
                          # glyphs ("2D") in the compiled PDF at 300dpi (body text: 22px;
                          # iterated until title matched) to look like the surrounding
                          # column body text once the figure is placed at \linewidth in
                          # the two-column doc

GRID = (270, 480)          # rasterization grid for the FFT (rows, cols)
SPEC_HALF = (100, 220)      # (half-height, half-width) of the central spectrum crop -
                              # wide enough in x to include Alias's off-axis artifact peak
                              # (verified at (dy,dx)=(48,182) in this grid)
def load_texture_rgb():
    im = cv2.imread(TEXTURE_PATH, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float64)
    mapped = im / (1.0 + im)            # simple Reinhard tonemap for display only
    return np.clip(mapped, 0, 1) ** (1 / 2.2)


def balanced_crop(seqs, sizes=(0.11, 0.13, 0.15), min_count=500):
    """Find a single crop window (same physical patch, since the texture is shown
    underneath every column) where all sequences - not just CDF - have a comparable
    point count. A window chosen from CDF's distribution alone tends to land in a
    brighter-than-average patch, where the raw uniform QMC input looks artificially
    sparse next to the density-warped methods (they concentrate there; it doesn't)."""
    best = None
    for w in sizes:
        half = w / 2
        for cx in np.arange(0.15, 0.86, 0.02):
            for cy in np.arange(0.15, 0.86, 0.02):
                counts = np.array([
                    np.sum((np.abs(x - cx) < half) & (np.abs(y - cy) < half))
                    for x, y in seqs
                ])
                if counts.min() < min_count:
                    continue
                ratio = counts.max() / counts.min()
                if best is None or ratio < best[0]:
                    best = (ratio, cx, cy, half)
    _, cx, cy, half = best
    x0, x1 = max(0.0, cx - half), min(1.0, cx + half)
    y0, y1 = max(0.0, cy - half), min(1.0, cy + half)
    return (x0, x1), (y0, y1)


def power_spectrum(x, y, grid=GRID):
    rows, cols = grid
    hist, _, _ = np.histogram2d(y, x, bins=[rows, cols], range=[[0, 1], [0, 1]])
    hist = hist - hist.mean()
    wy = np.hanning(rows)[:, None]
    wx = np.hanning(cols)[None, :]
    hist = hist * wy * wx
    F = np.fft.fftshift(np.fft.fft2(hist))
    return np.abs(F) ** 2


def central_crop(P, half=SPEC_HALF):
    rows, cols = P.shape
    cy, cx = rows // 2, cols // 2
    hy, hx = half
    return P[max(0, cy - hy):cy + hy, max(0, cx - hx):cx + hx]


data = np.load(os.path.join(OUT_DIR, f"samples_{TAG}.npz"))
texture = load_texture_rgb()
H, W = texture.shape[:2]
u, v = data["u"], data["v"]

xr, yr = balanced_crop([(u, v), (data["x_cdf"], data["y_cdf"]),
                        (data["x_alias"], data["y_alias"]), (data["x_bla"], data["y_bla"])])
col0, col1 = int(xr[0] * W), int(xr[1] * W)
row0, row1 = int(yr[0] * H), int(yr[1] * H)
tex_crop = texture[row0:row1, col0:col1]

# Geometry computed in absolute inches (not fractions) so panels stay exactly square
# and margins stay symmetric (centered) regardless of TITLE_FONTSIZE - fractions alone
# are fragile: growing a margin's fraction eats into panel width but not panel height,
# silently turning "square" panels into rectangles.
PANEL_IN = 1.55                        # panel side length
GAP_IN = 0.12                          # horizontal gap between panels
ROW_GAP_IN = 0.03                      # vertical gap between the points/spectrum rows
LEFT_MARGIN_IN = 0.065 * TITLE_FONTSIZE   # room for the rotated row labels; scales
RIGHT_MARGIN_IN = LEFT_MARGIN_IN          # with font size; kept equal to left to
                                            # center the panel block in the column
TOP_MARGIN_IN = 0.039 * TITLE_FONTSIZE * 2  # room for the 2-line column titles
BOTTOM_MARGIN_IN = 0.05

W_TOTAL = LEFT_MARGIN_IN + 4 * PANEL_IN + 3 * GAP_IN + RIGHT_MARGIN_IN
H_TOTAL = TOP_MARGIN_IN + 2 * PANEL_IN + ROW_GAP_IN + BOTTOM_MARGIN_IN

fig, axes = plt.subplots(2, 4, figsize=(W_TOTAL, H_TOTAL))

for m_i, (name, xk, yk) in enumerate(METHOD_KEYS):
    x, y = (u, v) if xk is None else (data[xk], data[yk])

    pt_ax, sp_ax = axes[0, m_i], axes[1, m_i]

    pt_ax.imshow(tex_crop, extent=(col0, col1, row1, row0), aspect="auto")
    m = (x >= xr[0]) & (x < xr[1]) & (y >= yr[0]) & (y < yr[1])
    pt_ax.scatter(x[m] * W, y[m] * H, s=3.0, c="#00E5FF",
                  edgecolors="black", linewidths=0.15)
    pt_ax.set_xlim(col0, col1)
    pt_ax.set_ylim(row1, row0)
    pt_ax.set_xticks([])
    pt_ax.set_yticks([])
    pt_ax.set_title(name, fontsize=TITLE_FONTSIZE, linespacing=0.9)

    P = central_crop(power_spectrum(x, y))
    logP = np.log1p(P)
    vmin, vmax = np.percentile(logP, [2, 99.7])
    norm = np.clip((logP - vmin) / (vmax - vmin), 0, 1) ** 0.5  # gamma boost - makes
                                                                    # the faint artifact
                                                                    # peaks legible
    sp_ax.imshow(norm, cmap="inferno", vmin=0, vmax=1, aspect="auto")
    sp_ax.set_xticks([])
    sp_ax.set_yticks([])
    if name.startswith("Alias"):
        hy, hx = SPEC_HALF
        pts = [(hx + dx, hy + dy) for dy, dx in [(48, 182), (-48, -182)]]
        sp_ax.scatter(*zip(*pts), s=280, facecolors="none",
                      edgecolors="#00E5FF", linewidths=1.3)  # marker size is in
                                                                # screen units, so this
                                                                # stays circular under
                                                                # aspect="auto"

axes[0, 0].set_ylabel("points", fontsize=TITLE_FONTSIZE)
axes[1, 0].set_ylabel("spectrum", fontsize=TITLE_FONTSIZE)

fig.subplots_adjust(
    left=LEFT_MARGIN_IN / W_TOTAL,
    right=1 - RIGHT_MARGIN_IN / W_TOTAL,
    top=1 - TOP_MARGIN_IN / H_TOTAL,
    bottom=BOTTOM_MARGIN_IN / H_TOTAL,
    hspace=ROW_GAP_IN / PANEL_IN,
    wspace=GAP_IN / PANEL_IN,
)
out_path = os.path.join(OUT_DIR, "fig_spectrum_paper_color.png")
fig.savefig(out_path, dpi=220)
print(f"Saved {out_path}")
