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

/** Compute shaders for building a 2D piecewise-constant (marginal/conditional CDF)
    importance-sampling structure from a quad light's texture. Two entry points:

    - mainRows: one thread per row. Samples the texture into `gLuminance`, and builds
      that row's (unnormalized) conditional CDF prefix-sum in `gConditionalCDF`.
    - mainMarginal: single thread. Builds the (unnormalized) marginal CDF prefix-sum
      over the per-row totals in `gMarginalCDF`. Must run after mainRows completes.

    All CDF values are left unnormalized (raw prefix sums); QuadLightSampler.slang
    scales the random sample by the relevant total instead of pre-dividing here.
*/
import Utils.Color.ColorHelpers;

cbuffer CB
{
    uint2 gridDim; // (M columns, N rows)
};

SamplerState        gTexSampler;
Texture2D<float4>   gTex;
RWTexture2D<float>   gLuminance;        // MxN
RWStructuredBuffer<float> gConditionalCDF; // N*(M+1)
RWStructuredBuffer<float> gMarginalCDF;    // N+1

[numthreads(64, 1, 1)]
void mainRows(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    uint row = dispatchThreadID.x;
    if (row >= gridDim.y) return;

    uint M = gridDim.x;
    uint condBegin = row * (M + 1);

    float sum = 0.f;
    gConditionalCDF[condBegin] = 0.f;
    for (uint col = 0; col < M; col++)
    {
        float2 uv = float2((float(col) + 0.5f) / float(M), (float(row) + 0.5f) / float(gridDim.y));
        float3 radiance = gTex.SampleLevel(gTexSampler, uv, 0).rgb;
        float lum = luminance(radiance);

        gLuminance[uint2(col, row)] = lum;
        sum += lum;
        gConditionalCDF[condBegin + col + 1] = sum;
    }
}

[numthreads(1, 1, 1)]
void mainMarginal(uint3 dispatchThreadID : SV_DispatchThreadID)
{
    uint N = gridDim.y;
    uint M = gridDim.x;

    float sum = 0.f;
    gMarginalCDF[0] = 0.f;
    for (uint row = 0; row < N; row++)
    {
        float rowTotal = gConditionalCDF[row * (M + 1) + M];
        sum += rowTotal;
        gMarginalCDF[row + 1] = sum;
    }
}
