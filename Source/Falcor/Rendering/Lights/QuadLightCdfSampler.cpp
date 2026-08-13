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
#include "QuadLightCdfSampler.h"
#include "QuadLightLuminance.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Logger.h"
#include "Utils/Timing/CpuTimer.h"

namespace Falcor
{
    QuadLightCdfSampler::QuadLightCdfSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : QuadLightSampler(QuadLightSamplerType::Cdf2D, pDevice, pQuadLight)
    {
        auto start = CpuTimer::getCurrentTimePoint();

        uint32_t w = 0, h = 0;
        std::vector<float> luminance = computeQuadLightLuminance(*pQuadLight, w, h);
        if (luminance.empty())
        {
            // Fall back to a single uniform texel so the sampler is still well-defined.
            w = h = 1;
            luminance = {1.f};
        }
        mGridDim = uint2(w, h);

        // Build the marginal/conditional CDFs on the CPU (raw prefix sums, left unnormalized -
        // the shader scales its random sample by the relevant total instead of pre-dividing).
        // Accumulate in double: for images with a very large pixel count and/or extreme
        // dynamic range (e.g. HDR sources with a small very-bright region against a much
        // dimmer background), naive float32 running sums compound rounding error over
        // hundreds of thousands of additions, which can measurably skew where CDF interval
        // boundaries land. The GPU-side buffers stay float (binary search only ever compares
        // adjacent entries), but accumulating in double before the final cast avoids that
        // compounding.
        std::vector<float> conditionalCDF((size_t)h * (w + 1));
        std::vector<float> marginalCDF((size_t)h + 1);

        double marginalAcc = 0.0;
        marginalCDF[0] = 0.f;
        for (uint32_t y = 0; y < h; ++y)
        {
            double rowAcc = 0.0;
            const size_t condBegin = (size_t)y * (w + 1);
            conditionalCDF[condBegin] = 0.f;
            for (uint32_t x = 0; x < w; ++x)
            {
                rowAcc += double(luminance[(size_t)y * w + x]);
                conditionalCDF[condBegin + x + 1] = float(rowAcc);
            }
            marginalAcc += rowAcc;
            marginalCDF[y + 1] = float(marginalAcc);
        }

        mpLuminance = mpDevice->createTexture2D(w, h, ResourceFormat::R32Float, 1, 1, luminance.data(), ResourceBindFlags::ShaderResource);
        mpConditionalCDF = mpDevice->createStructuredBuffer(
            sizeof(float), (uint32_t)conditionalCDF.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, conditionalCDF.data(), false
        );
        mpMarginalCDF = mpDevice->createStructuredBuffer(
            sizeof(float), (uint32_t)marginalCDF.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, marginalCDF.data(), false
        );

        auto end = CpuTimer::getCurrentTimePoint();
        logInfo("QuadLightCdfSampler: build time {:.3f} ms", CpuTimer::calcDuration(start, end));
    }

    void QuadLightCdfSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        var["gridDim"] = mGridDim;
        var["luminance"] = mpLuminance;
        var["conditionalCDF"] = mpConditionalCDF;
        var["marginalCDF"] = mpMarginalCDF;
    }
}
