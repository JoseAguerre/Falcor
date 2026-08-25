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
#include "Core/API/Sampler.h"
#include <vector>

namespace Falcor
{
    /** QuadLight sampler using a hierarchical importance mip pyramid, ported from
        EnvMapSampler's approach (see EnvMapSampler.slang) but simplified: since the light
        is planar, no octahedral reparameterization is needed - the pyramid is built
        directly over the quad's own uv space.

        The base level is the source luminance resampled (bilinearly, on the CPU) to a
        power-of-two square so the mip descent's implicit assumption - each mip is exactly
        half the resolution of the level below - holds exactly. The rest of the pyramid is
        built via Falcor's hardware mip generation (a box-filter average, not a sum - this
        doesn't affect the descent, which only ever compares sibling texels at a given
        level; see QuadLightMipSampler.slang).
    */
    class FALCOR_API QuadLightMipSampler : public QuadLightSampler
    {
    public:
        /** Decodes pQuadLight's source image itself (via computeQuadLightLuminance()) before building. */
        QuadLightMipSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight);

        /** Builds directly from an already-computed luminance array, skipping the decode -
            for callers (e.g. video playback prefetch) that already have one on hand from
            building the GPU texture, so the same source image isn't decoded twice.
        */
        QuadLightMipSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance);

        void bindShaderData(const ShaderVar& var) const override;

    private:
        void build(uint32_t width, uint32_t height, const std::vector<float>& luminance);

        ref<Texture> mpImportanceMap;      ///< Hierarchical importance map (luminance), entire mip chain.
        ref<Sampler> mpImportanceSampler;  ///< Point sampling with clamp to edge.
    };
}
