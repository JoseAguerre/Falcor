/** TOG major revision: GPU pointer chase. Every thread walks the same single random cycle from
    its own start, so reported time per hop reveals the capacity of the caches on the path. */
struct ChaseParams
{
    StructuredBuffer<uint> next;
    uint slots;
    uint lineWords;
    uint hops;
    uint seed;
    uint dim;
};

ParameterBlock<ChaseParams> gChase;
RWTexture2D<float4> gOutput;

uint pcg(uint v)
{
    uint state = v * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

[numthreads(16, 16, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    uint index = (pcg(id.x + id.y * gChase.dim + gChase.seed * 1000003u) % gChase.slots) * gChase.lineWords;
    for (uint i = 0; i < gChase.hops; i++)
        index = gChase.next[index];
    gOutput[uint2(id.x & 1023u, id.y & 1023u)] = float4(float(index), 0.f, 0.f, 1.f);
}
