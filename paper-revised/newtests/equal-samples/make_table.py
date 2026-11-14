"""Builds table_equal_samples.tex for this document from the E38 results (major-revision/E38_equal_sample_table1),
in the layout of the paper's Table 1: techniques as rows, scenes as column groups, best per column in bold."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
E38 = os.path.join(HERE, "..", "..", "E38_equal_sample_table1")
S = ["rover", "cinema", "fireplace_room", "phonehand", "convergence"]
LAB = {"rover": "Rover", "cinema": "Cinema", "fireplace_room": "Fireplace Room", "phonehand": "Phone", "convergence": "Convergence"}
T = ["Random", "2D CDF", "2D CDF/8", "Mipmap", "Alias per pixel", "BudgetLeafAlias", "CodecLeafAlias"]
D = {s: json.load(open(os.path.join(E38, f"table1_{s}.json"))) for s in S}
best = {}
for s in S:
    r = D[s]["results"]
    best[(s, "rmse")] = min(r[t]["rmse"] for t in T)
    best[(s, "psnr")] = max(r[t]["psnr"] for t in T)
    best[(s, "flip")] = min(r[t]["flip"] for t in T)


def cell(s, t, k, fmt):
    txt = fmt.format(D[s]["results"][t][k])
    return r"\textbf{" + txt + "}" if txt == fmt.format(best[(s, k)]) else txt


rows = []
for t in T:
    cells = []
    for s in S:
        cells += [cell(s, t, "rmse", "{:.4f}"), cell(s, t, "psnr", "{:.2f}"), cell(s, t, "flip", "{:.4f}")]
    rows.append(t + " & " + " & ".join(cells) + r" \\")
cfg = ", ".join(f"{LAB[s]} {D[s]['config']['spp']}$\\times${D[s]['config']['lspv']}" for s in S)
tex = (r"\begin{table*}[t]" "\n" r"\centering" "\n" r"\small" "\n" r"\setlength{\tabcolsep}{2.5pt}" "\n"
       r"\caption{RMSE, PSNR (dB) and \FLIP\ for all techniques at equal samples: within a scene, every technique uses the same "
       r"samples per pixel and light samples per shading point (" + cfg + r"). Representative frame of each scene against a "
       r"converged reference; mean of 24 independent renders (\FLIP: 8). The 95\% confidence intervals of the RMSE are "
       r"0.0001--0.0011. Best per column in bold.}" "\n"
       r"\label{tab:equal-samples}" "\n" r"\resizebox{\textwidth}{!}{%" "\n"
       r"\begin{tabular}{l ccc ccc ccc ccc ccc}" "\n" r"\toprule" "\n"
       r"\multirow{2}{*}{Technique} & " + " & ".join(r"\multicolumn{3}{c}{" + LAB[s] + "}" for s in S) + r" \\" "\n"
       r"\cmidrule(lr){2-4} \cmidrule(lr){5-7} \cmidrule(lr){8-10} \cmidrule(lr){11-13} \cmidrule(lr){14-16}" "\n"
       r" & " + " & ".join([r"RMSE $\downarrow$ & PSNR $\uparrow$ & \FLIP\ $\downarrow$"] * 5) + r" \\" "\n" r"\midrule" "\n"
       + "\n".join(rows) + "\n" + r"\bottomrule" "\n" r"\end{tabular}}" "\n" r"\end{table*}" "\n")
open(os.path.join(HERE, "table_equal_samples.tex"), "w", encoding="utf-8").write(tex)
print("ok")
