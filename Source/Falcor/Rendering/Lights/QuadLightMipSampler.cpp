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
#include "QuadLightMipSampler.h"
#include "QuadLightLuminance.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Logger.h"
#include "Utils/Timing/CpuTimer.h"

#include <algorithm>
#include <cmath>

namespace Falcor
{
    namespace
    {
        // Bilinearly resample a WxH luminance grid into a DxD grid (pixel centers aligned).
        std::vector<float> resampleToSquare(const std::vector<float>& src, uint32_t w, uint32_t h, uint32_t d)
        {
            std::vector<float> dst((size_t)d * d);
            for (uint32_t y = 0; y < d; ++y)
            {
                float v = (float(y) + 0.5f) / float(d) * float(h) - 0.5f;
                int y0 = (int)std::floor(v);
                float fy = v - float(y0);
                int y0c = std::clamp(y0, 0, (int)h - 1);
                int y1c = std::clamp(y0 + 1, 0, (int)h - 1);

                for (uint32_t x = 0; x < d; ++x)
                {
                    float u = (float(x) + 0.5f) / float(d) * float(w) - 0.5f;
                    int x0 = (int)std::floor(u);
                    float fx = u - float(x0);
                    int x0c = std::clamp(x0, 0, (int)w - 1);
                    int x1c = std::clamp(x0 + 1, 0, (int)w - 1);

                    float c00 = src[(size_t)y0c * w + x0c];
                    float c10 = src[(size_t)y0c * w + x1c];
                    float c01 = src[(size_t)y1c * w + x0c];
                    float c11 = src[(size_t)y1c * w + x1c];

                    float c0 = c00 + (c10 - c00) * fx;
                    float c1 = c01 + (c11 - c01) * fx;
                    dst[(size_t)y * d + x] = c0 + (c1 - c0) * fy;
                }
            }
            return dst;
        }
    }

    QuadLightMipSampler::QuadLightMipSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight)
        : QuadLightSampler(QuadLightSamplerType::HierarchicalMip, pDevice, pQuadLight)
    {
        auto luminanceStart = CpuTimer::getCurrentTimePoint();

        uint32_t w = 0, h = 0;
        std::vector<float> luminance = computeQuadLightLuminance(*pQuadLight, w, h);

        auto luminanceEnd = CpuTimer::getCurrentTimePoint();
        logInfo(
            "QuadLightMipSampler: source image load/decode time {:.3f} ms ({}x{})",
            CpuTimer::calcDuration(luminanceStart, luminanceEnd), w, h
        );

        build(w, h, luminance);
    }

    QuadLightMipSampler::QuadLightMipSampler(
        ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance
    )
        : QuadLightSampler(QuadLightSamplerType::HierarchicalMip, pDevice, pQuadLight)
    {
        build(width, height, luminance);
    }

    void QuadLightMipSampler::build(uint32_t w, uint32_t h, const std::vector<float>& luminanceIn)
    {
        std::vector<float> fallback;
        const std::vector<float>* pLuminance = &luminanceIn;
        if (luminanceIn.empty() || w == 0 || h == 0)
        {
            w = h = 1;
            fallback = {1.f};
            pLuminance = &fallback;
        }
        std::vector<float> luminance = *pLuminance; // local, mutable copy - resampleToSquare()/std::move() below may consume it

        auto start = CpuTimer::getCurrentTimePoint();

        // The mip descent assumes an exact quadtree (each mip exactly half the resolution
        // of the level below in both dimensions), so resample onto a power-of-two square.
        uint32_t dim = 1;
        while (dim < std::max(w, h) && dim < 1024) dim *= 2;
        dim = std::max(dim, 2u);

        std::vector<float> base = (w == dim && h == dim) ? std::move(luminance) : resampleToSquare(luminance, w, h, dim);

        // Passing init data together with the default (kMaxPossible) mip-level count makes
        // Texture's constructor auto-generate the full mip chain via hardware mip generation.
        mpImportanceMap = mpDevice->createTexture2D(dim, dim, ResourceFormat::R32Float, 1, Resource::kMaxPossible, base.data(), ResourceBindFlags::ShaderResource);

        Sampler::Desc samplerDesc;
        samplerDesc.setFilterMode(TextureFilteringMode::Point, TextureFilteringMode::Point, TextureFilteringMode::Point);
        samplerDesc.setAddressingMode(TextureAddressingMode::Clamp, TextureAddressingMode::Clamp, TextureAddressingMode::Clamp);
        mpImportanceSampler = mpDevice->createSampler(samplerDesc);

        auto end = CpuTimer::getCurrentTimePoint();
        logInfo("QuadLightMipSampler: build time {:.3f} ms", CpuTimer::calcDuration(start, end));
    }

    void QuadLightMipSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        float2 invDim = 1.f / float2(mpImportanceMap->getWidth(), mpImportanceMap->getHeight());
        var["importanceBaseMip"] = mpImportanceMap->getMipCount() - 1;
        var["importanceInvDim"] = invDim;
        var["importanceMap"] = mpImportanceMap;
        var["importanceSampler"] = mpImportanceSampler;
    }
}
