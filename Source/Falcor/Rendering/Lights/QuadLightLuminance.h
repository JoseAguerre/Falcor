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
#include <cstdint>
#include <vector>

namespace Falcor
{
    class QuadLight;

    /** Compute a row-major per-texel luminance array for a QuadLight's source image,
        entirely on the CPU (via Bitmap, reading the same file QuadLight's GPU texture
        was loaded from). Shared by every QuadLightSampler technique that needs raw
        luminance weights (all except QuadLightRandomSampler).

        Uses Rec.709 weights (0.2126, 0.7152, 0.0722), matching Utils/Color/ColorHelpers.slang's
        shader-side luminance() exactly, and reads the raw decoded bytes with no gamma
        correction - consistent with QuadLight::createFromFile loading with loadAsSrgb=false,
        so the GPU shader also samples these bytes as linear.

        \param[in] light The quad light whose source image should be read.
        \param[out] outWidth Image width in texels.
        \param[out] outHeight Image height in texels.
        \return Row-major luminance array of size outWidth*outHeight. Empty on failure.
    */
    FALCOR_API std::vector<float> computeQuadLightLuminance(const QuadLight& light, uint32_t& outWidth, uint32_t& outHeight);
}
