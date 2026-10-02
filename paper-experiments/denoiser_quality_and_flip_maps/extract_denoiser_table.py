"""
Experiment 22: extract the noisy/denoised RMSE rows for Random, Cdf2D, and our best technique
per scene for the results_section.tex denoiser table, from the existing measured data in
results/experiment8/results.json (not modified, not re-rendered here).

experiment8 only ran the denoiser on whichever of our two techniques was that scene's "ours"
at the time (results.json's isOurs=True row): BudgetLeafAlias4000 for rover, and AliasCtu
(=CodecLeafAlias, the coding-tree-unit-partitioned alias table - not a BudgetLeafAlias
variant) for cinema, fireplace_room, and convergence. That split matches Table 1's own
per-scene winners, so each row here is correctly labeled with the technique that was actually
denoised rather than merged under one name.

Only rover, cinema, fireplace_room, and convergence are included: on phonehand the AI
denoiser increases RMSE for all three techniques and inverts the ranking (see
results/experiment8/SUMMARY.md's own analysis) - a real, separately-documented scene-specific
denoiser limitation that is out of scope for this subsection, which is about how a cleaner
input image helps the denoiser.

Writes results/experiment22/denoiser_table_data.json (this folder only).
"""
import json
import os

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SCENES = ["rover", "cinema", "fireplace_room", "convergence"]
TECH_LABEL = {"Random": "Random", "Cdf2D": "2D CDF", "BudgetLeafAlias4000": "BudgetLeafAlias", "AliasCtu": "CodecLeafAlias"}

results_path = os.path.join(REPO, "results", "experiment8", "results.json")
data = json.load(open(results_path, encoding="utf-8-sig"))

out = {scene: {} for scene in SCENES}
for row in data:
    scene = row["scene"]
    if scene not in out:
        continue
    tech = row["label"]
    label = TECH_LABEL.get(tech, tech)
    out[scene][label] = {"noisy_rmse": row["noisyRmse"], "denoised_rmse": row["denoisedRmse"]}

out_path = os.path.join(OUT_DIR, "denoiser_table_data.json")
json.dump(out, open(out_path, "w"), indent=2)
print("Saved", out_path)
for scene, techs in out.items():
    for label, v in techs.items():
        print(f"  {scene:16s} {label:16s} noisy={v['noisy_rmse']:.4f} denoised={v['denoised_rmse']:.4f}")
