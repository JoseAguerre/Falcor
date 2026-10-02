# Figures-only comparison grid (Fireplace Room, Phone, Convergence)

Produces the paper's full-frame diagonal-band comparison figure for the three scenes not shown
in the teaser: Random / 2D CDF / CodecLeafAlias / converged reference, with real measured RMSE
per technique, two large matched closeups per scene, and each scene's own emissive HDR texture
shown as a top-left inset. `figures_only_restir_v9.png` here is byte-identical to the submitted
copy (`paper/images/figures_only_restir_v9.png`).

## How it was built

`make_figures_only_page_v9.py` (the final iteration — v2 through v8 were earlier layout/styling
attempts, not copied here, superseded and not used in the paper) composites 3 already-rendered
per-scene panel images plus their closeup crops:

- `v9_fireplace_room.png` + `v9_fireplace_room_closeups.png`
- `v9_phonehand.png` + `v9_phonehand_closeups.png`
- `v9_convergence.png` + `v9_convergence_closeups.png`

(all 6 copied here from experiment22; the v9 script consumes them directly, it does not
regenerate them), plus the small top-left HDR texture inset, built directly from the scene's own
raw quadlight frame: `quadlight/fireplace/4k/frame_00082.hdr`, `quadlight/colors/frame_00987.hdr`,
`quadlight/cave/frame_00221.hdr` (copied here).

**Provenance gap:** the `v9_<scene>.png`/`_closeups.png` panel images were themselves generated
by `results/experiment22/make_comparison_figure_v2.ps1` (copied here), invoked once per scene
from the command line with `-CropSize 128 -UpscaleTo 500 -ManualRegions ...` flags (per the v9
script's own docstring) — but the exact `-SceneDir` argument (which raw per-technique render
folder it pointed at, almost certainly one of the `quality_weyl/<scene>/` datasets used
elsewhere in this paper) was run ad hoc and was never saved to a log or wrapper script. If you
only need to reproduce the final `figures_only_restir_v9.png` exactly, this doesn't matter — the
6 panel images are already here and are all v9's script needs. If you need to regenerate the
panels themselves from scratch (e.g. after an algorithm change), you'll need to re-run
`make_comparison_figure_v2.ps1` yourself against a fresh `quality_weyl`-style render dump and
re-pick `-ManualRegions` (or adapt its auto-search, if it has one — check the script).

## To regenerate
Run `make_figures_only_page_v9.py` directly against the files in this folder (update its
hardcoded input paths if you move it). Requires the Linux Libertine Bold font (MiKTeX install
originally, not a repo file).

## Files
- `make_figures_only_page_v9.py` — final compositor (the one used for the paper).
- `make_comparison_figure_v2.ps1` — the per-scene panel+closeup generator (exact original
  `-SceneDir` invocation not recoverable, see note above).
- `v9_{fireplace_room,phonehand,convergence}.png` + `_closeups.png` — the 6 panel inputs.
- `frame_00082.hdr`, `frame_00987.hdr`, `frame_00221.hdr` — HDR texture insets (renamed from
  their shared `frame_NNNNN.hdr` basename to keep them distinguishable in this flat folder:
  `fireplace_frame_00082.hdr`, `colors_frame_00987.hdr`, `cave_frame_00221.hdr`).
- `figures_only_restir_v9.png` — final image.
