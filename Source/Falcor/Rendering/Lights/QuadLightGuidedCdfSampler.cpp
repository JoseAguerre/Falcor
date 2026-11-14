#include "QuadLightGuidedCdfSampler.h"
#include "QuadLightBuildTiming.h"
#include "QuadLightLuminance.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Timing/CpuTimer.h"

#include <algorithm>
#include <execution>
#include <numeric>

namespace Falcor
{
    QuadLightGuidedCdfSampler::QuadLightGuidedCdfSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : QuadLightSampler(QuadLightSamplerType::CdfGuided, pDevice, pQuadLight)
    {
        uint32_t w = 0, h = 0;
        std::vector<float> luminance = computeQuadLightLuminance(*pQuadLight, w, h);
        build(w, h, luminance);
    }

    QuadLightGuidedCdfSampler::QuadLightGuidedCdfSampler(
        ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance
    )
        : QuadLightSampler(QuadLightSamplerType::CdfGuided, pDevice, pQuadLight)
    {
        build(width, height, luminance);
    }

    void QuadLightGuidedCdfSampler::build(uint32_t w, uint32_t h, const std::vector<float>& luminance)
    {
        FALCOR_CHECK(!luminance.empty() && w > 0 && h > 0, "QuadLightGuidedCdfSampler: empty input.");
        mGridDim = uint2(w, h);
        auto start = CpuTimer::getCurrentTimePoint();

        std::vector<float> conditional((size_t)h * (w + 1));
        std::vector<uint16_t> conditionalGuide((size_t)h * w);
        std::vector<double> rowTotals(h);
        std::vector<uint32_t> rows(h);
        std::iota(rows.begin(), rows.end(), 0u);

        std::for_each(
            std::execution::par, rows.begin(), rows.end(),
            [&](uint32_t y)
            {
                float* cdf = conditional.data() + (size_t)y * (w + 1);
                uint16_t* guide = conditionalGuide.data() + (size_t)y * w;
                const float* src = luminance.data() + (size_t)y * w;
                double acc = 0.0;
                cdf[0] = 0.f;
                for (uint32_t x = 0; x < w; ++x)
                {
                    acc += double(src[x]);
                    cdf[x + 1] = float(acc);
                }
                rowTotals[y] = acc;
                uint32_t i = 0;
                for (uint32_t k = 0; k < w; ++k)
                {
                    const float target = float(acc * (double(k) / double(w)));
                    while (i + 1 < w && cdf[i + 1] <= target)
                        ++i;
                    guide[k] = uint16_t(i);
                }
            }
        );

        std::vector<float> marginal(h + 1);
        double acc = 0.0;
        marginal[0] = 0.f;
        for (uint32_t y = 0; y < h; ++y)
        {
            acc += rowTotals[y];
            marginal[y + 1] = float(acc);
        }
        std::vector<uint32_t> marginalGuide(h);
        {
            uint32_t i = 0;
            for (uint32_t k = 0; k < h; ++k)
            {
                const float target = float(acc * (double(k) / double(h)));
                while (i + 1 < h && marginal[i + 1] <= target)
                    ++i;
                marginalGuide[k] = i;
            }
        }

        auto uploadStart = CpuTimer::getCurrentTimePoint();
        mpLuminance = mpDevice->createTexture2D(w, h, ResourceFormat::R32Float, 1, 1, luminance.data(), ResourceBindFlags::ShaderResource);
        mpConditionalCDF = mpDevice->createStructuredBuffer(
            sizeof(float), (uint32_t)conditional.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, conditional.data(), false
        );
        mpMarginalCDF = mpDevice->createStructuredBuffer(
            sizeof(float), (uint32_t)marginal.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, marginal.data(), false
        );
        mpConditionalGuide = mpDevice->createTypedBuffer(
            ResourceFormat::R16Uint, (uint32_t)conditionalGuide.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, conditionalGuide.data()
        );
        mpMarginalGuide = mpDevice->createStructuredBuffer(
            sizeof(uint32_t), (uint32_t)marginalGuide.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, marginalGuide.data(), false
        );
        auto end = CpuTimer::getCurrentTimePoint();

        auto& timing = quadLightBuildTiming();
        timing.tableMs = CpuTimer::calcDuration(start, uploadStart);
        timing.uploadMs = CpuTimer::calcDuration(uploadStart, end);
        timing.leaves = w * h;
        timing.bytes = sizeof(float) * (uint64_t(w) * h + conditional.size() + marginal.size()) + sizeof(uint16_t) * conditionalGuide.size() +
                       sizeof(uint32_t) * marginalGuide.size();
    }

    void QuadLightGuidedCdfSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());
        var["gridDim"] = mGridDim;
        var["luminance"] = mpLuminance;
        var["conditionalCDF"] = mpConditionalCDF;
        var["marginalCDF"] = mpMarginalCDF;
        var["conditionalGuide"] = mpConditionalGuide;
        var["marginalGuide"] = mpMarginalGuide;
    }
}
