"""Builds the tables and the figure of equal_quality.tex from the E44 results (major-revision/E44_new_viewpoints).

table_scenes.tex  equal-quality speed-up over the 2D CDF on the five scenes (full videos, direct illumination).
table_wall.tex    the LED-wall test at three resolutions of the same photograph (one frame, direct illumination).
fig_wall.pdf      RMSE against frame time for the wall test.

Wall test, per technique: the frame time of a light-sample count is read from the measured ladder by linear
interpolation; the RMSE is a quadratic fit of log(MSE) against log(samples) over the 16 measured counts, which
smooths the noise of the single rungs (residual about 2%). The 2D CDF's operating point is the sample count
that fits 33.3 ms. Equal quality: the frame time at which a technique reaches the 2D CDF's RMSE at that point.
Equal time: the technique's RMSE at 33.3 ms (or at the engine's limit of 64 samples) over the 2D CDF's."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
E44 = os.path.join(HERE, "..", "..", "E44_new_viewpoints")
SC = ["rover", "cinema", "fireplace_room", "phonehand", "convergence"]
LAB = {"rover": "Rover", "cinema": "Cinema", "fireplace_room": "Fireplace Room", "phonehand": "Phone", "convergence": "Convergence"}
TECHS = ["2D CDF/8", "Mipmap", "Alias per pixel", "BudgetLeafAlias", "CodecLeafAlias"]
OURS = ("BudgetLeafAlias", "CodecLeafAlias")
BUDGET_MS = 1000 / 30
RES = [("2k", r"1820$\times$1024"), ("4k", r"3640$\times$2048"), ("8k", r"7280$\times$4096")]
IMAGES = [("ostrich_road", "Road, broad light"), ("qwantani_morning", "Morning, sun in frame")]
# BudgetLeafAlias stores a leaf's mean luminance in 16 bits, which saturates on the sun texels of this image.
EXCLUDED = {("qwantani_morning", "BudgetLeafAlias")}


def bold(t):
    return r"\textbf{" + t + "}" if t in OURS else t


def scenes_table():
    S = json.load(open(os.path.join(E44, "summary_final_direct.json")))
    rows = ["2D CDF & " + " & ".join(["1.00"] * len(SC)) + r" \\"]
    for t in TECHS:
        cells = []
        for s in SC:
            x = S[s]["techniques"][t]
            cells.append("--" if x["iso_ms"] is None else f"{x['median']['speedup']:.2f}")
        rows.append(f"{bold(t)} & " + " & ".join(cells) + r" \\")
    tex = (r"\begin{table}[H]" "\n" r"\centering\small" "\n"
           r"\caption{Speedup over the 2D CDF at equal quality on the five scenes (full videos, direct illumination): "
           r"the frame time of the 2D CDF divided by the frame time each technique needs to reach the same video RMSE. "
           r"Above 1 is faster than the 2D CDF. --: the technique does not reach the 2D CDF's quality at the measured "
           r"points.}" "\n" r"\label{tab:scenes}" "\n"
           r"\begin{tabular}{l" + "c" * len(SC) + "}\n\\toprule\n"
           "Technique & " + " & ".join(LAB[s] for s in SC) + r" \\" "\n\\midrule\n" + "\n".join(rows) + "\n"
           "\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    open(os.path.join(HERE, "table_scenes.tex"), "w", encoding="utf-8").write(tex)


class Ladder:
    def __init__(self, rows):
        rows = sorted(rows, key=lambda x: x["lspv"])
        self.n = np.array([x["lspv"] for x in rows], float)
        self.t = np.maximum.accumulate(np.array([x["frame_ms"] for x in rows]))
        self.rmse_pts = np.array([x["rmse"] for x in rows])
        self.t_pts = np.array([x["frame_ms"] for x in rows])
        self.p = np.polyfit(np.log(self.n), np.log([x["mse"] for x in rows]), 2)
        s = self.n >= 2
        self.slope = float(np.polyfit(self.n[s], self.t_pts[s], 1)[0])
        self.grid = np.linspace(1, self.n[-1], 8000)

    def time(self, n):
        return np.interp(n, self.n, self.t)

    def rmse(self, n):
        return np.sqrt(np.exp(np.polyval(self.p, np.log(n))))

    def samples_in(self, ms):
        ok = self.time(self.grid) <= ms
        return float(self.grid[ok][-1]) if ok.any() else 1.0

    def samples_for(self, rmse):
        ok = self.rmse(self.grid) <= rmse
        return float(self.grid[ok][0]) if ok.any() else None


def wall():
    out = {}
    for image, _ in IMAGES:
        for res, _ in RES:
            d = json.load(open(os.path.join(E44, f"wall_direct_{image}_{res}.json")))
            by = {}
            for x in d["ladder"]:
                by.setdefault(x["label"], []).append(x)
            L = {k: Ladder(v) for k, v in by.items()}
            c = L["2D CDF"]
            n0 = c.samples_in(BUDGET_MS)
            r0 = float(c.rmse(n0))
            row = {"2D CDF": dict(n=n0, slope=c.slope, speedup=1.0, ratio=1.0, rmse=r0)}
            for t in TECHS:
                l = L[t]
                nq = l.samples_for(r0)
                nt = l.samples_in(BUDGET_MS)
                row[t] = dict(n=nt, capped=nt >= l.n[-1] - 0.01, slope=l.slope,
                              speedup=None if nq is None else BUDGET_MS / float(l.time(nq)),
                              ratio=float(l.rmse(nt)) / r0, rmse=float(l.rmse(nt)))
            out[(image, res)] = (row, L)
    return out


def wall_table(W):
    rows = []
    for image, lab in IMAGES:
        rows.append(r"\midrule" "\n" r"\multicolumn{10}{l}{\textit{" + lab + r"}} \\")
        for t in ["2D CDF"] + TECHS:
            cells = []
            for res, _ in RES:
                x = W[(image, res)][0][t]
                if (image, t) in EXCLUDED:
                    cells += ["--", "--", "--"]
                    continue
                n = f"{x['n']:.0f}" + ("+" if x.get("capped") else "")
                sp = "1" if t == "2D CDF" else ("--" if x["speedup"] is None else f"{x['speedup']:.2f}")
                ra = "1" if t == "2D CDF" else f"{x['ratio']:.3f}"
                cells += [n, sp, ra]
            name = bold(t) + (r"$^\dagger$" if (image, t) in EXCLUDED else "")
            rows.append(f"{name} & " + " & ".join(cells) + r" \\")
    head = (r" & \multicolumn{3}{c}{" + RES[0][1] + r"} & \multicolumn{3}{c}{" + RES[1][1] + r"} & \multicolumn{3}{c}{" + RES[2][1] + r"} \\" "\n"
            r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-10}" "\n"
            "Technique" + r" & samples & faster & RMSE" * 3 + r" \\")
    tex = (r"\begin{table}[H]" "\n" r"\centering\small" "\n" r"\setlength{\tabcolsep}{4pt}" "\n"
           r"\caption{LED wall showing the same photograph at three resolutions (Rover scene, one frame, direct "
           r"illumination). \emph{samples}: light samples per shading point that fit in a 33.3\,ms frame (+: the "
           r"engine's limit of 64 is reached before 33.3\,ms). \emph{faster}: how many times shorter the frame is than "
           r"the 2D CDF's 33.3\,ms when the technique reaches the same RMSE. \emph{RMSE}: error at 33.3\,ms relative to "
           r"the 2D CDF (below 1 is better). $^\dagger$Not reported: see the text.}" "\n" r"\label{tab:wall}" "\n"
           r"\begin{tabular}{l ccc ccc ccc}" "\n\\toprule\n" + head + "\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    open(os.path.join(HERE, "table_wall.tex"), "w", encoding="utf-8").write(tex)


def wall_figure(W):
    style = {"2D CDF": dict(color="#000000", lw=1.6, marker="s"),
             "2D CDF/8": dict(color="#8a8a8a", lw=1.1, marker="v", ls="--"),
             "Mipmap": dict(color="#8a8a8a", lw=1.1, marker="^", ls=":"),
             "Alias per pixel": dict(color="#E69F00", lw=1.3, marker="D"),
             "BudgetLeafAlias": dict(color="#0072B2", lw=2.2, marker="o"),
             "CodecLeafAlias": dict(color="#D55E00", lw=2.2, marker="o")}
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.3), sharey=True)
    for ax, (res, lab) in zip(axes, RES):
        row, L = W[("ostrich_road", res)]
        for t, st in style.items():
            l = L[t]
            ok = l.n >= 3
            ax.plot(l.time(l.grid[l.grid >= 3]), l.rmse(l.grid[l.grid >= 3]), color=st["color"], lw=st["lw"], ls=st.get("ls", "-"), label=t)
            ax.plot(l.t_pts[ok], l.rmse_pts[ok], ls="none", marker=st["marker"], ms=3, color=st["color"], alpha=0.55)
        ax.axvline(BUDGET_MS, color="#444444", lw=0.7, ls=(0, (4, 3)))
        ax.axhline(row["2D CDF"]["rmse"], color="#444444", lw=0.7, ls=(0, (1, 3)))
        ax.set_xlim(4, 70)
        ax.set_ylim(0.038, 0.09)
        ax.set_title("Wall image " + lab.replace(r"$\times$", "\u00d7"), fontsize=10)
        ax.set_xlabel("Frame time (ms)")
        ax.grid(alpha=0.25, lw=0.5)
        ax.text(BUDGET_MS + 0.8, 0.0885, "33.3 ms", fontsize=7.5, va="top", color="#444444")
    axes[0].set_ylabel("RMSE")
    axes[0].legend(fontsize=7.5, frameon=False, loc="upper right", bbox_to_anchor=(1.0, 0.92))
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_wall.pdf"))


if __name__ == "__main__":
    scenes_table()
    W = wall()
    wall_table(W)
    wall_figure(W)
    for (image, res), (row, _) in W.items():
        print(image, res, {k: (round(v["n"], 1), None if v["speedup"] is None else round(v["speedup"], 2), round(v["ratio"], 3), round(v["slope"], 2)) for k, v in row.items()})
