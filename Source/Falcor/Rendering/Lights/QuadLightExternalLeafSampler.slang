/** TOG major-revision research sampler - see QuadLightExternalLeafSampler.h. */
import Scene.Scene;
__exported import Rendering.Lights.QuadLightSamplerInterface;

struct ExternalLeaf
{
    float4 rect;     ///< (u0, v0, u1, v1).
    float density;   ///< Mean sampling density over the leaf, in arbitrary units.
    float gx, gy;    ///< Separable linear tilt, |g| < 1. Zero = uniform inside the leaf.
    float threshold;
    uint alias;
    uint pad0, pad1, pad2;
};

/** Inverts the CDF of f(x) = 1 + g*(2x-1) on [0,1]. */
float externalLeafWarp(float xi, float g)
{
    if (abs(g) < 1e-4f) return xi;
    float b = 1.f - g;
    return saturate((-b + sqrt(max(b * b + 4.f * g * xi, 0.f))) / (2.f * g));
}

struct QuadLightExternalLeafSampler : IQuadLightSampler
{
    StructuredBuffer<ExternalLeaf> leaves;
    StructuredBuffer<float>        leafCdf;
    StructuredBuffer<uint>         leafMap;
    uint2                          gridDim;
    uint2                          mapDim;
    uint                           mapBlock;
    uint                           leafCount;
    float                          weightSum;
    uint                           useCdf;

    float leafPdfUv(ExternalLeaf leaf, float fx, float fy)
    {
        float tilt = (1.f + leaf.gx * (2.f * fx - 1.f)) * (1.f + leaf.gy * (2.f * fy - 1.f));
        return leaf.density * float(gridDim.x) * float(gridDim.y) / weightSum * tilt;
    }

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};
        if (!gScene.quadLight.isActive() || leafCount == 0 || weightSum <= 0.f) return false;

        uint leafIdx;
        float fx, fy;
        if (useCdf != 0)
        {
            int first = 0;
            int len = int(leafCount);
            while (len > 0)
            {
                int half = len >> 1;
                int middle = first + half;
                if (leafCdf[middle] <= rnd.x)
                {
                    first = middle + 1;
                    len -= half + 1;
                }
                else
                {
                    len = half;
                }
            }
            leafIdx = uint(clamp(first - 1, 0, int(leafCount) - 1));
            float lo = leafCdf[leafIdx];
            float hi = leafCdf[leafIdx + 1];
            fx = saturate((rnd.x - lo) / max(hi - lo, 1e-12f));
            fy = rnd.y;
        }
        else
        {
            float fCount = float(leafCount);
            uint bucket = min(leafCount - 1, uint(rnd.x * fCount));
            fx = rnd.x * fCount - float(bucket);
            float threshold = leaves[bucket].threshold;
            if (rnd.y < threshold)
            {
                leafIdx = bucket;
                fy = rnd.y / max(threshold, 1e-8f);
            }
            else
            {
                leafIdx = leaves[bucket].alias;
                fy = (rnd.y - threshold) / max(1.f - threshold, 1e-8f);
            }
        }

        ExternalLeaf leaf = leaves[leafIdx];
        if (leaf.density <= 0.f) return false;

        fx = externalLeafWarp(fx, leaf.gx);
        fy = externalLeafWarp(fy, leaf.gy);
        float2 uv = lerp(leaf.rect.xy, leaf.rect.zw, float2(fx, fy));

        float pdfArea = leafPdfUv(leaf, fx, fy) / gScene.quadLight.getArea();
        result.posW = gScene.quadLight.uvToWorld(uv);
        result.normalW = gScene.quadLight.getNormalW(uv);
        result.pdf = quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, result.posW, result.normalW, gScene.quadLight.isDoubleSided());
        result.Le = gScene.quadLight.eval(uv);
        return result.pdf > 0.f && any(result.Le > 0.f);
    }

    float evalPdf(float3 shadingPosW, float3 hitPosW)
    {
        if (!gScene.quadLight.isActive() || leafCount == 0 || weightSum <= 0.f) return 0.f;

        float2 uv = gScene.quadLight.worldToUv(hitPosW);
        if (any(uv < 0.f) || any(uv >= 1.f)) return 0.f;

        uint2 texel = min(uint2(uv * float2(gridDim)), gridDim - 1u);
        uint2 cell = min(texel / mapBlock, mapDim - 1u);
        ExternalLeaf leaf = leaves[leafMap[cell.y * mapDim.x + cell.x]];
        if (leaf.density <= 0.f) return 0.f;

        float2 f = saturate((uv - leaf.rect.xy) / max(leaf.rect.zw - leaf.rect.xy, float2(1e-8f)));
        float pdfArea = leafPdfUv(leaf, f.x, f.y) / gScene.quadLight.getArea();
        float3 normalW = gScene.quadLight.getNormalW(uv);
        return quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, hitPosW, normalW, gScene.quadLight.isDoubleSided());
    }
};
