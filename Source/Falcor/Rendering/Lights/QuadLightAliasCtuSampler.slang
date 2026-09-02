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

/** QuadLight importance sampler using the alias method over a luminance-adaptive quadtree
    of leaf blocks (see QuadLightAliasCtuSampler.cpp for the CPU construction: up to 64x64
    blocks, recursively quartered down to a minimum of 8x8 by luminance coefficient of
    variation).

    Leaves are alias-picked proportional to their total flux (avgLuma * area); the leftover
    fractional randomness from the alias decode (same trick as QuadLightAliasSampler) is
    reused as a uniform position within the chosen leaf's rect. The resulting density is
    therefore piecewise-constant per leaf: weight/weightSum divided by the leaf's own
    uv-space area exactly cancels the area term, leaving a density that depends only on the
    leaf's average luminance - i.e. flat within a leaf, discontinuous across leaf
    boundaries. sample() and evalPdf() both use this same model, so it stays unbiased for
    MIS even though it's a coarser approximation than the per-pixel techniques.
*/
import Scene.Scene;
import Utils.Sampling.AliasTable;
__exported import Rendering.Lights.QuadLightSamplerInterface;

struct QuadLightAliasCtuSampler : IQuadLightSampler
{
    AliasTable                 table;
    StructuredBuffer<float4>   leafRects;      ///< Per-leaf normalized (u0,v0,u1,v1) rects, indexed identically to 'table'.
    // Downsampled by kMinBlock=8 (see QuadLightAliasCtuSampler.cpp's splitBlock()): every
    // leaf boundary is guaranteed 8-aligned, so texel/8 -> leaf index is lossless while
    // using 1/64th the memory and build cost of a full WxH map.
    StructuredBuffer<uint>     leafIndexMap;   ///< ceil(W/8)xceil(H/8) (texel/8) -> leaf index map, for O(1) evalPdf() lookups.
    uint2                      leafIndexMapDim;
    uint2                      gridDim;

    // avgLuma_i = weight_i / (leaf area in texels), derived from the alias table's own
    // weight (avgLuma * area) rather than stored separately.
    float leafAvgLuma(uint leafIdx, float4 rect)
    {
        float weight = table.getWeight(leafIdx);
        float areaTexels = max((rect.z - rect.x) * (rect.w - rect.y) * float(gridDim.x) * float(gridDim.y), 1e-8f);
        return weight / areaTexels;
    }

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};

        if (!gScene.quadLight.isActive()) return false;
        if (table.count == 0 || table.weightSum <= 0.f) return false;

        // Same leftover-randomness reuse as QuadLightAliasSampler: the fractional part
        // left over after picking the alias-table bucket is itself a fresh uniform
        // variate, used here as the (fx, fy) position within the chosen leaf's rect.
        float fCount = float(table.count);
        uint idxA = min(table.count - 1, uint(rnd.x * fCount));
        float fx = rnd.x * fCount - float(idxA);

        AliasTable::Item item = table.items[idxA];
        float threshold = item.getThreshold();

        uint leafIdx;
        float fy;
        if (rnd.y < threshold)
        {
            leafIdx = item.getIndexB();
            fy = rnd.y / max(threshold, 1e-8f);
        }
        else
        {
            leafIdx = item.getIndexA();
            fy = (rnd.y - threshold) / max(1.f - threshold, 1e-8f);
        }

        float weight = table.getWeight(leafIdx);
        if (weight <= 0.f) return false;

        float4 rect = leafRects[leafIdx];
        float2 uv = lerp(rect.xy, rect.zw, float2(fx, fy));

        float avgLuma = leafAvgLuma(leafIdx, rect);
        float pdfUv = avgLuma * float(gridDim.x * gridDim.y) / table.weightSum;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        result.posW = gScene.quadLight.uvToWorld(uv);
        result.normalW = gScene.quadLight.getNormalW(uv);
        result.pdf = quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, result.posW, result.normalW, gScene.quadLight.isDoubleSided());
        result.Le = gScene.quadLight.eval(uv);

        return result.pdf > 0.f && any(result.Le > 0.f);
    }

    float evalPdf(float3 shadingPosW, float3 hitPosW)
    {
        if (!gScene.quadLight.isActive()) return 0.f;
        if (table.count == 0 || table.weightSum <= 0.f) return 0.f;

        float2 uv = gScene.quadLight.worldToUv(hitPosW);
        if (any(uv < 0.f) || any(uv >= 1.f)) return 0.f;

        uint col = clamp(uint(uv.x * float(gridDim.x)), 0u, gridDim.x - 1);
        uint row = clamp(uint(uv.y * float(gridDim.y)), 0u, gridDim.y - 1);
        uint mapCol = min(col / 8, leafIndexMapDim.x - 1);
        uint mapRow = min(row / 8, leafIndexMapDim.y - 1);
        uint leafIdx = leafIndexMap[mapRow * leafIndexMapDim.x + mapCol];

        float weight = table.getWeight(leafIdx);
        if (weight <= 0.f) return 0.f;

        float4 rect = leafRects[leafIdx];
        float avgLuma = leafAvgLuma(leafIdx, rect);
        float pdfUv = avgLuma * float(gridDim.x * gridDim.y) / table.weightSum;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        float3 normalW = gScene.quadLight.getNormalW(uv);
        return quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
