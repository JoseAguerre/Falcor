# Sample spectrum / per-pixel alias banding artifact

Produces the paper's 2D power-spectrum figure comparing 2D CDF inversion, plain per-pixel
alias, and our LeafAlias, all warped from the same Halton input — showing per-pixel alias's
sharp off-axis banding peak versus the other two methods' clean spectra.

- `spectrum_as_submitted.png` — `paper/images/fig_spectrum_paper_color.png` as submitted
  (not byte-identical to `spectrum_as_rendered_in_experiment22.png`; it was hand-tweaked
  slightly — crop/resize — after being copied into `paper/images/`, same as the quadtree and
  spp4 figures).
- `spectrum_as_rendered_in_experiment22.png` — the direct, unmodified output of
  `fig_paper_spectrum_libertine.py`.

## How it was built

Two-stage process, across two experiments:

1. `fig_paper_spectrum_color_original.py` (originally `results/experiment14/fig_paper_spectrum_color.py`)
   generates the actual sample sets: a Halton point set warped through 2D CDF inversion, through
   a plain per-pixel alias table, and through our (quadtree-leaf) alias table, over the
   `hdr`-family quadlight texture. It caches the raw point sets to `samples_hdr_4000.npz`
   (included here) so the figure can be re-styled without re-running the sampling. It also
   computes each method's 2D FFT, flatness, and peak/median ratio (the numbers quoted in the
   paper's caption).
2. `fig_paper_spectrum_libertine.py` (from `results/experiment22/`) is a pure visual re-styling
   pass over the SAME cached `samples_hdr_4000.npz` — same data, different font (Linux Libertine,
   matching the ACM template's body font) and layout polish. This is the one that actually
   produced the paper figure, not the experiment14 original.

Background texture crop shown under the point sets: `frame_00180.hdr` (copied here from
`quadlight/hdr/`).

## To regenerate
- If only re-styling: run `fig_paper_spectrum_libertine.py` directly against `samples_hdr_4000.npz`
  and `frame_00180.hdr` in this folder (update the hardcoded `REPO`/input paths at the top).
- If the underlying sampling algorithm changes (e.g. the alias-table construction): re-run
  `fig_paper_spectrum_color_original.py` first to regenerate `samples_hdr_4000.npz`, then re-run
  `fig_paper_spectrum_libertine.py` on the fresh cache.

## Requires
Linux Libertine font (`LinLibertine_R.otf`) available locally (the original setup used a MiKTeX
install's copy) — not a repo file, install separately if missing.

## Files
- `fig_paper_spectrum_color_original.py` — original sampling + analysis + first-pass figure.
- `fig_paper_spectrum_libertine.py` — final visual re-styling pass (the one used for the paper).
- `samples_hdr_4000.npz` — cached Halton/CDF/alias/LeafAlias point sets (the real intermediate
  result both scripts depend on).
- `frame_00180.hdr` — background texture crop.
- `spectrum_as_submitted.png` / `spectrum_as_rendered_in_experiment22.png` — final images.
