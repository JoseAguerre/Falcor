# Performance analysis comparison on two different GPUs

Produces `note.pdf`, a four-page comparison of BudgetLeafAlias and CodecLeafAlias against a dense
2D CDF and three further baselines, on an **RTX 4080 SUPER** and an **RTX 4050 Laptop**.

Nothing under `paper/`, `paper-revised/` or `paper-experiments/` is read-write: this directory only
reads from them. All output lives here.

## The two studies

| Study | What it measures | 4050 | 4080 SUPER |
|---|---|---|---|
| Equal quality | Speed-up over the 2D CDF to reach the quality it achieves in a 33.3 ms frame | measured here | the project's own equal-quality experiment (`paper-revised/newtests/equal-quality/table_scenes.tex`) |
| Leaf budget | Cost of BudgetLeafAlias against its leaf budget | measured here, rendered frames **and** isolated sampling | isolated sampling, from the leaf-budget supplement's Table 2 |

The isolated-sampling half of the leaf-budget study is the only comparison made with a
byte-identical protocol on both parts; it reuses `../supp-gpu-scaling/data/summary.json`. Everywhere
else the 4080 SUPER column carries the protocol of the experiment it came from, and the note says so
in its Section 2.

## Protocol (the 4050 column)

* Direct illumination only, quad light as the scene's sole light source, 1 spp, 1920x1080.
* Twelve rungs per ladder: 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64 light samples per shading point.
* Forty frames per rung, median frame time after a twelve-frame warm-up, one frame captured.
* Reference: 1200 accumulated frames with the Random sampler at 64 light samples.
* RMSE is computed against that reference and smoothed by a quadratic fit of log(MSE) against
  log(samples), as the project's own equal-quality script does.

Three settings matter and were each arrived at by a failed attempt first:

1. **Direct illumination.** With indirect bounces on, residual path-tracing noise does not fall with
   the light-sample count, so it masks the error being measured and the equal-quality crossing
   becomes ill-conditioned (it produced a 3.3x speed-up for Mipmap, which is nonsense).
2. **Primary samples at pixel centres.** A jittered pattern makes every frame differ from the
   accumulated reference by an anti-aliasing term that no number of light samples removes.
3. **`useEnvLight = False`.** Phone also carries a constant environment map; its lighting is not
   controlled by the light-sample count, so it flattens the whole ladder. The other two scenes are
   quad-light only already.

`data_gi/` holds the superseded first attempt (indirect bounces, 4 spp) and is kept only as a record
of point 1; its renders were deleted.

## Running it

```sh
python run_render.py reference     # ~6 min
python run_render.py ladder        # ~8 min, 18 ladders
python run_render.py leaves        # ~4 min, 15 leaf-budget ladders
<venv>/python run_render.py rmse   # needs opencv + numpy
<venv>/python analyze.py           # tables/, figures/, and the printed report
pdflatex note.tex                  # twice, for the cross-references
```

`run_render.py` skips any configuration whose result JSON already exists, so a sweep can be resumed.
The `rmse` and `analyze` steps need `numpy`, `matplotlib` and `opencv-python-headless`; the other
steps only launch Mogwai. On this machine pdflatex is in
`C:\Users\Elojo\AppData\Local\Programs\MiKTeX\miktex\bin\x64\`, not on `PATH`.

Mogwai needs the `QuadLightSamplerBench` plugin only for the sampling half of the leaf-budget study,
which is already summarised in `../supp-gpu-scaling/`. The ladders here need just a stock Release
build.

## Files

* `note.tex` / `note.pdf` — the document.
* `render_ladder.py` — Mogwai-side driver (graph, sampler, per-rung capture, frame timing).
* `run_render.py` — host-side orchestrator; `reference`, `ladder`, `leaves`, `rmse` phases.
* `analyze.py` — builds `tables/` and `figures/` and prints every number quoted in the note.
* `analyze_eq.py` — earlier exploratory analysis against the dense (spp, lspv) sweep in
  `paper-experiments/realtime_tradeoff_curves`. That sweep is indirect-illumination, so it is not
  comparable with the ladders here and is **not** used by the note; kept because it is the way to
  re-derive 4080 SUPER ladders if an indirect-illumination comparison is ever wanted.
* `data/` — one JSON per (scene, technique or leaf budget), each a ladder with frame time, RMSE and
  MSE per rung.
* `renders/` — the captured frames and the three references (~1.1 GB; safe to delete, the RMSE
  values are already in `data/`).
