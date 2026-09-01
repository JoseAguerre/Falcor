from falcor import *

def render_graph_PathTracerOptix():
    g = RenderGraph("PathTracerOptix")
    PathTracer = createPass("PathTracer", {'samplesPerPixel': 1})
    g.addPass(PathTracer, "PathTracer")
    VBufferRT = createPass("VBufferRT", {'samplePattern': 'Stratified', 'sampleCount': 16, 'useAlphaTest': True})
    g.addPass(VBufferRT, "VBufferRT")
    OptixDenoiser = createPass("OptixDenoiser", {'model': 'HDR'})
    g.addPass(OptixDenoiser, "OptixDenoiser")
    ToneMapper = createPass("ToneMapper", {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(ToneMapper, "ToneMapper")

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

PathTracerOptix = render_graph_PathTracerOptix()
try: m.addGraph(PathTracerOptix)
except NameError: None
