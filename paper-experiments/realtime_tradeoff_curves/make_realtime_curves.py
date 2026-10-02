"""
Experiment 22: fitted power-law curves (RMSE vs. mean frame time, linear scale) for 4 scenes
and all 4 techniques (including Random), from the real per-point data in
results/experiment11/<scene>/all_data.json (2048 real spp x lspv grid points per
scene/technique, RMSE measured against that scene's own converged reference - not re-rendered
here, just refit and replotted). Fireplace Room is left out of this figure - its fitted curves
sit essentially on top of each other and don't show the effect clearly, unlike the other 4
scenes (Table 1 already reports its calibrated-point numbers).
"""
import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LIBERTINE = fm.FontProperties(fname=r"C:\Users\Jose\AppData\Local\Programs\MiKTeX\fonts\opentype\public\libertine\LinLibertine_R.otf")
LIBERTINE_B = fm.FontProperties(fname=r"C:\Users\Jose\AppData\Local\Programs\MiKTeX\fonts\opentype\public\libertine\LinLibertine_RB.otf")

SCENES = ["rover", "cinema", "phonehand", "convergence"]
SCENE_TITLES = {"rover": "Rover", "cinema": "Cinema", "phonehand": "Phone", "convergence": "Convergence"}
# color + line style per technique, distinct styles so the plot still reads in black-and-white
TECHS = [("Random", "#000000", "-", "Random"), ("Cdf2D", "#1f77b4", "--", "2D CDF"),
         ("HierarchicalMip", "#2ca02c", ":", "Mipmap"), ("Ours", "#d62728", "-.", "BudgetLeafAlias")]


def fit(data, tech):
    rows = [r for r in data if r["technique"] == tech]
    t = np.array([r["meanFrameTimeMs"] for r in rows])
    y = np.array([r["rmse"] for r in rows])
    m = (t > 0) & (y > 0)
    t, y = t[m], y[m]
    b, loga = np.polyfit(np.log(t), np.log(y), 1)
    return np.exp(loga), b


# Figure is placed as a full-width (two-column) figure* in the paper - 4 scenes in one row.
fig, axes = plt.subplots(1, 4, figsize=(14.5, 3.5))

for ax, scene in zip(axes, SCENES):
    data = json.load(open(os.path.join(REPO, "results", "experiment11", scene, "all_data.json")))
    ts = np.linspace(3, 45, 200)
    for tech, color, style, label in TECHS:
        a, b = fit(data, tech)
        ax.plot(ts, a * ts ** b, color=color, linestyle=style, linewidth=1.6,
                 label=f"{label}", zorder=3 if tech == "Ours" else 2)
    ax.set_xlabel("time (ms)", fontproperties=LIBERTINE, fontsize=13)
    ax.set_title(SCENE_TITLES[scene], fontproperties=LIBERTINE_B, fontsize=15)
    ax.tick_params(labelsize=10)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontproperties(LIBERTINE)

axes[0].set_ylabel("RMSE", fontproperties=LIBERTINE, fontsize=13)
legend = axes[0].legend(loc="upper right", frameon=True, framealpha=0.9,
                         edgecolor="none", prop=LIBERTINE, fontsize=10.5,
                         handlelength=1.6, borderpad=0.4, labelspacing=0.3)

fig.tight_layout()
out_path = os.path.join(OUT_DIR, "realtime_curves.png")
fig.savefig(out_path, dpi=220, bbox_inches="tight", pad_inches=0.03, facecolor="white")
print("Saved", out_path)
