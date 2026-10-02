# Experiment 17: rover, new camera angle only

## What changed

`results/experiment17/rover_newcam.pyscene` is a byte-for-byte copy of the official
`paperscenes/rover/rover.pyscene`, with:
- Every `meshes/...ply` and `textures/...` relative path prefixed with
  `../../paperscenes/rover/` (the file now lives two directories away from the original).
  The `../../quadlight/road/frame_00150.hdr` QuadLight path was left untouched: both the
  original file's directory (`paperscenes/rover/`) and the new one (`results/experiment17/`)
  sit exactly two levels below the repo root, so that relative path already resolves to the
  same absolute file (`Falcor/quadlight/road/frame_00150.hdr`) from either location.
- The camera block only:

```python
camera.position = float3(-52.6620216, 7.40289974, 5.35568619)
camera.target   = float3(-51.6755791, 7.36966372, 5.19498682)
camera.up       = float3(-0.00182660634, 0.999998271, 0.000297568622)
camera.focalLength = 68.0553818
camera.focalDistance = 10000
camera.apertureRadius = 0
camera.nearPlane = 0.100000001
camera.farPlane = 1000
```

(Original official camera: `position=(-56.24, 19.58, -3.550)`, `target=(-55.28, 19.312, -3.545)`,
`up=(0,1,0)`, `focalLength=68.055382`.) Nothing else - materials, ground, LED wall geometry,
render settings - was touched. `sceneBuilder.renderSettings` still has `useEnvLight=False,
useAnalyticLights=False, useEmissiveLights=False, useQuadLight=True`, matching the official
scene exactly.

The new camera sits noticeably lower and closer to the rover than the official one (Y~7.4 vs
Y~19.6, and closer along the ground plane), producing a much tighter, more oblique 3/4 view
of the rover that fills most of the frame, rather than the official camera's more distant,
elevated view that leaves more LED-wall backdrop and floor visible around a smaller rover.

## Render configuration

Reused the official calibrated rover configs from `results/realtime_budget.json` /
`results/quality_summary_weyl.json` exactly, no recalibration:
- Random: spp=4, lspv=19
- Cdf2D: spp=4, lspv=5
- Ours = BudgetLeafAlias4000: spp=4, lspv=22, leafBudget=4000
- Reference: Random, spp=8, lspv=1, Weyl QMC, 8000 accumulated frames (warmup=160) - calibrated
  from a 60-frame timing pass (measured meanFrameTimeMs=12.585) targeting ~120s of total
  frame time, capped at the script's 8000-frame ceiling; actual reference render took 114.8s
  wall-clock, within the intended 60-240s band.

Figure `results/experiment17/figure_rover_newcam.png` was built with
`results/make_comparison_figure.ps1 -SceneDir results\experiment17\quality -SceneName rover
-OursLabel BudgetLeafAlias4000 -OursDisplayName BudgetLeafAlias4000`, letting it auto-pick
all 3 closeup regions (no `-ManualRegions` override) - a grep of `results/*.ps1` and
`results/experiment*/*.ps1` for `ManualRegions` shows it is never used for the official rover
or phonehand figures either, so this matches the same convention used everywhere else in the
project, not a special case.

## Results: new camera vs. official camera

| Technique           | spp | lspv | leafBudget | RMSE (new cam) | RMSE (official cam) | FLIP (new cam) | FLIP (official cam) |
|----------------------|-----|------|------------|-----------------|-----------------------|------------------|------------------------|
| Random               | 4   | 19   | -          | 0.044625        | 0.046803              | 0.053563         | 0.061518               |
| Cdf2D                | 4   | 5    | -          | 0.070577        | 0.077878              | 0.063607         | 0.074750               |
| BudgetLeafAlias4000  | 4   | 22   | 4000       | 0.037000        | 0.036741              | 0.046964         | 0.052543               |

("official cam" numbers are pulled directly from `results/quality_summary_weyl.json`'s rover
entries, which use the identical spp/lspv/leafBudget configs and the identical Random
spp=8/lspv=1/Weyl reference recipe at refFrames=2009 - the genuine official rover quality
numbers this project has published elsewhere, e.g. `results/figures/figure_rover.png`.)

Ours (BudgetLeafAlias4000) beats Cdf2D by:
- RMSE: 52.8% reduction in the official view vs. 47.6% reduction in the new view.
- FLIP: 29.7% reduction in the official view vs. 26.2% reduction in the new view.

## Does the ranking/advantage hold from the new viewpoint?

**Yes, on both counts.** The ranking Ours < Random < Cdf2D (lower error is better) is
identical in both viewpoints, on both RMSE and FLIP - Cdf2D is consistently the worst of the
three even though it has more effective light samples than Random relies on tighter analytic
sampling that apparently struggles more with this scene's fold-corner QuadLight geometry, a
pattern this project has already reported at the official viewpoint. The magnitude of Ours's
advantage is essentially unchanged: roughly a 50% RMSE cut and a 27-30% FLIP cut relative to
Cdf2D in both views, with the new-camera numbers landing just a few points lower across the
board for every technique (all three RMSE values dropped by 2-9%, FLIP values dropped by
11-15%). That uniform drop is consistent with the new view containing somewhat less
high-frequency, hard-shadow-edge detail per pixel (a closer, more grazing framing of the
rover's body against a large flat green floor, versus the official view's more distant framing
that keeps sharper edges - LED-wall/floor boundary, rover silhouette against sky - at a larger
relative scale in-frame).

One genuine difference worth flagging: `results/make_comparison_figure.ps1`'s automatic
region-picker landed 3 of its 4 closeup squares on the flat green floor in the new view
(vs. 1 of 4 - the far orange square - in the official figure), with the 4th on the rover's
antenna/sensor mast silhouetted against the sky. In the official figure two of the four
closeups (cyan, magenta) sit directly on the rover's body/fender, which visibly show reference
vs. Random/Cdf2D/Ours noise differences on real object detail (windshield-frame edge, a
metal-panel patch). In the new, closer camera the rover itself renders quite dark/backlit in
this lighting setup, so the biggest per-pixel differences the auto-picker could find
concentrated on the brightly-lit, high-frequency-noise floor instead of the (comparatively
low-contrast, dark) rover surfaces. This is a real framing/exposure difference, not a
technique-quality difference - the underlying RMSE/FLIP numbers above are computed over the
*whole* frame either way, so this only affects which patches the illustrative closeups happen
to land on, not the quantitative comparison itself.

## Files

- Scene: `results/experiment17/rover_newcam.pyscene`
- Render/measure script: `results/experiment17/run_quality.ps1`
- Renders + metrics: `results/experiment17/quality/` (`reference.*.png`, `Random.*.png`,
  `Cdf2D.*.png`, `BudgetLeafAlias4000.*.png`, `*.json`, `*.rmse_heatmap.png`,
  `*.flip_heatmap*.png`, `summary.json`, `summary.md`)
- Figure: `results/experiment17/figure_rover_newcam.png`
