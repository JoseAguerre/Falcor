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
#include "QuadLightVideo.h"
#include "Rendering/Lights/QuadLightSampler.h"
#include "Core/API/Device.h"
#include "Core/Platform/OS.h"
#include "Core/Program/ShaderVar.h"
#include "Utils/Image/Bitmap.h"
#include "Utils/Scripting/ScriptBindings.h"
#include "GlobalState.h"

#include <algorithm>

namespace Falcor
{
    namespace
    {
        // QuadLightPlaylist/QuadLightVideoPlayer are themselves format-agnostic (every frame
        // is decoded via Bitmap::createFromFile, which auto-detects format from file
        // content) - the extension only matters here, to distinguish "this path is a
        // playlist of frames" from "this path is a single static image".
        bool isPlaylistPath(const std::filesystem::path& path)
        {
            return path.extension() == ".exrplaylist" || path.extension() == ".hdrplaylist";
        }
    }

    QuadLight::~QuadLight() = default;

    ref<QuadLight> QuadLight::create(ref<Device> pDevice, const ref<Texture>& pTexture)
    {
        return ref<QuadLight>(new QuadLight(pDevice, pTexture));
    }

    ref<QuadLight> QuadLight::createFromFile(ref<Device> pDevice, const std::filesystem::path& path)
    {
        if (isPlaylistPath(path))
        {
            auto playlist = QuadLightPlaylist::parseFile(path);
            if (!playlist) return nullptr;

            // create() requires a non-null texture up front, but QuadLightVideoPlayer needs
            // a ref<QuadLight> owner that doesn't exist until after construction - decode
            // frame 0 once here just to satisfy that, then let the player redundantly (but
            // only this one time, at load) reload the same frame via primeFirstFrame() once
            // it exists. A one-time extra decode at scene-load time, traded for not needing
            // a second "already-loaded" constructor path on the player.
            // QuadLight::eval() always samples mip 0 (see QuadLight.slang) - a full mip chain
            // is pure wasted GPU work here, so mip generation is disabled.
            auto pTexture = Texture::createFromFile(pDevice, playlist->entries()[0].path, false, false);
            if (!pTexture) return nullptr;

            ref<QuadLight> pLight = create(pDevice, pTexture);
            pLight->mpVideoPlayer = std::make_unique<QuadLightVideoPlayer>(pDevice, pLight, std::move(*playlist), pLight->mSamplerType);
            pLight->mpVideoPlayer->primeFirstFrame();
            pLight->mpTexture = pLight->mpVideoPlayer->getCurrentTexture();
            pLight->mpPendingSampler = pLight->mpVideoPlayer->takeCurrentSampler();
            return pLight;
        }

        // QuadLight::eval() always samples mip 0 (see QuadLight.slang) - a full mip chain
        // is pure wasted GPU work here, so mip generation is disabled.
        auto pTexture = Texture::createFromFile(pDevice, path, false, false);
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

        if (isVideo())
        {
            widgets.text(fmt::format("Video: frame {}/{}", getVideoFrameIndex() + 1, getVideoFrameCount()));
        }

        if (widgets.button("Load Image"))
        {
            std::filesystem::path path;
            // Unlike EnvMap (typically HDR-only), QuadLight textures are commonly LDR
            // (png/jpg) - pass Unknown so the dialog lists both LDR and HDR extensions
            // (.hdr is already included by getFileDialogFilters() below). Also list the two
            // playlist extensions so a video playlist is directly browsable/selectable, not
            // just loadable by typing a path.
            auto filters = Bitmap::getFileDialogFilters(ResourceFormat::Unknown);
            filters.push_back({"exrplaylist", "EXR Playlist"});
            filters.push_back({"hdrplaylist", "HDR Playlist"});
            if (openFileDialog(filters, path))
            {
                if (!loadTextureFromFile(path))
                {
                    msgBox("Error", fmt::format("Failed to load quad light texture from '{}'.", path), MsgBoxType::Ok, MsgBoxIcon::Warning);
                }
            }
        }

        widgets.dropdown("Sampler", mSamplerType);
        widgets.tooltip("Selects which importance-sampling technique to use for this quad light.", true);

        widgets.var("Light samples/vertex", mData.lightSamplesPerVertex, 1u, 64u, 1u);
        widgets.tooltip(
            "Number of independent shadow-ray samples of this quad light to draw and average "
            "per path vertex. Reduces noise from this light specifically without re-tracing "
            "the whole path (unlike raising the pass's Samples Per Pixel), at the cost of one "
            "extra shadow ray per additional sample. Only applies on samples where the quad "
            "light is the stochastically-selected light type - other light types always draw "
            "exactly one sample.",
            true
        );
    }

    bool QuadLight::loadTextureFromFile(const std::filesystem::path& path)
    {
        if (isPlaylistPath(path))
        {
            auto playlist = QuadLightPlaylist::parseFile(path);
            if (!playlist) return false;

            mpVideoPlayer = std::make_unique<QuadLightVideoPlayer>(mpDevice, ref<QuadLight>(this), std::move(*playlist), mSamplerType);
            mpVideoPlayer->primeFirstFrame();
            mpTexture = mpVideoPlayer->getCurrentTexture();
            mpPendingSampler = mpVideoPlayer->takeCurrentSampler();
            mTextureChanged = true;
            return true;
        }

        mpVideoPlayer = nullptr; // switching back to a static image tears down any previous video player
        // QuadLight::eval() always samples mip 0 (see QuadLight.slang) - a full mip chain
        // is pure wasted GPU work here, so mip generation is disabled.
        auto pTexture = Texture::createFromFile(mpDevice, path, false, false);
        if (!pTexture) return false;

        mpTexture = pTexture;
        mTextureChanged = true;
        return true;
    }

    void QuadLight::updateVideoPlayback(double currentTime)
    {
        if (!mpVideoPlayer) return;

        mpVideoPlayer->tick(currentTime);
        if (mpVideoPlayer->consumeAdvanced())
        {
            mpTexture = mpVideoPlayer->getCurrentTexture();
            mpPendingSampler = mpVideoPlayer->takeCurrentSampler();
            mTextureChanged = true; // reuses the existing Changes::Texture / QuadLightChanged / AccumulatePass reset pipeline verbatim.
        }
    }

    std::unique_ptr<QuadLightSampler> QuadLight::takePrebuiltSampler()
    {
        return std::move(mpPendingSampler);
    }

    uint32_t QuadLight::getVideoFrameIndex() const
    {
        return mpVideoPlayer ? mpVideoPlayer->getPlaybackIndex() : 0;
    }

    uint32_t QuadLight::getVideoFrameCount() const
    {
        return mpVideoPlayer ? mpVideoPlayer->getPlaylistSize() : 0;
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

    void QuadLight::setLightSamplesPerVertex(uint32_t count)
    {
        mData.lightSamplesPerVertex = std::clamp(count, 1u, 64u);
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
        if (mData.lightSamplesPerVertex != mPrevData.lightSamplesPerVertex) mChanges |= Changes::Intensity;
        if (mSamplerType != mPrevSamplerType)
        {
            mChanges |= Changes::SamplerType;
            if (mpVideoPlayer) mpVideoPlayer->onSamplerTypeChanged(mSamplerType);
        }
        if (mTextureChanged) mChanges |= Changes::Texture;

        mPrevData = mData;
        mPrevSamplerType = mSamplerType;
        mTextureChanged = false;

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
        quadLight.def_property("samplerType", &QuadLight::getSamplerType, &QuadLight::setSamplerType);
        quadLight.def_property("lightSamplesPerVertex", &QuadLight::getLightSamplesPerVertex, &QuadLight::setLightSamplesPerVertex);
    }
}
