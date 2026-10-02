# Diffuse convolution on real HDR scene textures (Figure 4 / "spp4")

Produces the paper's Figure 4: Lambertian diffuse convolution on three real HDR emissive
textures — captioned "cave" (= Convergence's `quadlight/cave` family), "fire" (= Fireplace
Room's `quadlight/fireplace/4k`), and "colors" (= Phone's `quadlight/colors`) — comparing 2D
CDF, per-pixel alias, and BudgetLeafAlias at a fixed 4 spp against a high-sample-count
reference, with a zoomed noise-inset crop per panel.

**Provenance gap, please read before relying on this folder for an exact byte-for-byte
re-render:** `spp4_as_submitted.png` / `spp4b_as_submitted.png` (copied from
`paper/images/spp4.png` / `spp4b.png`) are NOT numerically reproduced by
`results_{convergence,fireplace_room,phonehand}.json` in this folder — those JSON files report
RMSE in the 0.18-0.29 range (at N=4), while the submitted figure's inset RMSE labels are in the
7-10 range (a different normalization/scale, and visually a different layout: per-column
"Original" photo + inset zoom box, vs. this JSON's full N-sweep grid with no inset). The actual
one-off script that produced the final `spp4b.png` layout and numbers was run directly before
submission and was not saved separately — it is lost. `diffuse_convolution.py` is, however, the
correct and faithful methodology (same 3 techniques, same scenes, same N=300 2D-CDF reference)
and the closest available starting point to rebuild an equivalent figure; you will need to
rewrite the final plotting/compositing section (the "Original" thumbnail + inset-zoom-box
layout) yourself, or adjust the RMSE normalization to match, if an exact match matters.

## How it was built (the part that IS reproducible)

`diffuse_convolution.py` (+ `sampling_common.py`, copied from experiment24) runs stratified
per-pixel-and-per-sample N-rooks importance sampling of each technique's Lambertian response
against a real quadlight HDR frame, at sample counts N={1,4,6,8,12,16,20,24,30}, against a 2D
CDF / N=300 reference, computing RMSE/PSNR/FLIP. `results_<scene>.json` holds the full N-sweep
numbers; `convolution_grid_<scene>.png` is the full diagnostic grid (all N values, all
techniques, one "Reference" panel) — useful for sanity-checking a re-run, but not what's in the
paper.

## To regenerate
```
python diffuse_convolution.py <scene_key>   # scene_key in {convergence, fireplace_room, phonehand}
```
Reads the scene's real quadlight frame directly (hardcoded `SCENE_HDR` dict mapping scene key to
a `quadlight/...` path — not copied here, already present at its normal repo location). Writes
`results_<scene>.json` and `convolution_grid_<scene>.png`.

## Files
- `diffuse_convolution.py`, `sampling_common.py` — the sampling/evaluation code.
- `results_{convergence,fireplace_room,phonehand}.json` — full N-sweep RMSE/PSNR/FLIP numbers.
- `convolution_grid_{convergence,fireplace_room,phonehand}.png` — full diagnostic grids.
- `spp4_as_submitted.png`, `spp4b_as_submitted.png` — the exact images used in the paper
  (`paper/images/spp4.png`, `spp4b.png`); `spp4b.png` is the one actually referenced by
  `\includegraphics` as Figure 4 — `spp4.png` appears to be an earlier/alternate crop kept
  alongside it, not itself referenced in `PAPER.tex`.
