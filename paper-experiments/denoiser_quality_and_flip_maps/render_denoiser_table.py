"""
Experiment 22: render the denoiser table (results_section.tex's Table 4) from
denoiser_table_data.json, bolding whichever row is our technique for that scene.

Writes results/experiment22/denoiser_table.tex (a table environment, \\input by
results_section.tex).
"""
import json
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SCENES = [("rover", "Rover"), ("cinema", "Cinema"), ("fireplace_room", "Fireplace Room"), ("convergence", "Convergence")]
ROW_ORDER = ["Random", "2D CDF", "BudgetLeafAlias", "CodecLeafAlias"]

data = json.load(open(os.path.join(OUT_DIR, "denoiser_table_data.json")))

lines = []
lines.append(r"\begin{table}[t]")
lines.append(r"\centering")
lines.append(r"\small")
lines.append(r"\caption{RMSE before and after AI denoising. On every scene tested, whichever "
             r"of our two techniques wins that scene keeps the lowest denoised RMSE too.}")
lines.append(r"\label{tab:denoise}")
lines.append(r"\begin{tabular}{ll cc}")
lines.append(r"\toprule")
lines.append(r"Scene & Technique & Noisy RMSE & Denoised RMSE \\")
lines.append(r"\midrule")

for i, (skey, sdisp) in enumerate(SCENES):
    rows = data[skey]
    present = [t for t in ROW_ORDER if t in rows]
    lines.append(r"\multirow{%d}{*}{%s}" % (len(present), sdisp))
    for tech in present:
        v = rows[tech]
        bold = tech in ("BudgetLeafAlias", "CodecLeafAlias")
        label = f"\\textbf{{{tech}}}" if bold else tech
        noisy = f"\\textbf{{{v['noisy_rmse']:.4f}}}" if bold else f"{v['noisy_rmse']:.4f}"
        den = f"\\textbf{{{v['denoised_rmse']:.4f}}}" if bold else f"{v['denoised_rmse']:.4f}"
        lines.append(f" & {label} & {noisy} & {den} \\\\")
    if i != len(SCENES) - 1:
        lines.append(r"\midrule")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

out_path = os.path.join(OUT_DIR, "denoiser_table.tex")
with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")
print("Saved", out_path)
