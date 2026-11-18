from falcor import *
import os

# Mogwai-side driver for QuadLightSamplerBench. The pass reads its own configuration from the
# BENCH_* environment variables in its constructor, so this script only has to build a graph that
# contains it and keep the frame loop alive long enough for the pass to write its JSON.

FRAMES = int(os.environ.get('BENCH_FRAMES', '200'))


def render_graph_bench():
    g = RenderGraph("SamplerBench")
    g.addPass(createPass("QuadLightSamplerBench"), "Bench")
    g.markOutput("Bench.dst")
    return g


try:
    m.addGraph(render_graph_bench())
except NameError:
    None

# The pass writes its result on the first frame with index >= BENCH_FRAMES, so give it a margin.
m.clock.exitFrame = FRAMES + 8

_state = {'configured': False}


def _on_scene_update(scene, current_time):
    if scene is None or _state['configured']:
        return
    scene.animated = False
    _state['configured'] = True


m.sceneUpdateCallback = _on_scene_update
