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

/** QuadLight importance sampler using the alias method (Vose's algorithm) over the
    per-texel luminance grid, via Falcor's generic Utils.Sampling.AliasTable.

    The table's own sample(float2) consumes both random numbers just to pick a discrete
    texel, leaving nothing to place a continuous position within it. Instead we decode the
    table manually here so the leftover fractional randomness - which is itself a fresh,
    independent uniform variate (the same "stratified reuse" trick QuadLightCdfSampler
    uses for its row/column inversion) - can be reused as the sub-texel uv offset, without
    needing extra random numbers from the caller.
*/
import Scene.Scene;
import Utils.Sampling.AliasTable;
__exported import Rendering.Lights.QuadLightSamplerInterface;

struct QuadLightAliasSampler : IQuadLightSampler
{
    AliasTable table;
    uint2      gridDim;

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};

        if (!gScene.quadLight.isActive()) return false;
        if (table.count == 0 || table.weightSum <= 0.f) return false;

        float fCount = float(table.count);
        uint idxA = min(table.count - 1, uint(rnd.x * fCount));
        float fx = rnd.x * fCount - float(idxA);

        AliasTable::Item item = table.items[idxA];
        float threshold = item.getThreshold();

        uint texelIdx;
        float fy;
        if (rnd.y < threshold)
        {
            texelIdx = item.getIndexB();
            fy = rnd.y / max(threshold, 1e-8f);
        }
        else
        {
            texelIdx = item.getIndexA();
            fy = (rnd.y - threshold) / max(1.f - threshold, 1e-8f);
        }

        float weight = table.getWeight(texelIdx);
        if (weight <= 0.f) return false;

        uint col = texelIdx % gridDim.x;
        uint row = texelIdx / gridDim.x;
        float2 uv = (float2(col, row) + float2(fx, fy)) / float2(gridDim);

        // Discrete pmf (weight / weightSum) converted to a continuous density over uv in
        // [0,1)^2 - each texel occupies 1/(W*H) of the unit square (same form as the CDF
        // sampler's pdfUv).
        float pdfUv = weight * float(gridDim.x * gridDim.y) / table.weightSum;
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
        uint texelIdx = row * gridDim.x + col;

        float weight = table.getWeight(texelIdx);
        if (weight <= 0.f) return 0.f;

        float pdfUv = weight * float(gridDim.x * gridDim.y) / table.weightSum;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        float3 normalW = gScene.quadLight.getNormalW(uv);
        return quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
