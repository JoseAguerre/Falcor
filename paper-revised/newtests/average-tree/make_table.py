"""Builds table_average_tree.tex from the E43 results (major-revision/E43_static_tree_video): the 4000-leaf trees
only. Absolute RMSE, PSNR and VMAF (mean with 95% CI over frames) and the per-frame RMSE ratio to the tree
rebuilt every frame (paired, 95% CI)."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
E43 = os.path.join(HERE, "..", "..", "E43_static_tree_video")
S = ["rover", "cinema", "fireplace_room", "phonehand", "convergence"]
LAB = {"rover": "Rover", "cinema": "Cinema", "fireplace_room": "Fireplace Room", "phonehand": "Phone", "convergence": "Convergence"}
V = [("static_avg", "Average tree, average weights"),
     ("topo_avg_4000", "Average tree, per-frame weights"),
     ("rebuild_30_fw", "New tree every 30 frames, per-frame weights"),
     ("perframe", "New tree and weights every frame (BudgetLeafAlias)")]
# The equal-leaf average tree was rendered in a second pass with its own per-frame render on the same reference.
BASE = {"topo_avg_4000": "perframe_pass2"}


def psnr_lit(x):
    rm = np.array(x["series_rmse"])
    v = -20 * np.log10(rm[rm > 1e-3])
    return v.mean(), 1.96 * v.std(ddof=1) / np.sqrt(len(v))


def paired(r, k):
    a = np.array(r[k]["series_rmse"])
    b = np.array(r[BASE.get(k, "perframe")]["series_rmse"])
    ok = b > 1e-3
    q = a[ok] / b[ok]
    return q.mean(), 1.96 * q.std(ddof=1) / np.sqrt(ok.sum())


def ci(v, c, d):
    cs = f"{c:.{d}f}"
    cs = cs[1:] if cs.startswith("0.") else cs
    return f"{v:.{d}f}\\,{{\\scriptsize$\\pm${cs}}}"


rows = []
for s in S:
    d = json.load(open(os.path.join(E43, f"result_{s}.json")))
    r, c = d["results"], d["config"]
    rows.append(r"\midrule" "\n" r"\multicolumn{5}{l}{\textit{" + LAB[s] + f" ({c['spp']}" + r"$\times$" + f"{c['lspv']})" + r"}} \\")
    for k, lab in V:
        x = r[k]
        pm, pc = psnr_lit(x)
        if k == "perframe":
            rel = "1"
            lab = r"\textbf{" + lab + "}"
        else:
            qm, qc = paired(r, k)
            rel = f"{qm:.3f}\\,{{\\scriptsize$\\pm${qc:.3f}}}"
        rows.append(f"{lab} & {ci(x['rmse'], x['rmse_ci95'], 4)} & {ci(pm, pc, 2)} & {ci(x['vmaf'], x['vmaf_ci95'], 1)} & {rel} \\\\")
tex = (r"\begin{table}[t]" "\n" r"\centering\small" "\n" r"\setlength{\tabcolsep}{3pt}" "\n"
       r"\caption{Full-video quality of a static tree, of partially updated trees and of the tree rebuilt every frame "
       r"(BudgetLeafAlias), all with 4000 leaves, at equal samples per scene (samples per pixel $\times$ light samples per "
       r"shading point in parentheses). RMSE, PSNR (dB) and VMAF are means over frames with their 95\% confidence intervals; "
       r"the last column is the per-frame RMSE ratio to BudgetLeafAlias, averaged over frames, with its 95\% confidence interval.}" "\n"
       r"\label{tab:average-tree}" "\n" r"\resizebox{\textwidth}{!}{%" "\n" r"\begin{tabular}{l c c c c}" "\n" r"\toprule" "\n"
       r"Tree & RMSE $\downarrow$ & PSNR $\uparrow$ & VMAF $\uparrow$ & RMSE / BudgetLeafAlias $\downarrow$ \\" "\n"
       + "\n".join(rows) + "\n" r"\bottomrule" "\n" r"\end{tabular}}" "\n" r"\end{table}" "\n")
open(os.path.join(HERE, "table_average_tree.tex"), "w", encoding="utf-8").write(tex)
print("ok")
