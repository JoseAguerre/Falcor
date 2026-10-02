# Main quality table (Table 1: RMSE/PSNR/FLIP, 7 techniques x 5 scenes)

Produces the paper's main results table: RMSE, PSNR, and FLIP for all 7 techniques (Random,
2D CDF, 2D CDF/8, Mipmap, Alias per pixel, BudgetLeafAlias, CodecLeafAlias) on all 5 scenes, at
each technique's real-time-calibrated configuration (spp + light-samples-per-vertex).
`main_table_inverted.tex` here is byte-identical to `paper/main_table_inverted.tex` as
submitted (techniques as rows, scenes as grouped column blocks).

## How it was built

```
quality_summary_weyl.json  (top-level measurement file: per scene/technique spp, lspv,
                             leafBudget, rmse, mse, averageFLIP, achievedMs - the ground truth)
        |
        v  extract_main_table.py
main_table_data.json  (filtered/renamed to the paper's 7 technique labels; PSNR derived as
                        -10*log10(mse); BudgetLeafAlias always takes the leafBudget=4000 row)
        |
        v  render_main_table_inverted.py
main_table_inverted.tex  (the \input'd table, techniques-as-rows layout)
```

`render_main_table.py` / `main_table.tex` (also included) is the original techniques-grouped-
by-scene-rows layout — superseded by the inverted version, not used in the final paper, kept
here only because it reads the same `main_table_data.json` and costs nothing to keep.

## To regenerate
If you only change which values are reported (formatting, bolding rule, rounding): re-run
`render_main_table_inverted.py` against `main_table_data.json` directly.

If you change an algorithm and need fresh numbers: you need a new `quality_summary_weyl.json`-
shaped sweep (per scene, per technique: calibrate spp/lspv to the real-time budget, measure
RMSE/MSE/FLIP/achievedMs) — that calibration sweep itself is a large cross-experiment process,
not captured as a single script in experiment22; `results/realtime_budget.json` (top-level) is
an earlier/related calibration pass if you need a template for that measurement format.

## Files
- `extract_main_table.py` — filters/renames the raw measurement file into table-ready JSON.
- `quality_summary_weyl.json` — the real per-technique-per-scene measurements (ground truth).
- `main_table_data.json` — intermediate (regenerable from the above, kept for convenience).
- `render_main_table.py` / `main_table.tex` — superseded non-inverted layout (kept, not used).
- `render_main_table_inverted.py` / `main_table_inverted.tex` — final layout (used in paper).
