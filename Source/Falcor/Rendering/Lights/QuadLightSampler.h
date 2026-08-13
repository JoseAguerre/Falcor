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
#include "QuadLightSamplerType.slangh"
#include "Core/Macros.h"
#include "Core/Program/DefineList.h"
#include "Scene/Lights/QuadLight.h"
#include <memory>

namespace Falcor
{
    class RenderContext;
    struct ShaderVar;

    /** Base class for QuadLight importance-sampling technique implementations.

        All techniques follow the same interface (see QuadLightSamplerInterface.slang for
        the shader-side counterpart) to make them interchangeable at runtime. Mirrors
        EmissiveLightSampler's role for the emissive-triangle sampler family.

        Owned by PathTracer, not by Scene - mirrors EnvMapSampler's relationship to EnvMap.
    */
    class FALCOR_API QuadLightSampler
    {
    public:
        virtual ~QuadLightSampler() = default;

        /** Bind the light sampler data to a given shader var.
        */
        virtual void bindShaderData(const ShaderVar& var) const = 0;

        /** Return the shader defines needed to select this technique in QuadLightSampler.slang.
        */
        virtual DefineList getDefines() const;

        /** Returns the type of quad light sampler.
        */
        QuadLightSamplerType getType() const { return mType; }

        const ref<QuadLight>& getQuadLight() const { return mpQuadLight; }

    protected:
        QuadLightSampler(QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight)
            : mType(type), mpDevice(pDevice), mpQuadLight(pQuadLight)
        {}

        const QuadLightSamplerType mType;
        ref<Device>                mpDevice;
        ref<QuadLight>             mpQuadLight;
    };

    /** Construct the concrete QuadLightSampler for the given technique.
        \param[in] type Which technique to construct.
        \param[in] pDevice GPU device.
        \param[in] pQuadLight The quad light to sample.
    */
    FALCOR_API std::unique_ptr<QuadLightSampler> createQuadLightSampler(QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight);
}
