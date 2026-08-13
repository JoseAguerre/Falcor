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

/** QuadLight importance sampler using a hierarchical mip pyramid, ported from
    EnvMapSampler.slang's quadtree descent. Unlike the env map, this is a planar light
    sampled directly in its own uv space (no octahedral reparameterization).

    The descent only ever compares four sibling texels against each other at each level,
    so it is correct regardless of whether the mip chain was built by summing or averaging
    2x2 blocks (Falcor's hardware generateMips() averages) - see QuadLightMipSampler.cpp.
*/
import Scene.Scene;
__exported import Rendering.Lights.QuadLightSamplerInterface;

struct QuadLightMipSampler : IQuadLightSampler
{
    SamplerState        importanceSampler;      ///< Point sampling with clamp to edge.
    Texture2D<float>    importanceMap;          ///< Hierarchical importance map (entire mip chain).
    float2              importanceInvDim;       ///< 1.0 / dimension of the base (mip 0) level.
    uint                importanceBaseMip;      ///< Mip level for 1x1 resolution.

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};

        if (!gScene.quadLight.isActive()) return false;

        float2 p = rnd;     // Random sample in [0,1)^2, warped along the way.
        uint2 pos = 0;      // Top-left texel pos of current 2x2 region.

        // Iterate over mips of 2x2...NxN resolution.
        for (int mip = int(importanceBaseMip) - 1; mip >= 0; mip--)
        {
            pos *= 2;

            float w[4];
            w[0] = importanceMap.Load(int3(pos, mip));
            w[1] = importanceMap.Load(int3(pos + uint2(1, 0), mip));
            w[2] = importanceMap.Load(int3(pos + uint2(0, 1), mip));
            w[3] = importanceMap.Load(int3(pos + uint2(1, 1), mip));

            float q[2];
            q[0] = w[0] + w[2];
            q[1] = w[1] + w[3];

            uint2 off;

            // Horizontal warp.
            float qSum = q[0] + q[1];
            float d = qSum > 0.f ? q[0] / qSum : 0.5f;

            if (p.x < d)
            {
                off.x = 0;
                p.x = d > 0.f ? p.x / d : 0.f;
            }
            else
            {
                off.x = 1;
                p.x = (1.f - d) > 0.f ? (p.x - d) / (1.f - d) : 0.f;
            }

            // Vertical warp.
            float e = off.x == 0 ? (q[0] > 0.f ? w[0] / q[0] : 0.5f) : (q[1] > 0.f ? w[1] / q[1] : 0.5f);

            if (p.y < e)
            {
                off.y = 0;
                p.y = e > 0.f ? p.y / e : 0.f;
            }
            else
            {
                off.y = 1;
                p.y = (1.f - e) > 0.f ? (p.y - e) / (1.f - e) : 0.f;
            }

            pos += off;
        }

        // Compute final sample position in the base level's uv space.
        float2 uv = ((float2)pos + p) * importanceInvDim;

        float avgW = importanceMap.Load(int3(0, 0, int(importanceBaseMip))); // 1x1 mip holds the mean of the base level.
        float texel = importanceMap[pos];
        if (avgW <= 0.f || texel <= 0.f) return false;

        // Density with respect to uv in [0,1)^2 (texel value normalized by the grid mean),
        // then converted to density with respect to area.
        float pdfUv = texel / avgW;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        result.posW = gScene.quadLight.uvToWorld(uv);
        result.normalW = gScene.quadLight.getNormalW();
        result.pdf = quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, result.posW, result.normalW, gScene.quadLight.isDoubleSided());
        result.Le = gScene.quadLight.eval(uv);

        return result.pdf > 0.f && any(result.Le > 0.f);
    }

    float evalPdf(float3 shadingPosW, float3 hitPosW)
    {
        if (!gScene.quadLight.isActive()) return 0.f;

        float2 uv = gScene.quadLight.worldToUv(hitPosW);
        if (any(uv < 0.f) || any(uv >= 1.f)) return 0.f;

        float avgW = importanceMap.Load(int3(0, 0, int(importanceBaseMip)));
        if (avgW <= 0.f) return 0.f;

        float texel = importanceMap.SampleLevel(importanceSampler, uv, 0);
        if (texel <= 0.f) return 0.f;

        float pdfUv = texel / avgW;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        float3 normalW = gScene.quadLight.getNormalW();
        return quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
