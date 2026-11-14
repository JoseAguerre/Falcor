/** TOG major revision: times QuadLightSampler::sample() with no ray tracing involved. */
import Scene.Scene;
import Rendering.Lights.QuadLightSampler;

struct BenchParams
{
    QuadLightSampler sampler;
    uint samplesPerThread;
    uint seed;
    uint dim;
};

ParameterBlock<BenchParams> gBench;
RWTexture2D<float4> gOutput;

/** PCG hash, so that the random stream costs far less than the structure being measured. */
uint pcg(uint v)
{
    uint state = v * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    uint s = pcg(id.x + id.y * gBench.dim + gBench.seed * 1000003u);
    const float3 shadingPos = gScene.camera.getPosition();
    float4 acc = float4(0.f);
    for (uint i = 0; i < gBench.samplesPerThread; i++)
    {
        s = pcg(s);
        float x = float(s) * (1.f / 4294967296.f);
        s = pcg(s);
        float y = float(s) * (1.f / 4294967296.f);
        QuadLightSample q;
        if (gBench.sampler.sample(float2(x, y), shadingPos, q))
            acc += float4(q.Le, q.pdf);
    }
    gOutput[uint2(id.x & 1023u, id.y & 1023u)] = acc;
}
