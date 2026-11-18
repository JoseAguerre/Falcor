"""Mogwai-side driver for the equal-quality ladder.

Two modes, selected by RB_MODE:
  reference  accumulate RB_REF_FRAMES frames with the Random sampler at RB_REF_SPP and capture the
             converged image, which every ladder point of that scene is then compared against.
  ladder     for each light-sample count in RB_LSPV, render RB_FRAMES unaccumulated frames at
             RB_SPP samples per pixel and capture the last one. Per-frame times go to RB_TIMES via
             Mogwai's own timing capture; the driver segments that file by block afterwards.

The sampler is fixed for the whole process and only the light-sample count changes between blocks,
so no sampling structure is rebuilt mid-run.
"""
from falcor import *
import os

MODE = os.environ.get('RB_MODE', 'ladder')
SAMPLER = os.environ.get('RB_SAMPLER', 'Cdf2D')
LEAF = int(os.environ.get('RB_LEAF', '0'))
SPP = int(os.environ.get('RB_SPP', '4'))
LSPVS = [int(x) for x in os.environ.get('RB_LSPV', '4').split(',')]
FRAMES = int(os.environ.get('RB_FRAMES', '60'))
OUT = os.environ.get('RB_OUT', '.')
NAME = os.environ.get('RB_NAME', 'img')
TIMES = os.environ.get('RB_TIMES', '')
REF_FRAMES = int(os.environ.get('RB_REF_FRAMES', '1500'))
REF_SPP = int(os.environ.get('RB_REF_SPP', '1'))
REF_LSPV = int(os.environ.get('RB_REF_LSPV', '64'))
WIDTH = int(os.environ.get('RB_WIDTH', '1920'))
HEIGHT = int(os.environ.get('RB_HEIGHT', '1080'))

# Direct illumination only, as in the paper's equal-quality test: with indirect bounces enabled the
# residual path-tracing noise does not fall with the light-sample count, so it masks exactly the
# error this study measures and makes the equal-quality crossing ill-conditioned.
MAX_DIFFUSE, MAX_SPECULAR, MAX_TRANSMISSION = 0, 0, 0
SAMPLE_GENERATOR = 3  # Weyl QMC

os.makedirs(OUT, exist_ok=True)
is_ref = (MODE == 'reference')
spp = REF_SPP if is_ref else SPP


def render_graph():
    g = RenderGraph("Ladder")
    pt = createPass("PathTracer", {
        'samplesPerPixel': spp,
        'maxSurfaceBounces': max(MAX_DIFFUSE, MAX_SPECULAR, MAX_TRANSMISSION),
        'maxDiffuseBounces': MAX_DIFFUSE,
        'maxSpecularBounces': MAX_SPECULAR,
        'maxTransmissionBounces': MAX_TRANSMISSION,
        'sampleGenerator': SAMPLE_GENERATOR,
        'useRussianRoulette': False,
    })
    g.addPass(pt, "PathTracer")
    # Pixel centres, not a jittered pattern: otherwise every frame differs from the accumulated
    # reference by an anti-aliasing term that does not shrink with the light-sample count, and
    # that term would dominate the error this study measures.
    vb = createPass("VBufferRT", {'samplePattern': 'Center', 'sampleCount': 1, 'useAlphaTest': True})
    g.addPass(vb, "VBufferRT")
    tm = createPass("ToneMapper", {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(tm, "ToneMapper")
    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW", "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec", "PathTracer.mvec")
    if is_ref:
        acc = createPass("AccumulatePass", {'enabled': True, 'precisionMode': 'Single'})
        g.addPass(acc, "AccumulatePass")
        g.addEdge("PathTracer.color", "AccumulatePass.input")
        g.addEdge("AccumulatePass.output", "ToneMapper.src")
    else:
        g.addEdge("PathTracer.color", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")
    return g


try:
    m.addGraph(render_graph())
    m.resizeFrameBuffer(WIDTH, HEIGHT)
except NameError:
    None

total = REF_FRAMES if is_ref else FRAMES * len(LSPVS)
m.clock.exitFrame = total + 3
m.frameCapture.outputDir = OUT
m.frameCapture.baseFilename = NAME
# Reference: only the final converged frame. Ladder: the last frame of each block.
m.frameCapture.addFrames(m.activeGraph, [REF_FRAMES] if is_ref else
                         [(i + 1) * FRAMES for i in range(len(LSPVS))])
if TIMES:
    m.timingCapture.captureFrameTime(TIMES)

_state = {'n': 0, 'init': False}


def _on_scene_update(scene, current_time):
    if scene is None:
        return
    if not _state['init']:
        scene.animated = False
        # Phone carries a constant environment map as well as the quad light. Its lighting is not
        # controlled by the light-sample count, so its noise would not fall along the ladder and
        # would mask the error this study measures. Leave the quad light as the only source, which
        # is what the other two scenes already do.
        rs = scene.renderSettings
        rs.useEnvLight = False
        rs.useAnalyticLights = False
        rs.useEmissiveLights = False
        rs.useQuadLight = True
        scene.renderSettings = rs
        scene.quadLight.samplerType = getattr(QuadLightSamplerType,
                                              'Random' if is_ref else SAMPLER)
        if LEAF > 0:
            scene.quadLight.budgetLeafAliasLeafBudget = LEAF
        scene.quadLight.lightSamplesPerVertex = (REF_LSPV if is_ref else LSPVS[0])
        _state['init'] = True
    elif not is_ref:
        # Switch to the next light-sample count exactly on a block boundary.
        blk = _state['n'] // FRAMES
        if blk < len(LSPVS) and _state['n'] % FRAMES == 0:
            scene.quadLight.lightSamplesPerVertex = LSPVS[blk]
    _state['n'] += 1


m.sceneUpdateCallback = _on_scene_update
