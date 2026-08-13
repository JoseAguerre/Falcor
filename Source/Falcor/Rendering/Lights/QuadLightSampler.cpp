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
#include "QuadLightSampler.h"
#include "Core/Error.h"
#include "Core/API/RenderContext.h"

namespace Falcor
{
    namespace
    {
        const char kShaderFilenameSetup[] = "Rendering/Lights/QuadLightSamplerSetup.cs.slang";

        // Default resolution of the importance-sampling grid. Doesn't need to match the
        // source texture's native resolution.
        const uint32_t kDefaultGridWidth = 256;
        const uint32_t kDefaultGridHeight = 256;
    }

    QuadLightSampler::QuadLightSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : mpDevice(pDevice)
        , mpQuadLight(pQuadLight)
    {
        FALCOR_ASSERT(pQuadLight);

        mpRowsPass = ComputePass::create(mpDevice, kShaderFilenameSetup, "mainRows");
        mpMarginalPass = ComputePass::create(mpDevice, kShaderFilenameSetup, "mainMarginal");

        buildImportanceMap(mpDevice->getRenderContext(), kDefaultGridWidth, kDefaultGridHeight);
    }

    void QuadLightSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        var["gridDim"] = mGridDim;
        var["luminance"] = mpLuminance;
        var["conditionalCDF"] = mpConditionalCDF;
        var["marginalCDF"] = mpMarginalCDF;
    }

    void QuadLightSampler::buildImportanceMap(RenderContext* pRenderContext, uint32_t gridWidth, uint32_t gridHeight)
    {
        mGridDim = uint2(gridWidth, gridHeight);

        mpLuminance = mpDevice->createTexture2D(
            gridWidth, gridHeight, ResourceFormat::R32Float, 1, 1, nullptr,
            ResourceBindFlags::ShaderResource | ResourceBindFlags::UnorderedAccess
        );
        mpConditionalCDF = mpDevice->createStructuredBuffer(
            sizeof(float), gridHeight * (gridWidth + 1),
            ResourceBindFlags::ShaderResource | ResourceBindFlags::UnorderedAccess
        );
        mpMarginalCDF = mpDevice->createStructuredBuffer(
            sizeof(float), gridHeight + 1,
            ResourceBindFlags::ShaderResource | ResourceBindFlags::UnorderedAccess
        );

        // Pass 1: one thread per row, samples the texture and builds each row's conditional CDF.
        {
            auto var = mpRowsPass->getRootVar();
            var["gTex"] = mpQuadLight->getTexture();
            var["gTexSampler"] = mpQuadLight->getSampler();
            var["gLuminance"] = mpLuminance;
            var["gConditionalCDF"] = mpConditionalCDF;
            var["gMarginalCDF"] = mpMarginalCDF;
            var["CB"]["gridDim"] = mGridDim;

            mpRowsPass->execute(pRenderContext, gridHeight, 1, 1);
        }

        // Pass 2: single thread, builds the marginal CDF over the per-row totals computed above.
        {
            auto var = mpMarginalPass->getRootVar();
            var["gConditionalCDF"] = mpConditionalCDF;
            var["gMarginalCDF"] = mpMarginalCDF;
            var["CB"]["gridDim"] = mGridDim;

            mpMarginalPass->execute(pRenderContext, 1, 1, 1);
        }
    }
}
