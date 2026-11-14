#include "QuadLightSamplerBench.h"
#include "Scene/Lights/QuadLight.h"
#include "Utils/Scripting/ScriptBindings.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <numeric>
#include <random>

extern "C" FALCOR_API_EXPORT void registerPlugin(Falcor::PluginRegistry& registry)
{
    registry.registerClass<RenderPass, QuadLightSamplerBench>();
}

namespace
{
    const char kShaderSampler[] = "RenderPasses/QuadLightSamplerBench/SamplerBench.cs.slang";
    const char kShaderChase[] = "RenderPasses/QuadLightSamplerBench/CacheChase.cs.slang";
    const char kShaderBuild[] = "RenderPasses/QuadLightSamplerBench/GpuBuild.cs.slang";

    std::string envOr(const char* name, const std::string& fallback)
    {
        const char* v = std::getenv(name);
        return v ? std::string(v) : fallback;
    }

    uint64_t envOr(const char* name, uint64_t fallback)
    {
        const char* v = std::getenv(name);
        return v ? std::strtoull(v, nullptr, 10) : fallback;
    }

    void summarize(const std::vector<double>& samples, std::ostream& out, const char* name)
    {
        if (samples.empty())
        {
            out << "\"" << name << "_median_ms\":null,\"" << name << "_mean_ms\":null";
            return;
        }
        std::vector<double> sorted = samples;
        std::sort(sorted.begin(), sorted.end());
        double mean = std::accumulate(sorted.begin(), sorted.end(), 0.0) / double(sorted.size());
        out << "\"" << name << "_median_ms\":" << sorted[sorted.size() / 2] << ",\"" << name << "_mean_ms\":" << mean << ",\"" << name
            << "_p05_ms\":" << sorted[sorted.size() / 20] << ",\"" << name << "_p95_ms\":" << sorted[sorted.size() * 19 / 20];
    }
}

QuadLightSamplerBench::QuadLightSamplerBench(ref<Device> pDevice, const Properties& props) : RenderPass(pDevice)
{
    mMode = envOr("BENCH_MODE", std::string("sampler"));
    mResultPath = envOr("BENCH_RESULT_PATH", std::string(""));
    mFrames = (uint32_t)envOr("BENCH_FRAMES", uint64_t(200));
    mWarmup = (uint32_t)envOr("BENCH_WARMUP", uint64_t(40));
    mDispatchDim = (uint32_t)envOr("BENCH_DISPATCH_DIM", uint64_t(1024));
    mSamplesPerThread = (uint32_t)envOr("BENCH_SAMPLES_PER_THREAD", uint64_t(8));
    mChaseBytes = envOr("BENCH_CHASE_BYTES", uint64_t(1) << 20);
    mChaseHops = (uint32_t)envOr("BENCH_CHASE_HOPS", uint64_t(128));
    mpTimerA = GpuTimer::create(mpDevice);
    mpTimerB = GpuTimer::create(mpDevice);
    mpTimerC = GpuTimer::create(mpDevice);
}

RenderPassReflection QuadLightSamplerBench::reflect(const CompileData& compileData)
{
    RenderPassReflection reflector;
    reflector.addOutput("dst", "Dummy output, keeps the pass alive in the graph.")
        .format(ResourceFormat::RGBA32Float)
        .bindFlags(ResourceBindFlags::UnorderedAccess | ResourceBindFlags::ShaderResource);
    return reflector;
}

void QuadLightSamplerBench::setScene(RenderContext* pRenderContext, const ref<Scene>& pScene)
{
    mpScene = pScene;
    mpSampler = nullptr;
    mpSamplerPass = nullptr;
}

void QuadLightSamplerBench::execute(RenderContext* pRenderContext, const RenderData& renderData)
{
    if (!mpScene) return;
    if (mMode == "sampler") executeSampler(pRenderContext, renderData);
    else if (mMode == "chase") executeChase(pRenderContext, renderData);
    else if (mMode == "gpubuild") executeGpuBuild(pRenderContext, renderData);
    else FALCOR_THROW("QuadLightSamplerBench: unknown BENCH_MODE '{}'.", mMode);
    mFrameIndex++;
}

void QuadLightSamplerBench::recordAndMaybeWrite(RenderContext* pRenderContext, const std::string& extra)
{
    if (mWritten || mFrameIndex < mFrames || mResultPath.empty()) return;
    std::ofstream out(mResultPath);
    out << "{\"mode\":\"" << mMode << "\",\"frames\":" << mFrames << ",\"warmup\":" << mWarmup << "," << extra << ",";
    summarize(mSamplesA, out, "a");
    out << ",";
    summarize(mSamplesB, out, "b");
    out << ",";
    summarize(mSamplesC, out, "c");
    out << "}\n";
    mWritten = true;
}

void QuadLightSamplerBench::executeSampler(RenderContext* pRenderContext, const RenderData& renderData)
{
    auto pLight = mpScene->getQuadLight();
    FALCOR_CHECK(pLight != nullptr, "QuadLightSamplerBench: the scene has no quad light.");

    if (!mpSampler)
    {
        const std::string name = envOr("BENCH_SAMPLER", std::string("BudgetLeafAlias"));
        const QuadLightSamplerType type = stringToEnum<QuadLightSamplerType>(name);
        const uint32_t budget = (uint32_t)envOr("BENCH_LEAF_BUDGET", uint64_t(0));
        if (budget > 0) pLight->setBudgetLeafAliasLeafBudget(budget);
        mpSampler = createQuadLightSampler(type, mpDevice, pLight);

        ProgramDesc desc;
        desc.addShaderModules(mpScene->getShaderModules());
        desc.addShaderLibrary(kShaderSampler).csEntry("main");
        desc.addTypeConformances(mpScene->getTypeConformances());
        DefineList defines = mpScene->getSceneDefines();
        defines.add(mpSampler->getDefines());
        mpSamplerPass = ComputePass::create(mpDevice, desc, defines, true);
    }

    auto pDst = renderData.getTexture("dst");
    auto var = mpSamplerPass->getRootVar();
    mpScene->bindShaderData(var["gScene"]);
    mpSampler->bindShaderData(var["gBench"]["sampler"]);
    var["gBench"]["samplesPerThread"] = mSamplesPerThread;
    var["gBench"]["seed"] = mFrameIndex;
    var["gBench"]["dim"] = mDispatchDim;
    var["gOutput"] = pDst;

    mpTimerA->begin();
    mpSamplerPass->execute(pRenderContext, mDispatchDim, mDispatchDim);
    pRenderContext->uavBarrier(pDst.get());
    mpTimerA->end();
    mpTimerA->resolve();
    pRenderContext->submit(true);
    double ms = mpTimerA->getElapsedTime();
    if (mFrameIndex >= mWarmup) mSamplesA.push_back(ms);

    const uint64_t total = uint64_t(mDispatchDim) * mDispatchDim * mSamplesPerThread;
    recordAndMaybeWrite(pRenderContext, fmt::format("\"samples_per_dispatch\":{},\"sampler\":\"{}\",\"leaf_budget\":{}", total, envOr("BENCH_SAMPLER", std::string("")), envOr("BENCH_LEAF_BUDGET", uint64_t(0))));
}

void QuadLightSamplerBench::executeChase(RenderContext* pRenderContext, const RenderData& renderData)
{
    if (!mpChasePass)
    {
        // Sattolo's algorithm over cache-line-sized slots gives one single cycle through the
        // whole buffer, so that no hop is predictable and every slot is on the path.
        const uint32_t kLineWords = 16; // 64 bytes.
        const uint32_t slots = std::max<uint32_t>(2, uint32_t(mChaseBytes / (kLineWords * 4)));
        std::vector<uint32_t> order(slots);
        std::iota(order.begin(), order.end(), 0u);
        std::mt19937 rng(1234u);
        for (uint32_t i = slots - 1; i > 0; --i)
        {
            std::uniform_int_distribution<uint32_t> dist(0, i - 1);
            std::swap(order[i], order[dist(rng)]);
        }
        std::vector<uint32_t> data(size_t(slots) * kLineWords, 0);
        for (uint32_t i = 0; i < slots; ++i)
            data[size_t(i) * kLineWords] = order[i] * kLineWords;
        mpChaseBuffer = mpDevice->createStructuredBuffer(sizeof(uint32_t), (uint32_t)data.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, data.data(), false);

        DefineList defines;
        mpChasePass = ComputePass::create(mpDevice, kShaderChase, "main", defines);
    }

    const uint32_t kLineWords = 16;
    const uint32_t slots = std::max<uint32_t>(2, uint32_t(mChaseBytes / (kLineWords * 4)));
    auto pDst = renderData.getTexture("dst");
    auto var = mpChasePass->getRootVar();
    var["gChase"]["next"] = mpChaseBuffer;
    var["gChase"]["slots"] = slots;
    var["gChase"]["lineWords"] = kLineWords;
    var["gChase"]["hops"] = mChaseHops;
    var["gChase"]["seed"] = mFrameIndex;
    var["gChase"]["dim"] = mDispatchDim;
    var["gOutput"] = pDst;

    mpTimerA->begin();
    mpChasePass->execute(pRenderContext, mDispatchDim, mDispatchDim);
    pRenderContext->uavBarrier(pDst.get());
    mpTimerA->end();
    mpTimerA->resolve();
    pRenderContext->submit(true);
    double ms = mpTimerA->getElapsedTime();
    if (mFrameIndex >= mWarmup) mSamplesA.push_back(ms);

    const uint64_t totalHops = uint64_t(mDispatchDim) * mDispatchDim * mChaseHops;
    recordAndMaybeWrite(pRenderContext, fmt::format("\"bytes\":{},\"total_hops\":{}", mChaseBytes, totalHops));
}

void QuadLightSamplerBench::executeGpuBuild(RenderContext* pRenderContext, const RenderData& renderData)
{
    auto pLight = mpScene->getQuadLight();
    FALCOR_CHECK(pLight != nullptr, "QuadLightSamplerBench: the scene has no quad light.");
    auto pTex = pLight->getTexture();
    const uint32_t w = pTex->getWidth(), h = pTex->getHeight();
    const auto rw = ResourceBindFlags::ShaderResource | ResourceBindFlags::UnorderedAccess;

    if (!mpRowPass)
    {
        mpConditional = mpDevice->createStructuredBuffer(sizeof(float), h * (w + 1), rw);
        mpGuide = mpDevice->createStructuredBuffer(sizeof(uint32_t), h * w, rw);
        mpRowTotals = mpDevice->createStructuredBuffer(sizeof(float), h, rw);
        mpMarginal = mpDevice->createStructuredBuffer(sizeof(float), h + 1, rw);
        mpBlockStats = mpDevice->createStructuredBuffer(sizeof(float) * 2, ((w + 7) / 8) * ((h + 7) / 8), rw);
        DefineList defines;
        mpRowPass = ComputePass::create(mpDevice, kShaderBuild, "rowPass", defines);
        mpMarginalPass = ComputePass::create(mpDevice, kShaderBuild, "marginalPass", defines);
        mpBlockPass = ComputePass::create(mpDevice, kShaderBuild, "blockPass", defines);
    }

    auto bind = [&](const ref<ComputePass>& pass)
    {
        auto var = pass->getRootVar();
        var["gBuild"]["source"] = pTex;
        var["gBuild"]["conditional"] = mpConditional;
        var["gBuild"]["guide"] = mpGuide;
        var["gBuild"]["rowTotals"] = mpRowTotals;
        var["gBuild"]["marginal"] = mpMarginal;
        var["gBuild"]["blockStats"] = mpBlockStats;
        var["gBuild"]["dim"] = uint2(w, h);
    };
    bind(mpRowPass);
    bind(mpMarginalPass);
    bind(mpBlockPass);

    mpTimerA->begin();
    mpRowPass->execute(pRenderContext, h, 1);
    pRenderContext->uavBarrier(mpRowTotals.get());
    pRenderContext->uavBarrier(mpConditional.get());
    pRenderContext->uavBarrier(mpGuide.get());
    mpTimerA->end();
    mpTimerB->begin();
    mpMarginalPass->execute(pRenderContext, 1, 1);
    pRenderContext->uavBarrier(mpMarginal.get());
    mpTimerB->end();
    mpTimerC->begin();
    mpBlockPass->execute(pRenderContext, (w + 7) / 8, (h + 7) / 8);
    pRenderContext->uavBarrier(mpBlockStats.get());
    mpTimerC->end();
    mpTimerA->resolve();
    mpTimerB->resolve();
    mpTimerC->resolve();
    pRenderContext->submit(true);
    double a = mpTimerA->getElapsedTime();
    double b = mpTimerB->getElapsedTime();
    double c = mpTimerC->getElapsedTime();
    if (mFrameIndex >= mWarmup)
    {
        mSamplesA.push_back(a);
        mSamplesB.push_back(b);
        mSamplesC.push_back(c);
    }
    recordAndMaybeWrite(pRenderContext, fmt::format("\"width\":{},\"height\":{},\"a_is\":\"rows+guides\",\"b_is\":\"marginal\",\"c_is\":\"8x8 block stats\"", w, h));
}
