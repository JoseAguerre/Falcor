r"""
Experiment 22: an "inverted" layout of Table 1 - techniques as rows (appearing once each,
first column only), scenes as column groups (one \multicolumn header per scene, spanning 3
sub-columns each: RMSE/PSNR/FLIP). Same underlying data as the original render_main_table.py
(main_table_data.json, kept in this folder for comparison), same programmatic
best-per-column bolding - just transposed and regrouped into a single wide table* instead of
grouped-by-scene rows with a repeated Technique column.

Writes results/experiment22/main_table_inverted.tex (a table* environment, now \input by
results_section.tex in place of the original main_table.tex).
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


# Precompute best technique per (scene, metric)
best = {}
for skey, _ in SCENES:
    rows = data[skey]
    best[(skey, "rmse")] = min(TECHS, key=lambda t: rows[t[0]]["rmse"])[0]
    best[(skey, "psnr")] = max(TECHS, key=lambda t: rows[t[0]]["psnr"])[0]
    best[(skey, "flip")] = min(TECHS, key=lambda t: rows[t[0]]["flip"])[0]

n_scenes = len(SCENES)
col_spec = "l" + " ccc" * n_scenes

lines = []
lines.append(r"\begin{table*}[t]")
lines.append(r"\centering")
lines.append(r"\small")
lines.append(r"\setlength{\tabcolsep}{2.5pt}")
lines.append(r"\caption{RMSE, PSNR (dB), and \FLIP\ for all seven techniques (rows), all five "
             r"scenes (column groups), at their real-time calibrated configurations. On every "
             r"single scene, at least one of our two techniques -- BudgetLeafAlias or "
             r"CodecLeafAlias -- is the best technique on every metric.}")
lines.append(r"\label{tab:main}")
lines.append(r"\begin{tabular}{%s}" % col_spec)
lines.append(r"\toprule")

# Scene header row with multicolumn + cmidrule per scene
header1 = ["\\multirow{2}{*}{Technique}"]
cmidrules = []
col = 2
for _, sdisp in SCENES:
    header1.append(r"\multicolumn{3}{c}{%s}" % sdisp)
    cmidrules.append(r"\cmidrule(lr){%d-%d}" % (col, col + 2))
    col += 3
lines.append(" & ".join(header1) + r" \\")
lines.append(" ".join(cmidrules))

# Metric sub-header row
header2 = [""]
for _ in SCENES:
    header2 += [r"RMSE $\downarrow$", r"PSNR $\uparrow$", r"\FLIP\ $\downarrow$"]
lines.append(" & ".join(header2) + r" \\")
lines.append(r"\midrule")

for tkey, tdisp in TECHS:
    row = [tdisp]
    for skey, _ in SCENES:
        v = data[skey][tkey]
        row.append(fmt(v["rmse"], "rmse", tkey == best[(skey, "rmse")]))
        row.append(fmt(v["psnr"], "psnr", tkey == best[(skey, "psnr")]))
        row.append(fmt(v["flip"], "flip", tkey == best[(skey, "flip")]))
    lines.append(" & ".join(row) + r" \\")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table*}")

out_path = os.path.join(OUT_DIR, "main_table_inverted.tex")
with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")
print("Saved", out_path)
