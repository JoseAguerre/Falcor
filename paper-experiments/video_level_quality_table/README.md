# Video-level quality table (Table 2: PSNR/VMAF/RMSE across full video)

Produces the paper's video-quality table: mean +/- std PSNR and RMSE, and pooled VMAF
[min-max], for our technique vs. a converged reference, measured frame-by-frame across each
scene's full rendered video sequence (not just one representative frame).
`video_table.tex` here is byte-identical to `paper/`'s copy as submitted.

## How it was built

```
experiment16/video_metrics.json        (per-scene, per-variant PSNR/RMSE mean+std, from a
experiment16/vmaf_logs/<scene>_ours_vmaf.json   48-frame "ours"-vs-reference video comparison)
        |
        v  extract_video_table.py   (pulls the "ours" variant only; denoised numbers are
        |                            handled separately by the denoiser table)
video_table_data.json
        |
        v  render_video_table.py
video_table.tex
```

## To regenerate
If you only change formatting: re-run `render_video_table.py` against `video_table_data.json`.

If you need fresh numbers (e.g. after an algorithm change, or to extend past 48 frames): you
need to re-render each scene's video with the new technique, re-encode a converged reference
video, and re-run whatever per-frame PSNR/RMSE + `libvmaf` comparison experiment16 used to
produce `video_metrics.json`/`vmaf_logs/*.json` — that raw rendering pipeline lives in
`results/experiment16/` (not copied here in full; only its two small output JSON files per
scene are needed by this table). `results/experiment9b/` and `results/experiment26/` hold the
actual longer-form video renders used elsewhere in the paper (supplementary material) and would
be the natural starting point for a fuller video (see `../supplementary_videos/`).

## Files
- `extract_video_table.py` — pulls PSNR/RMSE/VMAF out of experiment16's measurement files.
- `video_metrics.json` — per-scene/variant PSNR+RMSE mean/std (from experiment16).
- `vmaf_logs/` — per-scene pooled VMAF logs (from experiment16; "ours" variant only, matching
  what this table reports — the folder also has "_denoised" logs, kept for completeness).
- `video_table_data.json` — intermediate (regenerable from the above).
- `render_video_table.py` / `video_table.tex` — final table.
