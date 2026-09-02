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
#include "QuadLightSamplerType.slangh"
__exported import Rendering.Lights.QuadLightSamplerInterface;

/** The host sets the _QUAD_LIGHT_SAMPLER_TYPE define to select which technique to use.

    This code typedefs the chosen type to the type 'QuadLightSampler'. All quad light
    samplers adhere to the same interface (IQuadLightSampler), but note that the size of
    the 'QuadLightSampler' type may vary depending on the type. Mirrors
    EmissiveLightSampler.slang's role for the emissive-triangle sampler family.
*/

// If _QUAD_LIGHT_SAMPLER_TYPE is not defined, define it to the null sampler.
// This case happens if the user imports QuadLightSampler.slang but doesn't use it.
// This is a workaround to avoid compiler warnings since Slang warns on undefined
// preprocessor defines even if they are inside #ifdef .. #endif blocks.
#ifndef _QUAD_LIGHT_SAMPLER_TYPE
#define _QUAD_LIGHT_SAMPLER_TYPE QUAD_LIGHT_SAMPLER_NULL
#endif

#if _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_RANDOM
    import Rendering.Lights.QuadLightRandomSampler;
    typedef QuadLightRandomSampler QuadLightSampler;

#elif _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_CDF_2D || \
      _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_CDF_2D_DIV8 || \
      _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_CDF_2D_DIV16 || \
      _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_CDF_2D_DIV32
    // Cdf2DDiv8/16/32 reuse this exact same shader type: the CDF grid's resolution is a
    // purely CPU-side build-time choice (see QuadLightCdfSampler.cpp/.h) that this code
    // never sees - it only ever reads whatever gridDim was bound (see
    // QuadLightCdfSampler.slang), so there's nothing here to specialize on.
    import Rendering.Lights.QuadLightCdfSampler;
    typedef QuadLightCdfSampler QuadLightSampler;

#elif _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_HIERARCHICAL_MIP
    import Rendering.Lights.QuadLightMipSampler;
    typedef QuadLightMipSampler QuadLightSampler;

#elif _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_ALIAS_PER_PIXEL
    import Rendering.Lights.QuadLightAliasSampler;
    typedef QuadLightAliasSampler QuadLightSampler;

#elif _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_ALIAS_CTU
    import Rendering.Lights.QuadLightAliasCtuSampler;
    typedef QuadLightAliasCtuSampler QuadLightSampler;

#elif _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_BUDGET_LEAF_ALIAS
    import Rendering.Lights.QuadLightBudgetLeafAliasSampler;
    typedef QuadLightBudgetLeafAliasSampler QuadLightSampler;

#elif _QUAD_LIGHT_SAMPLER_TYPE == QUAD_LIGHT_SAMPLER_NULL

    /** Null sampler.
        This is provided so that implementations always have a valid sampler struct.
    */
    struct NullQuadLightSampler : IQuadLightSampler
    {
        bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
        {
            result = {};
            return false;
        }

        float evalPdf(float3 shadingPosW, float3 hitPosW)
        {
            return 0.f;
        }

        int _dummy; // Dummy variable to make sure Slang doesn't remove the struct.
    };
    typedef NullQuadLightSampler QuadLightSampler;

#else
    // Compile-time error if _QUAD_LIGHT_SAMPLER_TYPE is an invalid type.
    #error _QUAD_LIGHT_SAMPLER_TYPE is not set to a supported type. See QuadLightSamplerType.slangh.

#endif
