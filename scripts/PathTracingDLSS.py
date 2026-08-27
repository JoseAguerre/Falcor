from falcor import *

# Regular path tracing (same graph as scripts/PathTracer.py) with DLSS added on top for
# temporal accumulation/upscaling - no NRD, no GBufferRT, no ModulateIllumination.
# DLSS needs three inputs: color (fed from AccumulatePass.output, so it upscales/stabilizes the
# same image AccumulatePass already produced), depth and motion vectors (both already available
# as optional VBufferRT outputs - "depth" isn't wired into anything in the plain PathTracer.py
# graph, so it's normally never computed; wiring it to DLSS here makes VBufferRT produce it).

def render_graph_PathTracingDLSS():
    g = RenderGraph("PathTracingDLSS")
    PathTracer = createPass("PathTracer", {'samplesPerPixel': 1})
    g.addPass(PathTracer, "PathTracer")
    VBufferRT = createPass("VBufferRT", {'samplePattern': 'Stratified', 'sampleCount': 16, 'useAlphaTest': True})
    g.addPass(VBufferRT, "VBufferRT")
    AccumulatePass = createPass("AccumulatePass", {'enabled': True, 'precisionMode': 'Single'})
    g.addPass(AccumulatePass, "AccumulatePass")
    DLSS = createPass("DLSSPass", {'enabled': True, 'profile': 'Balanced', 'motionVectorScale': 'Relative', 'isHDR': True, 'sharpness': 0.0, 'exposure': 0.0})
    g.addPass(DLSS, "DLSS")
    ToneMapper = createPass("ToneMapper", {'autoExposure': False, 'exposureCompensation': 0.0})
    g.addPass(ToneMapper, "ToneMapper")

    g.addEdge("VBufferRT.vbuffer", "PathTracer.vbuffer")
    g.addEdge("VBufferRT.viewW", "PathTracer.viewW")
    g.addEdge("VBufferRT.mvec", "PathTracer.mvec")
    g.addEdge("PathTracer.color", "AccumulatePass.input")

    g.addEdge("AccumulatePass.output", "DLSS.color")
    g.addEdge("VBufferRT.depth", "DLSS.depth")
    g.addEdge("VBufferRT.mvec", "DLSS.mvec")

    g.addEdge("DLSS.output", "ToneMapper.src")
    g.markOutput("ToneMapper.dst")
    return g

PathTracingDLSS = render_graph_PathTracingDLSS()
try: m.addGraph(PathTracingDLSS)
except NameError: None
