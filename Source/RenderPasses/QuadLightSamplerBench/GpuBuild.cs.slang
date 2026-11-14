/** TOG major revision: GPU compute construction of the structures a CPU otherwise builds -
    a full-resolution 2D CDF with per-row guide tables, and per-8x8-block mean + variance. */
struct BuildParams
{
    Texture2D<float4> source;
    RWStructuredBuffer<float> conditional; ///< H*(W+1)
    RWStructuredBuffer<uint> guide;        ///< H*W
    RWStructuredBuffer<float> rowTotals;   ///< H
    RWStructuredBuffer<float> marginal;    ///< H+1
    RWStructuredBuffer<float2> blockStats; ///< ceil(W/8)*ceil(H/8)
    uint2 dim;
};

ParameterBlock<BuildParams> gBuild;

float luminanceAt(uint2 p)
{
    float3 c = gBuild.source.Load(int3(p, 0)).rgb;
    return dot(c, float3(0.2126f, 0.7152f, 0.0722f));
}

/** One thread per row: the row's prefix sum, then a linear merge into its guide table. */
[numthreads(32, 1, 1)]
void rowPass(uint3 id : SV_DispatchThreadID)
{
    uint y = id.x;
    if (y >= gBuild.dim.y) return;
    uint W = gBuild.dim.x;
    uint begin = y * (W + 1u);
    float acc = 0.f;
    gBuild.conditional[begin] = 0.f;
    for (uint x = 0; x < W; x++)
    {
        acc += luminanceAt(uint2(x, y));
        gBuild.conditional[begin + x + 1u] = acc;
    }
    gBuild.rowTotals[y] = acc;

    uint i = 0;
    for (uint k = 0; k < W; k++)
    {
        float target = acc * (float(k) / float(W));
        while (i + 1u < W && gBuild.conditional[begin + i + 1u] <= target) i++;
        gBuild.guide[y * W + k] = i;
    }
}

[numthreads(1, 1, 1)]
void marginalPass(uint3 id : SV_DispatchThreadID)
{
    float acc = 0.f;
    gBuild.marginal[0] = 0.f;
    for (uint y = 0; y < gBuild.dim.y; y++)
    {
        acc += gBuild.rowTotals[y];
        gBuild.marginal[y + 1u] = acc;
    }
}

[numthreads(16, 16, 1)]
void blockPass(uint3 id : SV_DispatchThreadID)
{
    uint bw = (gBuild.dim.x + 7u) / 8u;
    uint bh = (gBuild.dim.y + 7u) / 8u;
    if (id.x >= bw || id.y >= bh) return;
    float sum = 0.f, sumSq = 0.f, count = 0.f;
    for (uint dy = 0; dy < 8u; dy++)
    {
        for (uint dx = 0; dx < 8u; dx++)
        {
            uint2 p = id.xy * 8u + uint2(dx, dy);
            if (any(p >= gBuild.dim)) continue;
            float l = luminanceAt(p);
            sum += l;
            sumSq += l * l;
            count += 1.f;
        }
    }
    gBuild.blockStats[id.y * bw + id.x] = float2(sum / count, sumSq / count);
}
