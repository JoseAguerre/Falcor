"""Builds the tables and figures of the GPU comparison note.

Two studies, each reported for both GPUs:

  equal quality   how much faster than the dense 2D CDF each technique reaches the same image
                  quality, at a 33.3 ms real-time budget. The RTX 4050 Laptop column is measured
                  here by run_render.py; the RTX 4080 SUPER column is the same measurement from the
                  project's own equal-quality experiment (paper-revised/newtests/equal-quality).
  leaf budget     how the cost of BudgetLeafAlias moves with its leaf budget, in rendered frames
                  on the 4050 and in isolated light sampling on both GPUs.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
FIG, TAB = os.path.join(HERE, "figures"), os.path.join(HERE, "tables")
SAMPLING = os.path.join(REPO, "supp-gpu-scaling", "data", "summary.json")

BUDGET_MS = 1000 / 30
SCENES = ["phonehand", "fireplace_room", "convergence"]
SCENE_LAB = {"phonehand": "Phone", "fireplace_room": "Fireplace Room", "convergence": "Convergence"}
EMITTER = {"phonehand": r"1920$\times$1080", "fireplace_room": r"3840$\times$2160",
           "convergence": r"3840$\times$2160"}

TECHS = [("2D CDF", ("Cdf2D", 0)), ("2D CDF/8", ("Cdf2DDiv8", 0)), ("Mipmap", ("HierarchicalMip", 0)),
         ("Alias per pixel", ("AliasPerPixel", 0)), ("BudgetLeafAlias", ("BudgetLeafAlias", 4000)),
         ("CodecLeafAlias", ("AliasCtu", 0))]
OURS = ("BudgetLeafAlias", "CodecLeafAlias")
LEAF_BUDGETS = [250, 1000, 2000, 4000, 8000, 16000]

# --- RTX 4080 SUPER, from the project's equal-quality experiment (table_scenes.tex) -------------
# Speedup over the 2D CDF at equal quality, direct illumination. None = never reaches its quality.
REF_EQ = {
    "fireplace_room": {"2D CDF/8": 1.29, "Mipmap": 1.10, "Alias per pixel": 0.91,
                       "BudgetLeafAlias": 1.19, "CodecLeafAlias": 1.54},
    "phonehand": {"2D CDF/8": 1.17, "Mipmap": None, "Alias per pixel": 1.26,
                  "BudgetLeafAlias": 1.47, "CodecLeafAlias": 1.23},
    "convergence": {"2D CDF/8": 1.17, "Mipmap": 1.06, "Alias per pixel": 0.93,
                    "BudgetLeafAlias": 1.27, "CodecLeafAlias": 1.37},
}
# Isolated light-sampling cost on the 4080 SUPER, ms for one 1920x1080 frame at 128 light samples
# per pixel (leaf-budget supplement, Table 2). Phone/Fireplace/Convergence rows.
REF_SAMPLING = {
    "phonehand": {1000: 11.5, 2000: 12.1, 4000: 13.3, 8000: 14.2, 16000: 14.6},
    "fireplace_room": {1000: 11.5, 2000: 12.1, 4000: 13.2, 8000: 14.0, 16000: 14.5},
    "convergence": {1000: 11.7, 2000: 12.1, 4000: 13.1, 8000: 14.1, 16000: 14.7},
}


class Ladder:
    def __init__(self, rows):
        rows = sorted((r for r in rows if r.get("rmse") and r.get("frame_ms")), key=lambda r: r["lspv"])
        self.n = np.array([r["lspv"] for r in rows], float)
        self.t_pts = np.array([r["frame_ms"] for r in rows], float)
        self.rmse_pts = np.array([r["rmse"] for r in rows], float)
        self.t = np.maximum.accumulate(self.t_pts)
        self.p = np.polyfit(np.log(self.n), np.log(np.array([r["mse"] for r in rows])), 2)
        self.grid = np.linspace(self.n[0], self.n[-1], 8000)

    def time(self, n):
        return np.interp(n, self.n, self.t)

    def rmse(self, n):
        return np.sqrt(np.exp(np.polyval(self.p, np.log(n))))

    def samples_in(self, ms):
        ok = self.time(self.grid) <= ms
        return float(self.grid[ok][-1]) if ok.any() else float(self.n[0])

    def samples_for(self, r):
        ok = self.rmse(self.grid) <= r
        return float(self.grid[ok][0]) if ok.any() else None


def load(scene, name, leaf):
    p = os.path.join(DATA, f"{scene}_{name}_{leaf}.json")
    if not os.path.exists(p):
        return None
    rows = json.load(open(p))["ladder"]
    return Ladder(rows) if sum(1 for r in rows if r.get("rmse")) >= 5 else None


def equal_quality(scene, entries):
    """entries: list of (label, Ladder). The first must be the 2D CDF."""
    L = dict(entries)
    c = L["2D CDF"]
    n0 = c.samples_in(BUDGET_MS)
    r0 = float(c.rmse(n0))
    out = {"2D CDF": dict(speedup=1.0, rmse_rel=1.0, n=n0, ms=float(c.time(n0)))}
    for lab, l in entries:
        if lab == "2D CDF":
            continue
        nq = l.samples_for(r0)
        nt = l.samples_in(BUDGET_MS)
        out[lab] = dict(speedup=None if nq is None else BUDGET_MS / float(l.time(nq)),
                        rmse_rel=float(l.rmse(nt)) / r0, n=nt, ms=float(l.time(nt)))
    return out, n0, r0


def study_equal_quality():
    res = {}
    for s in SCENES:
        entries = [(lab, load(s, n, b)) for lab, (n, b) in TECHS]
        entries = [(lab, l) for lab, l in entries if l is not None]
        res[s] = equal_quality(s, entries)
    return res


def study_leaves():
    """Equal-quality speedup and 33.3 ms sample count against the leaf budget, on the 4050."""
    res = {}
    for s in SCENES:
        cdf = load(s, "Cdf2D", 0)
        n0 = cdf.samples_in(BUDGET_MS)
        r0 = float(cdf.rmse(n0))
        rows = {}
        for b in LEAF_BUDGETS:
            l = load(s, "BudgetLeafAlias", b)
            if l is None:
                continue
            nq = l.samples_for(r0)
            rows[b] = dict(speedup=None if nq is None else BUDGET_MS / float(l.time(nq)),
                           n=l.samples_in(BUDGET_MS), t64=float(l.time(l.n[-1])),
                           rmse64=float(l.rmse(l.n[-1])))
        res[s] = rows
    return res


def sampling_4050():
    if not os.path.exists(SAMPLING):
        return {}
    d = json.load(open(SAMPLING))["sampler_ms"]
    return {k: v["median"] for k, v in d.items()}


# ---------------------------------------------------------------- tables

def table_equal_quality(EQ):
    rows = []
    for lab, _ in TECHS:
        cells = []
        for s in SCENES:
            a = EQ[s][0].get(lab)
            b = REF_EQ[s].get(lab, 1.00 if lab == "2D CDF" else None)
            cells.append("--" if a is None or a["speedup"] is None else f"{a['speedup']:.2f}")
            cells.append("--" if b is None else f"{b:.2f}")
        name = r"\textbf{" + lab + "}" if lab in OURS else lab
        rows.append(f"{name} & " + " & ".join(cells) + r" \\")
    head = (" & " + " & ".join(r"\multicolumn{2}{c}{" + SCENE_LAB[s] + "}" for s in SCENES) + r" \\" "\n"
            + "".join(rf"\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(3)) + "\n"
            + "Technique" + r" & 4050 & 4080S" * 3 + r" \\")
    tex = (r"\begin{table}[H]" "\n" r"\centering\small" "\n" r"\setlength{\tabcolsep}{5pt}" "\n"
           r"\caption{Speed-up over the dense 2D CDF at equal quality, in a 33.3\,ms real-time "
           r"frame: the frame time of the 2D CDF divided by the frame time each technique needs to "
           r"reach the same RMSE. Above 1 is faster than the 2D CDF. --: the technique does not "
           r"reach that quality within the measured range. Direct illumination in both columns; see "
           r"Section~2 for the difference in protocol between them.}" "\n" r"\label{tab:eq}" "\n"
           r"\begin{tabular}{l cc cc cc}" "\n\\toprule\n" + head + "\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    open(os.path.join(TAB, "table_eq.tex"), "w", encoding="utf-8").write(tex)


def table_operating_point(EQ):
    rows = []
    for lab, _ in TECHS:
        cells = []
        for s in SCENES:
            x = EQ[s][0].get(lab)
            cells += ["--", "--"] if x is None else [f"{x['n']:.0f}", f"{x['rmse_rel']:.3f}"]
        name = r"\textbf{" + lab + "}" if lab in OURS else lab
        rows.append(f"{name} & " + " & ".join(cells) + r" \\")
    head = (" & " + " & ".join(r"\multicolumn{2}{c}{" + SCENE_LAB[s] + "}" for s in SCENES) + r" \\" "\n"
            + "".join(rf"\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(3)) + "\n"
            + "Technique" + r" & samples & RMSE" * 3 + r" \\")
    tex = (r"\begin{table}[H]" "\n" r"\centering\small" "\n" r"\setlength{\tabcolsep}{5pt}" "\n"
           r"\caption{The same 33.3\,ms frame on the RTX 4050 Laptop, read at equal \emph{time} "
           r"instead of equal quality. \emph{samples}: light samples per shading point that fit in "
           r"the budget (64 is the engine's limit). \emph{RMSE}: error at that point relative to the "
           r"2D CDF's, where below 1 is better.}" "\n" r"\label{tab:op}" "\n"
           r"\begin{tabular}{l cc cc cc}" "\n\\toprule\n" + head + "\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    open(os.path.join(TAB, "table_op.tex"), "w", encoding="utf-8").write(tex)


def table_leaves(LV, S):
    rows = []
    for b in LEAF_BUDGETS:
        cells = []
        for s in SCENES:
            x = LV[s].get(b)
            cells.append("--" if x is None or x["speedup"] is None else f"{x['speedup']:.2f}")
        # Isolated sampling cost, both GPUs, relative to that GPU's own B=1000.
        for s in SCENES:
            a = S.get(f"{s}|BudgetLeafAlias|{b}")
            a0 = S.get(f"{s}|BudgetLeafAlias|1000")
            r = REF_SAMPLING[s].get(b)
            r0 = REF_SAMPLING[s].get(1000)
            cells.append("--" if a is None or a0 is None else f"{a / a0:.2f}")
            cells.append("--" if r is None else f"{r / r0:.2f}")
        rows.append(f"$B$={b} & " + " & ".join(cells) + r" \\")
    head = (r" & \multicolumn{3}{c}{Speed-up at equal quality (4050)} & "
            + " & ".join(r"\multicolumn{2}{c}{" + SCENE_LAB[s] + "}" for s in SCENES) + r" \\" "\n"
            r"\cmidrule(lr){2-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}" "\n"
            + "Budget & " + " & ".join(SCENE_LAB[s] for s in SCENES)
            + r" & 4050 & 4080S" * 3 + r" \\")
    tex = (r"\begin{table}[H]" "\n" r"\centering\small" "\n" r"\setlength{\tabcolsep}{4pt}" "\n"
           r"\caption{Leaf budget of BudgetLeafAlias. Left: speed-up over the 2D CDF at equal "
           r"quality in a 33.3\,ms frame, measured here on the RTX 4050 Laptop. Right: the cost of "
           r"light sampling alone, relative to that GPU's own $B=1000$, on both GPUs --- the one "
           r"measurement in this note made with an identical protocol on each. $B=250$ was not run "
           r"in the sampling benchmark.}" "\n" r"\label{tab:leaves}" "\n"
           r"\begin{tabular}{l ccc cc cc cc}" "\n\\toprule\n" + head + "\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    open(os.path.join(TAB, "table_leaves.tex"), "w", encoding="utf-8").write(tex)


# ---------------------------------------------------------------- figures

STYLE = {"2D CDF": dict(color="#000000", lw=1.7, marker="s"),
         "2D CDF/8": dict(color="#8a8a8a", lw=1.0, marker="v", ls="--"),
         "Mipmap": dict(color="#8a8a8a", lw=1.0, marker="^", ls=":"),
         "Alias per pixel": dict(color="#E69F00", lw=1.2, marker="D"),
         "BudgetLeafAlias": dict(color="#0072B2", lw=2.0, marker="o"),
         "CodecLeafAlias": dict(color="#D55E00", lw=2.0, marker="o")}


def fig_curves(EQ):
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.25))
    for ax, s in zip(axes, SCENES):
        r0 = EQ[s][2]
        for lab, (n, b) in TECHS:
            l = load(s, n, b)
            if l is None:
                continue
            st = STYLE[lab]
            g = l.grid
            ax.plot(l.time(g), l.rmse(g), color=st["color"], lw=st["lw"], ls=st.get("ls", "-"),
                    label=lab, zorder=3 if lab in OURS else 2)
            ax.plot(l.t_pts, l.rmse_pts, ls="none", marker=st["marker"], ms=2.6,
                    color=st["color"], alpha=0.5)
        ax.axvline(BUDGET_MS, color="#444444", lw=0.7, ls=(0, (4, 3)))
        ax.axhline(r0, color="#444444", lw=0.7, ls=(0, (1, 3)))
        ax.set_xscale("log"); ax.set_yscale("log"); ax.minorticks_off()
        ax.set_xticks([4, 10, 33, 100, 200]); ax.set_xticklabels(["4", "10", "33", "100", "200"])
        ax.set_xlabel("Frame time (ms)", fontsize=7.5)
        ax.set_title(f"{SCENE_LAB[s]}", fontsize=8)
        ax.tick_params(labelsize=6.5)
        ax.grid(alpha=0.22, lw=0.5)
    axes[0].set_ylabel("RMSE", fontsize=7.5)
    h, lb = axes[0].get_legend_handles_labels()
    fig.legend(h, lb, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.015), fontsize=6.4,
               frameon=False, columnspacing=1.3, handlelength=1.6, handletextpad=0.4)
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(os.path.join(FIG, "fig_curves.pdf"))
    plt.close(fig)


def fig_speedup(EQ):
    """Side-by-side speed-ups over the 2D CDF on the two GPUs."""
    labs = [l for l, _ in TECHS if l != "2D CDF"]
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.15), sharey=True)
    x = np.arange(len(labs))
    for ax, s in zip(axes, SCENES):
        a = [EQ[s][0][l]["speedup"] if l in EQ[s][0] and EQ[s][0][l]["speedup"] else 0 for l in labs]
        b = [REF_EQ[s].get(l) or 0 for l in labs]
        ax.bar(x - 0.2, a, 0.38, color="#0072B2", label="RTX 4050 Laptop")
        ax.bar(x + 0.2, b, 0.38, color="#9e9e9e", label="RTX 4080 SUPER")
        ax.axhline(1.0, color="#000000", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labs, rotation=35, ha="right", fontsize=6)
        ax.set_title(SCENE_LAB[s], fontsize=8)
        ax.tick_params(labelsize=6.5)
        ax.grid(alpha=0.22, lw=0.5, axis="y")
    axes[0].set_ylabel("speed-up over 2D CDF\nat equal quality", fontsize=7.5)
    axes[0].legend(fontsize=6, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_speedup.pdf"))
    plt.close(fig)


def fig_leaves(LV, S):
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.2))
    col = {"phonehand": "#0072B2", "fireplace_room": "#D55E00", "convergence": "#6250d6"}
    for s in SCENES:
        B = [x for x in LEAF_BUDGETS if LV[s].get(x) and LV[s][x]["speedup"]]
        a.plot(B, [LV[s][x]["speedup"] for x in B], "-o", color=col[s], lw=1.3, ms=3,
               label=SCENE_LAB[s])
    a.axhline(1.0, color="#000000", lw=0.8)
    a.set_xscale("log"); a.minorticks_off()
    a.set_xticks(LEAF_BUDGETS); a.set_xticklabels([str(x) for x in LEAF_BUDGETS], fontsize=6.5)
    a.set_xlabel("Leaf budget $B$", fontsize=7.5)
    a.set_ylabel("speed-up over 2D CDF", fontsize=7.5)
    a.set_title("Rendered frames, RTX 4050 Laptop", fontsize=8)
    a.tick_params(labelsize=6.5); a.grid(alpha=0.22, lw=0.5); a.legend(fontsize=6, frameon=False)

    for s in SCENES:
        B = [x for x in (1000, 2000, 4000, 8000, 16000) if S.get(f"{s}|BudgetLeafAlias|{x}")]
        y = [S[f"{s}|BudgetLeafAlias|{x}"] for x in B]
        b.plot(B, [v / y[0] for v in y], "-o", color=col[s], lw=1.4, ms=3, label=f"{SCENE_LAB[s]} (4050)")
        r = [REF_SAMPLING[s][x] for x in B]
        b.plot(B, [v / r[0] for v in r], "--s", color=col[s], lw=0.9, ms=2.6, alpha=0.55,
               label=f"{SCENE_LAB[s]} (4080S)")
    b.axhline(1.0, color="#888888", lw=0.7)
    b.set_xscale("log"); b.minorticks_off()
    b.set_xticks([1000, 2000, 4000, 8000, 16000])
    b.set_xticklabels(["1000", "2000", "4000", "8000", "16000"], fontsize=6.5)
    b.set_xlabel("Leaf budget $B$", fontsize=7.5)
    b.set_ylabel("sampling cost, rel. to $B$=1000", fontsize=7.5)
    b.set_title("Light sampling alone, both GPUs", fontsize=8)
    b.tick_params(labelsize=6.5); b.grid(alpha=0.22, lw=0.5)
    b.legend(fontsize=5.4, frameon=False, ncol=2, columnspacing=0.8, loc="upper left",
             borderaxespad=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_leaves.pdf"))
    plt.close(fig)


def report(EQ, LV, S):
    print("=== equal quality: speed-up over the 2D CDF in a 33.3 ms frame ===")
    for s in SCENES:
        res, n0, r0 = EQ[s]
        print(f"  {SCENE_LAB[s]}  (2D CDF fits {n0:.1f} light samples, RMSE {r0:.4f})")
        for lab, _ in TECHS:
            if lab not in res:
                continue
            a, b = res[lab]["speedup"], REF_EQ[s].get(lab, 1.0 if lab == "2D CDF" else None)
            sa = "--" if a is None else f"{a:.2f}"
            sb = "--" if b is None else f"{b:.2f}"
            print(f"    {lab:16} 4050 {sa:>5}   4080S {sb:>5}   "
                  f"n@33ms {res[lab]['n']:5.1f}  rmse_rel {res[lab]['rmse_rel']:.3f}")
    print("\n=== leaf budget, speed-up over the 2D CDF (4050, rendered frames) ===")
    for s in SCENES:
        print(f"  {SCENE_LAB[s]:16} " + "  ".join(
            f"B={b}:" + ("--" if LV[s][b]['speedup'] is None else f"{LV[s][b]['speedup']:.2f}")
            for b in LEAF_BUDGETS if b in LV[s]))


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(TAB, exist_ok=True)
    EQ, LV, S = study_equal_quality(), study_leaves(), sampling_4050()
    table_equal_quality(EQ)
    table_operating_point(EQ)
    table_leaves(LV, S)
    fig_curves(EQ)
    fig_speedup(EQ)
    fig_leaves(LV, S)
    report(EQ, LV, S)
