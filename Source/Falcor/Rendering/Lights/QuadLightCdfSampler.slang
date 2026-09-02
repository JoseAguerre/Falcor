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

/** QuadLight importance sampler using a 2D piecewise-constant distribution (marginal CDF
    over rows + per-row conditional CDF), inverted via binary search. Default technique.
    See EnvMapSampler.slang for the (differently-parameterized) env-map analogue; unlike
    the env map, this is a planar light so no solid-angle reparameterization is needed -
    just the standard area-light Jacobian (see quadLightPdfAreaToSolidAngle).

    The CDF (gLuminance/gConditionalCDF/gMarginalCDF) is built once on the CPU (see
    QuadLightLuminance.h, QuadLightCdfSampler.cpp) and is read-only from here. Radiance
    evaluation calls back into gScene.quadLight rather than holding its own texture
    reference (mirrors EnvMapSampler/EnvMap).
*/
import Scene.Scene;
__exported import Rendering.Lights.QuadLightSamplerInterface;

/** Find the largest index i in [0, count-1] such that cdf[begin+i] <= u < cdf[begin+i+1].
    cdf must have count+1 valid entries starting at 'begin', monotonically non-decreasing.
*/
int quadLightCdfFindInterval(StructuredBuffer<float> cdf, uint begin, uint count, float u)
{
    int first = 0;
    int len = int(count);
    while (len > 0)
    {
        int half = len >> 1;
        int middle = first + half;
        if (cdf[begin + middle] <= u)
        {
            first = middle + 1;
            len -= half + 1;
        }
        else
        {
            len = half;
        }
    }
    return clamp(first - 1, 0, int(count) - 1);
}

struct QuadLightCdfSampler : IQuadLightSampler
{
    Texture2D<float>            luminance;      ///< WxH raw (unnormalized) luminance grid used to build the CDFs.
    StructuredBuffer<float>     conditionalCDF; ///< H*(W+1) raw prefix sums, one row of W+1 entries per texel row.
    StructuredBuffer<float>     marginalCDF;    ///< H+1 raw prefix sum over row totals.
    uint2                       gridDim;        ///< (W columns, H rows).

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};

        if (!gScene.quadLight.isActive()) return false;

        uint W = gridDim.x;
        uint H = gridDim.y;

        float total = marginalCDF[H];
        if (total <= 0.f) return false;

        // Select row via the marginal distribution.
        float uy = rnd.y * total;
        int row = quadLightCdfFindInterval(marginalCDF, 0, H, uy);
        float rowLo = marginalCDF[row];
        float rowHi = marginalCDF[row + 1];
        float v = (float(row) + (uy - rowLo) / max(rowHi - rowLo, 1e-8f)) / float(H);

        // Select column via that row's conditional distribution.
        uint condBegin = row * (W + 1);
        float rowTotal = rowHi - rowLo;
        float ux = rnd.x * rowTotal;
        int col = quadLightCdfFindInterval(conditionalCDF, condBegin, W, ux);
        float colLo = conditionalCDF[condBegin + col];
        float colHi = conditionalCDF[condBegin + col + 1];
        float u = (float(col) + (ux - colLo) / max(colHi - colLo, 1e-8f)) / float(W);

        float2 uv = float2(u, v);
        float lum = luminance[uint2(col, row)];
        if (lum <= 0.f) return false;

        // Density with respect to uv in [0,1)^2, then converted to density with respect to area.
        float pdfUv = lum * float(W * H) / total;
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

        uint W = gridDim.x;
        uint H = gridDim.y;

        float total = marginalCDF[H];
        if (total <= 0.f) return 0.f;

        float2 uv = gScene.quadLight.worldToUv(hitPosW);
        if (any(uv < 0.f) || any(uv >= 1.f)) return 0.f;

        uint col = clamp(uint(uv.x * float(W)), 0u, W - 1);
        uint row = clamp(uint(uv.y * float(H)), 0u, H - 1);

        float lum = luminance[uint2(col, row)];
        if (lum <= 0.f) return 0.f;

        float pdfUv = lum * float(W * H) / total;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        float3 normalW = gScene.quadLight.getNormalW(uv);
        return quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
