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
#pragma once
#include "QuadLightSampler.h"
#include "Core/API/Buffer.h"
#include <memory>
#include <vector>

namespace Falcor
{
    /** QuadLight importance sampler using a best-first, budget-limited variance quadtree
        over the source image, combined with a maximally GPU-compacted alias table over
        its leaves.

        Unlike QuadLightAliasCtuSampler - which recursively quarters fixed-size 64x64
        blocks whenever a block's local coefficient of variation exceeds a fixed
        threshold, so its leaf count (and memory footprint) grows unboundedly with image
        detail/resolution - this technique instead fixes a hard leaf budget up front
        (default 4096, tunable via renderUI()) and spends it greedily: a priority queue
        always refines whichever block currently contributes the most total squared
        error (variance * area) to the piecewise-constant approximation, across the
        *whole* image at once rather than per fixed-size block. This is the standard
        greedy/best-first construction for a budget-limited piecewise-constant
        approximation - optimal at each step for minimizing total squared error, and it
        gives a predictable, bounded memory/cache footprint regardless of image content
        or resolution, at the cost of a coarser approximation than AliasCtu for very
        detailed images once the budget is spent.

        GPU structures are packed as tightly as correctness allows:
          - Quadtree topology is a flat array of 16-bit nodes (internal: index of first
            of 4 contiguous children; leaf: index into the leaf array), with node bounds
            tracked implicitly during traversal (like QuadLightMipSampler's mip descent)
            rather than stored - see QuadLightBudgetLeafAliasSampler.slang.
          - Each leaf is a single 16-byte record: a uint16 rect (assumes the quadtree
            image is at most 4096 texels in either dimension, so texel coordinates fit
            uint16 with room to spare), a half-precision alias threshold, a uint16 alias
            redirect index, and a half-precision average luminance (not flux - see
            build()'s comment on why raw avgLuma is stored instead of avgLuma*area).
          - The alias table's "own index" (indexB in the generic Utils::Sampling::
            AliasTable - see its TODO comment) is resorted away entirely at build time
            instead of stored, since it's always implied by a leaf's own array position
            once resorted - see build().

        renderUI() reports the resulting live structure size against this machine's
        detected per-core L1 data cache size.
    */
    class FALCOR_API QuadLightBudgetLeafAliasSampler : public QuadLightSampler
    {
    public:
        /** Decodes pQuadLight's source image itself (via computeQuadLightLuminance()) before building. */
        QuadLightBudgetLeafAliasSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight);

        /** Builds directly from an already-computed luminance array, skipping the decode -
            for callers (e.g. video playback prefetch) that already have one on hand from
            building the GPU texture, so the same source image isn't decoded twice.
        */
        QuadLightBudgetLeafAliasSampler(
            ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance
        );

        void bindShaderData(const ShaderVar& var) const override;
        bool renderUI(Gui::Widgets& widget) override;

        static constexpr uint32_t kDefaultLeafBudget = 4096;
        static constexpr uint32_t kMinLeafBudget = 4;
        // Bounded so total node count (~4/3 x leaf count, see build()) stays comfortably
        // under the 15-bit payload the node topology packs each child/leaf index into.
        static constexpr uint32_t kMaxLeafBudget = 16384;

    private:
        void build(uint32_t width, uint32_t height, const std::vector<float>& luminance);
        void updateStats();

        // Cached source data, so renderUI() can rebuild in place when the leaf budget
        // changes without needing to re-decode the light's source image from disk.
        uint32_t mSrcWidth = 0;
        uint32_t mSrcHeight = 0;
        std::vector<float> mSrcLuminance;

        uint32_t mLeafBudget = kDefaultLeafBudget;
        uint32_t mNodeCount = 0;
        uint32_t mLeafCount = 0;
        double mWeightSum = 0.0;

        ref<Buffer> mpNodes;  ///< Flat quadtree topology: one typed R16Uint element per node (root is node 0).
        ref<Buffer> mpLeaves; ///< Flat leaf array, one 16-byte packed record per leaf (see .cpp/.slang).

        // Stats surfaced by renderUI().
        size_t mStructureBytes = 0;         ///< Total GPU bytes: node buffer + leaf buffer.
        bool mL1CacheDetected = false;       ///< False if detection failed and mL1CacheBytes is a fallback guess.
        size_t mL1CacheBytes = 0;            ///< Detected (or, failing that, assumed) per-core L1 data cache size for this machine.
        size_t mL1BudgetBytes = 0;           ///< Half of mL1CacheBytes - the budget this technique targets fitting within.
        size_t mMaxLeavesInL1Budget = 0;     ///< How many leaves (node+leaf structure together) fit within mL1BudgetBytes.
    };
}
