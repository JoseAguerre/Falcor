# Experiment 9b: full-length videos (fixing the "5 second" problem)

**What was wrong before**: the earlier experiment 9/10 videos used a hardcoded 48-frame
window (2 seconds at 24fps) regardless of how long a scene's actual quadlight family
was, and rendered each frame via a full Mogwai process relaunch (~10.6s/frame in pure
process-startup overhead). Both problems are fixed here.

## The fix: Falcor's native QuadLightVideoPlayer

Falcor already has a complete, production-grade animated-quadlight system
(`Source/Falcor/Scene/Lights/QuadLightVideo.{h,cpp}`) driven by `.hdrplaylist` files -
a background-thread ring-buffer prefetcher that advances frames automatically based on
`m.clock`'s simulated time, with no per-frame Python intervention needed. This had never
been used anywhere in this project before (every prior quadlight-family experiment used
the "one Mogwai relaunch per frame, swap the texture path" trick, which only makes sense
for a handful of frames).

Custom `.hdrplaylist` files were generated (`results/experiment9b/playlists/`, absolute
frame paths, `durationMs=1` per entry so the player always advances exactly once per
rendered frame regardless of `m.clock.framerate`) covering each scene's **entire**
official quadlight family - not a 48-frame window. A temp sibling `.pyscene` (same
established technique as every other quadlight experiment - `QuadLight.createFromFile`
only works in a scene-building context) points at the playlist instead of a single
frame, and the whole video renders in ONE continuous Mogwai process.

**Measured speedup**: 300 frames (rover) in ~27s wall time (pilot test), vs. an
estimated ~53 minutes the old way - roughly **120x faster**. This is what makes
rendering the FULL playlists (up to 1199 frames) tractable in a single overnight run
rather than requiring hours per scene.

## Per-scene video lengths (24fps, matching each scene's official quadlight family)

| Scene | Frames | Duration |
|---|---|---|
| phonehand | 1199 | 49.96s |
| cinema | 251 | 10.46s |
| fireplace_room | 300 | 12.5s |
| rover | 300 | 12.5s |
| convergence | 637 | 26.5s |

## Variants

- **ours**: the scene's official calibrated real-time technique (spp/lspv/leafBudget
  from `results/realtime_budget.json`, read-only), one unaccumulated frame per video
  frame - matches every "real-time budget" convention elsewhere in this project.
- **reference**: Random sampler, spp=32, lspv=64, one frame per video frame. Simpler
  than the original experiment 9's multi-frame-accumulation reference: since the
  playlist advances once per render frame regardless, accumulating several sub-frames
  "of the same moment" would desync from the continuously-advancing light. A higher spp
  alone is the correctly-synced stand-in for extra quality.
- **denoised** (cinema, fireplace_room, rover, convergence only - matches experiment 8's
  finding that denoising hurts phonehand): same OptixDenoiser graph as
  `results/experiment8/_bench_denoise.py`, but run continuously across the real evolving
  video rather than experiment 8's static-frame-repeat trick - actually closer to the
  denoiser's intended real use case (genuine temporal accumulation via motion vectors
  across an actually-changing sequence, not a workaround for a static scene).

## A bug found and fixed

`m.clock.framerate = 24.0` (a Python float) throws `TypeError` - the binding only
accepts an int. Fixed by using `int(os.environ.get('BENCH_FPS', '24'))` instead of
`float(...)`. Caught immediately via a single-scene (rover) pilot before scaling to all
5 scenes, so no wasted render time.

## Disk usage

**2.9GB** total, all 28 files (14 mp4 + 14 webm across 5 scenes' ours+reference, plus 4
scenes' denoised). Convergence's videos are by far the largest (~1GB alone) - its
mirror/glass/glossy material grid produces much less compressible high-frequency detail
than the other scenes' simpler materials, both before and after denoising.

## Files

`results/experiment9b/videos/<scene>_{ours,reference,denoised}.{mp4,webm}` (28 files),
`results/experiment9b/run_videos.ps1` (driver), `results/experiment9b/_bench_video.py`
(the three render-graph variants), `results/experiment9b/playlists/` (generated
full-length `.hdrplaylist` files, absolute paths, not touching `quadlight/`).

No existing scene file or official result was modified.
