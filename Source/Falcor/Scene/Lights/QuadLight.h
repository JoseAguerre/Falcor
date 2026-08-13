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
#include "QuadLightData.slang"
#include "Core/Macros.h"
#include "Core/Object.h"
#include "Core/API/Texture.h"
#include "Core/API/Sampler.h"
#include "Scene/SceneIDs.h"
#include "Utils/Math/Vector.h"
#include "Utils/Math/Matrix.h"
#include "Utils/UI/Gui.h"
#include <memory>
#include <filesystem>

namespace Falcor
{
    struct ShaderVar;

    /** Textured rectangular area light.
        A unit quad in local space (see QuadLightData), placed in world space by a transform,
        emitting radiance sampled from a texture. Intended to be a real, hittable piece of
        scene geometry (assigned a non-emissive placeholder material, identified at hit time
        via materialID) so it is excluded from the standard emissive-triangle light pipeline
        and instead sampled by a dedicated QuadLightSampler.
    */
    class FALCOR_API QuadLight : public Object
    {
        FALCOR_OBJECT(QuadLight)
    public:
        virtual ~QuadLight() = default;

        /** Create a new quad light.
            \param[in] pDevice GPU device.
            \param[in] texture The light's emission texture.
        */
        static ref<QuadLight> create(ref<Device> pDevice, const ref<Texture>& texture);

        /** Create a new quad light from file.
            \param[in] pDevice GPU device.
            \param[in] path The texture file path (absolute or relative to working directory).
            \return A new object, or nullptr if the texture failed to load.
        */
        static ref<QuadLight> createFromFile(ref<Device> pDevice, const std::filesystem::path& path);

        /** Render the GUI.
        */
        void renderUI(Gui::Widgets& widgets);

        /** Set the local-to-world transform. The full affine transform (including translation) is stored.
        */
        void setTransform(const float4x4& matrix);

        /** Get the local-to-world transform.
        */
        float4x4 getTransform() const { return float4x4(mData.transform); }

        /** Set the quad's size in local space (full width/height, matching TriangleMesh::createQuad's
            size parameter). The quad's transform should carry no scale (see QuadLightData) so that
            this is the exact world-space size.
        */
        void setSize(const float2& size) { mData.size = size; }

        /** Get the quad's local-space size.
        */
        float2 getSize() const { return mData.size; }

        /** Set intensity (scalar multiplier, independent of color tint).
        */
        void setIntensity(float intensity);

        /** Get intensity.
        */
        float getIntensity() const { return mData.intensity; }

        /** Set color tint (rgb multiplier).
        */
        void setTint(const float3& tint);

        /** Get color tint.
        */
        float3 getTint() const { return mData.tint; }

        /** Set the materialID of the placeholder material assigned to the quad's mesh instance.
            Used at hit time to identify direct hits on this light's geometry.
        */
        void setMaterialID(MaterialID materialID) { mData.materialID = materialID.getSlang(); }

        /** Get the materialID of the quad's placeholder material.
        */
        MaterialID getMaterialID() const { return MaterialID{mData.materialID}; }

        /** Set whether the light emits from both faces. Default is false: only the side
            the normal (local +Y) points toward is lit, the back side is dark.
        */
        void setDoubleSided(bool doubleSided) { mData.doubleSided = doubleSided ? 1 : 0; }

        /** Get whether the light emits from both faces.
        */
        bool getDoubleSided() const { return mData.doubleSided != 0; }

        /** Get the file path of the light's texture.
        */
        const std::filesystem::path& getPath() const { return mpTexture->getSourcePath(); }

        const ref<Texture>& getTexture() const { return mpTexture; }
        const ref<Sampler>& getSampler() const { return mpSampler; }

        /** Get the world-space area of the quad (accounts for transform scale).
        */
        float getArea() const;

        /** Bind the quad light to a given shader variable.
            \param[in] var Shader variable.
        */
        void bindShaderData(const ShaderVar& var) const;

        enum class Changes
        {
            None            = 0x0,
            Transform       = 0x1,
            Intensity       = 0x2,
        };

        /** Begin frame. Should be called once at the start of each frame.
        */
        Changes beginFrame();

        /** Get the quad light changes that happened since the previous frame.
        */
        Changes getChanges() const { return mChanges; }

        /** Get the total GPU memory usage in bytes.
        */
        uint64_t getMemoryUsageInBytes() const;

    protected:
        QuadLight(ref<Device> pDevice, const ref<Texture>& texture);

        ref<Device>             mpDevice;
        ref<Texture>            mpTexture;          ///< Emission texture (RGB).
        ref<Sampler>            mpSampler;          ///< Texture sampler.

        QuadLightData            mData;
        QuadLightData            mPrevData;

        Changes                 mChanges = Changes::None;

        friend class Scene;
        friend class SceneCache;
    };

    FALCOR_ENUM_CLASS_OPERATORS(QuadLight::Changes);
}
