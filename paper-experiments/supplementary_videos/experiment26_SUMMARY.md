# Experiment 26: re-doing experiment9b's videos - genuinely higher-sample references, plus
# new camera flythrough videos

Two deliverables, both extending experiment9b (not modifying it): (1) regenerate the 5
scenes' reference videos with a REAL sample-count increase (9b's reference was noisier than
intended - see the bug below), same output length as 9b; (2) new camera flythrough videos -
our technique only, denoiser on, camera orbiting/rising while each scene's own HDR video
plays back (looped a couple of times, per request), for the 4 scenes experiment8 found
denoising actually helps (not phonehand).

## Part 1: high-quality reference videos

### Real bug found: PathTracer's samplesPerPixel is hard-capped at 16

`Source/RenderPasses/PathTracer/Params.slang`: `kMaxSamplesPerPixel = 16`.
`PathTracer.cpp` silently CLAMPS any higher value, only logging a warning. This means
experiment9b's own reference (`BENCH_SPP=32`) was actually only ever rendering at 16 the
whole time. Confirmed by calibration: raising BENCH_SPP up to 65536 produced IDENTICAL
noise and IDENTICAL timing every time, all secretly clamped to 16.

### The fix, and three real bugs found while building it

Real convergence needs accumulating multiple independent PathTracer sub-frames per output
frame via `AccumulatePass`, while holding the light-video frame fixed for the group. Three
things had to be fixed, in order, each confirmed by a numerical std-deviation check on a
flat wall region (not just eyeballing):

1. **Time-based "hold" via a large `durationMs`, plus explicitly setting
   `m.clock.framerate`** (round 1): broke PathTracer's own progressive accumulation
   entirely - a 64-subframe accumulation test showed ZERO noise reduction vs. a single
   frame. Root cause: setting `m.clock.framerate` switches Falcor's clock into
   "isSimulatingFps" mode, which for reasons not fully traced (kept as a documented "don't
   do this" rather than an engine fix, per the no-recompile constraint) breaks something in
   the render loop's accumulation path.
2. **Not setting framerate at all** (default, real-time mode) fixed accumulation on a
   STATIC (non-video) test scene (~2x reduction at K=64) - but current_time in this mode is
   REAL WALL-CLOCK TIME (confirmed via debug logging: ~1.4s/tick deltas matching actual
   render cost, not a fixed nominal step), making duration-based "hold for K ticks" gating
   fundamentally unreliable once real render time varies. Fixed by authoring the playlist
   to repeat each real content frame K times directly in the DATA (durationMs=1 each, same
   "advance once per tick" convention as the original playlists) - holding becomes purely
   positional, independent of clock mode or real time entirely.
3. **`AccumulatePass`'s default `autoReset=True`** resets accumulation on any scene-update
   flag (other than camera properties) every execute() call - and
   `QuadLightVideoPlayer::updateVideoPlayback` sets a texture-changed flag on every sequence
   advance, even between repeated/identical entries. Left at default, this actively made
   accumulation WORSE than a single sample (confirmed: K=8 on the real video scene showed
   HIGHER std than K=1, not lower) - not just ineffective, actively corrupting. Fixed with
   `'autoReset': False` on the AccumulatePass, driving resets entirely from this script's own
   frame-counted `Graph.getPass("AccumulatePass").reset()` calls at group boundaries.

Final config: LSPV=256 (4x experiment9b's 64) + ACCUM_K=8 accumulated sub-frames (128
effective samples/pixel vs. the ~16 experiment9b actually achieved). Validated as a real,
non-corrupting improvement on both an easy scene (rover, modest but real reduction - most of
its noise was already handled by the higher LSPV) and the hardest one (convergence, glass/
mirror materials resist convergence more, smaller relative improvement but still real and
positive, not negative).

### Render results

All 5 scenes completed: rover (14:58), cinema (20:50), fireplace_room (30:24), convergence
(1:13:12). phonehand's render failed twice in a row partway through this run - **the GPU
crashed** (`nvidia-smi`: "GPU is lost. Reboot the system to recover this GPU"), most likely
from the cumulative ~2.5 hours of continuous heavy rendering. This is a system/driver-level
fault (confirmed happening at Mogwai/CUDA init, before any of this experiment's script logic
runs), not a script bug - so no fix was attempted automatically; reported to you and waited.
Once you rebooted, `nvidia-smi` showed the GPU healthy again and phonehand's HQ reference
completed cleanly on the next attempt (9:13).

Disk usage after part 1: 586MB (well under the 10GB budget).

## Part 2: camera flythrough videos

Camera does a smooth orbit-and-rise around each scene's own EXISTING camera target (read
from the scene at runtime, not hardcoded) - one full sweep-and-return cycle (sine-based)
spread across the whole flythrough, not one cycle per loop. Per your request, each scene's
flythrough covers its own FULL native frame count, looped 2 times (`$LoopCount` in
run_flythrough.ps1) - `QuadLightVideoPlayer` loops its playlist natively (confirmed by
reading `QuadLightVideo.cpp`: `index = sequence % playlist.size()`), so this needs no
special playlist authoring, just requesting `NativeFrames*LoopCount` total frames.

### Amplitude calibration (pilot-tested before committing to a full run)

An initial guess (35 deg azimuthal sweep, 40% height rise) revealed Rover's LED-wall
panel's edges - a real, scene-specific limitation (it's a finite virtual-production panel,
not an infinite backdrop), not a bug: the shot is deliberately close/zoomed-in, so even a
moderate angular change sweeps across a large visual arc. Reduced to 8 deg sweep / 12% rise
and re-validated clean on rover (worst case - tight framing), convergence (enclosed room),
and phonehand (close-up) - all three pilots showed sensible, well-composed motion with no
clipping.

phonehand is excluded from the flythrough+denoise set, same as experiment9b's own denoised
videos - experiment8 found denoising hurts phonehand specifically.

### Status

All 4 scenes completed after the GPU came back: rover (2:39, 596 frames), cinema (1:45, 498
frames), fireplace_room (3:49, 596 frames), convergence (8:11, 1270 frames) - 16:24 total,
2,960 raw frames across the 4 scenes at 2 loops each. Visually spot-checked the convergence
flythrough (the trickiest scene - longest, most reflective/refractive materials) by
extracting frames 0/150/400/700 from the final encoded mp4: frame 0 matches the scene's
original composed angle exactly (confirms the base-pose read is correct), frames 150/400/700
show a smooth, natural azimuthal swing with the HDR light video's own color/intensity
changes playing through underneath, no clipping into geometry, no denoiser fireflies or
ghosting artifacts.

Final disk usage (parts 1+2 combined): **760MB**, well under the 10GB budget.

## Files
- `gen_playlists.py` - copy of experiment9b's playlist generator, output dir changed to
  this experiment's own `playlists/` folder (same full-length, non-repeated playlists).
- `gen_playlists_hq.py` - generates the repeated-frame (K copies each) playlists the HQ
  reference needs; usage: `python gen_playlists_hq.py <accum_k>`.
- `_bench_video_hq.py` - the HQ reference render script (PathTracer/VBufferRT/
  AccumulatePass/ToneMapper, samplesPerPixel=16 fixed, manual per-group reset).
- `_bench_flythrough.py` - the camera flythrough render script (PathTracer/VBufferRT/
  OptixDenoiser/ToneMapper, denoise graph identical to experiment9b's "denoised" variant,
  plus the orbit-and-rise camera animation).
- `run_reference_hq.ps1` - driver for part 1 (`-OnlyScene <name>` to run just one scene).
- `run_flythrough.ps1` - driver for part 2 (`-OnlyScene <name>` to run just one scene).
- `_make_pilot_scene.py` - small helper used throughout calibration to build a temp sibling
  .pyscene pointing at a specific playlist/texture (same technique every quadlight
  experiment in this project uses - never touches the original scene files).
- `videos/` - output videos (`<scene>_reference_hq.{mp4,webm}`,
  `<scene>_flythrough_denoised.{mp4,webm}` once rendered).
- `playlists/` - generated `.hdrplaylist` files (both the plain full-length ones and the
  K-repeated HQ variants), absolute paths, never touching `quadlight/`.

No existing scene file, engine source, or experiment9b output was modified.
