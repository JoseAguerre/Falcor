import os
import sys

# Experiment 26 (round 2 - see SUMMARY.md for round 1's dead end): authors a variant of each
# scene's .hdrplaylist where every REAL content frame is repeated ACCUM_K times consecutively
# (durationMs=1 per entry, same "advance exactly once per tick" convention experiment9b's own
# playlists already used and documented). Round 1 tried to hold each frame via a large
# durationMs (time-based gating) instead - but QuadLightVideoPlayer.tick()'s elapsed-time
# check uses the CLOCK's real current_time, and running headless in Falcor's default
# (non-"isSimulatingFps") clock mode means current_time is ACTUAL WALL-CLOCK TIME (confirmed
# via debug logging: per-tick deltas of ~1.4s, matching real per-frame render cost, wildly
# uneven - not a fixed nominal timestep) - duration-based holding is fundamentally unreliable
# there. Explicitly setting m.clock.framerate to force deterministic "isSimulatingFps" mode
# was tried too, but that broke PathTracer's own progressive accumulation entirely (confirmed
# empirically: a 64-subframe accumulation test showed ZERO noise reduction with framerate
# set, vs. a real ~2x reduction with it left at the engine default) - so framerate must NOT
# be set. Repeating frames in the playlist DATA itself sidesteps time entirely: durationMs=1
# guarantees advance-by-exactly-1-position per tick regardless of real elapsed time, so K
# consecutive identical entries reliably hold the same content for exactly K ticks.
#
# Usage: python gen_playlists_hq.py <accum_k>

QUADROOT = r"C:\Users\Jose\Desktop\Falcor\quadlight"
OUTDIR = r"C:\Users\Jose\Desktop\Falcor\results\experiment26\playlists"
os.makedirs(OUTDIR, exist_ok=True)

FAMILIES = {
    'phonehand': ('colors', 1199),
    'cinema': ('hdr', 251),
    'fireplace_room': (os.path.join('fireplace', '4k'), 300),
    'rover': ('road', 300),
    'convergence': ('cave', 637),
}

ACCUM_K = int(sys.argv[1])

for scene, (family, count) in FAMILIES.items():
    lines = ['#prefetch 12']
    for i in range(1, count + 1):
        path = os.path.join(QUADROOT, family, f'frame_{i:05d}.hdr')
        for _ in range(ACCUM_K):
            lines.append(f'{path} 1')
    outpath = os.path.join(OUTDIR, f'{scene}_full_hq_k{ACCUM_K}.hdrplaylist')
    with open(outpath, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'{scene}: {count} real frames x {ACCUM_K} repeats = {count * ACCUM_K} entries -> {outpath}')
