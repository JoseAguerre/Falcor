#pragma once
#include "QuadLightSampler.h"
#include "Core/API/Buffer.h"
#include <filesystem>

namespace Falcor
{
    /** TOG major-revision research sampler: a leaf partition supplied per frame by an external
        file (see major-revision/common/leaf_io.py), rather than computed by the engine. One
        engine path therefore evaluates every partition / weight / codec hypothesis in the real
        GPU path tracer, in two selection modes:
          ExternalLeafAlias - Walker/Vose alias table over the leaves.
          ExternalLeafCdf   - binary search of a 1D CDF over the leaves, in file order.
        Both give identical pdfs, which is what makes this the partition-vs-alias ablation.
        Each leaf may also carry a separable linear density tilt (gx, gy), the within-leaf DCT
        experiment.

        File: <LEAFALIAS_EXTERNAL_DIR>/<frame stem>.leaf. A missing file is a hard error.
        Not a production sampler: 48-byte records and a lookup map, and it reads from disk,
        so its build time and absolute frame time are meaningless. Compare only ExternalLeafAlias
        against ExternalLeafCdf for cost.
    */
    class FALCOR_API QuadLightExternalLeafSampler : public QuadLightSampler
    {
    public:
        QuadLightExternalLeafSampler(QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight, const std::filesystem::path& framePath);
        void bindShaderData(const ShaderVar& var) const override;

    private:
        uint2 mGridDim;
        uint2 mMapDim;
        uint32_t mMapBlock = 1;
        uint32_t mLeafCount = 0;
        float mWeightSum = 0.f;
        ref<Buffer> mpLeaves;
        ref<Buffer> mpLeafCdf;
        ref<Buffer> mpLeafMap;
    };
}
