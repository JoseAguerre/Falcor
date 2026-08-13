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
#include "QuadLightAliasSampler.h"
#include "QuadLightLuminance.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Logger.h"
#include "Utils/Timing/CpuTimer.h"

#include <random>

namespace Falcor
{
    QuadLightAliasSampler::QuadLightAliasSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : QuadLightSampler(QuadLightSamplerType::AliasPerPixel, pDevice, pQuadLight)
    {
        auto start = CpuTimer::getCurrentTimePoint();

        uint32_t w = 0, h = 0;
        std::vector<float> luminance = computeQuadLightLuminance(*pQuadLight, w, h);
        if (luminance.empty())
        {
            w = h = 1;
            luminance = {1.f};
        }
        mGridDim = uint2(w, h);

        // Deterministic seed: construction happens once per technique switch (or scene
        // load), no need for cross-run entropy, and it keeps rebuilds reproducible.
        std::mt19937 rng(1234u);
        mpAliasTable = std::make_unique<AliasTable>(pDevice, std::move(luminance), rng);

        auto end = CpuTimer::getCurrentTimePoint();
        logInfo("QuadLightAliasSampler: build time {:.3f} ms", CpuTimer::calcDuration(start, end));
    }

    void QuadLightAliasSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        var["gridDim"] = mGridDim;
        mpAliasTable->bindShaderData(var["table"]);
    }
}
