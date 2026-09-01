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
#include <vector>

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

        /** Render technique-specific UI (e.g. tunable parameters, diagnostics). Default is a no-op.
            \return True if a setting changed that requires re-binding shader data (defines are unaffected either way - see getDefines()).
        */
        virtual bool renderUI(Gui::Widgets& widget) { return false; }

        /** Returns the type of quad light sampler.
        */
        QuadLightSamplerType getType() const { return mType; }

        /** Returns a new strong reference to the owning quad light. Stored internally as a
            raw, non-owning pointer rather than a ref<QuadLight> - a QuadLightSampler can be
            kept alive by structures that are themselves (transitively) owned by that same
            QuadLight (e.g. QuadLightVideoPlayer's prefetch ring, see QuadLightVideo.cpp),
            and a stored strong ref back would create an ownership cycle, leaking the
            QuadLight (and any thread it owns) forever. Safe because a QuadLightSampler's
            lifetime is always bounded by its owning QuadLight's lifetime, whether owned
            directly by PathTracer (which drops its sampler before the scene's QuadLight ref
            - see PathTracer::setScene()) or transitively via the QuadLight itself.
        */
        ref<QuadLight> getQuadLight() const { return ref<QuadLight>(mpQuadLight); }

    protected:
        QuadLightSampler(QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight)
            : mType(type), mpDevice(pDevice), mpQuadLight(pQuadLight.get())
        {}

        const QuadLightSamplerType mType;
        ref<Device>                mpDevice;
        QuadLight*                 mpQuadLight; ///< Non-owning - see getQuadLight()'s comment.
    };

    /** Construct the concrete QuadLightSampler for the given technique.
        Decodes pQuadLight's source image itself (via computeQuadLightLuminance()).
        \param[in] type Which technique to construct.
        \param[in] pDevice GPU device.
        \param[in] pQuadLight The quad light to sample.
    */
    FALCOR_API std::unique_ptr<QuadLightSampler> createQuadLightSampler(QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight);

    /** Construct the concrete QuadLightSampler for the given technique, from an
        already-computed luminance array - skips the decode, for callers (e.g. video
        playback prefetch) that already have one on hand from building the GPU texture, so
        the same source image isn't decoded twice. QuadLightSamplerType::Random ignores
        width/height/luminance entirely (it never uses luminance data).
        \param[in] type Which technique to construct.
        \param[in] pDevice GPU device.
        \param[in] pQuadLight The quad light to sample.
        \param[in] width Luminance array width in texels.
        \param[in] height Luminance array height in texels.
        \param[in] luminance Row-major luminance array of size width*height.
    */
    FALCOR_API std::unique_ptr<QuadLightSampler> createQuadLightSamplerFromLuminance(
        QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance
    );
}
