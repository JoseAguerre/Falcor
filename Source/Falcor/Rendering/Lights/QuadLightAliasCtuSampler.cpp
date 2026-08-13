/***************************************************************************
 # Copyright (c) 2015-24, NVIDIA CORPORATION. All rights reserved.
 #
 # Redistribution and use in source and binary forms, with or without
 # modification, are permitted provided that the following conditions
 # are met:
 #  * Redistributions of source code must retain the above copyright
 #    notice, this list of conditions and the following disclaimer.
 #  * Redistributions in binary form must reproduce the above copyright
 #    notice, this list of conditions and the following disclaimer in the
 #    documentation and/or other materials provided with the distribution.
 #  * Neither the name of NVIDIA CORPORATION nor the names of its
 #    contributors may be used to endorse or promote products derived
 #    from this software without specific prior written permission.
 #
 # THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS "AS IS" AND ANY
 # EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 # IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 # PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 # CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 # EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 # PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 # PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 # OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 # (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 # OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 **************************************************************************/
#include "QuadLightAliasCtuSampler.h"
#include "QuadLightLuminance.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Logger.h"
#include "Utils/Timing/CpuTimer.h"

#include <algorithm>
#include <cmath>
#include <random>

namespace Falcor
{
    namespace
    {
        // Split policy: cover the image with up to 64x64 blocks, recursively quartering
        // any block larger than 8x8 whose luminance coefficient of variation exceeds the
        // threshold. Deterministic, single pass per node.
        constexpr uint32_t kMaxBlock = 64;
        constexpr uint32_t kMinBlock = 8;
        constexpr float kCvThreshold = 0.35f;

        struct Leaf
        {
            uint32_t x0, y0, x1, y1;
            float avgLuma;
        };

        double rectSum(const std::vector<double>& sat, uint32_t stride, uint32_t x0, uint32_t y0, uint32_t x1, uint32_t y1)
        {
            return sat[(size_t)y1 * stride + x1] - sat[(size_t)y0 * stride + x1] - sat[(size_t)y1 * stride + x0] +
                   sat[(size_t)y0 * stride + x0];
        }

        void splitBlock(
            const std::vector<double>& sat,
            const std::vector<double>& satSq,
            uint32_t stride,
            uint32_t x0,
            uint32_t y0,
            uint32_t x1,
            uint32_t y1,
            std::vector<Leaf>& leaves
        )
        {
            uint32_t bw = x1 - x0;
            uint32_t bh = y1 - y0;
            double area = double(bw) * double(bh);

            double sum = rectSum(sat, stride, x0, y0, x1, y1);
            double mean = sum / area;

            bool shouldSplit = false;
            if (bw > kMinBlock && bh > kMinBlock)
            {
                double sumSq = rectSum(satSq, stride, x0, y0, x1, y1);
                double variance = std::max(0.0, sumSq / area - mean * mean);
                double stddev = std::sqrt(variance);
                double cv = mean > 1e-8 ? stddev / mean : 0.0;
                shouldSplit = cv > kCvThreshold;
            }

            if (shouldSplit)
            {
                uint32_t xm = x0 + bw / 2;
                uint32_t ym = y0 + bh / 2;
                splitBlock(sat, satSq, stride, x0, y0, xm, ym, leaves);
                splitBlock(sat, satSq, stride, xm, y0, x1, ym, leaves);
                splitBlock(sat, satSq, stride, x0, ym, xm, y1, leaves);
                splitBlock(sat, satSq, stride, xm, ym, x1, y1, leaves);
            }
            else
            {
                leaves.push_back({x0, y0, x1, y1, float(mean)});
            }
        }
    }

    QuadLightAliasCtuSampler::QuadLightAliasCtuSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : QuadLightSampler(QuadLightSamplerType::AliasCtu, pDevice, pQuadLight)
    {
        auto hierarchyStart = CpuTimer::getCurrentTimePoint();

        uint32_t w = 0, h = 0;
        std::vector<float> luminance = computeQuadLightLuminance(*pQuadLight, w, h);
        if (luminance.empty())
        {
            w = h = 1;
            luminance = {1.f};
        }
        mGridDim = uint2(w, h);

        // Summed-area tables (double precision) for O(1) mean/variance queries per block.
        uint32_t stride = w + 1;
        std::vector<double> sat((size_t)stride * (h + 1), 0.0);
        std::vector<double> satSq((size_t)stride * (h + 1), 0.0);
        for (uint32_t y = 0; y < h; ++y)
        {
            for (uint32_t x = 0; x < w; ++x)
            {
                double v = double(luminance[(size_t)y * w + x]);
                size_t i00 = (size_t)y * stride + x;
                size_t i01 = (size_t)y * stride + (x + 1);
                size_t i10 = (size_t)(y + 1) * stride + x;
                size_t i11 = (size_t)(y + 1) * stride + (x + 1);
                sat[i11] = v + sat[i10] + sat[i01] - sat[i00];
                satSq[i11] = v * v + satSq[i10] + satSq[i01] - satSq[i00];
            }
        }

        std::vector<Leaf> leaves;
        for (uint32_t y0 = 0; y0 < h; y0 += kMaxBlock)
        {
            uint32_t y1 = std::min(y0 + kMaxBlock, h);
            for (uint32_t x0 = 0; x0 < w; x0 += kMaxBlock)
            {
                uint32_t x1 = std::min(x0 + kMaxBlock, w);
                splitBlock(sat, satSq, stride, x0, y0, x1, y1, leaves);
            }
        }

        auto hierarchyEnd = CpuTimer::getCurrentTimePoint();
        logInfo(
            "QuadLightAliasCtuSampler: superblock hierarchy build time {:.3f} ms ({} leaves)",
            CpuTimer::calcDuration(hierarchyStart, hierarchyEnd), leaves.size()
        );

        // Weight each leaf by its total flux (avg luminance * area) - the same unbiased
        // weighting the per-pixel/CDF techniques use, just aggregated over the leaf.
        std::vector<float> weights(leaves.size());
        std::vector<float4> rects(leaves.size());
        for (size_t i = 0; i < leaves.size(); ++i)
        {
            const Leaf& leaf = leaves[i];
            float area = float(leaf.x1 - leaf.x0) * float(leaf.y1 - leaf.y0);
            weights[i] = leaf.avgLuma * area;
            rects[i] = float4(float(leaf.x0) / float(w), float(leaf.y0) / float(h), float(leaf.x1) / float(w), float(leaf.y1) / float(h));
        }

        // Per-texel -> leaf-index map, for O(1) evalPdf() lookups (built in one pass over
        // the final leaf list, each texel visited exactly once).
        std::vector<uint32_t> leafIndexMap((size_t)w * h, 0);
        for (size_t i = 0; i < leaves.size(); ++i)
        {
            const Leaf& leaf = leaves[i];
            for (uint32_t y = leaf.y0; y < leaf.y1; ++y)
                for (uint32_t x = leaf.x0; x < leaf.x1; ++x)
                    leafIndexMap[(size_t)y * w + x] = (uint32_t)i;
        }

        // Deterministic seed: construction happens once per technique switch (or scene
        // load), no need for cross-run entropy, and it keeps rebuilds reproducible.
        auto aliasStart = CpuTimer::getCurrentTimePoint();
        std::mt19937 rng(1234u);
        mpAliasTable = std::make_unique<AliasTable>(pDevice, std::move(weights), rng);
        auto aliasEnd = CpuTimer::getCurrentTimePoint();
        logInfo("QuadLightAliasCtuSampler: alias table build time {:.3f} ms", CpuTimer::calcDuration(aliasStart, aliasEnd));

        mpLeafRects = pDevice->createStructuredBuffer(
            sizeof(float4), (uint32_t)rects.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, rects.data(), false
        );
        mpLeafIndexMap = pDevice->createStructuredBuffer(
            sizeof(uint32_t), (uint32_t)leafIndexMap.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, leafIndexMap.data(),
            false
        );
    }

    void QuadLightAliasCtuSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        var["gridDim"] = mGridDim;
        var["leafRects"] = mpLeafRects;
        var["leafIndexMap"] = mpLeafIndexMap;
        mpAliasTable->bindShaderData(var["table"]);
    }
}
