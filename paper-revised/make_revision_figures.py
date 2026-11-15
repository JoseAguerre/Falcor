"""Figures of the revised paper that are drawn from the result files of the revision experiments
(major-revision/E09, E14, E16, E36, E38, E41, E43, E44). Writes PDF files into images/.

fig_equal_samples.pdf  RMSE relative to the 2D CDF at equal samples (E38).
fig_equal_quality.pdf  Speed-up over the 2D CDF at equal quality, full videos, direct illumination (E44).
fig_static_tree.pdf    RMSE of static and partially updated trees relative to a tree rebuilt every frame (E43).
fig_wall.pdf           RMSE against frame time for the LED wall at three resolutions, single column (E44).
fig_gpu_cost.pdf       Pointer chase and cost per light sample against structure size, single column (E09).
fig_leaf_budget.pdf    RMSE relative to B=4000 against the leaf budget, one curve per sample count (E36).
fig_partitions.jpg     Leaf partitions of one frame of Rover and Phone (E16).
fig_variance_vs_leaves.pdf  Light-sampling variance against leaf count, budget curve and codec partition (E41).
fig_temporal.pdf       Change of the sampling density per frame and rendered flicker, single column (E14).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MR = os.path.join(HERE, "..", "major-revision")
sys.path.insert(0, os.path.join(MR, "common"))
import plotstyle as ps  # noqa: E402

plt = ps.plt
ps.setup()
plt.rcParams.update({"font.size": 7.5, "axes.labelsize": 7.5, "legend.fontsize": 6.8, "xtick.labelsize": 6.6,
                     "ytick.labelsize": 7, "pdf.fonttype": 42})
OUT = os.path.join(HERE, "images")
SC = ["rover", "cinema", "fireplace_room", "phonehand", "convergence"]
LAB = ["Rover", "Cinema", "Fireplace R.", "Phone", "Convergence"]
COLW = 3.33
# (label in the result files, colour key, legend label, marker)
TECH = [("2D CDF/8", "Cdf2DDiv8", "2D CDF/8", "v"), ("Mipmap", "HierarchicalMip", "Mipmap", "^"),
        ("Alias per pixel", "AliasPerPixel", "Per-pixel alias", "D"),
        ("BudgetLeafAlias", "BudgetLeafAlias", "BudgetLeafAlias", "o"), ("CodecLeafAlias", "AliasCtu", "CodecLeafAlias", "s")]


def offsets(n, width=0.62):
    return np.linspace(-width / 2, width / 2, n)


def frame(ax, n):
    ax.set_xticks(range(n))
    ax.set_xticklabels(LAB)
    ax.set_xlim(-0.5, n - 0.5)
    ax.grid(axis="x", visible=False)
    for i in range(n - 1):
        ax.axvline(i + 0.5, color=ps.GRID, lw=0.6)


def equal_samples():
    fig, ax = plt.subplots(figsize=(COLW, 1.9))
    off = offsets(len(TECH))
    for j, (key, ck, lab, mk) in enumerate(TECH):
        ys, es = [], []
        for s in SC:
            r = json.load(open(os.path.join(MR, "E38_equal_sample_table1", f"table1_{s}.json")))["results"]
            c, t = r["2D CDF"], r[key]
            q = t["rmse"] / c["rmse"]
            ys.append(q)
            es.append(q * np.hypot(t["rmse_ci95"] / t["rmse"], c["rmse_ci95"] / c["rmse"]))
        ours = "Leaf" in key
        ax.errorbar(np.arange(len(SC)) + off[j], ys, yerr=es, fmt=mk, color=ps.TECH_COLOR[ck], ms=4.2 if ours else 3.4,
                    mec="white", mew=0.5, elinewidth=0.8, label=lab, zorder=3)
    ax.axhline(1, color=ps.INK2, lw=0.8, zorder=1)

    frame(ax, len(SC))
    ax.set_ylabel("RMSE / RMSE of 2D CDF")
    ax.set_ylim(0.975, 1.105)
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, 1.3), columnspacing=1.0, handletextpad=0.2)
    fig.savefig(os.path.join(OUT, "fig_equal_samples.pdf"))
    plt.close(fig)


def equal_quality():
    S = json.load(open(os.path.join(MR, "E44_new_viewpoints", "summary_final_direct.json")))
    fig, ax = plt.subplots(figsize=(COLW, 1.9))
    off = offsets(len(TECH))
    for j, (key, ck, lab, mk) in enumerate(TECH):
        first = True
        for i, s in enumerate(SC):
            x = S[s]["techniques"][key]
            if x["iso_ms"] is None:
                continue
            med, fast = x["median"]["speedup"], x["fastest"]["speedup"]
            ours = "Leaf" in key
            ax.plot(i + off[j], med, mk, color=ps.TECH_COLOR[ck], ms=4.2 if ours else 3.4, mec="white", mew=0.5,
                    label=lab if first else None, zorder=3)
            first = False
            print(f"{s:16s} {key:16s} median {med:.2f} fastest {fast:.2f}")
    ax.axhline(1, color=ps.INK2, lw=0.8, zorder=1)
    ax.text(-0.47, 1.0, "2D CDF", ha="left", va="bottom", fontsize=6, color=ps.INK2)
    frame(ax, len(SC))
    ax.set_ylabel("Speed-up at equal quality")
    ax.set_ylim(0.7, 2.45)
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, 1.3), columnspacing=1.0, handletextpad=0.2)
    fig.savefig(os.path.join(OUT, "fig_equal_quality.pdf"))
    plt.close(fig)


def static_tree():
    V = [("static_avg", "perframe", "Average tree, average weights", "#8a8983", "X"),
         ("topo_avg_4000", "perframe_pass2", "Average tree, per-frame weights", "#2a78d6", "o"),
         ("rebuild_30_fw", "perframe", "New tree every 30 frames, per-frame weights", "#1baf7a", "s")]
    fig, ax = plt.subplots(figsize=(COLW, 1.9))
    off = offsets(len(V), 0.44)
    for j, (k, base, lab, col, mk) in enumerate(V):
        ys, es = [], []
        for s in SC:
            r = json.load(open(os.path.join(MR, "E43_static_tree_video", f"result_{s}.json")))["results"]
            a, b = np.array(r[k]["series_rmse"]), np.array(r[base]["series_rmse"])
            ok = b > 1e-3
            q = a[ok] / b[ok]
            ys.append(q.mean())
            es.append(1.96 * q.std(ddof=1) / np.sqrt(ok.sum()))
            print(f"{s:16s} {k:14s} {ys[-1]:.3f} +- {es[-1]:.3f}")
        ax.errorbar(np.arange(len(SC)) + off[j], ys, yerr=es, fmt=mk, color=col, ms=4, mec="white", mew=0.5,
                    elinewidth=0.8, label=lab, zorder=3)
    ax.axhline(1, color=ps.INK2, lw=0.8, zorder=1)

    frame(ax, len(SC))
    ax.set_ylabel("RMSE / RMSE of per-frame tree")
    ax.set_ylim(0.96, 1.47)
    ax.legend(ncol=1, loc="upper left", bbox_to_anchor=(0, 1.0), handletextpad=0.2)
    fig.savefig(os.path.join(OUT, "fig_static_tree.pdf"))
    plt.close(fig)



class Ladder:
    """Frame time and RMSE of one technique as a function of the light samples per shading point (wall test).
    Same model as newtests/equal-quality/make_table.py: time by linear interpolation of the measured ladder,
    RMSE from a quadratic fit of log(MSE) against log(samples)."""

    def __init__(self, rows):
        rows = sorted(rows, key=lambda x: x["lspv"])
        self.n = np.array([x["lspv"] for x in rows], float)
        self.t = np.maximum.accumulate(np.array([x["frame_ms"] for x in rows]))
        self.rmse_pts = np.array([x["rmse"] for x in rows])
        self.t_pts = np.array([x["frame_ms"] for x in rows])
        self.p = np.polyfit(np.log(self.n), np.log([x["mse"] for x in rows]), 2)
        self.grid = np.linspace(1, self.n[-1], 8000)

    def time(self, n):
        return np.interp(n, self.n, self.t)

    def rmse(self, n):
        return np.sqrt(np.exp(np.polyval(self.p, np.log(n))))

    def samples_in(self, ms):
        ok = self.time(self.grid) <= ms
        return float(self.grid[ok][-1]) if ok.any() else 1.0


def wall():
    """Single-column version of the LED-wall figure (E44, road photograph at three resolutions)."""
    budget = 1000 / 30
    style = [("2D CDF", "2D CDF", dict(color="#000000", lw=0.9), "s"),
             ("2D CDF/8", "2D CDF/8", dict(color="#8a8a8a", lw=0.7, ls="--"), "v"),
             ("Mipmap", "Mipmap", dict(color="#8a8a8a", lw=0.7, ls=":"), "^"),
             ("Alias per pixel", "Per-pixel Alias", dict(color="#E69F00", lw=0.8), "D"),
             ("BudgetLeafAlias", "BudgetLeafAlias", dict(color="#0072B2", lw=1.1), "o"),
             ("CodecLeafAlias", "CodecLeafAlias", dict(color="#D55E00", lw=1.1), "o")]
    res = [("2k", "1820×1024"), ("4k", "3640×2048"), ("8k", "7280×4096")]
    fig, axes = plt.subplots(1, 3, figsize=(COLW, 1.75), sharey=True)
    for ax, (r, lab) in zip(axes, res):
        d = json.load(open(os.path.join(MR, "E44_new_viewpoints", f"wall_direct_ostrich_road_{r}.json")))
        by = {}
        for x in d["ladder"]:
            by.setdefault(x["label"], []).append(x)
        L = {k: Ladder(v) for k, v in by.items()}
        for key, leg, st, mk in style:
            l = L[key]
            g = l.grid[l.grid >= 3]
            ok = l.n >= 3
            ax.plot(l.time(g), l.rmse(g), label=leg, **st)
            ax.plot(l.t_pts[ok], l.rmse_pts[ok], ls="none", marker=mk, ms=1.6, color=st["color"], alpha=0.55)
        c = L["2D CDF"]
        ax.axvline(budget, color="#444444", lw=0.6, ls=(0, (4, 3)))
        ax.axhline(float(c.rmse(c.samples_in(budget))), color="#444444", lw=0.6, ls=(0, (1, 3)))
        ax.set_xlim(4, 70)
        ax.set_ylim(0.038, 0.09)
        ax.set_xticks([20, 40, 60])
        ax.set_yticks([0.04, 0.06, 0.08])
        ax.set_yticklabels([".04", ".06", ".08"])
        ax.set_title(lab, fontsize=6.5, pad=2.5)
        ax.tick_params(labelsize=6, pad=1.5)
    axes[1].set_xlabel("Frame time (ms)", fontsize=6.5, labelpad=1.5)
    h, lb = axes[0].get_legend_handles_labels()
    fig.legend(h, lb, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 0.97), columnspacing=0.9, handlelength=1.3,
               handletextpad=0.4, labelspacing=0.25, fontsize=6)
    fig.subplots_adjust(left=0.05, right=0.998, wspace=0.05)
    fig.savefig(os.path.join(OUT, "fig_wall.pdf"))
    plt.close(fig)


def gpu_cost():
    """Single-column version of the GPU cache figure (E09): pointer chase, and cost per light sample against
    the size of the sampling structure."""
    from matplotlib.lines import Line2D
    E09 = os.path.join(MR, "E09_gpu_cache_and_sampler_cost")
    chase = json.load(open(os.path.join(E09, "results.json")))["chase"]
    rep = json.load(open(os.path.join(E09, "results_repeat.json")))
    kb = 1024.0
    col = {"rover": "#2a78d6", "convergence": "#6250d6"}
    # size of the per-texel structures in KB: (2D CDF, per-pixel alias, 2D CDF/8)
    size = {"rover": (16.6e3, 41.5e3, 0.26e3), "convergence": (66e3, 166e3, 1.0e3)}
    fig, (a, b) = plt.subplots(1, 2, figsize=(COLW, 1.7))
    for ax in (a, b):
        ax.axvspan(128, 192, color="#eb6834", alpha=0.18, lw=0)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.minorticks_off()
        ax.tick_params(labelsize=6, pad=1.5)
    x = np.array([c["bytes"] for c in chase]) / kb
    y = np.array([c["a_median_ms"] / c["total_hops"] * 1e9 for c in chase])
    a.plot(x, y, "-o", color=col["rover"], lw=1.1, ms=2)
    a.set_xticks([4, 256, 16384])
    a.set_xticklabels(["4K", "256K", "16M"])
    a.set_yticks([3, 10, 30, 100])
    a.set_yticklabels(["3", "10", "30", "100"])
    a.set_xlabel("Working set (bytes)", fontsize=6.5, labelpad=1.5)
    a.set_title("ps per dependent read", fontsize=6.5, pad=2.5)
    a.text(230, 4.3, "first-level\ncache limit", fontsize=5.8, color="#b5471d", va="center", linespacing=0.95)
    for s in ("rover", "convergence"):
        B = sorted(int(k.split("|")[2]) for k in rep if k.startswith(s + "|BudgetLeafAlias|"))
        b.plot([n * 18.75 / kb for n in B], [rep[f"{s}|BudgetLeafAlias|{n}"]["ns_median"] for n in B], "-o", color=col[s],
               lw=1.1, ms=2)
        for key, sz, mk in (("Cdf2D", size[s][0], "s"), ("AliasPerPixel", size[s][1], "D"), ("Cdf2DDiv8", size[s][2], "^")):
            b.plot(sz, rep[f"{s}|{key}|0"]["ns_median"], mk, color=col[s], ms=3.6, mec="white", mew=0.4)
    b.set_xticks([1, 100, 10000])
    b.set_xticklabels(["1K", "100K", "10M"])
    b.set_xlim(0.7, 400000)
    b.set_yticks([0.05, 0.1, 0.2, 0.4])
    b.set_yticklabels(["0.05", "0.1", "0.2", "0.4"])
    b.set_ylim(0.036, 0.6)
    b.set_xlabel("Structure size (bytes)", fontsize=6.5, labelpad=1.5)
    b.set_title("ns per light sample", fontsize=6.5, pad=2.5)
    b.text(0.04, 0.95, "Rover", transform=b.transAxes, fontsize=6, color=col["rover"], va="top")
    b.text(0.04, 0.85, "Convergence", transform=b.transAxes, fontsize=6, color=col["convergence"], va="top")
    g = "#52514e"
    H = [Line2D([], [], color=g, marker="o", ms=2, lw=1.1, label="BudgetLeafAlias"),
         Line2D([], [], color=g, marker="s", ls="none", ms=3.6, label="2D CDF"),
         Line2D([], [], color=g, marker="D", ls="none", ms=3.4, label="Per-pixel Alias"),
         Line2D([], [], color=g, marker="^", ls="none", ms=3.6, label="2D CDF/8")]
    fig.subplots_adjust(left=0.06, right=0.998, wspace=0.17)
    fig.legend(handles=H, ncol=4, loc="lower center", bbox_to_anchor=(0.53, 0.98), columnspacing=0.7, handlelength=1.2,
               handletextpad=0.25, borderpad=0, borderaxespad=0.2, fontsize=6)
    fig.savefig(os.path.join(OUT, "fig_gpu_cost.pdf"))
    plt.close(fig)


def leaf_budget():
    """RMSE relative to B=4000 against the leaf budget, one curve per sample count (E36).
    Same data and curves as major-revision/E36_budget_by_samples/plot_final.py."""
    E36 = os.path.join(MR, "E36_budget_by_samples")
    src = open(os.path.join(E36, "plots.py")).read()
    ns = {"__file__": os.path.join(E36, "plots.py")}
    exec(src[:src.index("def surface(")], ns)
    rc = {"font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11, "xtick.labelsize": 9, "ytick.labelsize": 9}
    with plt.rc_context(rc):
        fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.0))
        for ax, s in zip(axs, ["cinema", "fireplace_room", "convergence"]):
            B, N, Z = ns["grid"](ns["data"][s][2])
            R = ns["rel"](B, Z)
            keep = B != 4000
            for k, n in enumerate(N):
                ax.plot(B[keep], R[k, keep], color=ns["seqc"](k, len(N)), lw=1.4, marker="o", ms=2.5, label=f"spp={n}")
            ax.axhline(1, color="0.6", ls=":", lw=1)
            ax.axvline(4000, color="0.6", ls=":", lw=1)
            ax.set_xscale("log")
            ax.set_title(ns["LABEL"][s])
            ax.set_xlabel("leaves B")
            if ax is not axs[0]:
                ax.text(4000 / 1.08, 0.97, "B=4000", transform=ax.get_xaxis_transform(), rotation=90, fontsize=8,
                        color="0.4", va="top", ha="right")
        axs[0].text(4000 * 1.1, 0.5, "B=4000", transform=axs[0].get_xaxis_transform(), fontsize=8, color="0.4",
                    va="center", ha="left")
        axs[0].set_ylabel("RMSE / RMSE(B=4000)")
        axs[0].legend(fontsize=9, ncol=2, frameon=False, loc="upper right", bbox_to_anchor=(1.03, 1.03),
                      handlelength=1.3, labelspacing=0.25, columnspacing=0.9, handletextpad=0.4)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "fig_leaf_budget.pdf"))
        plt.close(fig)


def partitions():
    """Leaf partitions of one frame of Rover and Phone: BudgetLeafAlias and the CodecLeafAlias partition of
    the renderer. Same computation as major-revision/E16_codec_vs_budget_direct/run.py."""
    import mr
    from leaf_io import Sat, budget_quadtree, ctu_partition
    from matplotlib.collections import LineCollection

    def segs(rects):
        out = []
        for x0, y0, x1, y1 in rects.tolist():
            out += [[(x0, y0), (x1, y0)], [(x1, y0), (x1, y1)]]
        return out

    scenes = ["rover", "phonehand"]
    fig, axes = plt.subplots(len(scenes), 2, figsize=(7.0, 4.3))
    for row, scene in enumerate(scenes):
        rgb = mr.load_hdr(mr.frame_path(scene))
        L = np.maximum(mr.luminance(rgb), 0)
        h, w = L.shape
        sat = Sat(L)
        b = budget_quadtree(sat, 4000)
        c = ctu_partition(sat)
        tm = np.clip(rgb / max(np.percentile(L, 99), 1e-6), 0, 1) ** (1 / 2.2)
        names = ("BudgetLeafAlias", "CodecLeafAlias")
        for col, (name, r) in enumerate(zip(names, (b, c))):
            ax = axes[row, col]
            if scene == "rover":  # this frame is stored bottom-up: show it upright, with its partition
                r = np.stack([r[:, 0], h - r[:, 3], r[:, 2], h - r[:, 1]], axis=1)
            ax.imshow(tm[::-1] if scene == "rover" else tm, extent=(0, w, h, 0))
            ax.add_collection(LineCollection(segs(r), colors="#ffffff", linewidths=0.25, alpha=0.9))
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
            ax.set_title(f"{name}, {len(r)} leaves" if row == 0 else f"{len(r)} leaves", fontsize=9)
            if col == 0:
                ax.set_ylabel(mr.SCENES[scene]["label"], fontsize=10)
        print(scene, len(b), len(c))
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(OUT, "fig_partitions.jpg"), dpi=260, pil_kwargs={"quality": 93})
    plt.close(fig)


def variance_vs_leaves():
    """Light-sampling variance against leaf count (E41), relative to BudgetLeafAlias with 4000 leaves, median over
    frames: the BudgetLeafAlias curve and the CodecLeafAlias partition of each scene."""
    from matplotlib.lines import Line2D
    E41 = os.path.join(MR, "E41_budget_vs_codec")
    cols = ["#0072B2", "#E69F00", "#D55E00", "#009E73", "#7B4BB8"]
    labs = ["Rover", "Cinema", "Fireplace Room", "Phone", "Convergence"]
    bud = [500, 1000, 2000, 4000, 8000, 16000]
    fig, ax = plt.subplots(figsize=(COLW, 1.55))
    for s, col in zip(SC, cols):
        rows = [r for r in json.load(open(os.path.join(E41, f"offline_{s}.json")))["rows"] if r["budget_4000"]["V"] > 0]
        base = np.array([r["budget_4000"]["V"] for r in rows])
        ax.plot(bud, [np.median(np.array([r[f"budget_{b}"]["V"] for r in rows]) / base) for b in bud], "-o", color=col, lw=1.1,
                ms=2.2, zorder=2)
        x, y = np.median([r["ctu"]["leaves"] for r in rows]), np.median(np.array([r["ctu"]["V"] for r in rows]) / base)
        ax.plot(x, y, "s", color=col, ms=4.8, mec="white", mew=0.5, zorder=3)
        print(f"{s:16s} codec leaves {x:.0f} V ratio {y:.3f}")
    ax.set_xscale("log")
    ax.set_xticks([500, 1000, 2000, 4000, 8000, 16000, 32000])
    ax.set_xticklabels(["500", "1K", "2K", "4K", "8K", "16K", "32K"])
    ax.set_ylim(0, 6.3)
    ax.set_yticks([0, 2, 4, 6])
    ax.minorticks_off()
    ax.tick_params(labelsize=6.5, pad=1.5)
    ax.set_xlabel("Leaves", fontsize=7, labelpad=1.5)
    ax.set_title("Variance relative to BudgetLeafAlias with 4000 leaves", fontsize=7, pad=3)
    g = "#52514e"
    H = [Line2D([], [], color=c, lw=2.2, label=l) for l, c in zip(labs, cols)]
    H += [Line2D([], [], color=g, marker="o", ms=2.2, lw=1.1, label="BudgetLeafAlias"),
          Line2D([], [], color=g, marker="s", ls="none", ms=4.6, label="CodecLeafAlias")]
    ax.legend(handles=H, ncol=2, loc="upper right", bbox_to_anchor=(1.0, 1.0), handlelength=1.3, handletextpad=0.5,
              labelspacing=0.25, columnspacing=1.0, fontsize=6.5, borderpad=0, borderaxespad=0.3)
    fig.subplots_adjust(left=0.05, right=0.995, bottom=0.19, top=0.89)
    fig.savefig(os.path.join(OUT, "fig_variance_vs_leaves.pdf"))
    plt.close(fig)


def temporal():
    """Temporal stability (E14), single column, two stacked panels: change of the sampling density between
    consecutive frames, and rendered flicker of BudgetLeafAlias relative to the 2D CDF at equal samples."""
    E14 = os.path.join(MR, "E14_temporal_stability")
    D = [json.load(open(os.path.join(E14, f"result_{s}.json"))) for s in SC]
    x = np.arange(len(SC))
    fig, (a, b) = plt.subplots(2, 1, figsize=(COLW, 3.0))
    kw = dict(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), columnspacing=0.7, handlelength=0.9, handletextpad=0.35,
              fontsize=6.1, borderpad=0, borderaxespad=0.3)
    w = 0.26
    js = lambda rows: float(np.mean([r["js"] for r in rows if r.get("js") is not None]))
    top = [("Exact per-texel (2D CDF)", "#9aa0a6", [float(np.mean(d["churn"]["exact_js"])) for d in D]),
           ("BudgetLeafAlias", "#0072B2", [js(d["churn"]["budget"]) for d in D]),
           ("CodecLeafAlias", "#D55E00", [js(d["churn"]["ctu"]) for d in D])]
    for j, (lab, col, v) in enumerate(top):
        a.bar(x + (j - 1) * w, v, w - 0.02, color=col, label=lab, zorder=3)
        print(f"{lab:26s}", " ".join(f"{q:.4f}" for q in v))
    a.set_ylim(0, 0.026)
    a.set_yticks([0, 0.01, 0.02])
    a.set_yticklabels(["0", ".01", ".02"])
    a.set_title("Change of the sampling density per frame (JS divergence)", fontsize=7, pad=14, loc="left")
    a.legend(**kw)
    r = lambda d, k, g="free": d[f"{g}/BudgetLeafAlias"][k] / d[f"{g}/Cdf2D"][k]
    bot = [("Low-frequency flicker", "#0072B2", [r(d, "terr_lf") for d in D]),
           ("Flicker / per-frame error", "#7fb8dd", [(d["free/BudgetLeafAlias"]["terr"] / d["free/BudgetLeafAlias"]["rmse"])
                                                    / (d["free/Cdf2D"]["terr"] / d["free/Cdf2D"]["rmse"]) for d in D]),
           ("After denoising", "#0b3c5d", [r(d, "terr", "denoised") for d in D])]
    for j, (lab, col, v) in enumerate(bot):
        b.bar(x + (j - 1) * w, np.array(v) - 1, w - 0.02, bottom=1, color=col, label=lab, zorder=3)
        print(f"{lab:26s}", " ".join(f"{q:.3f}" for q in v))
    b.axhline(1, color=ps.INK2, lw=0.8, zorder=4)
    b.set_ylim(0.92, 1.01)
    b.set_yticks([0.92, 0.94, 0.96, 0.98, 1.0])
    b.set_yticklabels([".92", ".94", ".96", ".98", "1"])
    b.set_title("Flicker of BudgetLeafAlias / flicker of the 2D CDF", fontsize=7, pad=14, loc="left")
    b.legend(**kw)
    for ax in (a, b):
        ax.set_xticks(x)
        ax.set_xticklabels(LAB)
        ax.set_xlim(-0.5, len(SC) - 0.5)
        ax.grid(axis="x", visible=False)
        ax.tick_params(labelsize=6.5, pad=1.5)
    fig.subplots_adjust(left=0.07, right=0.995, bottom=0.06, top=0.9, hspace=0.62)
    fig.savefig(os.path.join(OUT, "fig_temporal.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    if "temporal" in sys.argv[1:]:
        temporal()
        sys.exit()
    if "partitions" in sys.argv[1:]:
        partitions()
        variance_vs_leaves()
        sys.exit()
    equal_samples()
    equal_quality()
    static_tree()
    wall()
    gpu_cost()
    leaf_budget()
    partitions()
    variance_vs_leaves()
    temporal()
    print("ok")
