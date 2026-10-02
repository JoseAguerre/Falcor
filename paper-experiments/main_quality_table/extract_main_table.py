"""
Experiment 22: extract the real-time calibrated RMSE/MSE/FLIP/PSNR for the seven techniques
reported in the Results section's main table, for all five official scenes, from the
existing measurement file results/quality_summary_weyl.json (read-only, not modified).

PSNR is derived here as -10*log10(mse) from that file's own mse field - a standard metric
transform of an already-measured number, not a new measurement. For BudgetLeafAlias we
always take the leafBudget=4000 row, per the paper's convention of only reporting the 4000
leaf configuration. "AliasCtu" is the in-engine QuadLightSamplerType name for CodecLeafAlias
(it partitions using the video codec's coding-tree-unit structure, hence the name) - it is
not a BudgetLeafAlias variant, and it is real per-frame data on all 5 official scenes, not
the separate 3-video-sequence poster data used for the CodecLeafAlias iterations/PSNR table.

Writes results/experiment22/main_table_data.json (this folder only).
"""
import json
import math
import os

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SCENES = ["rover", "cinema", "fireplace_room", "phonehand", "convergence"]
TECHS = ["Random", "Cdf2D", "Cdf2DDiv8", "HierarchicalMip", "AliasPerPixel", "BudgetLeafAlias", "AliasCtu"]
RENAME = {"BudgetLeafAlias": "BudgetLeafAlias4000", "AliasCtu": "CodecLeafAlias"}

data = json.load(open(os.path.join(REPO, "results", "quality_summary_weyl.json")))

out = {scene: {} for scene in SCENES}
for row in data:
    scene, tech = row["scene"], row["technique"]
    if scene not in out or tech not in TECHS:
        continue
    if tech == "BudgetLeafAlias" and row.get("leafBudget") != 4000:
        continue
    key = RENAME.get(tech, tech)
    out[scene][key] = {
        "spp": row["samplesPerPixel"],
        "lspv": row["lightSamplesPerVertex"],
        "leaf": row.get("leafBudget"),
        "rmse": row["rmse"],
        "mse": row["mse"],
        "flip": row["averageFLIP"],
        "psnr": -10.0 * math.log10(row["mse"]),
        "ms": row["achievedMs"],
    }

out_path = os.path.join(OUT_DIR, "main_table_data.json")
json.dump(out, open(out_path, "w"), indent=2)
print("Saved", out_path)
for scene in SCENES:
    expected = [RENAME.get(t, t) for t in TECHS]
    missing = [t for t in expected if t not in out[scene]]
    if missing:
        print("  WARNING missing", scene, missing)
    else:
        best_rmse = min(out[scene].items(), key=lambda kv: kv[1]["rmse"])
        print(f"  {scene:16s} best RMSE -> {best_rmse[0]} ({best_rmse[1]['rmse']:.4f})")
