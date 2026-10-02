"""
Experiment 22: assemble the video-quality table (Table 3 of results_section.tex) from the
existing, already-computed measurement files in results/experiment16/ (not modified, not
re-measured). PSNR/RMSE mean and std come directly from video_metrics.json's "ours" variant
per scene (48-frame sequence vs. converged reference, std computed by that experiment across
the 48 per-frame values); VMAF's mean/min/max come from the matching <scene>_ours_vmaf.json
log's own pooled_metrics (libvmaf computes one VMAF score per frame internally and pools them
- the pooled mean is already a whole-video aggregate, not a single-frame number). Only the
non-denoised "ours" variant is used here - denoised numbers are reported separately in the
denoiser subsection (extract_denoiser_table.py).

Writes results/experiment22/video_table_data.json (this folder only).
"""
import json
import os

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
EXP16 = os.path.join(REPO, "results", "experiment16")

SCENES = ["rover", "cinema", "fireplace_room", "phonehand", "convergence"]

metrics = json.load(open(os.path.join(EXP16, "video_metrics.json")))
by_key = {(r["scene"], r["variant"]): r for r in metrics}

out = {}
for scene in SCENES:
    r = by_key[(scene, "ours")]
    vmaf_path = os.path.join(EXP16, "vmaf_logs", f"{scene}_ours_vmaf.json")
    vmaf_pooled = json.load(open(vmaf_path))["pooled_metrics"]["vmaf"]
    out[scene] = {
        "psnr": r["psnr_mean"],
        "psnr_std": r["psnr_std"],
        "rmse": r["rmse_mean"],
        "rmse_std": r["rmse_std"],
        "vmaf": vmaf_pooled["mean"],
        "vmaf_min": vmaf_pooled["min"],
        "vmaf_max": vmaf_pooled["max"],
    }

out_path = os.path.join(OUT_DIR, "video_table_data.json")
json.dump(out, open(out_path, "w"), indent=2)
print("Saved", out_path)
for scene, v in out.items():
    print(f"  {scene:16s} PSNR={v['psnr']:.2f}+-{v['psnr_std']:.3f}  "
          f"VMAF={v['vmaf']:.1f} [{v['vmaf_min']:.1f}-{v['vmaf_max']:.1f}]  "
          f"RMSE={v['rmse']:.4f}+-{v['rmse_std']:.5f}")
