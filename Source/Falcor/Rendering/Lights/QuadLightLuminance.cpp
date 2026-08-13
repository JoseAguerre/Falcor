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
#include "QuadLightLuminance.h"
#include "Scene/Lights/QuadLight.h"
#include "Utils/Image/Bitmap.h"
#include "Utils/Logger.h"
#include "Utils/Math/ScalarTypes.h"

#include <cmath>

namespace Falcor
{
    namespace
    {
        constexpr float kLumR = 0.2126f;
        constexpr float kLumG = 0.7152f;
        constexpr float kLumB = 0.0722f;

        inline float unormToFloat(uint8_t v) { return float(v) * (1.f / 255.f); }
        inline float unormToFloat(uint16_t v) { return float(v) * (1.f / 65535.f); }
    }

    std::vector<float> computeQuadLightLuminance(const QuadLight& light, uint32_t& outWidth, uint32_t& outHeight)
    {
        outWidth = 0;
        outHeight = 0;

        // isTopDown=true matches Texture::createFromFile's kTopDown (Texture.cpp), so this
        // decodes the exact same bytes that were uploaded to the GPU texture.
        auto pBitmap = Bitmap::createFromFile(light.getPath(), true);
        if (!pBitmap)
        {
            logWarning("QuadLight: failed to re-read source image '{}' for CPU luminance computation.", light.getPath());
            return {};
        }

        const uint32_t w = pBitmap->getWidth();
        const uint32_t h = pBitmap->getHeight();
        const uint32_t rowPitch = pBitmap->getRowPitch();
        const uint8_t* pData = pBitmap->getData();

        std::vector<float> luminance((size_t)w * h, 0.f);

        auto forEachPixel = [&](auto&& readPixelLuminance)
        {
            for (uint32_t y = 0; y < h; ++y)
            {
                const uint8_t* pRow = pData + (size_t)y * rowPitch;
                float* pOutRow = luminance.data() + (size_t)y * w;
                for (uint32_t x = 0; x < w; ++x)
                {
                    pOutRow[x] = readPixelLuminance(pRow, x);
                }
            }
        };

        switch (pBitmap->getFormat())
        {
        case ResourceFormat::RGBA32Float:
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const float* p = reinterpret_cast<const float*>(pRow) + (size_t)x * 4;
                    return kLumR * p[0] + kLumG * p[1] + kLumB * p[2];
                }
            );
            break;
        case ResourceFormat::RGB32Float:
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const float* p = reinterpret_cast<const float*>(pRow) + (size_t)x * 3;
                    return kLumR * p[0] + kLumG * p[1] + kLumB * p[2];
                }
            );
            break;
        case ResourceFormat::RGBA16Float:
            // Bitmap converts any float-per-channel EXR whose channels are all stored as
            // OpenEXR HALF (the common case - see Bitmap.cpp's isFloat16Exr()/
            // convertToRGBA16Float()) into this format, R/G/B/A order (unlike the 8-bit
            // legacy path below, there's no BGRA swap here). This is a genuinely different,
            // unbounded floating-point format from RGBA16Unorm just below - easy to conflate
            // by name, but not interchangeable.
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const float16_t* p = reinterpret_cast<const float16_t*>(pRow) + (size_t)x * 4;
                    return kLumR * p[0] + kLumG * p[1] + kLumB * p[2];
                }
            );
            break;
        case ResourceFormat::RGBA16Unorm:
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const uint16_t* p = reinterpret_cast<const uint16_t*>(pRow) + (size_t)x * 4;
                    return kLumR * unormToFloat(p[0]) + kLumG * unormToFloat(p[1]) + kLumB * unormToFloat(p[2]);
                }
            );
            break;
        case ResourceFormat::BGRA8Unorm:
        case ResourceFormat::BGRA8UnormSrgb:
        case ResourceFormat::BGRX8Unorm:
        case ResourceFormat::BGRX8UnormSrgb:
            // Note the B/G/R order - Bitmap decodes typical 8-bit PNG/JPG sources into BGRA
            // (or BGRX for opaque sources with no alpha channel, e.g. most JPEGs), not RGBA.
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const uint8_t* p = pRow + (size_t)x * 4;
                    return kLumR * unormToFloat(p[2]) + kLumG * unormToFloat(p[1]) + kLumB * unormToFloat(p[0]);
                }
            );
            break;
        case ResourceFormat::RG8Unorm:
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const uint8_t* p = pRow + (size_t)x * 2;
                    // No blue channel available; treat as a 2-channel image (rare for light textures).
                    return kLumR * unormToFloat(p[0]) + kLumG * unormToFloat(p[1]);
                }
            );
            break;
        case ResourceFormat::R16Unorm:
            forEachPixel(
                [](const uint8_t* pRow, uint32_t x)
                {
                    const uint16_t* p = reinterpret_cast<const uint16_t*>(pRow) + x;
                    return unormToFloat(p[0]);
                }
            );
            break;
        case ResourceFormat::R8Unorm:
            forEachPixel([](const uint8_t* pRow, uint32_t x) { return unormToFloat(pRow[x]); });
            break;
        default:
            logWarning(
                "QuadLight: source image '{}' decoded to an unsupported format ({}) for CPU luminance computation; treating as uniform.",
                light.getPath(), uint32_t(pBitmap->getFormat())
            );
            std::fill(luminance.begin(), luminance.end(), 1.f);
            break;
        }

        // Sanitize non-finite/negative texels - real-world HDR sources occasionally contain
        // NaN/Inf pixels (e.g. artifacts from HDR merging or specular fireflies baked into
        // the file). Left unchecked, a single bad texel poisons every technique's
        // precomputed structure: CDF/marginal running sums, the mip pyramid (NaN propagates
        // upward through box filtering, corrupting the 1x1 normalization mip), and the
        // alias table's weight sum are all a single running accumulation away from NaN
        // contaminating the entire sampler.
        uint32_t numInvalid = 0;
        for (float& l : luminance)
        {
            if (!std::isfinite(l) || l < 0.f)
            {
                l = 0.f;
                ++numInvalid;
            }
        }
        if (numInvalid > 0)
        {
            logWarning(
                "QuadLight: source image '{}' contained {} non-finite/negative luminance texel(s); treated as black.",
                light.getPath(), numInvalid
            );
        }

        outWidth = w;
        outHeight = h;
        return luminance;
    }
}
