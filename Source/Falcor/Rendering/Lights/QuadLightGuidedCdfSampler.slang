/** TOG major-revision baseline: Cdf2D with guide tables - see QuadLightGuidedCdfSampler.h. */
import Scene.Scene;
__exported import Rendering.Lights.QuadLightSamplerInterface;

struct QuadLightGuidedCdfSampler : IQuadLightSampler
{
    Texture2D<float>        luminance;
    StructuredBuffer<float> conditionalCDF;
    StructuredBuffer<float> marginalCDF;
    Buffer<uint>            conditionalGuide; ///< H*W, per-row cutpoints.
    StructuredBuffer<uint>  marginalGuide;    ///< H, row cutpoints.
    uint2                   gridDim;

    int searchMarginal(float u, float total)
    {
        uint H = gridDim.y;
        uint k = min(uint(u / total * float(H)), H - 1u);
        int first = int(marginalGuide[k]);
        int last = (k + 1u < H) ? int(marginalGuide[k + 1u]) : int(H) - 1;
        while (first < last)
        {
            int middle = (first + last + 1) >> 1;
            if (marginalCDF[middle] <= u) first = middle; else last = middle - 1;
        }
        return first;
    }

    int searchConditional(uint row, float u, float total)
    {
        uint W = gridDim.x;
        uint begin = row * (W + 1u);
        uint guideBegin = row * W;
        uint k = min(uint(u / max(total, 1e-20f) * float(W)), W - 1u);
        int first = int(conditionalGuide[guideBegin + k]);
        int last = (k + 1u < W) ? int(conditionalGuide[guideBegin + k + 1u]) : int(W) - 1;
        while (first < last)
        {
            int middle = (first + last + 1) >> 1;
            if (conditionalCDF[begin + middle] <= u) first = middle; else last = middle - 1;
        }
        return first;
    }

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};
        if (!gScene.quadLight.isActive()) return false;

        uint W = gridDim.x;
        uint H = gridDim.y;
        float total = marginalCDF[H];
        if (total <= 0.f) return false;

        float uy = rnd.y * total;
        int row = searchMarginal(uy, total);
        float rowLo = marginalCDF[row];
        float rowHi = marginalCDF[row + 1];
        float v = (float(row) + (uy - rowLo) / max(rowHi - rowLo, 1e-8f)) / float(H);

        uint condBegin = row * (W + 1);
        float rowTotal = rowHi - rowLo;
        float ux = rnd.x * rowTotal;
        int col = searchConditional(row, ux, rowTotal);
        float colLo = conditionalCDF[condBegin + col];
        float colHi = conditionalCDF[condBegin + col + 1];
        float u = (float(col) + (ux - colLo) / max(colHi - colLo, 1e-8f)) / float(W);

        float2 uv = float2(u, v);
        float lum = luminance[uint2(col, row)];
        if (lum <= 0.f) return false;

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
