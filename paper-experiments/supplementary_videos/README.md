# Supplementary material videos

The paper's Results section says "The resulting videos are found in the supplementary
material" — this is that material: `results/SupplementaryMaterial/*.zip` (confirmed by exact
byte match against the two experiments below; not copied into this folder since they're large
and already sit in one place — see "Where the final files live" below).

Two different experiments contributed the final zips, for two different purposes:

## 1. Per-scene "ours" real-time videos (noisy, our technique only) — from experiment9b

`results/experiment9b/_bench_video.py` + `gen_playlists.py` render each scene's **entire**
native quadlight video sequence in one continuous Mogwai process (using Falcor's native
`QuadLightVideoPlayer` + `.hdrplaylist` files, not a per-frame relaunch — see
`experiment9b/SUMMARY.md` for why that matters, ~120x faster). Output: `<scene>_ours.webm` for
rover, cinema, fireplace_room, phonehand (convergence's "ours" video is not part of the
submitted supplementary set). These became `rover_ours_noisy.zip`, `fireplace_ours_noisy.zip`,
and `ours_noisy_1.zip` (bundling phonehand + cinema) in `SupplementaryMaterial/`.

## 2. High-quality references + camera flythroughs — from experiment26

`results/experiment26/` re-renders the reference videos at genuinely higher quality (fixing a
real bug found along the way: `PathTracer` silently hard-caps `samplesPerPixel` at 16, so
experiment9b's own "high-sample" reference was secretly capped the whole time — see
`experiment26/SUMMARY.md`), using 8x manual sub-frame accumulation for ~128 effective spp. It
also adds new camera-flythrough videos (our technique + OptiX denoiser, camera orbiting/rising
while the scene's HDR video plays, looped twice through the native sequence) for the 4 scenes
denoising actually helps (not phonehand, matching experiment8's finding).

- `<scene>_reference_hq.webm` (all 5 scenes) -> `references noisy.zip` (despite the
  misleading name, these ARE the HQ re-renders, not the original noisy 9b references) +
  `convergence_reference.zip` (convergence shipped separately, likely just for zip-size
  reasons).
- `<scene>_flythrough_denoised.webm` (rover, cinema, fireplace_room, convergence) ->
  `flythroughs_denoised.zip`.

Key scripts: `_bench_video_hq.py`, `gen_playlists_hq.py`, `_bench_flythrough.py`,
`run_reference_hq.ps1`, `run_flythrough.ps1`.

## Where the final files live
Not duplicated into this folder (large binaries, already centralized):
- `results/SupplementaryMaterial/*.zip` — the exact files as submitted.
- `results/experiment9b/videos/*_ours.webm` — the per-scene source videos (zip 1).
- `results/experiment26/videos/*_reference_hq.webm`, `*_flythrough_denoised.webm` — the
  per-scene source videos (zip 2), also available as `.mp4`.

## What IS copied into this folder (lightweight — just the generation code)
- `experiment9b_bench_video.py`, `experiment9b_gen_playlists.py` (renamed on copy from
  `_bench_video.py`/`gen_playlists.py` for clarity in this flat folder)
- `experiment9b_SUMMARY.md`
- `experiment26_bench_video_hq.py`, `experiment26_gen_playlists_hq.py`,
  `experiment26_bench_flythrough.py`, `experiment26_run_reference_hq.ps1`,
  `experiment26_run_flythrough.ps1`
- `experiment26_SUMMARY.md`

## To regenerate
Both experiments' scripts require Falcor's `Mogwai.exe` (built, not rebuilt by these scripts)
and the real quadlight video frame sequences under `quadlight/` (shared repo asset, not
copied). See each experiment's own SUMMARY.md for calibrated per-scene parameters (sampler,
spp, lightSamplesPerVertex, leaf budget) and known pitfalls (in particular experiment26's
3-bug accumulation story — framerate-mode breaks accumulation, duration-based holding is
unreliable, and `AccumulatePass`'s default `autoReset` actively corrupts accumulation when
combined with the video-light player — all three must be respected or a "higher-sample"
re-render can silently come out *worse* than the original).
