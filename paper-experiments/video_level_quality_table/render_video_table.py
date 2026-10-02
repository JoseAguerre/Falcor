"""
Experiment 22: render the video-quality table (results_section.tex's Table 3) from
video_table_data.json. PSNR and RMSE are shown as mean +/- std across the 48-frame sequence
(both fields come straight from experiment16's video_metrics.json); VMAF is shown as its
pooled mean with the [min-max] range libvmaf itself reports across those same 48 frames.

Writes results/experiment22/video_table.tex (a table environment, \\input by
results_section.tex).
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

data = json.load(open(os.path.join(OUT_DIR, "video_table_data.json")))

lines = []
lines.append(r"\begin{table}[t]")
lines.append(r"\centering")
lines.append(r"\small")
lines.append(r"\caption{Video-level quality of our real-time technique vs.\ a converged "
             r"reference, averaged over a 48-frame animated sequence per scene. PSNR and RMSE "
             r"are mean $\pm$ std.\ dev.\ across the 48 frames; VMAF is the pooled mean with "
             r"its [min--max] range over the same frames.}")
lines.append(r"\label{tab:video}")
lines.append(r"\begin{tabular}{l c c c}")
lines.append(r"\toprule")
lines.append(r"Scene & PSNR (dB) & VMAF & RMSE \\")
lines.append(r"\midrule")

for skey, sdisp in SCENES:
    v = data[skey]
    psnr = f"{v['psnr']:.2f} $\\pm$ {v['psnr_std']:.3f}"
    vmaf = f"{v['vmaf']:.1f} [{v['vmaf_min']:.1f}--{v['vmaf_max']:.1f}]"
    rmse = f"{v['rmse']:.4f} $\\pm$ {v['rmse_std']:.5f}"
    lines.append(f"{sdisp} & {psnr} & {vmaf} & {rmse} \\\\")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

out_path = os.path.join(OUT_DIR, "video_table.tex")
with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")
print("Saved", out_path)
