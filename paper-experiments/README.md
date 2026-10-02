# Paper experiments

A curated, self-contained copy of only the scripts/data/images that actually ended up in the
submitted paper (`paper/PAPER.tex`), organized by figure/table family instead of by experiment
number — so a later revision (after a reviewer comment, an algorithm tweak, or a Falcor change)
doesn't require re-discovering which of the 26 `results/experimentN/` folders produced which
final figure.

Nothing was removed or modified in any `results/experimentN/` folder, and nothing in `paper/`
was touched — everything here is a copy. Where a final image/table is byte-identical to its
counterpart in `paper/` or `paper/images/`, that's noted in the family's own README. Where the
exact generating script for a final figure wasn't preserved anywhere (one real gap — see
`diffuse_convolution_real_scenes/README.md`), that's flagged explicitly rather than guessed at.

Many scripts hardcode an absolute repo path (`REPO = r"C:\Users\Jose\Desktop\Falcor"`) rather
than a path relative to the script itself — this means copying a script here does not
automatically make it read its inputs from this folder; check each family's README for whether
you need to update that path before re-running.

## Families

- **teaser_rover_cinema_comparison** — Figure 1 (teaser): Rover (BudgetLeafAlias) + Cinema
  (CodecLeafAlias) diagonal-band comparisons with closeups.
- **codec_quadtree_visualization** — the VP9 coding-tree quadtree overlay figure.
- **sample_spectrum_banding** — 2D power-spectrum comparison showing per-pixel alias's banding
  artifact vs. 2D CDF and LeafAlias.
- **diffuse_convolution_real_scenes** — Figure 4: Lambertian diffuse convolution at 4 spp on
  three real scene HDR textures (cave/fire/colors). Has a documented provenance gap — see its
  README before relying on it for an exact re-render.
- **main_quality_table** — Table 1: RMSE/PSNR/FLIP for all 7 techniques x 5 scenes.
- **realtime_tradeoff_curves** — fitted RMSE-vs-frame-time curves (BudgetLeafAlias vs. 2D CDF
  vs. Mipmap).
- **video_level_quality_table** — Table 2: PSNR/VMAF/RMSE across full rendered video sequences.
- **denoiser_quality_and_flip_maps** — Table 3 (denoised RMSE) + the denoised-closeup FLIP grid
  figure.
- **figures_only_comparison_grid** — the Fireplace Room / Phone / Convergence full-frame
  comparison figure (also has a minor, non-blocking provenance gap for the raw-render source of
  its 3 panel images — see its README).
- **supplementary_videos** — the scripts behind the paper's supplementary-material videos
  (experiment9b's per-scene real-time "ours" videos + experiment26's high-quality references and
  camera-flythrough videos). The large final video files themselves are NOT duplicated here —
  see that family's README for where they live.

## Also worth knowing about
- `paper/cover_letter.txt` — the submission cover letter (not a figure/table, not copied here;
  already lives in `paper/`).
- `results/experiment22/` is the real hub most of these tables/figures were assembled in — it
  also contains several abandoned iteration drafts (`v2` through `v8` of a couple of figures,
  `hdr_tests/` synthetic-pattern exploration) that did NOT end up in the paper and were
  deliberately left out of this folder.
