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
#include "Core/Macros.h"
#include "Core/API/Texture.h"
#include "Core/API/Buffer.h"
#include "Core/Pass/ComputePass.h"
#include "Scene/Lights/QuadLight.h"

namespace Falcor
{
    class RenderContext;

    /** Quad light sampler. Builds a 2D piecewise-constant importance-sampling structure
        (marginal/conditional CDF) from the quad light's texture, and provides sampling
        and pdf evaluation for next-event estimation.

        Owned by PathTracer, not by Scene - mirrors EnvMapSampler's relationship to EnvMap.
    */
    class FALCOR_API QuadLightSampler
    {
    public:
        /** Create a new object.
            \param[in] pDevice GPU device.
            \param[in] pQuadLight The quad light.
        */
        QuadLightSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight);
        virtual ~QuadLightSampler() = default;

        /** Bind the quad light sampler to a given shader variable.
            \param[in] var Shader variable.
        */
        void bindShaderData(const ShaderVar& var) const;

        const ref<QuadLight>& getQuadLight() const { return mpQuadLight; }

    protected:
        void buildImportanceMap(RenderContext* pRenderContext, uint32_t gridWidth, uint32_t gridHeight);

        ref<Device>       mpDevice;

        ref<QuadLight>    mpQuadLight;

        ref<ComputePass>  mpRowsPass;
        ref<ComputePass>  mpMarginalPass;

        uint2             mGridDim;

        ref<Texture>      mpLuminance;      ///< MxN raw luminance grid.
        ref<Buffer>       mpConditionalCDF; ///< N*(M+1) raw prefix sums.
        ref<Buffer>       mpMarginalCDF;    ///< N+1 raw prefix sum.
    };
}
