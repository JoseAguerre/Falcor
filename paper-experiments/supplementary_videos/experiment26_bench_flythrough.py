from falcor import *
import os
import math

# Experiment 26: camera flythrough videos - our technique only, denoiser on, while the
# scene's own HDR light video plays back. Camera motion is a smooth orbit-and-rise around
# each scene's OWN existing camera target (read from the scene at runtime, not hardcoded -
# works for all 5 scenes without per-scene tuning): an azimuthal back-and-forth swing
# (+/-SWEEP_DEG around the scene's original viewing angle, one full cycle over the clip) plus
# a gentle rise-and-fall in height (+RISE_FRAC of the original height at the midpoint), at
# the SAME distance from the target the original camera used - conservative by construction
# (the original angle is a known-safe, already-composed shot; a moderate swing/rise around it
# stays close to that same known-safe region rather than risking a full 360 orbit clipping
# into geometry the shot was never composed to show).
#
# TOTAL_FRAMES (the flythrough's own chosen length) is independent of the scene's native HDR
# video length - QuadLightVideoPlayer loops its playlist natively (index = sequence %
# playlist.size(), confirmed by reading Source/Falcor/Scene/Lights/QuadLightVideo.cpp), so a
# flythrough longer than the native video just loops it automatically; no special playlist
# authoring needed for that (unlike experiment26's reference renderer, this script reuses the
# scene's UNMODIFIED playlist - each real frame appears once, normal per-tick advance).
#
# Denoiser graph is identical to experiment9b's own "denoised" variant (PathTracer with
# albedo/guideNormal + VBufferRT.mvec -> OptixDenoiser -> ToneMapper) - same warmup-frames
# convention for temporal history to build before the first captured frame.
#
# Env vars: BENCH_SAMPLER, BENCH_SPP, BENCH_LSPV, BENCH_LEAF_BUDGET (the scene's own
# calibrated "ours" config, same values run_videos.ps1/run_reference_hq.ps1 use),
# BENCH_TOTAL_FRAMES, BENCH_WARMUP_FRAMES, BENCH_SWEEP_DEG, BENCH_RISE_FRAC, BENCH_OUT_DIR,
# BENCH_OUT_NAME.

SAMPLER_NAME = os.environ.get('BENCH_SAMPLER', 'AliasCtu')
SPP = int(os.environ.get('BENCH_SPP', '4'))
LSPV = int(os.environ.get('BENCH_LSPV', '8'))
LEAF_BUDGET = int(os.environ.get('BENCH_LEAF_BUDGET', '0'))
TOTAL_FRAMES = int(os.environ.get('BENCH_TOTAL_FRAMES', '480'))
WARMUP_FRAMES = int(os.environ.get('BENCH_WARMUP_FRAMES', '4'))
SWEEP_DEG = float(os.environ.get('BENCH_SWEEP_DEG', '35'))
RISE_FRAC = float(os.environ.get('BENCH_RISE_FRAC', '0.4'))
OUT_DIR = os.environ.get('BENCH_OUT_DIR', '.')
OUT_NAME = os.environ.get('BENCH_OUT_NAME', 'flythrough')

MAX_DIFFUSE_BOUNCES = 2
MAX_SPECULAR_BOUNCES = 5
MAX_TRANSMISSION_BOUNCES = 5
MAX_SURFACE_BOUNCES = max(MAX_DIFFUSE_BOUNCES, MAX_SPECULAR_BOUNCES, MAX_TRANSMISSION_BOUNCES)
SAMPLE_GENERATOR = 3

os.makedirs(OUT_DIR, exist_ok=True)


def render_graph_denoise():
    g = RenderGraph("Flythrough")
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


Graph = render_graph_denoise()
try: m.addGraph(Graph)
except NameError: None

m.clock.exitFrame = TOTAL_FRAMES + 2
m.frameCapture.outputDir = OUT_DIR
m.frameCapture.baseFilename = OUT_NAME
firstCapture = WARMUP_FRAMES + 1
m.frameCapture.addFrames(m.activeGraph, list(range(firstCapture, TOTAL_FRAMES + 1)))

_state = {'configured': False, 'frame_count': 0, 'base_pos': None, 'base_target': None}


def _on_scene_update(scene, current_time):
    if scene is None:
        return
    if not _state['configured']:
        scene.animated = False
        scene.quadLight.samplerType = getattr(QuadLightSamplerType, SAMPLER_NAME)
        scene.quadLight.lightSamplesPerVertex = LSPV
        if SAMPLER_NAME == 'BudgetLeafAlias' and LEAF_BUDGET > 0:
            scene.quadLight.budgetLeafAliasLeafBudget = LEAF_BUDGET
        cam = scene.camera
        _state['base_pos'] = float3(cam.position.x, cam.position.y, cam.position.z)
        _state['base_target'] = float3(cam.target.x, cam.target.y, cam.target.z)
        _state['configured'] = True

    _state['frame_count'] += 1
    t = (_state['frame_count'] - 1) / max(1, TOTAL_FRAMES - 1)

    pos0 = _state['base_pos']
    tgt0 = _state['base_target']
    off_x = pos0.x - tgt0.x
    off_y = pos0.y - tgt0.y
    off_z = pos0.z - tgt0.z
    radius_xz = math.sqrt(off_x * off_x + off_z * off_z)
    base_angle = math.atan2(off_z, off_x)

    azimuth_delta = math.radians(SWEEP_DEG) * math.sin(2 * math.pi * t)
    height_mult = 1.0 + RISE_FRAC * math.sin(math.pi * t)

    new_angle = base_angle + azimuth_delta
    new_x = tgt0.x + radius_xz * math.cos(new_angle)
    new_z = tgt0.z + radius_xz * math.sin(new_angle)
    new_y = tgt0.y + off_y * height_mult

    scene.camera.position = float3(new_x, new_y, new_z)
    scene.camera.target = tgt0


m.sceneUpdateCallback = _on_scene_update
