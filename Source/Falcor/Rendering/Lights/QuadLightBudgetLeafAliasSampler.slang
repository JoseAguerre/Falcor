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

/** QuadLight importance sampler using a best-first, budget-limited variance quadtree with
    a maximally GPU-compacted alias table over its leaves. See
    QuadLightBudgetLeafAliasSampler.h/.cpp for the CPU-side construction; this file is just
    the runtime read side: pick a leaf via the alias table (sample()), or walk the
    quadtree to find which leaf a given point falls in (evalPdf()).

    All fields are packed into plain uint32s (two 16-bit values per field) rather than
    native uint16_t/half struct fields, so this doesn't depend on 16-bit shader type
    support being enabled - see PackedLeaf below.
*/
import Scene.Scene;
__exported import Rendering.Lights.QuadLightSamplerInterface;

/** 16-byte packed leaf record: rect (in quadtree texel space), alias-method threshold +
    redirect index, and average luminance. See QuadLightBudgetLeafAliasSampler.cpp's
    build() for how these are packed and why avgLuma (not flux = avgLuma*area) is stored.
*/
struct PackedLeaf
{
    uint x0y0;           ///< x0 | (y0 << 16)
    uint x1y1;            ///< x1 | (y1 << 16)
    uint thresholdAlias;  ///< f16(threshold) | (aliasIndex << 16)
    uint avgLumaPad;      ///< f16(avgLuma) | 0

    uint2 rectMin() { return uint2(x0y0 & 0xffffu, x0y0 >> 16); }
    uint2 rectMax() { return uint2(x1y1 & 0xffffu, x1y1 >> 16); }
    float threshold() { return f16tof32(thresholdAlias & 0xffffu); }
    uint aliasIndex() { return thresholdAlias >> 16; }
    float avgLuma() { return f16tof32(avgLumaPad & 0xffffu); }
};

struct QuadLightBudgetLeafAliasSampler : IQuadLightSampler
{
    // Typed R16Uint buffer (2 bytes/element in memory, auto-widened to uint on read) -
    // topology only: MSB set = leaf (low 15 bits = leaf array index), MSB clear =
    // internal (low 15 bits = index of the first of 4 contiguous children, in
    // (TL,TR,BL,BR) order - see QuadLightBudgetLeafAliasSampler.cpp's build()).
    Buffer<uint>                nodes;
    StructuredBuffer<PackedLeaf> leaves;
    uint2                       gridDim;    ///< Source image size = the quadtree root's rect.
    uint                        leafCount;
    float                       weightSum;  ///< Total flux (avgLuma * area) summed over all leaves.

    static const uint kNodeLeafFlag = 0x8000u;
    static const uint kNodePayloadMask = 0x7fffu;
    // Generous bound on quadtree depth (real max is ~log2(max(gridDim)), <=16 even at the
    // 4K resolutions this technique assumes) - just needs to be large enough that the loop
    // always reaches a leaf; the early-return means it costs nothing beyond the true depth.
    static const uint kMaxDescentSteps = 24u;

    /** Walk the quadtree from the root to find which leaf a texel falls in. Uses the
        exact same integer split-point arithmetic build() used to create the tree
        (xm = x0 + (x1-x0)/2), so it reproduces the true leaf boundaries bit-for-bit
        regardless of odd/even block sizes anywhere in the tree - required for sample()
        and evalPdf() to agree (see IQuadLightSampler's unbiasedness requirement).
    */
    uint findLeaf(uint2 texel)
    {
        uint nodeIdx = 0;
        uint x0 = 0, y0 = 0, x1 = gridDim.x, y1 = gridDim.y;
        for (uint step = 0; step < kMaxDescentSteps; step++)
        {
            uint v = nodes[nodeIdx];
            if ((v & kNodeLeafFlag) != 0)
                return v & kNodePayloadMask;

            uint firstChild = v & kNodePayloadMask;
            uint xm = x0 + (x1 - x0) / 2u;
            uint ym = y0 + (y1 - y0) / 2u;
            uint qx = texel.x >= xm ? 1u : 0u;
            uint qy = texel.y >= ym ? 1u : 0u;
            if (qx == 0u) x1 = xm; else x0 = xm;
            if (qy == 0u) y1 = ym; else y0 = ym;
            nodeIdx = firstChild + (qy * 2u + qx);
        }
        return 0u; // Unreachable given kMaxDescentSteps, but keeps the compiler happy.
    }

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};

        if (!gScene.quadLight.isActive()) return false;
        if (leafCount == 0 || weightSum <= 0.f) return false;

        // Same leftover-randomness reuse as QuadLightAliasSampler/QuadLightAliasCtuSampler:
        // the fractional part left over after picking the alias-table bucket is itself a
        // fresh uniform variate, reused as the (fx, fy) position within the chosen leaf.
        float fCount = float(leafCount);
        uint bucket = min(leafCount - 1, uint(rnd.x * fCount));
        float fx = rnd.x * fCount - float(bucket);

        PackedLeaf bucketLeaf = leaves[bucket];
        float threshold = bucketLeaf.threshold();

        uint chosenIdx;
        float fy;
        if (rnd.y < threshold)
        {
            // Resorted alias table (see build()): a bucket's own array position implies
            // its "indexB" - no separate field needed.
            chosenIdx = bucket;
            fy = rnd.y / max(threshold, 1e-8f);
        }
        else
        {
            chosenIdx = bucketLeaf.aliasIndex();
            fy = (rnd.y - threshold) / max(1.f - threshold, 1e-8f);
        }

        PackedLeaf chosen = (chosenIdx == bucket) ? bucketLeaf : leaves[chosenIdx];
        float avgLuma = chosen.avgLuma();
        if (avgLuma <= 0.f) return false;

        uint2 rectMin = chosen.rectMin();
        uint2 rectMax = chosen.rectMax();
        float2 uv = lerp(float2(rectMin) / float2(gridDim), float2(rectMax) / float2(gridDim), float2(fx, fy));

        // Density with respect to uv in [0,1)^2 - depends only on the chosen leaf's
        // average luminance, since its area term exactly cancels (same derivation as
        // QuadLightAliasCtuSampler.slang's leafAvgLuma()/pdfUv, but avgLuma is read
        // directly here rather than derived from a stored flux/area).
        float pdfUv = avgLuma * float(gridDim.x * gridDim.y) / weightSum;
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
        if (leafCount == 0 || weightSum <= 0.f) return 0.f;

        float2 uv = gScene.quadLight.worldToUv(hitPosW);
        if (any(uv < 0.f) || any(uv >= 1.f)) return 0.f;

        uint2 texel = min(uint2(uv * float2(gridDim)), gridDim - 1u);
        uint leafIdx = findLeaf(texel);

        float avgLuma = leaves[leafIdx].avgLuma();
        if (avgLuma <= 0.f) return 0.f;

        float pdfUv = avgLuma * float(gridDim.x * gridDim.y) / weightSum;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        float3 normalW = gScene.quadLight.getNormalW(uv);
        return quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
