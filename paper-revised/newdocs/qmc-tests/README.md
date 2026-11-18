# QMC tests: per-pixel alias tables vs. LeafAlias

Code and data for the note `note/qmc_note.pdf`, *On QMC stratification generating patterns with per-pixel alias
tables and how LeafAlias avoids that*. It reproduces Figures 1–3 and Tables 1 and 3 of the note.

## Contents

| Path | What it is |
|---|---|
| `samplers.py` | Python ports of the Falcor emitter samplers: 2D CDF, per-pixel alias (Falcor's `AliasTable.cpp` construction) and BudgetLeafAlias (budget quadtree, resorted alias table over the leaves). Also the Halton sequence. |
| `fence_test.py` | The fence test: a diffuse floor lit by a textured area light through a fence, direct lighting by light sampling, rendered with every sampler using per-pixel randomized QMC and pseudorandom numbers, against an exact reference. |
| `make_figures.py` | Figures 1–3 of the note. |
| `convergence.py` | Table 3 of the note: error against sample count (128 to 16384) in the unoccluded and partially occluded parts of the floor, and the sample count that reaches 1% error. About 13 minutes. |
| `data/` | Emitter textures: a region of frame 232 of the paper's Cinema video, at x = 704, y = 284, cropped to 1024×512 (fence test) and 1024×507 (Figure 1). |
| `figures/` | The figures as produced by `make_figures.py`. |
| `note/` | The note: LaTeX source, figures and PDF. |

## Requirements

Python 3.8 or newer and the packages in `requirements.txt`:

```
pip install -r requirements.txt
```

## Running

From this folder:

```
python fence_test.py --spp 128
python make_figures.py points
python make_figures.py scene results/fence_cinema_frame232_x704_y284_1024x512_128spp.npz
python make_figures.py fence results/fence_cinema_frame232_x704_y284_1024x512_128spp.npz
python convergence.py results/fence_cinema_frame232_x704_y284_1024x512_128spp.npz
```

`fence_test.py` takes about 4 minutes on a desktop CPU, most of it computing the exact reference, and prints the
relative RMSE of every render. With the default settings it gives:

| Sampler, 128 spp | pseudorandom | QMC |
|---|---|---|
| 2D CDF | 0.0736 | 0.0214 |
| Per-pixel alias | 0.0720 | 0.1855 |
| LeafAlias, 4000 leaves | 0.0741 | 0.0728 |
| LeafAlias, 1000 leaves | 0.0753 | 0.0723 |

All random numbers are seeded, so the results are deterministic.

Options:
- `fence_test.py --emitter <image> --spp <N> --width <W>` renders another emitter (`.hdr`, `.exr` or an 8-bit image),
  sample count or resolution. `--reference <earlier .npz>` reuses the exact image of an earlier run with the same
  emitter and width, which makes runs at other sample counts take seconds.
- `make_figures.py points --emitter <image> --points <N>` draws the point sets for another emitter or point count.
- Set `QMC_FONT` to a `.otf`/`.ttf` file to use a specific font in the figures (the note uses Linux Libertine).

## What to look for

- **Points (Figure 1).** The first coordinate of a low-discrepancy sequence visits the per-pixel alias table at a
  near-constant stride. Falcor's table construction keeps texels of a uniform region in scan order, so the stride
  becomes a fixed step through the image and the samples fall on straight lines. The 2D CDF and LeafAlias keep the
  points evenly spread.
- **Rendering (Figure 3, Table 1).** With QMC input the 2D CDF error drops 3.5×, per-pixel alias error rises 2.6×,
  and LeafAlias stays at its pseudorandom level.
- **Stride.** With 128 samples and an emitter 512 texels high, the stride is exactly 4 rows and the samples stack in
  one column. On the 1024×507 emitter (stride 3.96 rows) the lines slant and the increase disappears: per-pixel
  alias with QMC gives 0.0601 against 0.0731 pseudorandom (LeafAlias 4000: 0.0704; 2D CDF: 0.0211).

## Notes

- The samplers follow the Falcor shaders: the leftovers of the bucket selection place the sample inside the texel
  or leaf. In the fence test LeafAlias uses a third random number for the vertical position inside the leaf
  (Algorithm 2 of the paper); in Figure 1 it uses the leftovers, as the engine does. Both behave the same here.
- The renderer is a small Python ray caster with analytic geometry, not the Falcor renderer.
