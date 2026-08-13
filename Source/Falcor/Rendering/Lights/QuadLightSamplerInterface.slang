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

/** Slang interface and structs shared by all QuadLight importance-sampling techniques.
    Mirrors EmissiveLightSamplerInterface.slang's role for the emissive-triangle family.
*/

/** Result of sampling the quad light.
*/
struct QuadLightSample
{
    float3 posW;    ///< Sampled world-space position on the quad.
    float3 normalW; ///< World-space normal of the quad at the sampled position.
    float pdf;      ///< Probability density function for the sampled point, with respect to solid angle at the shading point.
    float3 Le;      ///< Emitted radiance.
};

/** Converts a pdf with respect to area on the quad to a pdf with respect to solid angle
    at a shading point. Returns 0 if the shading point is on the light's back side and the
    light isn't double-sided (see QuadLightData::doubleSided). Shared by every concrete
    sampler so this math (and its one-sidedness fix) is defined exactly once.
    \param[in] pdfArea Pdf with respect to area on the light.
    \param[in] shadingPosW World-space shading point.
    \param[in] lightPosW World-space position on the light.
    \param[in] lightNormalW World-space normal of the light at lightPosW.
    \param[in] doubleSided True if the light emits from both faces.
*/
float quadLightPdfAreaToSolidAngle(float pdfArea, float3 shadingPosW, float3 lightPosW, float3 lightNormalW, bool doubleSided)
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

/** Slang interface for QuadLight importance-sampling technique implementations.
*/
interface IQuadLightSampler
{
    /** Importance sample the quad light.
        \param[in] rnd Uniform random numbers in [0,1)^2.
        \param[in] shadingPosW World-space shading point, used only to report a solid-angle pdf.
        \param[out] result Result struct. `result.pdf` is with respect to solid angle at shadingPosW.
        \return True if the sample is valid and has nonzero contribution.
    */
    bool sample(const float2 rnd, const float3 shadingPosW, out QuadLightSample result);

    /** Evaluate the pdf (with respect to solid angle at shadingPosW) for a given hit on the quad.
        \param[in] shadingPosW World-space shading point.
        \param[in] hitPosW World-space position of the hit on the quad.
    */
    float evalPdf(float3 shadingPosW, float3 hitPosW);
};
