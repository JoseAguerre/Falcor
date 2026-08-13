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

/** Importance sampler for a QuadLight, using a 2D piecewise-constant distribution
    (marginal CDF over rows + per-row conditional CDF), inverted via binary search.
    See EnvMapSampler.slang for the (differently-parameterized) env-map analogue;
    unlike the env map, this is a planar light so no solid-angle reparameterization
    is needed - just the standard area-light Jacobian.

    The importance-sampling structure (gLuminance/gConditionalCDF/gMarginalCDF) is
    built once by QuadLightSamplerSetup.cs.slang and read-only from here. Radiance
    evaluation calls back into gScene.quadLight rather than holding its own texture
    reference (mirrors EnvMapSampler/EnvMap).
*/
import Scene.Scene;

/** Result of sampling the quad light.
*/
struct QuadLightSample
{
    float3 posW;    ///< Sampled world-space position on the quad.
    float3 normalW; ///< World-space normal of the quad at the sampled position.
    float pdf;      ///< Probability density function for the sampled point, with respect to solid angle at the shading point (filled in by the caller after distance/cosine are known - see evalPdfFromArea).
    float3 Le;      ///< Emitted radiance.
};

/** Find the largest index i in [0, count-1] such that cdf[begin+i] <= u < cdf[begin+i+1].
    cdf must have count+1 valid entries starting at 'begin', monotonically non-decreasing.
*/
int findInterval(StructuredBuffer<float> cdf, uint begin, uint count, float u)
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

struct QuadLightSampler
{
    Texture2D<float>            luminance;      ///< MxN raw (unnormalized) luminance grid used to build the CDFs.
    StructuredBuffer<float>     conditionalCDF; ///< N*(M+1) raw prefix sums, one row of M+1 entries per texel row.
    StructuredBuffer<float>     marginalCDF;    ///< N+1 raw prefix sum over row totals.
    uint2                       gridDim;        ///< (M columns, N rows).

    /** Converts a pdf with respect to area on the quad to a pdf with respect to solid angle
        at a shading point. Returns 0 if the shading point is on the light's back side and
        the light isn't double-sided (see QuadLightData::doubleSided).
        \param[in] pdfArea Pdf with respect to area on the light.
        \param[in] shadingPosW World-space shading point.
        \param[in] lightPosW World-space position on the light.
        \param[in] lightNormalW World-space normal of the light at lightPosW.
        \param[in] doubleSided True if the light emits from both faces.
    */
    static float pdfAreaToSolidAngle(float pdfArea, float3 shadingPosW, float3 lightPosW, float3 lightNormalW, bool doubleSided)
    {
        float3 toLight = lightPosW - shadingPosW;
        float distSqr = max(dot(toLight, toLight), 1e-8f);
        float dist = sqrt(distSqr);
        // Cosine between the light's outward normal and the direction from the light to the
        // shading point (note the sign: toLight points the other way, from shading point to light).
        float cosTheta = -dot(lightNormalW, toLight / dist);
        if (!doubleSided && cosTheta <= 0.f) return 0.f;
        cosTheta = abs(cosTheta);
        if (cosTheta <= 1e-6f) return 0.f;
        return pdfArea * distSqr / cosTheta;
    }

    /** Importance sample the quad light.
        \param[in] rnd Uniform random numbers in [0,1)^2.
        \param[in] shadingPosW World-space shading point, used only to report a solid-angle pdf.
        \param[out] result Result struct. `result.pdf` is with respect to solid angle at shadingPosW.
        \return True if the sample is valid and has nonzero contribution.
    */
    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};

        if (!gScene.quadLight.isActive()) return false;

        uint M = gridDim.x;
        uint N = gridDim.y;

        float total = marginalCDF[N];
        if (total <= 0.f) return false;

        // Select row via the marginal distribution.
        float uy = rnd.y * total;
        int row = findInterval(marginalCDF, 0, N, uy);
        float rowLo = marginalCDF[row];
        float rowHi = marginalCDF[row + 1];
        float v = (float(row) + (uy - rowLo) / max(rowHi - rowLo, 1e-8f)) / float(N);

        // Select column via that row's conditional distribution.
        uint condBegin = row * (M + 1);
        float rowTotal = rowHi - rowLo;
        float ux = rnd.x * rowTotal;
        int col = findInterval(conditionalCDF, condBegin, M, ux);
        float colLo = conditionalCDF[condBegin + col];
        float colHi = conditionalCDF[condBegin + col + 1];
        float u = (float(col) + (ux - colLo) / max(colHi - colLo, 1e-8f)) / float(M);

        float2 uv = float2(u, v);
        float lum = luminance[uint2(col, row)];
        if (lum <= 0.f) return false;

        // Density with respect to uv in [0,1)^2, then converted to density with respect to area.
        float pdfUv = lum * float(M * N) / total;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        result.posW = gScene.quadLight.uvToWorld(uv);
        result.normalW = gScene.quadLight.getNormalW();
        result.pdf = pdfAreaToSolidAngle(pdfArea, shadingPosW, result.posW, result.normalW, gScene.quadLight.isDoubleSided());
        result.Le = gScene.quadLight.eval(uv);

        return result.pdf > 0.f && any(result.Le > 0.f);
    }

    /** Evaluate the pdf (with respect to solid angle at shadingPosW) for a given hit on the quad.
        \param[in] shadingPosW World-space shading point.
        \param[in] hitPosW World-space position of the hit on the quad.
    */
    float evalPdf(float3 shadingPosW, float3 hitPosW)
    {
        if (!gScene.quadLight.isActive()) return 0.f;

        uint M = gridDim.x;
        uint N = gridDim.y;

        float total = marginalCDF[N];
        if (total <= 0.f) return 0.f;

        float2 uv = gScene.quadLight.worldToUv(hitPosW);
        if (any(uv < 0.f) || any(uv >= 1.f)) return 0.f;

        uint col = clamp(uint(uv.x * float(M)), 0u, M - 1);
        uint row = clamp(uint(uv.y * float(N)), 0u, N - 1);

        float lum = luminance[uint2(col, row)];
        if (lum <= 0.f) return 0.f;

        float pdfUv = lum * float(M * N) / total;
        float pdfArea = pdfUv / gScene.quadLight.getArea();

        float3 normalW = gScene.quadLight.getNormalW();
        return pdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
