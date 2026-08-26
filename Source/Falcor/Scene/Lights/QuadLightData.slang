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
#include "Utils/HostDeviceShared.slangh"

BEGIN_NAMESPACE_FALCOR

/** This is a host/device structure that describes a textured rectangular area light.

    The light is a quad centered at the local origin, lying in the local XZ plane with
    the surface normal along local +Y (matching TriangleMesh::createQuad's convention),
    spanning [-size.x/2, size.x/2] in local X and [-size.y/2, size.y/2] in local Z.
    `transform` is expected to carry rotation and translation only (no scale) so that the
    same transform can be shared directly with the quad's visible mesh instance, and so
    that `size.x * size.y` is the exact world-space area without needing to inspect the
    transform for a scale factor.
*/
struct QuadLightData
{
    // Field order matters here: HLSL/Slang constant-buffer packing forbids a vector from
    // straddling a 16-byte boundary and silently inserts padding to avoid it, which the
    // plain C++ struct does not replicate. Each float3 below is paired with exactly one
    // trailing scalar to complete its 16-byte slot with no padding, so the C++ and shader
    // layouts stay identical (same idiom as EnvMapData.slang).
    float3x4    transform;              ///< Local to world transform. Must be initialized explicitly (see QuadLight's constructor).
    float3x4    invTransform;           ///< World to local transform. Must be initialized explicitly (see QuadLight's constructor).

    float3      tint = {1.f, 1.f, 1.f}; ///< Color tint.
    float       intensity = 1.f;        ///< Scalar radiance multiplier (matches EnvMapData's intensity/tint split).

    uint        materialID = 0;         ///< MaterialID of the placeholder (non-emissive) material assigned to the quad's geometry, used to identify direct hits.
    uint        active = 0;             ///< True if the light is set up and should be sampled/evaluated.
    float2      size = {1.f, 1.f};      ///< Size of the quad in local space (world size depends on transform scale).

    uint        doubleSided = 0;        ///< If false (default), the light only emits from the side its normal (local +Y) points toward; the back side is dark.
    uint        lightSamplesPerVertex = 1; ///< Number of independent NEE samples of this light to draw and average per path vertex (only when this light is the selected type - see PathTracer.slang). Plain runtime value, not a specialization constant, so changing it doesn't trigger a shader recompile.
    float       maxBsdfHitContribution = 0.f; ///< Caps the radiance contribution added when a BSDF-sampled ray hits this light on a bounced (non-primary) ray only (see PathTracer.slang) - rescales toward the cap preserving hue, rather than clamping the raw texture value, so a legitimately bright but well-sampled feature (e.g. a bright sun texel) is left alone and only pathological low-pdf/high-value outlier samples are affected. Never applied on a camera ray that sees the light directly. 0 (default) disables clamping entirely.
};

END_NAMESPACE_FALCOR
