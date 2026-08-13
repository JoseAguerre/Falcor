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
#include "QuadLight.h"
#include "Core/API/Device.h"
#include "Core/Program/ShaderVar.h"
#include "Utils/Scripting/ScriptBindings.h"
#include "GlobalState.h"

namespace Falcor
{
    ref<QuadLight> QuadLight::create(ref<Device> pDevice, const ref<Texture>& pTexture)
    {
        return ref<QuadLight>(new QuadLight(pDevice, pTexture));
    }

    ref<QuadLight> QuadLight::createFromFile(ref<Device> pDevice, const std::filesystem::path& path)
    {
        auto pTexture = Texture::createFromFile(pDevice, path, true, false);
        if (!pTexture) return nullptr;
        return create(pDevice, pTexture);
    }

    void QuadLight::renderUI(Gui::Widgets& widgets)
    {
        widgets.var("Size", mData.size, 0.001f, FLT_MAX, 0.01f);
        widgets.var("Intensity", mData.intensity, 0.f, 1000000.f);
        widgets.var("Color tint", mData.tint, 0.f, 1.f);
        widgets.text("QuadLight: " + mpTexture->getSourcePath().string());
        widgets.text(fmt::format("Resolution: {}x{}", mpTexture->getWidth(), mpTexture->getHeight()));
    }

    void QuadLight::setTransform(const float4x4& matrix)
    {
        mData.transform = float3x4(matrix);
        mData.invTransform = float3x4(inverse(matrix));
    }

    void QuadLight::setIntensity(float intensity)
    {
        mData.intensity = intensity;
    }

    void QuadLight::setTint(const float3& tint)
    {
        mData.tint = tint;
    }

    float QuadLight::getArea() const
    {
        return mData.size.x * mData.size.y;
    }

    void QuadLight::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());

        // Set variables.
        var["data"].setBlob(mData);

        // Bind resources.
        var["tex"].setTexture(mpTexture);
        var["sampler"].setSampler(mpSampler);
    }

    QuadLight::Changes QuadLight::beginFrame()
    {
        mChanges = Changes::None;

        if (mData.transform != mPrevData.transform) mChanges |= Changes::Transform;
        if (mData.intensity != mPrevData.intensity) mChanges |= Changes::Intensity;
        if (any(mData.tint != mPrevData.tint)) mChanges |= Changes::Intensity;

        mPrevData = mData;

        return getChanges();
    }

    uint64_t QuadLight::getMemoryUsageInBytes() const
    {
        return mpTexture ? mpTexture->getTextureSizeInBytes() : 0;
    }

    QuadLight::QuadLight(ref<Device> pDevice, const ref<Texture>& pTexture)
        : mpDevice(pDevice)
    {
        FALCOR_CHECK(mpDevice != nullptr, "'pDevice' must be a valid device");
        FALCOR_CHECK(pTexture != nullptr, "'pTexture' must be a valid texture");

        mpTexture = pTexture;

        // Identity transform (rotation+translation only, no scale - see QuadLightData).
        mData.transform = float3x4(float4x4::identity());
        mData.invTransform = float3x4(float4x4::identity());
        mData.active = 1;
        mPrevData = mData;

        Sampler::Desc samplerDesc;
        samplerDesc.setFilterMode(TextureFilteringMode::Linear, TextureFilteringMode::Linear, TextureFilteringMode::Linear);
        samplerDesc.setAddressingMode(TextureAddressingMode::Clamp, TextureAddressingMode::Clamp, TextureAddressingMode::Clamp);
        mpSampler = mpDevice->createSampler(samplerDesc);
    }

    FALCOR_SCRIPT_BINDING(QuadLight)
    {
        using namespace pybind11::literals;

        pybind11::class_<QuadLight, ref<QuadLight>> quadLight(m, "QuadLight");
        auto createFromFile = [](const std::filesystem::path& path)
        {
            ref<QuadLight> light = QuadLight::createFromFile(accessActivePythonSceneBuilder().getDevice(), getActiveAssetResolver().resolvePath(path));
            if (!light)
                FALCOR_THROW("Failed to load quad light texture from '{}'.", path);
            return light;
        };
        quadLight.def_static("createFromFile", createFromFile, "path"_a);
        quadLight.def_property_readonly("path", &QuadLight::getPath);
        quadLight.def_property("transform", &QuadLight::getTransform, &QuadLight::setTransform);
        quadLight.def_property("intensity", &QuadLight::getIntensity, &QuadLight::setIntensity);
        quadLight.def_property("tint", &QuadLight::getTint, &QuadLight::setTint);
        quadLight.def_property(
            "size", [](const QuadLight& light) { return light.getSize(); }, [](QuadLight& light, float2 size) { light.setSize(size); }
        );
        quadLight.def_property(
            "materialID",
            [](const QuadLight& light) { return light.getMaterialID().getSlang(); },
            [](QuadLight& light, uint32_t id) { light.setMaterialID(MaterialID{id}); }
        );
        quadLight.def_property("doubleSided", &QuadLight::getDoubleSided, &QuadLight::setDoubleSided);
    }
}
