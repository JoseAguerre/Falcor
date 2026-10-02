# Real-time quality-vs-time tradeoff curves

Produces the paper's Figure (`realtime_curves.png`): fitted RMSE-vs-frame-time power-law curves
for Rover, Cinema, Phone, and Convergence, for 2D CDF, Mipmap, and BudgetLeafAlias — showing
BudgetLeafAlias's curve staying below both baselines across the whole measured range, and
steepest (the advantage widens as more time budget is available).

`realtime_curves.png` here is byte-identical to `paper/images/realtime_curves.png`.

## How it was built

`make_realtime_curves.py` reads one `all_data.json` per scene (`results/experiment11/<scene>/`,
copied into this folder) — each a dense sweep of ~2048 (spp, lightSamplesPerVertex) measurement
points per technique, with RMSE and achieved frame time — fits a power-law curve per
(scene, technique) via `numpy.polyfit` in log-log space, and plots the four scene panels.
Fireplace Room is deliberately excluded from this figure: its curves for the three techniques
overlap too much at this sweep's resolution to be informative, per the script's own comment.

## To regenerate
Re-run `make_realtime_curves.py` directly against the `all_data.json` files in this folder (it
only needs those four, update its hardcoded input paths if you move this folder). To refresh
with new numbers after an algorithm change, you'd need to redo the dense sweep that produced
`all_data.json` for whichever scenes/techniques changed — see `results/experiment11/` for that
sweep's own driver scripts if you need the original sweep methodology.

## Files
- `make_realtime_curves.py` — curve fitting + plotting.
- `rover_all_data.json`, `cinema_all_data.json`, `phonehand_all_data.json`,
  `convergence_all_data.json` — the raw sweep points per scene (renamed on copy from each
  scene's own `all_data.json` to avoid a four-way filename collision in this flat folder).
- `realtime_curves.png` — final image.
