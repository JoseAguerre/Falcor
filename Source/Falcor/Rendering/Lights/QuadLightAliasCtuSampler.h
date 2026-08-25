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
#include "Utils/Sampling/AliasTable.h"
#include "Core/API/Buffer.h"
#include <memory>
#include <vector>

namespace Falcor
{
    /** QuadLight sampler using the alias method over a luminance-adaptive quadtree of leaf
        blocks (up to 64x64, recursively quartered down to a minimum of 8x8 whenever a
        block's luminance coefficient of variation exceeds a fixed threshold). Approximates
        the VP9/AV1-style CTU partitioning idea from the reference CPU prototype
        (helper/sample.cpp's build_leaf_alias_table/iterate_blocks), rebuilt here with a
        custom CPU quadtree since no bitstream partition data is available.

        Leaves are picked via Falcor's generic AliasTable, weighted by (avg luminance *
        leaf area) - i.e. total flux, the same unbiased weighting the per-pixel/CDF
        techniques use. Sampling is then uniform within the chosen leaf's rect, so the
        resulting density is piecewise-constant per leaf: exact and unbiased (sample() and
        evalPdf() agree on the same model), but higher-variance within a leaf than the
        per-pixel techniques - an intentional trade for O(1) sampling/eval cost independent
        of texture resolution.
    */
    class FALCOR_API QuadLightAliasCtuSampler : public QuadLightSampler
    {
    public:
        /** Decodes pQuadLight's source image itself (via computeQuadLightLuminance()) before building. */
        QuadLightAliasCtuSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight);

        /** Builds directly from an already-computed luminance array, skipping the decode -
            for callers (e.g. video playback prefetch) that already have one on hand from
            building the GPU texture, so the same source image isn't decoded twice.
        */
        QuadLightAliasCtuSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance);

        void bindShaderData(const ShaderVar& var) const override;

    private:
        void build(uint32_t width, uint32_t height, const std::vector<float>& luminance);

        uint2 mGridDim;
        ref<Buffer> mpLeafRects;       ///< Per-leaf normalized (u0,v0,u1,v1) rects, indexed identically to the alias table.
        ref<Buffer> mpLeafIndexMap;    ///< WxH map from texel -> leaf index, for O(1) evalPdf() lookups.
        std::unique_ptr<AliasTable> mpAliasTable;
    };
}
