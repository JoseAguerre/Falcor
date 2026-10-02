# Denoiser quality table + denoised FLIP closeups

Two related deliverables about pairing each technique with OptiX's AI denoiser:

1. **Table 3** (`denoiser_table.tex`, byte-identical to the submitted copy): RMSE before/after
   denoising for Random, 2D CDF, and whichever of our two techniques was that scene's official
   winner (BudgetLeafAlias for Rover, CodecLeafAlias/AliasCtu for Cinema, Fireplace Room, and
   Convergence). Phonehand is intentionally excluded — the AI denoiser increases RMSE for every
   technique there and inverts the ranking, a real scene-specific denoiser limitation documented
   in `results/experiment8/SUMMARY.md`, out of scope for "does a cleaner input help the
   denoiser."
2. **Figure** `denoised_flip_grid.png` (byte-identical to the submitted copy): denoised closeups
   + FLIP error-map heatmaps for Convergence and Fireplace Room, 2D CDF vs. CodecLeafAlias, at
   the two regions per scene with the largest denoised-FLIP gap between them.

## How Table 3 was built
```
experiment8/results.json  (noisyRmse/denoisedRmse per scene, per technique, isOurs flag)
        |
        v  extract_denoiser_table.py
denoiser_table_data.json
        |
        v  render_denoiser_table.py
denoiser_table.tex
```

## How the FLIP grid was built
`make_denoised_flip_grid.py` reads, per scene, a converged `reference.ToneMapper.dst.*.png`
(from `quality_weyl/<scene>/`, copied into `reference_renders/<scene>/` here) and each
technique's already-denoised render (`denoised.ToneMapper.dst.4.png`, from
`experiment8/renders/<scene>_<Technique>/`, copied into `denoised_renders/` here). It then
computes FLIP itself at runtime using NVIDIA's official `flip_evaluator` pip package (NOT the
heatmaps already sitting in `experiment8/renders/`, which came from Falcor's own FLIPPass node —
same metric, different code path, so don't expect the absolute numbers to match exactly; only
used here for *relative*, same-technique-pair region selection, which is unaffected), searches
for the 2 highest-FLIP-gap 128px regions per scene, and composites the 2-row x 8-column grid.

## To regenerate
- Table 3: if only reformatting, re-run `render_denoiser_table.py` on `denoiser_table_data.json`.
  For fresh numbers, you need a new per-scene noisy+denoised RMSE pass like `experiment8/results.json` provides.
- FLIP grid: re-run `make_denoised_flip_grid.py` against the renders in this folder (update its
  hardcoded input paths). Requires `pip install flip_evaluator` and the Linux Libertine Bold/
  Regular fonts (originally read from a local MiKTeX install — not repo files).

## Files
- `extract_denoiser_table.py`, `experiment8_results.json` (renamed from `results.json` to be
  self-descriptive), `denoiser_table_data.json`, `render_denoiser_table.py`, `denoiser_table.tex`
- `make_denoised_flip_grid.py`
- `reference_renders/{convergence,fireplace_room}/` — converged reference frame per scene.
- `denoised_renders/{convergence,fireplace_room}_{AliasCtu,Cdf2D}/` — denoised renders per
  scene/technique.
- `denoised_flip_grid.png` — final image.
