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
import Scene.Lights.QuadLightData;

/** Struct for accessing a textured rectangular area light.

    The quad lies in the local XZ plane centered at the local origin, normal along local +Y
    (matching TriangleMesh::createQuad), spanning [-size.x/2,size.x/2] x [-size.y/2,size.y/2].
    `transform` is expected to carry rotation+translation only (no scale).
*/
struct QuadLight
{
    Texture2D       tex;            ///< Emission texture.
    SamplerState    sampler;        ///< Texture sampler.

    QuadLightData   data;           ///< Quad light data.

    /** World-space area of the quad. Exact since `transform` carries no scale.
    */
    float getArea()
    {
        return data.size.x * data.size.y;
    }

    /** World-space (unit-length) normal of the quad.
    */
    float3 getNormalW()
    {
        return normalize(mul((float3x3)data.transform, float3(0, 1, 0)));
    }

    /** Evaluates the radiance at a given uv coordinate, uv in [0,1)^2.
    */
    float3 eval(float2 uv, float lod = 0.f)
    {
        return tex.SampleLevel(sampler, uv, lod).rgb * getIntensity();
    }

    /** EXPERIMENTAL: the precomputed average of eval() over the whole texture (see
        QuadLightData::useAvgEmissionOnDiffuseBsdfHit) - same tint/intensity scaling as eval(),
        just a flat value instead of a per-uv texture sample.
    */
    float3 evalAverage()
    {
        return data.avgEmission * getIntensity();
    }

    /** True if a BSDF-sampled hit on this light whose last scatter event was diffuse/rough
        should use evalAverage() instead of eval() (see QuadLightData::useAvgEmissionOnDiffuseBsdfHit).
    */
    bool useAvgEmissionOnDiffuseBsdfHit()
    {
        return data.useAvgEmissionOnDiffuseBsdfHit != 0;
    }

    /** Transform a local-space uv coordinate ([0,1)^2) to a world-space position.
        v=0 is the top row of the source texture (standard image convention), which maps
        to local +Z (screen "up") - i.e. the v axis is flipped relative to local Z.
    */
    float3 uvToWorld(float2 uv)
    {
        float3 posL = float3((uv.x - 0.5f) * data.size.x, 0.f, (0.5f - uv.y) * data.size.y);
        return mul(data.transform, float4(posL, 1.f));
    }

    /** Transform a world-space position (assumed to lie on the quad's plane) to a local-space uv coordinate.
    */
    float2 worldToUv(float3 posW)
    {
        float3 posL = mul(data.invTransform, float4(posW, 1.f));
        return float2(posL.x / data.size.x + 0.5f, 0.5f - posL.z / data.size.y);
    }

    /** Get the intensity scaling factor (including tint).
    */
    float3 getIntensity()
    {
        return data.intensity * data.tint;
    }

    /** True if the light is set up and should be sampled/evaluated.
    */
    bool isActive()
    {
        return data.active != 0;
    }

    /** True if the light emits from both faces.
    */
    bool isDoubleSided()
    {
        return data.doubleSided != 0;
    }

    /** Number of independent NEE samples of this light to draw and average per path
        vertex (only applies when this light is the selected type - see PathTracer.slang).
    */
    uint getLightSamplesPerVertex()
    {
        return data.lightSamplesPerVertex;
    }
};
