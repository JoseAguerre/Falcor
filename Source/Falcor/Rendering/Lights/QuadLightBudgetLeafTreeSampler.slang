/** TOG major revision: the same budgeted quadtree as BudgetLeafAlias, sampled by a hierarchical warp
    instead of the alias table [Clarberg et al. 2005]. An alias table maps neighbouring inputs to unrelated
    leaves, which discards the stratification of a low-discrepancy sequence; this descent is continuous
    inside each node and keeps it, at the price of O(depth) fetches instead of O(1), in a structure small
    enough to stay cached. Same pdf as BudgetLeafAlias.
*/
import Scene.Scene;
__exported import Rendering.Lights.QuadLightSamplerInterface;
import Rendering.Lights.QuadLightBudgetLeafAliasSampler;

struct BudgetTreeNode
{
    float pTop;        ///< Probability of the top two children.
    float pLeftTop;    ///< Probability of the left child, given the top row.
    float pLeftBottom; ///< Probability of the left child, given the bottom row.
    uint child;        ///< MSB set: leaf, low bits = leaf index. Otherwise: first of 4 contiguous children.
};

struct QuadLightBudgetLeafTreeSampler : IQuadLightSampler
{
    Buffer<uint>                  nodes;
    StructuredBuffer<PackedLeaf>  leaves;
    StructuredBuffer<BudgetTreeNode> tree;
    uint2                         gridDim;
    uint                          leafCount;
    float                         weightSum;
    uint                          alignBlock;

    static const uint kNodeLeafFlag = 0x8000u;
    static const uint kNodePayloadMask = 0x7fffu;
    static const uint kTreeLeafFlag = 0x80000000u;
    static const uint kMaxDescentSteps = 24u;

    uint findLeaf(uint2 texel)
    {
        uint nodeIdx = 0;
        uint x0 = 0, y0 = 0, x1 = gridDim.x, y1 = gridDim.y;
        for (uint step = 0; step < kMaxDescentSteps; step++)
        {
            uint v = nodes[nodeIdx];
            if ((v & kNodeLeafFlag) != 0) return v & kNodePayloadMask;
            uint firstChild = v & kNodePayloadMask;
            uint xm = x0 + ((x1 - x0) / 2u / alignBlock) * alignBlock;
            uint ym = y0 + ((y1 - y0) / 2u / alignBlock) * alignBlock;
            uint qx = texel.x >= xm ? 1u : 0u;
            uint qy = texel.y >= ym ? 1u : 0u;
            if (qx == 0u) x1 = xm; else x0 = xm;
            if (qy == 0u) y1 = ym; else y0 = ym;
            nodeIdx = firstChild + (qy * 2u + qx);
        }
        return 0u;
    }

    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result)
    {
        result = {};
        if (!gScene.quadLight.isActive()) return false;
        if (leafCount == 0 || weightSum <= 0.f) return false;

        float u = rnd.x;
        float v = rnd.y;
        uint idx = 0;
        uint leafIdx = 0;
        for (uint step = 0; step < kMaxDescentSteps; step++)
        {
            BudgetTreeNode n = tree[idx];
            if ((n.child & kTreeLeafFlag) != 0)
            {
                leafIdx = n.child & ~kTreeLeafFlag;
                break;
            }
            float pl;
            uint q;
            if (v < n.pTop)
            {
                v = v / max(n.pTop, 1e-20f);
                pl = n.pLeftTop;
                q = 0u;
            }
            else
            {
                v = (v - n.pTop) / max(1.f - n.pTop, 1e-20f);
                pl = n.pLeftBottom;
                q = 2u;
            }
            if (u < pl)
            {
                u = u / max(pl, 1e-20f);
            }
            else
            {
                u = (u - pl) / max(1.f - pl, 1e-20f);
                q += 1u;
            }
            u = saturate(u);
            v = saturate(v);
            idx = n.child + q;
        }

        PackedLeaf chosen = leaves[leafIdx];
        float avgLuma = chosen.avgLuma();
        if (avgLuma <= 0.f) return false;

        uint2 rectMin = chosen.rectMin();
        uint2 rectMax = chosen.rectMax();
        float2 uvOut = lerp(float2(rectMin) / float2(gridDim), float2(rectMax) / float2(gridDim), float2(u, v));

        float pdfUv = avgLuma * float(gridDim.x * gridDim.y) / weightSum;
        float pdfArea = pdfUv / gScene.quadLight.getArea();
        result.posW = gScene.quadLight.uvToWorld(uvOut);
        result.normalW = gScene.quadLight.getNormalW(uvOut);
        result.pdf = quadLightPdfAreaToSolidAngle(pdfArea, shadingPosW, result.posW, result.normalW, gScene.quadLight.isDoubleSided());
        result.Le = gScene.quadLight.eval(uvOut);
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
