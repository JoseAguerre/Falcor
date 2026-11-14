#pragma once
#include "Falcor.h"
#include "RenderGraph/RenderPass.h"
#include "Core/API/GpuTimer.h"
#include "Core/Pass/ComputePass.h"
#include "Rendering/Lights/QuadLightSampler.h"
#include <memory>
#include <string>
#include <vector>

using namespace Falcor;

/** TOG major revision: isolated GPU timing, configured through environment variables.

    BENCH_MODE=sampler  Times QuadLightSampler::sample() alone, without any ray tracing.
    BENCH_MODE=chase    Pointer-chase latency over a buffer of BENCH_CHASE_BYTES, to locate the
                        GPU's real cache-hierarchy knees (the L1 sizing claim).
    BENCH_MODE=gpubuild Times GPU compute construction of a 2D CDF + guide tables, and of 8x8
                        block statistics, from the light's own texture (the GPU baselines).

    Results go to the JSON file in BENCH_RESULT_PATH, written once BENCH_FRAMES frames ran.
*/
class QuadLightSamplerBench : public RenderPass
{
public:
    FALCOR_PLUGIN_CLASS(QuadLightSamplerBench, "QuadLightSamplerBench", "TOG major revision: isolated sampler / cache / GPU-build timing.");

    static ref<QuadLightSamplerBench> create(ref<Device> pDevice, const Properties& props) { return make_ref<QuadLightSamplerBench>(pDevice, props); }

    QuadLightSamplerBench(ref<Device> pDevice, const Properties& props);

    virtual Properties getProperties() const override { return {}; }
    virtual RenderPassReflection reflect(const CompileData& compileData) override;
    virtual void execute(RenderContext* pRenderContext, const RenderData& renderData) override;
    virtual void setScene(RenderContext* pRenderContext, const ref<Scene>& pScene) override;

private:
    void executeSampler(RenderContext* pRenderContext, const RenderData& renderData);
    void executeChase(RenderContext* pRenderContext, const RenderData& renderData);
    void executeGpuBuild(RenderContext* pRenderContext, const RenderData& renderData);
    void recordAndMaybeWrite(RenderContext* pRenderContext, const std::string& extra);

    std::string mMode;
    std::string mResultPath;
    uint32_t mFrames = 200;
    uint32_t mWarmup = 40;
    uint32_t mFrameIndex = 0;
    bool mWritten = false;

    ref<Scene> mpScene;
    std::unique_ptr<QuadLightSampler> mpSampler;
    ref<ComputePass> mpSamplerPass;
    uint32_t mDispatchDim = 1024;
    uint32_t mSamplesPerThread = 8;

    ref<ComputePass> mpChasePass;
    ref<Buffer> mpChaseBuffer;
    uint64_t mChaseBytes = 1 << 20;
    uint32_t mChaseHops = 128;

    ref<ComputePass> mpRowPass;
    ref<ComputePass> mpMarginalPass;
    ref<ComputePass> mpBlockPass;
    ref<Buffer> mpConditional;
    ref<Buffer> mpGuide;
    ref<Buffer> mpRowTotals;
    ref<Buffer> mpMarginal;
    ref<Buffer> mpBlockStats;
    ref<GpuTimer> mpTimerA;
    ref<GpuTimer> mpTimerB;
    ref<GpuTimer> mpTimerC;
    std::vector<double> mSamplesA;
    std::vector<double> mSamplesB;
    std::vector<double> mSamplesC;
};
