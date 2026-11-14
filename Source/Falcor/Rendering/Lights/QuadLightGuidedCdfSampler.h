#pragma once
#include "QuadLightSampler.h"
#include "Core/API/Texture.h"
#include "Core/API/Buffer.h"
#include <vector>

namespace Falcor
{
    /** TOG major-revision baseline: 2D CDF with guide tables (Chen & Asau's cutpoint method), a
        stronger alternative to plain binary search, in the same expected-O(1) family as radix
        tree forests [Binder & Keller 2019]. It produces the SAME sample mapping as Cdf2D, so any
        difference from Cdf2D is purely lookup cost. Prefix sums and guides are built in parallel
        across rows on the CPU.
    */
    class FALCOR_API QuadLightGuidedCdfSampler : public QuadLightSampler
    {
    public:
        QuadLightGuidedCdfSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight);
        QuadLightGuidedCdfSampler(ref<Device> pDevice, ref<QuadLight> pQuadLight, uint32_t width, uint32_t height, const std::vector<float>& luminance);
        void bindShaderData(const ShaderVar& var) const override;

    private:
        void build(uint32_t width, uint32_t height, const std::vector<float>& luminance);

        uint2 mGridDim;
        ref<Texture> mpLuminance;
        ref<Buffer> mpConditionalCDF;
        ref<Buffer> mpMarginalCDF;
        ref<Buffer> mpConditionalGuide;
        ref<Buffer> mpMarginalGuide;
    };
}
