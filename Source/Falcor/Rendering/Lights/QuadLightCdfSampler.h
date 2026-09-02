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
#include "Core/API/Texture.h"
#include "Core/API/Buffer.h"
#include <vector>

namespace Falcor
{
    /** QuadLight importance sampler using a 2D piecewise-constant distribution (marginal
        CDF over rows + per-row conditional CDF), inverted via binary search in the shader.
        The default technique - identical math to the original single-technique QuadLightSampler.

        Everything is built on the CPU (see QuadLightLuminance.h) and uploaded once; the
        shader only does the (log N) binary-search sampling. Also backs the Cdf2DDiv8/16/32
        technique variants (see the downsampleFactor constructor parameter and
        QuadLightSamplerType.slangh): the CDF/luminance grid is built at 1/8, 1/16, or 1/32
        of the source image's resolution (box-filtered, see QuadLightLuminance.h's
        downsampleLuminanceBox()) instead of natively, trading precision for a much smaller
        GPU structure and shorter binary search - the runtime sample()/evalPdf() shader code
        is identical regardless (see QuadLightCdfSampler.slang - it only ever sees gridDim,
        not the source image's actual resolution).
    */
    class FALCOR_API QuadLightCdfSampler : public QuadLightSampler
    {
    public:
        /** Decodes pQuadLight's source image itself (via computeQuadLightLuminance()) before building.
            \param[in] downsampleFactor Build the CDF/luminance grid at 1/downsampleFactor of
                the source resolution (box-filtered). Must be 1 (native, the default -
                QuadLightSamplerType::Cdf2D), 8, 16, or 32 (Cdf2DDiv8/16/32 respectively).
        */
        QuadLightCdfSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t downsampleFactor = 1);

        /** Builds directly from an already-computed luminance array, skipping the decode -
            for callers (e.g. video playback prefetch) that already have one on hand from
            building the GPU texture, so the same source image isn't decoded twice.
        */
        QuadLightCdfSampler(
            ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance,
            uint32_t downsampleFactor = 1
        );

        void bindShaderData(const ShaderVar& var) const override;

    private:
        void build(uint32_t width, uint32_t height, const std::vector<float>& luminance, uint32_t downsampleFactor);

        uint2       mGridDim;
        ref<Texture> mpLuminance;      ///< WxH (post-downsample, if any) raw luminance grid.
        ref<Buffer>  mpConditionalCDF; ///< H*(W+1) raw prefix sums.
        ref<Buffer>  mpMarginalCDF;    ///< H+1 raw prefix sum.
    };
}
