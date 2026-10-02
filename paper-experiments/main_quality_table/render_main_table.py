r"""
Experiment 22: render the main RMSE/PSNR/FLIP table (results_section.tex's Table 1) directly
from main_table_data.json, bolding ONLY the best value per column per scene, computed
programmatically (rather than by hand) so the printed numbers and the bolding can never drift
apart from the underlying measured data in results/quality_summary_weyl.json. Technique-name
labels are never bolded, regardless of whether that row is one of our own techniques -
bolding is purely a function of who has the best number in that column, for that scene.

Writes results/experiment22/main_table.tex (a table environment, \input by results_section.tex).
"""
import json
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SCENES = [
    ("rover", "Rover"),
    ("cinema", "Cinema"),
    ("fireplace_room", "Fireplace Room"),
    ("phonehand", "Phone"),
    ("convergence", "Convergence"),
]
TECHS = [
    ("Random", "Random"),
    ("Cdf2D", "2D CDF"),
    ("Cdf2DDiv8", "2D CDF/8"),
    ("HierarchicalMip", "Mipmap"),
    ("AliasPerPixel", "Alias per pixel"),
    ("BudgetLeafAlias4000", "BudgetLeafAlias"),
    ("CodecLeafAlias", "CodecLeafAlias"),
]

data = json.load(open(os.path.join(OUT_DIR, "main_table_data.json")))


def fmt(v, kind, bold):
    s = f"{v:.4f}" if kind != "psnr" else f"{v:.2f}"
    return f"\\textbf{{{s}}}" if bold else s


lines = []
lines.append(r"\begin{table}[t]")
lines.append(r"\centering")
lines.append(r"\footnotesize")
lines.append(r"\setlength{\tabcolsep}{3pt}")
lines.append(r"\caption{RMSE, PSNR (dB), and \FLIP\ for all seven techniques, all five "
             r"scenes, at their real-time calibrated configurations. On every single scene, "
             r"at least one of our two techniques -- BudgetLeafAlias or CodecLeafAlias -- is "
             r"the best technique on every metric.}")
lines.append(r"\label{tab:main}")
lines.append(r"\begin{tabular}{ll ccc}")
lines.append(r"\toprule")
lines.append(r"Scene & Technique & RMSE $\downarrow$ & PSNR $\uparrow$ & \FLIP\ $\downarrow$ \\")
lines.append(r"\midrule")

win_counts = {}
for i, (skey, sdisp) in enumerate(SCENES):
    rows = data[skey]
    best_rmse = min(TECHS, key=lambda t: rows[t[0]]["rmse"])[0]
    best_psnr = max(TECHS, key=lambda t: rows[t[0]]["psnr"])[0]
    best_flip = min(TECHS, key=lambda t: rows[t[0]]["flip"])[0]
    for key in (best_rmse, best_psnr, best_flip):
        win_counts[key] = win_counts.get(key, 0) + 1

    lines.append(r"\multirow{%d}{*}{%s}" % (len(TECHS), sdisp))
    for tkey, tdisp in TECHS:
        v = rows[tkey]
        label = tdisp
        rmse_s = fmt(v["rmse"], "rmse", tkey == best_rmse)
        psnr_s = fmt(v["psnr"], "psnr", tkey == best_psnr)
        flip_s = fmt(v["flip"], "flip", tkey == best_flip)
        lines.append(f" & {label} & {rmse_s} & {psnr_s} & {flip_s} \\\\")
    if i != len(SCENES) - 1:
        lines.append(r"\midrule")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

out_path = os.path.join(OUT_DIR, "main_table.tex")
with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")
print("Saved", out_path)
print("Win counts (out of 15 metric-columns across 5 scenes):", win_counts)
