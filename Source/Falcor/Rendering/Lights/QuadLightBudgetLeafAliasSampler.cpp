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
#include "QuadLightBudgetLeafAliasSampler.h"
#include "QuadLightLuminance.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Logger.h"
#include "Utils/Math/Float16.h"
#include "Utils/Timing/CpuTimer.h"

#include <algorithm>
#include <cmath>
#include <queue>

#if FALCOR_WINDOWS
#include <windows.h>
#elif FALCOR_LINUX
#include <fstream>
#include <string>
#endif

namespace Falcor
{
    namespace
    {
        // GPU-side leaf record - 16 bytes, four uint32 fields each packing two 16-bit
        // values (rather than native uint16_t/half struct fields) so it doesn't depend on
        // 16-bit shader type support being enabled - see QuadLightBudgetLeafAliasSampler.slang.
        struct PackedLeaf
        {
            uint32_t x0y0;            ///< x0 | (y0 << 16)
            uint32_t x1y1;            ///< x1 | (y1 << 16)
            uint32_t thresholdAlias;  ///< fp16(threshold) | (aliasIndex << 16)
            uint32_t avgLumaPad;      ///< fp16(avgLuma) | 0
        };
        static_assert(sizeof(PackedLeaf) == 16, "PackedLeaf must be exactly 16 bytes");

        inline uint32_t pack16(uint16_t lo, uint16_t hi)
        {
            return uint32_t(lo) | (uint32_t(hi) << 16);
        }

        // Node topology encoding: MSB set = leaf (low 15 bits = leaf array index), MSB
        // clear = internal (low 15 bits = index of the first of 4 contiguous children).
        constexpr uint16_t kNodeLeafFlag = 0x8000u;
        constexpr uint16_t kNodePayloadMask = 0x7fffu;

        // Best-effort per-core L1 *data* cache size detection (not L1 instruction, not
        // L2/L3 - this technique targets the smallest, fastest cache tier). Returns 0 if
        // it couldn't be determined (the caller falls back to a conservative assumption
        // in that case) - this is a UI/diagnostic convenience, not something correctness
        // depends on.
        size_t detectL1DataCacheSizeBytes()
        {
#if FALCOR_WINDOWS
            DWORD len = 0;
            GetLogicalProcessorInformationEx(RelationCache, nullptr, &len);
            if (len == 0)
                return 0;
            std::vector<uint8_t> buffer(len);
            if (!GetLogicalProcessorInformationEx(RelationCache, reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX>(buffer.data()), &len))
                return 0;

            size_t bestL1Data = 0;
            size_t offset = 0;
            while (offset + sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX) <= len)
            {
                auto* info = reinterpret_cast<const SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX*>(buffer.data() + offset);
                if (info->Relationship == RelationCache && info->Cache.Level == 1 && info->Cache.Type == CacheData)
                    bestL1Data = std::max(bestL1Data, size_t(info->Cache.CacheSize));
                if (info->Size == 0)
                    break; // Defensive: avoid an infinite loop on malformed data.
                offset += info->Size;
            }
            return bestL1Data;
#elif FALCOR_LINUX
            // Typical sysfs layout: /sys/devices/system/cpu/cpu0/cache/indexN/{level,size,type}.
            // Scan a handful of indices (L1/L2/L3 rarely go past index 3-4) for whichever
            // reports level 1 and type "Data" (L1 is normally split into separate Data/
            // Instruction entries, unlike the usually-unified L2/L3).
            for (int idx = 0; idx <= 4; ++idx)
            {
                std::string base = "/sys/devices/system/cpu/cpu0/cache/index" + std::to_string(idx);
                std::ifstream levelFile(base + "/level");
                if (!levelFile.good())
                    continue;
                int level = 0;
                levelFile >> level;
                if (level != 1)
                    continue;

                std::ifstream typeFile(base + "/type");
                if (!typeFile.good())
                    continue;
                std::string type;
                typeFile >> type;
                if (type != "Data")
                    continue;

                std::ifstream sizeFile(base + "/size");
                if (!sizeFile.good())
                    continue;
                std::string s;
                sizeFile >> s;
                if (s.empty())
                    continue;

                size_t mult = 1;
                char suffix = s.back();
                if (suffix == 'K' || suffix == 'k')
                {
                    mult = 1024;
                    s.pop_back();
                }
                else if (suffix == 'M' || suffix == 'm')
                {
                    mult = 1024 * 1024;
                    s.pop_back();
                }
                try
                {
                    return size_t(std::stoul(s)) * mult;
                }
                catch (...)
                {
                    return 0;
                }
            }
            return 0;
#else
            return 0;
#endif
        }
    } // namespace

    QuadLightBudgetLeafAliasSampler::QuadLightBudgetLeafAliasSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : QuadLightSampler(QuadLightSamplerType::BudgetLeafAlias, pDevice, pQuadLight)
    {
        mLeafBudget = pQuadLight->getBudgetLeafAliasLeafBudget();

        auto luminanceStart = CpuTimer::getCurrentTimePoint();

        uint32_t w = 0, h = 0;
        std::vector<float> luminance = computeQuadLightLuminance(*pQuadLight, w, h);

        auto luminanceEnd = CpuTimer::getCurrentTimePoint();
        logInfo(
            "QuadLightBudgetLeafAliasSampler: source image load/decode time {:.3f} ms ({}x{})",
            CpuTimer::calcDuration(luminanceStart, luminanceEnd), w, h
        );

        build(w, h, luminance);
    }

    QuadLightBudgetLeafAliasSampler::QuadLightBudgetLeafAliasSampler(
        ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance
    )
        : QuadLightSampler(QuadLightSamplerType::BudgetLeafAlias, pDevice, pQuadLight)
    {
        mLeafBudget = pQuadLight->getBudgetLeafAliasLeafBudget();
        build(width, height, luminance);
    }

    void QuadLightBudgetLeafAliasSampler::build(uint32_t w, uint32_t h, const std::vector<float>& luminanceIn)
    {
        std::vector<float> fallback;
        const std::vector<float>* pLuminance = &luminanceIn;
        if (luminanceIn.empty() || w == 0 || h == 0)
        {
            w = h = 1;
            fallback = {1.f};
            pLuminance = &fallback;
        }
        // Copy (not reference) before touching mSrcLuminance below: renderUI() calls
        // build(mSrcWidth, mSrcHeight, mSrcLuminance) to rebuild in place when the budget
        // changes, so luminanceIn may already alias mSrcLuminance.
        std::vector<float> luminance = *pLuminance;

        auto start = CpuTimer::getCurrentTimePoint();

        mSrcWidth = w;
        mSrcHeight = h;
        mSrcLuminance = luminance;

        uint32_t budget = std::clamp(mLeafBudget, kMinLeafBudget, kMaxLeafBudget);

        // ---- Summed-area table over the WxH luminance grid, for O(1) rect mean/variance
        // queries. Accumulated in double for the same reason QuadLightCdfSampler/
        // QuadLightAliasCtuSampler do (compounding float32 rounding error over millions of
        // additions). Unlike QuadLightAliasCtuSampler's direct-rescan computeBlockStats()
        // - which is the right call for ITS fixed, bounded recursive-descent access
        // pattern (see its own comment) - best-first refinement here issues a much larger
        // number of stats queries at arbitrary, priority-driven rects, so a one-time O(WH)
        // SAT precompute paying for O(1) queries afterward is the better tradeoff. This
        // costs ~2*(W+1)*(H+1)*8 bytes of temporary memory (freed when build() returns) -
        // ~268MB at the assumed 4K-resolution ceiling, negligible at typical resolutions.
        const size_t sw = size_t(w) + 1, sh = size_t(h) + 1;
        std::vector<double> sat(sw * sh, 0.0);
        std::vector<double> satSq(sw * sh, 0.0);
        for (uint32_t y = 0; y < h; ++y)
        {
            for (uint32_t x = 0; x < w; ++x)
            {
                double v = double(luminance[(size_t)y * w + x]);
                size_t i = (size_t)(y + 1) * sw + (x + 1);
                sat[i] = v + sat[i - sw] + sat[i - 1] - sat[i - sw - 1];
                satSq[i] = v * v + satSq[i - sw] + satSq[i - 1] - satSq[i - sw - 1];
            }
        }
        auto queryStats = [&](uint32_t x0, uint32_t y0, uint32_t x1, uint32_t y1, double& outSum, double& outSumSq)
        {
            outSum = sat[(size_t)y1 * sw + x1] - sat[(size_t)y0 * sw + x1] - sat[(size_t)y1 * sw + x0] + sat[(size_t)y0 * sw + x0];
            outSumSq =
                satSq[(size_t)y1 * sw + x1] - satSq[(size_t)y0 * sw + x1] - satSq[(size_t)y1 * sw + x0] + satSq[(size_t)y0 * sw + x0];
        };

        // ---- Best-first, budget-limited quadtree refinement. At each step, split
        // whichever pending block currently contributes the most total squared error
        // (variance * area) to the piecewise-constant approximation - the standard greedy
        // choice for minimizing total error under a fixed leaf budget. Unlike
        // QuadLightAliasCtuSampler's fixed 64x64-tiled, fixed-CV-threshold recursion (whose
        // leaf count grows unboundedly with image detail), this always produces at most
        // `budget` leaves regardless of content, at the cost of a coarser fit once the
        // budget runs out on very detailed images.
        struct PendingLeaf
        {
            uint32_t x0, y0, x1, y1;
            float avgLuma;
            uint32_t nodeIndex;
        };
        struct Candidate
        {
            uint32_t x0, y0, x1, y1;
            double mean;
            double priority;
            uint32_t nodeIndex;
            bool operator<(const Candidate& o) const { return priority < o.priority; } // std::priority_queue is a max-heap.
        };

        std::vector<uint16_t> nodes;
        std::vector<PendingLeaf> finalLeaves;
        std::priority_queue<Candidate> pq;

        auto allocNode = [&]() -> uint32_t
        {
            nodes.push_back(0);
            return uint32_t(nodes.size()) - 1;
        };

        auto consider = [&](uint32_t x0, uint32_t y0, uint32_t x1, uint32_t y1, uint32_t nodeIndex)
        {
            double sum, sumSq;
            queryStats(x0, y0, x1, y1, sum, sumSq);
            double area = double(x1 - x0) * double(y1 - y0);
            double mean = area > 0.0 ? sum / area : 0.0;
            double variance = std::max(0.0, sumSq / area - mean * mean);
            bool canSplit = (x1 - x0) > 1 && (y1 - y0) > 1 && variance > 0.0;
            if (canSplit)
                pq.push({x0, y0, x1, y1, mean, variance * area, nodeIndex});
            else
                finalLeaves.push_back({x0, y0, x1, y1, float(mean), nodeIndex});
        };

        uint32_t rootNode = allocNode();
        consider(0, 0, w, h, rootNode);

        while (!pq.empty() && finalLeaves.size() + pq.size() + 3 <= budget)
        {
            Candidate c = pq.top();
            pq.pop();

            uint32_t firstChild = uint32_t(nodes.size());
            allocNode();
            allocNode();
            allocNode();
            allocNode();
            FALCOR_CHECK(firstChild <= kNodePayloadMask, "QuadLightBudgetLeafAliasSampler: quadtree exceeded its 15-bit node index range.");
            nodes[c.nodeIndex] = uint16_t(firstChild); // internal node: points at its 4 contiguous children.

            uint32_t xm = c.x0 + (c.x1 - c.x0) / 2;
            uint32_t ym = c.y0 + (c.y1 - c.y0) / 2;
            consider(c.x0, c.y0, xm, ym, firstChild + 0);
            consider(xm, c.y0, c.x1, ym, firstChild + 1);
            consider(c.x0, ym, xm, c.y1, firstChild + 2);
            consider(xm, ym, c.x1, c.y1, firstChild + 3);
        }
        // Whatever's left in the queue (budget exhausted, or nothing left worth splitting)
        // becomes a leaf as-is.
        while (!pq.empty())
        {
            const Candidate& c = pq.top();
            finalLeaves.push_back({c.x0, c.y0, c.x1, c.y1, float(c.mean), c.nodeIndex});
            pq.pop();
        }

        uint32_t leafCount = uint32_t(finalLeaves.size());
        FALCOR_CHECK(leafCount <= kNodePayloadMask, "QuadLightBudgetLeafAliasSampler: leaf count exceeded its 15-bit node index range.");
        for (uint32_t i = 0; i < leafCount; ++i)
            nodes[finalLeaves[i].nodeIndex] = uint16_t(kNodeLeafFlag | i);

        // ---- Alias table over the leaves' flux (avgLuma * area), resorted so a bucket's
        // own array position implies its "indexB" (see Utils/Sampling/AliasTable.cpp's own
        // TODO comment: "only one element in the table has indexB==j for any j", i.e. this
        // resort is always possible) - dropping that field entirely instead of storing it,
        // unlike the generic AliasTable this technique intentionally doesn't reuse (its
        // Item is 16 bytes + a separate 4-byte weight per entry; the resort here plus
        // half-precision packing gets a leaf's alias entry down to 6 of PackedLeaf's 16
        // bytes, with the rest spent on the leaf's rect).
        std::vector<float> weights(leafCount);
        for (uint32_t i = 0; i < leafCount; ++i)
        {
            const PendingLeaf& leaf = finalLeaves[i];
            float area = float(leaf.x1 - leaf.x0) * float(leaf.y1 - leaf.y0);
            weights[i] = leaf.avgLuma * area;
        }

        mWeightSum = 0.0;
        for (float wgt : weights)
            mWeightSum += double(wgt);
        float avgWeight = leafCount > 0 ? float(mWeightSum / double(leafCount)) : 0.f;

        constexpr uint32_t kInvalid = 0xffffffffu;
        std::vector<uint32_t> lowIdx(leafCount, kInvalid), highIdx(leafCount, kInvalid);
        uint32_t lowCount = 0, highCount = 0;
        for (uint32_t i = 0; i < leafCount; ++i)
        {
            if (weights[i] < avgWeight)
                lowIdx[lowCount++] = i;
            else
                highIdx[highCount++] = i;
        }

        std::vector<float> outThreshold(leafCount, 1.f);
        std::vector<uint32_t> outAlias(leafCount, 0);
        for (uint32_t i = 0; i < leafCount; ++i)
        {
            if (lowIdx[i] != kInvalid && highIdx[i] != kInvalid)
            {
                uint32_t bucket = lowIdx[i]; // Resorted: store at the "own item" position, not at loop index i.
                outThreshold[bucket] = weights[lowIdx[i]] / avgWeight;
                outAlias[bucket] = highIdx[i];

                float updatedWeight = (weights[lowIdx[i]] + weights[highIdx[i]]) - avgWeight;
                weights[highIdx[i]] = updatedWeight;
                if (updatedWeight < avgWeight)
                    lowIdx[lowCount++] = highIdx[i];
                else
                    highIdx[highCount++] = highIdx[i];
            }
            else if (highIdx[i] != kInvalid)
            {
                uint32_t bucket = highIdx[i];
                outThreshold[bucket] = 1.f;
                outAlias[bucket] = highIdx[i];
            }
            else if (lowIdx[i] != kInvalid)
            {
                uint32_t bucket = lowIdx[i];
                outThreshold[bucket] = 1.f;
                outAlias[bucket] = lowIdx[i];
            }
            // else: unreachable by construction (mirrors AliasTable::AliasTable's own invariant).
        }

        // ---- Pack the final GPU buffers.
        std::vector<PackedLeaf> packedLeaves(leafCount);
        for (uint32_t i = 0; i < leafCount; ++i)
        {
            const PendingLeaf& leaf = finalLeaves[i];
            packedLeaves[i].x0y0 = pack16(uint16_t(leaf.x0), uint16_t(leaf.y0));
            packedLeaves[i].x1y1 = pack16(uint16_t(leaf.x1), uint16_t(leaf.y1));
            packedLeaves[i].thresholdAlias = pack16(math::float32ToFloat16(outThreshold[i]), uint16_t(outAlias[i]));
            packedLeaves[i].avgLumaPad = pack16(math::float32ToFloat16(leaf.avgLuma), 0);
        }

        mNodeCount = uint32_t(nodes.size());
        mLeafCount = leafCount;

        mpNodes = mpDevice->createTypedBuffer(ResourceFormat::R16Uint, mNodeCount, ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, nodes.data());
        mpLeaves = mpDevice->createStructuredBuffer(
            sizeof(PackedLeaf), leafCount, ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, packedLeaves.data(), false
        );

        updateStats();

        auto end = CpuTimer::getCurrentTimePoint();
        logInfo(
            "QuadLightBudgetLeafAliasSampler: build time {:.3f} ms ({} leaves / {} budget, {} nodes, {:.1f} KB)",
            CpuTimer::calcDuration(start, end), mLeafCount, budget, mNodeCount, mStructureBytes / 1024.0
        );
    }

    void QuadLightBudgetLeafAliasSampler::updateStats()
    {
        size_t nodeBytes = size_t(mNodeCount) * sizeof(uint16_t);
        size_t leafBytes = size_t(mLeafCount) * sizeof(PackedLeaf);
        mStructureBytes = nodeBytes + leafBytes;

        size_t detected = detectL1DataCacheSizeBytes();
        mL1CacheDetected = detected > 0;
        // Conservative fallback if detection isn't available on this platform/machine - a
        // common per-core L1 data cache size on modern desktop/workstation CPUs (some are
        // larger, e.g. 48-64KB, but 32KB is a safe lower-bound assumption).
        constexpr size_t kFallbackL1Bytes = 32ull * 1024;
        mL1CacheBytes = mL1CacheDetected ? detected : kFallbackL1Bytes;
        mL1BudgetBytes = mL1CacheBytes / 2;

        // Nodes and leaves grow together (~4/3 nodes per leaf - see build()'s comment on
        // the split/leaf-count relationship), so "how many leaves fit" means fitting the
        // whole structure, not just the leaf array.
        constexpr double kNodesPerLeaf = 4.0 / 3.0;
        double bytesPerLeafEquivalent = double(sizeof(PackedLeaf)) + kNodesPerLeaf * double(sizeof(uint16_t));
        mMaxLeavesInL1Budget = bytesPerLeafEquivalent > 0.0 ? size_t(double(mL1BudgetBytes) / bytesPerLeafEquivalent) : 0;
    }

    void QuadLightBudgetLeafAliasSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        var["gridDim"] = uint2(mSrcWidth, mSrcHeight);
        var["leafCount"] = mLeafCount;
        var["weightSum"] = float(mWeightSum);
        var["nodes"] = mpNodes;
        var["leaves"] = mpLeaves;
    }

    bool QuadLightBudgetLeafAliasSampler::renderUI(Gui::Widgets& widget)
    {
        bool dirty = false;

        int budget = int(mLeafBudget);
        if (widget.var("Leaf budget", budget, int(kMinLeafBudget), int(kMaxLeafBudget), 1))
        {
            mLeafBudget = uint32_t(budget);
            build(mSrcWidth, mSrcHeight, mSrcLuminance);
            dirty = true;
        }
        widget.tooltip(
            "Maximum quadtree leaf count. Built via best-first refinement: whichever block "
            "currently contributes the most total squared error (variance x area) to the "
            "piecewise-constant approximation is split first, so the budget is spent where "
            "the source image actually has detail rather than uniformly across it.",
            true
        );

        widget.text(fmt::format("Leaves used: {} / {}", mLeafCount, mLeafBudget));
        widget.text(fmt::format("Quadtree nodes: {}", mNodeCount));
        widget.text(fmt::format("GPU structure size: {:.1f} KB ({} bytes)", mStructureBytes / 1024.0, mStructureBytes));
        widget.text(fmt::format(
            "{} L1 data cache: {:.1f} KB (targeting half: {:.1f} KB)",
            mL1CacheDetected ? "Detected" : "Assumed (detection failed)",
            mL1CacheBytes / 1024.0, mL1BudgetBytes / 1024.0
        ));
        widget.text(fmt::format("Leaves that fit in that budget: ~{}", mMaxLeavesInL1Budget));
        if (mLeafCount > mMaxLeavesInL1Budget)
        {
            widget.text("Current structure exceeds the estimated L1 budget.");
        }

        return dirty;
    }
}
