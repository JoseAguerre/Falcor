from falcor import *
import os

# Full-length video renderer using Falcor's NATIVE QuadLightVideoPlayer (.hdrplaylist)
# instead of the old approach (one Mogwai process relaunch per output frame, with a
# fresh temp .pyscene pointing at each individual frame_NNNNN.hdr in turn - fine for a
# short 48-frame clip but far too slow for a full ~300-1200 frame video: ~10s/frame in
# process-startup overhead alone, i.e. hours per scene). The playlist file (each entry
# duration=1ms, so it always advances exactly once per rendered frame regardless of
# m.clock.framerate) lets the engine's own background-thread prefetcher cycle through
# the ENTIRE video within a single continuous process - confirmed empirically
# (results/experiment9b/'s pilot: 300 frames in ~27s wall time vs. ~53 minutes the old
# way) - about two orders of magnitude faster, which is what makes rendering the full
# official playlists (not just a 48-frame window) tractable overnight.
#
# Three variants, selected by BENCH_VARIANT:
#   'ours'      - the scene's official calibrated real-time technique, one unaccumulated
#                 frame per video frame (matches every "real-time budget" convention
#                 elsewhere in this project).
#   'reference' - Random sampler, high spp, one frame per video frame - no temporal
#                 accumulation across sub-frames (unlike the old experiment9, which
#                 accumulated N sub-frames per output frame): the light-video advances
#                 once per rendered frame regardless, so accumulating several sub-frames
#                 of "the same" moment isn't available without desyncing the two clocks -
#                 a higher spp alone is used instead as the practical stand-in for extra
#                 quality, simpler and correctly synced to the evolving video.
#   'denoised'  - same graph as results/experiment8/_bench_denoise.py (PathTracer with
#                 albedo/guideNormal + VBufferRT.mvec -> OptixDenoiser -> ToneMapper, no
#                 AccumulatePass), but run CONTINUOUSLY across the real evolving video
#                 rather than experiment8's static-frame-repeat trick - this is actually
#                 closer to the denoiser's intended real use case (genuine per-frame
#                 temporal accumulation via mvec across an actually-changing sequence),
#                 not a workaround.
#
# Env vars: BENCH_VARIANT, BENCH_SAMPLER, BENCH_SPP, BENCH_LSPV, BENCH_LEAF_BUDGET,
# BENCH_TOTAL_FRAMES (playlist length), BENCH_FPS, BENCH_OUT_DIR, BENCH_OUT_NAME,
# BENCH_WARMUP_FRAMES (denoised only - frames to let temporal history build before the
# first captured frame).

VARIANT = os.environ.get('BENCH_VARIANT', 'ours')
SAMPLER_NAME = os.environ.get('BENCH_SAMPLER', 'Random')
SPP = int(os.environ.get('BENCH_SPP', '4'))
LSPV = int(os.environ.get('BENCH_LSPV', '8'))
LEAF_BUDGET = int(os.environ.get('BENCH_LEAF_BUDGET', '0'))
TOTAL_FRAMES = int(os.environ.get('BENCH_TOTAL_FRAMES', '300'))
FPS = int(os.environ.get('BENCH_FPS', '24'))
OUT_DIR = os.environ.get('BENCH_OUT_DIR', '.')
OUT_NAME = os.environ.get('BENCH_OUT_NAME', 'video')
WARMUP_FRAMES = int(os.environ.get('BENCH_WARMUP_FRAMES', '4'))

MAX_DIFFUSE_BOUNCES = 2
MAX_SPECULAR_BOUNCES = 5
MAX_TRANSMISSION_BOUNCES = 5
MAX_SURFACE_BOUNCES = max(MAX_DIFFUSE_BOUNCES, MAX_SPECULAR_BOUNCES, MAX_TRANSMISSION_BOUNCES)
SAMPLE_GENERATOR = 3  # Weyl QMC, same convention as every other benchmark in this project

os.makedirs(OUT_DIR, exist_ok=True)


def render_graph_plain():
    g = RenderGraph("Video")
    pt = createPass("PathTracer", {
        'samplesPerPixel': SPP,
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
    tm = createPass("ToneMapper", {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(tm, "ToneMapper")
    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW", "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec", "PathTracer.mvec")
    g.addEdge("PathTracer.color", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")
    return g


def render_graph_denoise():
    g = RenderGraph("VideoDenoise")
    pt = createPass("PathTracer", {
        'samplesPerPixel': SPP,
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
    od = createPass("OptixDenoiser", {'model': 'HDR'})
    g.addPass(od, "OptixDenoiser")
    tm = createPass("ToneMapper", {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(tm, "ToneMapper")
    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW", "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec", "PathTracer.mvec")
    g.addEdge("PathTracer.color", "OptixDenoiser.color")
    g.addEdge("PathTracer.albedo", "OptixDenoiser.albedo")
    g.addEdge("PathTracer.guideNormal", "OptixDenoiser.normal")
    g.addEdge("VBufferRT.mvec", "OptixDenoiser.mvec")
    g.addEdge("OptixDenoiser.output", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")
    return g


if VARIANT == 'denoised':
    Graph = render_graph_denoise()
    firstCapture = WARMUP_FRAMES + 1
else:
    Graph = render_graph_plain()
    firstCapture = 1

try: m.addGraph(Graph)
except NameError: None

m.clock.exitFrame = TOTAL_FRAMES + 2
m.frameCapture.outputDir = OUT_DIR
m.frameCapture.baseFilename = OUT_NAME
m.frameCapture.addFrames(m.activeGraph, list(range(firstCapture, TOTAL_FRAMES + 1)))

_state = {'configured': False}


def _on_scene_update(scene, current_time):
    if scene is None:
        return
    if not _state['configured']:
        scene.animated = False
        scene.quadLight.samplerType = getattr(QuadLightSamplerType, SAMPLER_NAME)
        scene.quadLight.lightSamplesPerVertex = LSPV
        if SAMPLER_NAME == 'BudgetLeafAlias' and LEAF_BUDGET > 0:
            scene.quadLight.budgetLeafAliasLeafBudget = LEAF_BUDGET
        m.clock.framerate = FPS
        _state['configured'] = True


m.sceneUpdateCallback = _on_scene_update
