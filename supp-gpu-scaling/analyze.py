"""Reduces the raw benchmark JSONs into the tables and figures of the supplementary note.

Every number attributed to the RTX 4080 SUPER is quoted from the paper and its leaf-budget
supplement (Table "tab:sampling" and Sections 3-4 of ablation_leaf_number.tex); nothing about that
GPU is measured here. Everything attributed to the RTX 4050 Laptop is measured by run_bench.py on
this machine, as the median over the rounds, which discards the occasional run that lands in a
faster or a throttled clock state.
"""
import json
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FIG = os.path.join(HERE, "figures")
TAB = os.path.join(HERE, "tables")

CHASE_HOPS_TOTAL = 512 * 512 * 128           # threads x hops
TABLE_SAMPLES = 1440 * 1440 * 128            # = 1920x1080 threads x 128 samples
NS_PER_SAMPLE = 1e6 / TABLE_SAMPLES          # ms -> ns per sample

SCENES = ["phonehand", "fireplace_room", "convergence"]
SCENE_LAB = {"phonehand": "Phone", "fireplace_room": "Fireplace", "convergence": "Convergence"}
EMITTER = {"phonehand": "1080p", "fireplace_room": "4K", "convergence": "4K"}

# Engine name -> label used in the note.
SAMPLERS = [("BudgetLeafAlias", 1000), ("BudgetLeafAlias", 2000), ("BudgetLeafAlias", 4000),
            ("BudgetLeafAlias", 8000), ("BudgetLeafAlias", 16000), ("AliasCtu", 0),
            ("Cdf2DDiv8", 0), ("HierarchicalMip", 0), ("AliasPerPixel", 0), ("Cdf2D", 0)]
LAB = {("BudgetLeafAlias", b): f"BudgetLeafAlias $B$={b}" for b in (1000, 2000, 4000, 8000, 16000)}
LAB.update({("AliasCtu", 0): "CodecLeafAlias", ("Cdf2DDiv8", 0): "2D CDF/8",
            ("HierarchicalMip", 0): "Mipmap", ("AliasPerPixel", 0): "Per-pixel alias",
            ("Cdf2D", 0): "2D CDF"})

# --- RTX 4080 SUPER reference, quoted from the paper -------------------------------------------
# ablation_leaf_number.tex, Table tab:sampling: ms for one 1920x1080 frame at 128 light samples.
REF_MS = {
    "phonehand":      {("BudgetLeafAlias", 1000): 11.5, ("BudgetLeafAlias", 2000): 12.1,
                       ("BudgetLeafAlias", 4000): 13.3, ("BudgetLeafAlias", 8000): 14.2,
                       ("BudgetLeafAlias", 16000): 14.6, ("AliasPerPixel", 0): 22.9,
                       ("Cdf2D", 0): 114.8},
    "fireplace_room": {("BudgetLeafAlias", 1000): 11.5, ("BudgetLeafAlias", 2000): 12.1,
                       ("BudgetLeafAlias", 4000): 13.2, ("BudgetLeafAlias", 8000): 14.0,
                       ("BudgetLeafAlias", 16000): 14.5, ("AliasPerPixel", 0): 75.7,
                       ("Cdf2D", 0): 63.8},
    "convergence":    {("BudgetLeafAlias", 1000): 11.7, ("BudgetLeafAlias", 2000): 12.1,
                       ("BudgetLeafAlias", 4000): 13.1, ("BudgetLeafAlias", 8000): 14.1,
                       ("BudgetLeafAlias", 16000): 14.7, ("AliasPerPixel", 0): 69.9,
                       ("Cdf2D", 0): 62.1},
}
# Pointer chase on the 4080 SUPER, PAPER.tex Sec. "Sampling cost on the GPU" and ablation Sec. 4.
REF_CHASE_L1_PS, REF_CHASE_POSTL1_PS = 3.0, 9.6
REF_L1_LO, REF_L1_HI = 128 << 10, 192 << 10   # first-level cache limit, same Ada SM on both GPUs
REF_L2_BYTES = 64 << 20                       # 4080 SUPER
MEAS_L2_BYTES = 24 << 20                      # measured here, see chase()

# Structure sizes the paper reports, in bytes, by emitter resolution.
BYTES_PER_LEAF = 19
STRUCT = {("Cdf2D", 0): {"1080p": 16.6e6, "4K": 66e6},
          ("AliasPerPixel", 0): {"1080p": 41.5e6, "4K": 166e6},
          ("Cdf2DDiv8", 0): {"1080p": 0.26e6, "4K": 1.0e6}}


def struct_bytes(key, scene):
    name, b = key
    if name == "BudgetLeafAlias":
        return b * BYTES_PER_LEAF
    if key in STRUCT:
        return STRUCT[key][EMITTER[scene]]
    return None  # CodecLeafAlias and Mipmap: size not reported in the paper.


def load(prefix):
    out = {}
    for fn in os.listdir(DATA):
        if fn.startswith(prefix) and fn.endswith(".json"):
            with open(os.path.join(DATA, fn)) as f:
                out[fn[:-5]] = json.load(f)
    return out


def chase():
    """ps per dependent read against working set, median over rounds."""
    raw = load("chase_")
    by = {}
    for tag, r in raw.items():
        b = int(tag.split("_")[1][1:])
        by.setdefault(b, []).append(r["a_median_ms"] / CHASE_HOPS_TOTAL * 1e9)
    return {b: st.median(v) for b, v in sorted(by.items())}, {b: len(v) for b, v in by.items()}


def sampler():
    """Median ms per configuration, plus the spread across rounds."""
    raw = load("samp_")
    by = {}
    for tag, r in raw.items():
        # samp_<scene>_<name>_<budget>_d<dim>_s<spt>_r<round>
        body = tag[len("samp_"):]
        for s in SCENES:
            if body.startswith(s + "_"):
                rest = body[len(s) + 1:]
                parts = rest.split("_")
                name, budget = parts[0], int(parts[1])
                by.setdefault((s, (name, budget)), []).append(r["a_median_ms"])
                break
    return {k: dict(median=st.median(v), lo=min(v), hi=max(v), n=len(v)) for k, v in by.items()}


def fig_chase(C):
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.15))
    x = np.array(sorted(C)) / 1024.0
    y = np.array([C[k] for k in sorted(C)])

    a.axvspan(REF_L1_LO / 1024, REF_L1_HI / 1024, color="#eb6834", alpha=0.18, lw=0)
    a.plot(x, y, "-o", color="#0072B2", lw=1.3, ms=3, label="RTX 4050 Laptop (measured)")
    a.axhline(REF_CHASE_L1_PS, color="#888888", lw=0.9, ls="--")
    a.axhline(REF_CHASE_POSTL1_PS, color="#888888", lw=0.9, ls=":")
    a.text(4.6, REF_CHASE_L1_PS * 1.06, "4080 SUPER, in L1 (3 ps)", fontsize=6, color="#666666")
    a.text(4.6, REF_CHASE_POSTL1_PS * 1.06, "4080 SUPER, past L1 (9.6 ps)", fontsize=6, color="#666666")
    a.axvline(MEAS_L2_BYTES / 1024, color="#0072B2", lw=0.8, ls=(0, (4, 3)))
    a.axvline(REF_L2_BYTES / 1024, color="#444444", lw=0.8, ls=(0, (1, 3)))
    a.text(MEAS_L2_BYTES / 1024 * 0.80, 3.25, "L2 24 MB\n(4050)", fontsize=6, color="#0072B2", ha="right",
           va="bottom", linespacing=0.95)
    a.text(REF_L2_BYTES / 1024 * 1.30, 3.25, "L2 64 MB\n(4080S)", fontsize=6, color="#444444", va="bottom",
           linespacing=0.95)
    a.set_xscale("log"); a.set_yscale("log"); a.minorticks_off()
    a.set_xticks([4, 256, 16384, 524288]); a.set_xticklabels(["4K", "256K", "16M", "512M"])
    a.set_yticks([3, 10, 30, 100, 300]); a.set_yticklabels(["3", "10", "30", "100", "300"])
    a.set_xlabel("Working set (bytes)", fontsize=7.5)
    a.set_ylabel("ps per dependent read", fontsize=7.5)
    a.set_title("Latency of dependent random reads", fontsize=8)
    a.tick_params(labelsize=6.5)
    a.grid(alpha=0.25, lw=0.5)
    a.legend(fontsize=6.2, frameon=False, loc="upper left")

    # Normalised to each GPU's own L1 plateau: the shape, not the absolute throughput.
    base = y[x <= 64].mean()
    b.axvspan(REF_L1_LO / 1024, REF_L1_HI / 1024, color="#eb6834", alpha=0.18, lw=0)
    b.plot(x, y / base, "-o", color="#0072B2", lw=1.3, ms=3, label="RTX 4050 Laptop (measured)")
    # The paper gives two values for this GPU: the L1 plateau and the level just past the L1 limit.
    b.plot([REF_L1_LO / 1024, 256], [1.0, REF_CHASE_POSTL1_PS / REF_CHASE_L1_PS], ls="none",
           marker="s", ms=4.5, color="#444444", label="4080 SUPER (paper, 2 points)")
    b.axhline(1.0, color="#888888", lw=0.7)
    b.axhline(REF_CHASE_POSTL1_PS / REF_CHASE_L1_PS, color="#888888", lw=0.7, ls=":")
    # The two horizontal lines are the 4080 SUPER's own plateau and its step past L1; the caption
    # names them, so no in-axes labels are needed and the curve stays unobstructed.
    b.set_xscale("log"); b.set_yscale("log"); b.minorticks_off()
    b.set_xticks([4, 256, 16384, 524288]); b.set_xticklabels(["4K", "256K", "16M", "512M"])
    b.set_yticks([1, 2, 5, 10, 20, 40]); b.set_yticklabels(["1", "2", "5", "10", "20", "40"])
    b.set_xlabel("Working set (bytes)", fontsize=7.5)
    b.set_ylabel("relative to own L1 plateau", fontsize=7.5)
    b.set_title("Same curve, normalised", fontsize=8)
    b.tick_params(labelsize=6.5)
    b.grid(alpha=0.25, lw=0.5)
    b.legend(fontsize=6.2, frameon=False, loc="upper left")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_chase.pdf"))
    plt.close(fig)


def fig_cost(S):
    """ns per light sample against structure size, this GPU against the paper's reference points."""
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.05), sharey=True)
    col = {"phonehand": "#0072B2", "fireplace_room": "#D55E00", "convergence": "#6250d6"}
    for ax, s in zip(axes, SCENES):
        ax.axvspan(REF_L1_LO / 1024, REF_L1_HI / 1024, color="#eb6834", alpha=0.18, lw=0)
        ax.axvline(MEAS_L2_BYTES / 1024, color="#0072B2", lw=0.8, ls=(0, (4, 3)))
        ax.axvline(REF_L2_BYTES / 1024, color="#444444", lw=0.8, ls=(0, (1, 3)))
        B = [1000, 2000, 4000, 8000, 16000]
        xb = [b * BYTES_PER_LEAF / 1024 for b in B]
        yb = [S[(s, ("BudgetLeafAlias", b))]["median"] * NS_PER_SAMPLE for b in B]
        ax.plot(xb, yb, "-o", color=col[s], lw=1.2, ms=3, label="BudgetLeafAlias (4050)")
        rb = [REF_MS[s][("BudgetLeafAlias", b)] * NS_PER_SAMPLE for b in B]
        ax.plot(xb, rb, "-o", color="#999999", lw=1.0, ms=2.5, label="BudgetLeafAlias (4080S)")
        for key, mk in ((("Cdf2DDiv8", 0), "^"), (("AliasPerPixel", 0), "D"), (("Cdf2D", 0), "s")):
            sb = struct_bytes(key, s)
            if sb is None:
                continue
            ax.plot(sb / 1024, S[(s, key)]["median"] * NS_PER_SAMPLE, mk, color=col[s], ms=5,
                    mec="white", mew=0.5)
            if key in REF_MS[s]:
                ax.plot(sb / 1024, REF_MS[s][key] * NS_PER_SAMPLE, mk, color="#999999", ms=4.2,
                        mec="white", mew=0.5)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.minorticks_off()
        ax.set_xticks([10, 1000, 100000]); ax.set_xticklabels(["10K", "1M", "100M"])
        ax.set_xlabel("Structure size (bytes)", fontsize=7.5)
        ax.set_title(f"{SCENE_LAB[s]} ({EMITTER[s]} emitter)", fontsize=8)
        ax.tick_params(labelsize=6.5)
        ax.grid(alpha=0.25, lw=0.5)
    axes[0].set_ylabel("ns per light sample", fontsize=7.5)
    axes[0].legend(fontsize=5.8, frameon=False, loc="upper left")
    h = [plt.Line2D([], [], color="#52514e", marker=m, ls="none", ms=4.5, label=l)
         for m, l in (("^", "2D CDF/8"), ("D", "Per-pixel alias"), ("s", "2D CDF"))]
    h.append(plt.Line2D([], [], color="#999999", marker="o", ms=4, ls="-", lw=1,
                        label="grey = RTX 4080 SUPER (paper)"))
    fig.legend(handles=h, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.02), fontsize=6.2,
               frameon=False, columnspacing=1.4, handletextpad=0.3)
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(os.path.join(FIG, "fig_cost.pdf"))
    plt.close(fig)


def fig_budget(S):
    """Cost against leaf budget, each GPU normalised to its own B=1000."""
    fig, ax = plt.subplots(figsize=(5.4, 1.95))
    B = [1000, 2000, 4000, 8000, 16000]
    col = {"phonehand": "#0072B2", "fireplace_room": "#D55E00", "convergence": "#6250d6"}
    ax.axvspan(REF_L1_LO / 1024, REF_L1_HI / 1024, color="#eb6834", alpha=0.18, lw=0)
    x = [b * BYTES_PER_LEAF / 1024 for b in B]
    for s in SCENES:
        y = [S[(s, ("BudgetLeafAlias", b))]["median"] for b in B]
        ax.plot(x, [v / y[0] for v in y], "-o", color=col[s], lw=1.3, ms=3.2, label=f"{SCENE_LAB[s]} (4050)")
        r = [REF_MS[s][("BudgetLeafAlias", b)] for b in B]
        ax.plot(x, [v / r[0] for v in r], "--s", color=col[s], lw=0.9, ms=2.6, alpha=0.55,
                label=f"{SCENE_LAB[s]} (4080S)")
    ax.set_xscale("log")
    ax.minorticks_off()
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b // 1000}K\n$B$={lab}" for b, lab in
                        zip([19000, 38000, 75000, 150000, 300000], [1000, 2000, 4000, 8000, 16000])])
    ax.axhline(1.0, color="#888888", lw=0.6)
    ax.set_xlabel("Structure size (bytes)", fontsize=9, labelpad=1)
    ax.set_ylabel("relative cost", fontsize=9)
    ax.tick_params(labelsize=7.2)
    ax.grid(alpha=0.25, lw=0.5, axis="y")
    ax.legend(fontsize=7, frameon=False, ncol=2, columnspacing=0.8, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_budget.pdf"))
    plt.close(fig)


def table_cost(S):
    """Main comparison table: measured ms on the 4050 against the paper's 4080 SUPER."""
    rows = []
    for key in SAMPLERS:
        cells = []
        for s in SCENES:
            m = S.get((s, key))
            cells.append("--" if m is None else f"{m['median']:.1f}")
            ref = REF_MS[s].get(key)
            cells.append("--" if ref is None else f"{ref:.1f}")
            cells.append("--" if (m is None or ref is None) else f"{m['median'] / ref:.1f}")
        rows.append(f"{LAB[key]} & " + " & ".join(cells) + r" \\")
    head = (" & " + " & ".join(r"\multicolumn{3}{c}{" + SCENE_LAB[s] + f" ({EMITTER[s]})" + "}" for s in SCENES)
            + r" \\" "\n" + "".join(rf"\cmidrule(lr){{{2 + 3 * i}-{4 + 3 * i}}}" for i in range(3)) + "\n"
            + "Technique" + r" & 4050 & 4080S & $\times$" * 3 + r" \\")
    tex = (r"\begin{table}[H]" "\n" r"\centering\small" "\n" r"\setlength{\tabcolsep}{4.5pt}" "\n"
           r"\caption{GPU time of light sampling alone, without ray tracing or shading, for one "
           r"$1920\times1080$ frame at 128 light samples per pixel, in milliseconds. \emph{4050}: "
           r"measured on the RTX 4050 Laptop (median of seven rounds). \emph{4080S}: the same "
           r"measurement on the RTX 4080 SUPER, quoted from Table~2 of the leaf-budget supplement. "
           r"$\times$: the ratio between the two. The emitter resolution is given per scene.}" "\n"
           r"\label{tab:cost}" "\n" r"\begin{tabular}{l ccc ccc ccc}" "\n\\toprule\n" + head
           + "\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    open(os.path.join(TAB, "table_cost.tex"), "w", encoding="utf-8").write(tex)


def table_chase(C):
    """Cache hierarchy read off the pointer chase."""
    pts = [(4 << 10, "4 KB"), (64 << 10, "64 KB"), (128 << 10, "128 KB"), (192 << 10, "192 KB"),
           (256 << 10, "256 KB"), (1 << 20, "1 MB"), (16 << 20, "16 MB"), (24 << 20, "24 MB"),
           (32 << 20, "32 MB"), (64 << 20, "64 MB"), (128 << 20, "128 MB"), (512 << 20, "512 MB")]
    base = C[4 << 10]
    # Laid out as two blocks side by side, so that the table stays short.
    half = (len(pts) + 1) // 2
    left, right = pts[:half], pts[half:]
    rows = []
    for i in range(half):
        cells = []
        for blk in (left, right):
            if i < len(blk) and blk[i][0] in C:
                b, lab = blk[i]
                cells += [lab, f"{C[b]:.1f}", f"{C[b] / base:.1f}"]
            else:
                cells += ["", "", ""]
        rows.append(" & ".join(cells) + r" \\")
    head = ("Working set & ps & rel. & Working set & ps & rel. \\\\")
    tex = (r"\begin{tabular}{lcc@{\hspace{2em}}lcc}" "\n\\toprule\n" + head + "\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")
    open(os.path.join(TAB, "table_chase_body.tex"), "w", encoding="utf-8").write(tex)


def report(C, S, n):
    """Prints the numbers quoted in the prose of the note, so that they can be checked."""
    print("\n--- pointer chase, ps per dependent read (median of rounds) ---")
    for b in sorted(C):
        lab = f"{b // 1024} KB" if b < (1 << 20) else f"{b // (1 << 20)} MB"
        print(f"  {lab:>8}: {C[b]:7.1f} ps   ({C[b] / C[4 << 10]:5.1f}x the 4 KB value)")
    print("\n--- sampling cost, ms for a 1920x1080 frame at 128 light samples ---")
    for s in SCENES:
        print(f"  {SCENE_LAB[s]} ({EMITTER[s]} emitter)")
        for key in SAMPLERS:
            m = S.get((s, key))
            if m is None:
                continue
            ref = REF_MS[s].get(key)
            sp = 100 * (m["hi"] - m["lo"]) / m["median"]
            r = f"  4080S {ref:6.1f}  ratio {m['median'] / ref:4.2f}" if ref else " " * 28
            print(f"    {LAB[key]:28} {m['median']:7.1f} ms  (spread {sp:4.1f}%, n={m['n']}){r}"
                  f"   {m['median'] * NS_PER_SAMPLE:.3f} ns/sample")
    print("\n--- leaf budget, cost relative to B=1000 ---")
    for s in SCENES:
        y = [S[(s, ("BudgetLeafAlias", b))]["median"] for b in (1000, 2000, 4000, 8000, 16000)]
        r = [REF_MS[s][("BudgetLeafAlias", b)] for b in (1000, 2000, 4000, 8000, 16000)]
        print(f"  {SCENE_LAB[s]:12} 4050 " + " ".join(f"{v / y[0]:.3f}" for v in y)
              + "   4080S " + " ".join(f"{v / r[0]:.3f}" for v in r))


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(TAB, exist_ok=True)
    C, n = chase()
    S = sampler()
    fig_chase(C)
    fig_cost(S)
    fig_budget(S)
    table_cost(S)
    table_chase(C)
    report(C, S, n)
    json.dump({"chase_ps": {str(k): v for k, v in C.items()},
               "sampler_ms": {f"{s}|{k[0]}|{k[1]}": v for (s, k), v in S.items()}},
              open(os.path.join(DATA, "summary.json"), "w"), indent=1)
