# Codec coding-tree quadtree visualization

Produces the paper's "variance-driven quadtree built by the VP9 video codec" figure
(`quadtree.png` / `quadtree2.png` in `paper/images/`), showing the real per-frame coding-tree
partition overlaid on one of the quadlight video frames, with high-variance zones refined into
denser cells.

- `quadtree_as_submitted_uncropped.png` — byte-identical to `paper/images/quadtree2.png`
  (the full 1920x1080 render).
- `quadtree_as_submitted_cropped.png` — byte-identical to `paper/images/quadtree.png`, the
  version actually `\includegraphics`'d in the paper (manually cropped top/bottom, 1920x779,
  directly in the paper folder — there is no script for that crop step, it was a manual image
  edit done once at submission time).

## Provenance note

`make_quadtree_figures.py` is the "faithful port" generator: for each quadlight family under
`quadlight/`, it extracts the real coding-tree partition from a representative frame and draws
it in several line colors (`quadtree_<family>_<scene>_frame_*_<color>.png` — black/cyan/lime/
red/white variants), matching exactly what `QuadLightBudgetLeafAliasSampler`/CodecLeafAlias
actually samples from (non-square leaves, native aspect ratio). `make_quadtree_square_variant.py`
is a documented one-off stylistic alternative (square leaves via zero-padding) for a single
request, explicitly NOT representative of the real sampler's construction (see its own
docstring) — kept for completeness but not what's in the paper.

The exact final `quadtree.png` content here is visually the Rover family (road/mountain sunset
frame) but is not byte-identical to any of the specific `quadtree_road_rover_frame_*_black.png`
variants `make_quadtree_figures.py` produces in `results/experiment19/` — it was very likely a
one-off re-run of that script with the output filename hardcoded to `quadtree.png` instead of
the loop's own naming convention, which wasn't saved back as a separate script. If you need to
regenerate this exact figure, run `make_quadtree_figures.py` for the `road`/`rover` family and
frame, pick the black-outline variant, and crop as needed to match
`quadtree_as_submitted_cropped.png`'s aspect ratio.

## To regenerate
Both scripts read directly from `quadlight/<family>/frame_*.hdr` (shared repo asset, not copied
here — already present at its normal location) and need no other inputs. Just run either script
from a Python environment with `opencv-python`/`numpy` installed; outputs are written next to
the script.

## Files
- `make_quadtree_figures.py` — faithful per-family coding-tree partition visualizer.
- `make_quadtree_square_variant.py` — one-off square-leaf stylistic variant (not used in paper).
- `quadtree_as_submitted_uncropped.png` / `quadtree_as_submitted_cropped.png` — final images.
