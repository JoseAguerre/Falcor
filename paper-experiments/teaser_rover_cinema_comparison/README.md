# Teaser figure (Rover + Cinema comparison)

Produces the paper's teaser figure: two panels (Rover, Cinema), each a 4-way diagonal-band
comparison of Random / 2D CDF / our technique / converged reference, with two zoomed closeup
regions per panel.

- Rover panel uses **BudgetLeafAlias**.
- Cinema panel uses **AliasCtu** (= CodecLeafAlias).

`teaser_final.png` here is byte-identical to `paper/images/teaser.png` as submitted.

## How it was built

`make_teaser.py` reads pre-rendered `ToneMapper.dst.1.png` frames (one per technique, plus a
converged reference) directly from two per-scene render dumps, and composites the diagonal-band
panels + closeup crops from them:

- Rover: `rover_renders_quality_v3/` (copied from `results/experiment17/quality_v3/`)
- Cinema: `cinema_renders_quality_weyl/` (copied from `results/quality_weyl/cinema/`)

Each render dump also contains per-technique `.json` metric sidecars (RMSE/PSNR/FLIP) and
FLIP/RMSE heatmap PNGs, not just the tonemapped color image — kept here in case those are
useful for a revision, even though `make_teaser.py` itself only reads the color PNGs.

The closeup crop regions (`rover_regions`, `cinema_regions` in the script) were picked by hand
by inspecting `results/experiment17/figure_rover_newcam_v5.png` and an equivalent cinema figure
during calibration — see `experiment17_SUMMARY.md` for that narrative. If you re-render after an
algorithm change, you may want to re-pick these regions if the new noise pattern looks different.

## To regenerate

1. Re-render each technique (Random, Cdf2D, BudgetLeafAlias4000 for Rover; Random, Cdf2D,
   AliasCtu for Cinema) plus a converged reference, saving `<Technique>.ToneMapper.dst.1.png`
   into a folder matching the layout above (see `experiment17_SUMMARY.md` for the exact
   calibrated spp/lightSamplesPerVertex per technique used originally).
2. Run `make_teaser.py` (it hardcodes `REPO = C:\Users\Jose\Desktop\Falcor`, so it will read from
   wherever you point `rover_dir`/`cinema_dir` — currently the original experiment17/quality_weyl
   locations; update those two paths at the bottom of the script to point at the folders in this
   directory, or at freshly rendered ones).

## Files
- `make_teaser.py` — the compositing script (panels + closeups + labels).
- `experiment17_SUMMARY.md` — calibration narrative (camera framing, closeup region picking).
- `rover_renders_quality_v3/` — raw per-technique Rover renders + metrics (from experiment17).
- `cinema_renders_quality_weyl/` — raw per-technique Cinema renders + metrics (from the
  top-level `results/quality_weyl/cinema/` dataset, which also backs Table 1 and other figures).
- `teaser_final.png` — the exact image used in the paper (`paper/images/teaser.png`).
