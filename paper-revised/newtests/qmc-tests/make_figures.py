"""Figures of the note.

  points   QMC point sets and power spectra: the input Halton set and the points warped by the 2D CDF, per-pixel alias
           and LeafAlias (4000 leaves, engine placement), over a whole emitter.
  scene    Fence scene overview from a fence_test.py result: exact render, emitter texture, side view.
  fence    Six renders with close-ups from a fence_test.py result: reference, 2D CDF pseudorandom / QMC,
           per-pixel alias pseudorandom / QMC, LeafAlias 4000 QMC.

Usage:
  python make_figures.py points [--emitter data/cinema_frame232_x704_y284_1024x507.hdr] [--points 500]
  python make_figures.py scene  results/fence_cinema_frame232_x704_y284_1024x512_128spp.npz
  python make_figures.py fence  results/fence_cinema_frame232_x704_y284_1024x512_128spp.npz
Output goes to figures/ as .pdf and .png.
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

import fence_test as S  # noqa: E402
from samplers import Cdf2D, LeafAlias, PerPixelAlias, halton, load_emitter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
LUM = np.array([0.2126, 0.7152, 0.0722])
ZOOM = (0.42, 0.69, 0.13)  # close-up: centre x, centre y, width (fractions of the image)
_font = os.environ.get("QMC_FONT")  # optional path to a .otf/.ttf (the note uses Linux Libertine)
if _font and os.path.exists(_font):
    from matplotlib import font_manager
    font_manager.fontManager.addfont(_font)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=_font).get_name()
else:
    plt.rcParams["font.family"] = "serif"


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".pdf"), facecolor="white")
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=220, facecolor="white")
    print("saved", os.path.join(OUT, name + ".pdf"))


def spectrum(x, y, grid=(270, 480)):
    """Power spectrum of the point histogram (Hann window)."""
    rows, cols = grid
    h = np.histogram2d(y, x, bins=[rows, cols], range=[[0, 1], [0, 1]])[0]
    h = (h - h.mean()) * np.hanning(rows)[:, None] * np.hanning(cols)[None, :]
    return np.abs(np.fft.fftshift(np.fft.fft2(h))) ** 2


def central(P, half=(100, 220)):
    cy, cx = P.shape[0] // 2, P.shape[1] // 2
    return P[cy - half[0]:cy + half[0], cx - half[1]:cx + half[1]]


def stripe_ratio(P, dc=3):
    """Strongest line of the spectrum averaged over one axis, divided by its median (1-2 for unstructured sets)."""
    cy, cx = P.shape[0] // 2, P.shape[1] // 2
    px = np.delete(np.delete(P, range(cy - dc, cy + dc + 1), 0).mean(0), range(cx - dc, cx + dc + 1))
    py = np.delete(np.delete(P, range(cx - dc, cx + dc + 1), 1).mean(1), range(cy - dc, cy + dc + 1))
    return max(px.max() / np.median(px), py.max() / np.median(py))


def fig_points(emitter, n_show, n_spectrum=60000, dot=4.5):
    rgb, L = load_emitter(emitter)
    H, W = L.shape
    u, v = halton(n_spectrum, 2), halton(n_spectrum, 3)
    cols = [("Input\n(QMC seq.)", (u, v)), ("2D CDF", Cdf2D(L).sample(u, v)),
            ("Alias\n(per-pixel)", PerPixelAlias(L).sample(u, v)), ("BudgetLeaf\nAlias", LeafAlias(L, 4000).sample(u, v))]
    tex = np.clip(rgb / np.percentile(rgb.mean(-1), 99.5), 0, 1) ** (1 / 2.2)
    PW, GAP, LM, TM, RG = 1.55, 0.10, 0.30, 0.50, 0.04
    PH = PW * H / W
    FW, FH = LM + 4 * PW + 3 * GAP + 0.06, TM + 2 * PH + RG + 0.05
    fig = plt.figure(figsize=(FW, FH))
    for c, (lab, (x, y)) in enumerate(cols):
        left = (LM + c * (PW + GAP)) / FW
        a = fig.add_axes([left, (FH - TM - PH) / FH, PW / FW, PH / FH])
        a.imshow(tex, extent=(0, 1, 1, 0), aspect="auto", interpolation="lanczos")
        a.scatter(x[:n_show], y[:n_show], s=dot, c="#FF1FA0", edgecolors="black", linewidths=0.15)
        a.set_xlim(0, 1)
        a.set_ylim(1, 0)
        a.set_title(lab, fontsize=10.5, linespacing=0.9, pad=3)
        b = fig.add_axes([left, (FH - TM - 2 * PH - RG) / FH, PW / FW, PH / FH])
        P = spectrum(x, y)
        lp = np.log1p(central(P))
        lo, hi = np.percentile(lp, [2, 99.7])
        b.imshow(np.clip((lp - lo) / (hi - lo), 0, 1) ** 0.5, cmap="inferno", aspect="auto")
        for ax in (a, b):
            ax.set_xticks([])
            ax.set_yticks([])
        if c == 0:
            a.set_ylabel("points", fontsize=10.5)
            b.set_ylabel("spectrum", fontsize=10.5)
        print(f"  {lab.replace(chr(10), ' '):22s} spectral stripe ratio {stripe_ratio(P):.2f}")
    save(fig, f"points_{os.path.splitext(os.path.basename(emitter))[0]}_{n_show}")


class Render:
    """Loads a fence_test.py result and composes / tone maps full images."""

    def __init__(self, path):
        self.d = np.load(path)
        self.H, self.W = self.d["base"].shape[:2]
        self.floor = self.d["floor_idx"]
        self.base = self.d["base"].reshape(-1, 3).copy()
        self.em_px = self.d["kind"] == 1
        self.em_exposure = np.percentile(self.base[self.em_px] @ LUM, 99) if self.em_px.any() else 1.0
        self.exposure = 1.0 / np.percentile(self.d["ref"] @ LUM, 99.5)
        zx, zy, zw = ZOOM
        zh = zw * self.W / self.H * 9 / 16
        self.box = (int((zx - zw / 2) * self.W), int((zx + zw / 2) * self.W), max(0, int((zy - zh / 2) * self.H)), min(self.H, int((zy + zh / 2) * self.H)))

    def image(self, key):
        img = self.base.copy()
        img[self.floor] = self.d[key]
        x = img * self.exposure
        x[self.em_px] = img[self.em_px] / self.em_exposure * 0.95  # the visible emitter at its own exposure
        return np.clip(x, 0, 1).reshape(self.H, self.W, 3) ** (1 / 2.2)

    def rmse(self, key):
        ref = self.d["ref"]
        return np.sqrt((((self.d[key] - ref) @ LUM) ** 2).mean()) / (ref @ LUM).mean()

    def boxed(self, ax, img):
        x0, x1, y0, y1 = self.box
        ax.imshow(img, interpolation="lanczos")
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#00E5FF", lw=0.7))

    def closeup(self, ax, img):
        x0, x1, y0, y1 = self.box
        ax.imshow(img[y0:y1, x0:x1], interpolation="nearest", aspect="auto")
        for sp in ax.spines.values():
            sp.set_edgecolor("#00E5FF")
            sp.set_linewidth(0.7)


def grid_figure(rows_title_space, n_rows):
    COLW, GAP, LM = 3.33, 0.04, 0.02
    PW = (COLW - 2 * LM - 2 * GAP) / 3
    PH = PW * 9 / 16
    FH = n_rows * PH + sum(rows_title_space) + 0.02
    fig = plt.figure(figsize=(COLW, FH))

    def ax_at(r, c):
        bottom = FH - (r + 1) * PH - sum(rows_title_space[:r + 1])
        a = fig.add_axes([(LM + c * (PW + GAP)) / COLW, bottom / FH, PW / COLW, PH / FH])
        a.set_xticks([])
        a.set_yticks([])
        return a
    return fig, ax_at


def fig_scene(path):
    R = Render(path)
    fig, ax_at = grid_figure((0.15, 0.02), 1)
    R.boxed(a := ax_at(0, 0), R.image("ref"))
    a.set_title("Scene (exact)", fontsize=7, pad=2)
    b = ax_at(0, 1)
    em = R.d["emitter"]
    b.imshow(np.clip(em / np.percentile(em @ LUM, 99.5), 0, 1) ** (1 / 2.2), interpolation="lanczos")
    b.set_title("Emitter texture", fontsize=7, pad=2)
    b.axis("off")
    c = ax_at(0, 2)
    eh = S.EMIT_W * em.shape[0] / em.shape[1]
    c.plot([0, 0], [S.EMIT_Y0, S.EMIT_Y0 + eh], color="#E0A000", lw=2.2, solid_capstyle="butt")
    for y in np.arange(0, S.FENCE_H, S.FENCE_PERIOD):
        c.plot([S.FENCE_Z, S.FENCE_Z], [y, y + S.FENCE_BAR], color="0.2", lw=1.6, solid_capstyle="butt")
    c.plot([S.FENCE_Z, S.FENCE_Z], [0, S.FENCE_H], color="0.2", lw=0.4)
    c.plot([0, 9.3], [0, 0], color="0.45", lw=1.0)
    for q in (S.EMIT_Y0 + 0.1, S.EMIT_Y0 + eh - 0.1):
        c.plot([4.3, 0], [0, q], color="#0090B0", lw=0.45, ls=(0, (2, 1.5)))
    c.plot(S.CAM[2], S.CAM[1], "k^", ms=3)
    c.annotate("", xy=(S.LOOK[2], S.LOOK[1]), xytext=(S.CAM[2], S.CAM[1]), arrowprops=dict(arrowstyle="->", color="k", lw=0.5))
    c.text(0.0, S.EMIT_Y0 + eh + 0.15, "emitter", fontsize=5.5, ha="center")
    c.text(S.FENCE_Z, S.FENCE_H + 0.15, "fence", fontsize=5.5, ha="center")
    c.text(S.CAM[2] - 0.3, S.CAM[1] + 0.25, "camera", fontsize=5.5, ha="right")
    c.text(6.4, 0.12, "floor", fontsize=5.5, ha="center")
    c.set_xlim(-0.5, 9.6)
    c.set_ylim(-0.3, 3.3)
    c.set_title("Side view", fontsize=7, pad=2)
    c.axis("off")
    save(fig, "scene_" + os.path.splitext(os.path.basename(path))[0])


def fig_fence(path):
    R = Render(path)
    panels = [("ref", "Reference\nexact"), ("2D CDF (random)", "2D CDF\npseudorandom"), ("2D CDF (qmc)", "2D CDF\nQMC"),
              ("PerPixelAlias (random)", "PerPixelAlias\npseudorandom"), ("PerPixelAlias (qmc)", "PerPixelAlias\nQMC"),
              ("LeafAlias 4000 (qmc)", "BudgetLeafAlias\nQMC")]
    fig, ax_at = grid_figure((0.34, 0.03, 0.34, 0.03), 4)
    for k, (key, lab) in enumerate(panels):
        blk, c = divmod(k, 3)
        img = R.image(key)
        R.boxed(a := ax_at(2 * blk, c), img)
        a.set_title(lab if key == "ref" else f"{lab}\nrel. RMSE {R.rmse(key):.3f}", fontsize=6.6, pad=2, linespacing=1.0)
        R.closeup(ax_at(2 * blk + 1, c), img)
    save(fig, "fence_" + os.path.splitext(os.path.basename(path))[0])


def main():
    ap = argparse.ArgumentParser(description="Figures of the QMC note.")
    ap.add_argument("figure", choices=["points", "scene", "fence"])
    ap.add_argument("result", nargs="?", help="fence_test.py .npz (scene and fence figures)")
    ap.add_argument("--emitter", default=os.path.join(HERE, "data", "cinema_frame232_x704_y284_1024x507.hdr"))
    ap.add_argument("--points", type=int, default=500, help="points shown in the points figure")
    a = ap.parse_args()
    if a.figure == "points":
        fig_points(a.emitter, a.points)
    else:
        if not a.result:
            ap.error("give the fence_test.py result (.npz)")
        (fig_scene if a.figure == "scene" else fig_fence)(a.result)


if __name__ == "__main__":
    main()
