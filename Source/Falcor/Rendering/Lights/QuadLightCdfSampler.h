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

namespace Falcor
{
    /** QuadLight importance sampler using a 2D piecewise-constant distribution (marginal
        CDF over rows + per-row conditional CDF), inverted via binary search in the shader.
        The default technique - identical math to the original single-technique QuadLightSampler.

        Everything is built on the CPU (see QuadLightLuminance.h) at the source image's
        native resolution and uploaded once; the shader only does the (log N) binary-search
        sampling.
    */
    class FALCOR_API QuadLightCdfSampler : public QuadLightSampler
    {
    public:
        QuadLightCdfSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight);

        void bindShaderData(const ShaderVar& var) const override;

    private:
        uint2       mGridDim;
        ref<Texture> mpLuminance;      ///< WxH raw luminance grid.
        ref<Buffer>  mpConditionalCDF; ///< H*(W+1) raw prefix sums.
        ref<Buffer>  mpMarginalCDF;    ///< H+1 raw prefix sum.
    };
}
