from falcor import *
import os

# Experiment 26: a GENUINELY higher-sample reference video. Two real bugs found and fixed
# while building this (see SUMMARY.md for the full "round 1 dead end" narrative):
#
# 1. Falcor's PathTracer hard-caps samplesPerPixel at 16 internally
#    (Source/RenderPasses/PathTracer/Params.slang: kMaxSamplesPerPixel=16; PathTracer.cpp
#    silently CLAMPS anything above that, only logging a warning). experiment9b's own
#    "reference" (BENCH_SPP=32) was actually only ever rendering at 16 the whole time,
#    silently - and naively raising BENCH_SPP further (tried up to 65536 while calibrating
#    this experiment) does NOTHING: identical noise, identical timing, every time.
#
# 2. The fix requires accumulating multiple independent PathTracer sub-frames per output
#    video frame via AccumulatePass, while holding the QuadLightVideoPlayer's current frame
#    fixed across the group - via a playlist where each real content frame is repeated
#    ACCUM_K times (durationMs=1 each, gen_playlists_hq.py). An EARLIER attempt used a
#    single large durationMs per real frame instead (time-based holding) PLUS explicitly
#    setting m.clock.framerate to get deterministic timing - but setting framerate switches
#    the clock into "isSimulatingFps" mode, which was empirically found to silently break
#    PathTracer's own progressive accumulation entirely (a 64-subframe test showed ZERO
#    noise reduction with framerate set, vs. a real ~2x reduction with it left at the
#    engine's own default/non-simulating mode). So m.clock.framerate must NOT be set here -
#    the repeated-frame playlist makes holding purely positional (durationMs=1 always
#    advances exactly one playlist position per tick, regardless of real elapsed time),
#    sidestepping the timing issue entirely rather than fighting it.
#
# AccumulatePass.reset() (Python-exposed: AccumulatePass.cpp's regAccumulatePass) is called
# at the start of each group so accumulation doesn't blend across different light content -
# tracked via this script's own frame counter, not the engine's scene-change auto-reset
# (left at its default; verified harmless once framerate is no longer being set).
#
# Effective samples per output frame = 16 (PathTracer's own max) * ACCUM_K. Only the LAST
# sub-frame of each group (the fully-accumulated one) is captured as that group's output
# video frame.
#
# Env vars: BENCH_LSPV, BENCH_ACCUM_K (sub-frames per output frame - must match the repeat
# count baked into the playlist passed via -S), BENCH_OUTPUT_FRAMES (number of distinct
# output video frames - matches each scene's official frame count, same as experiment9b),
# BENCH_OUT_DIR, BENCH_OUT_NAME. Sampler is always 'Random' (matches the reference
# convention everywhere else in this project) with high LSPV for direct-light quality;
# PathTracer itself is fixed at the engine's own max (16).

LSPV = int(os.environ.get('BENCH_LSPV', '256'))
ACCUM_K = int(os.environ.get('BENCH_ACCUM_K', '8'))
OUTPUT_FRAMES = int(os.environ.get('BENCH_OUTPUT_FRAMES', '300'))
OUT_DIR = os.environ.get('BENCH_OUT_DIR', '.')
OUT_NAME = os.environ.get('BENCH_OUT_NAME', 'video')

MAX_DIFFUSE_BOUNCES = 2
MAX_SPECULAR_BOUNCES = 5
MAX_TRANSMISSION_BOUNCES = 5
MAX_SURFACE_BOUNCES = max(MAX_DIFFUSE_BOUNCES, MAX_SPECULAR_BOUNCES, MAX_TRANSMISSION_BOUNCES)
SAMPLE_GENERATOR = 3  # Weyl QMC, same convention as every other benchmark in this project

os.makedirs(OUT_DIR, exist_ok=True)


def render_graph_hq():
    g = RenderGraph("VideoHQ")
    pt = createPass("PathTracer", {
        'samplesPerPixel': 16,  # the engine's own hard max - see module docstring
        'maxSurfaceBounces': MAX_SURFACE_BOUNCES,
        'maxDiffuseBounces': MAX_DIFFUSE_BOUNCES,
        'maxSpecularBounces': MAX_SPECULAR_BOUNCES,
        'maxTransmissionBounces': MAX_TRANSMISSION_BOUNCES,
        'sampleGenerator': SAMPLE_GENERATOR,
        'useRussianRoulette': False,
    })
    g.addPass(pt, "PathTracer")
    vb = createPass("VBufferRT", {'samplePattern': 'Stratified', 'sampleCount': 16, 'useAlphaTest': True})
    g.addPass(vb, "VBufferRT")
    # autoReset=False: AccumulatePass defaults to autoReset=True, which resets accumulation
    # on ANY scene update flag (other than camera properties) every execute() call - and
    # QuadLightVideoPlayer's mSequence advances (via updateVideoPlayback -> mTextureChanged)
    # even between REPEATED/identical playlist entries (advancing sequence position is not
    # the same as changing visible content, but still sets the changed flag). Left at
    # default this wipes accumulation every tick. Reset is instead driven entirely by this
    # script's own explicit Graph.getPass("AccumulatePass").reset() calls below.
    ap = createPass("AccumulatePass", {'enabled': True, 'precisionMode': 'Single', 'autoReset': False})
    g.addPass(ap, "AccumulatePass")
    tm = createPass("ToneMapper", {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(tm, "ToneMapper")
    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW", "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec", "PathTracer.mvec")
    g.addEdge("PathTracer.color", "AccumulatePass.input")
    g.addEdge("AccumulatePass.output", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")
    return g


Graph = render_graph_hq()
try: m.addGraph(Graph)
except NameError: None

TOTAL_RAW_FRAMES = OUTPUT_FRAMES * ACCUM_K
m.clock.exitFrame = TOTAL_RAW_FRAMES + 2
m.frameCapture.outputDir = OUT_DIR
m.frameCapture.baseFilename = OUT_NAME
# Capture only the LAST sub-frame of each group (fully accumulated).
capture_frames = [k * ACCUM_K for k in range(1, OUTPUT_FRAMES + 1)]
m.frameCapture.addFrames(m.activeGraph, capture_frames)

_state = {'configured': False, 'frame_count': 0}


def _on_scene_update(scene, current_time):
    if scene is None:
        return
    if not _state['configured']:
        scene.animated = False
        scene.quadLight.samplerType = QuadLightSamplerType.Random
        scene.quadLight.lightSamplesPerVertex = LSPV
        # Deliberately NOT setting m.clock.framerate - see module docstring point 2.
        _state['configured'] = True
    _state['frame_count'] += 1
    if (_state['frame_count'] - 1) % ACCUM_K == 0:
        Graph.getPass("AccumulatePass").reset()


m.sceneUpdateCallback = _on_scene_update
