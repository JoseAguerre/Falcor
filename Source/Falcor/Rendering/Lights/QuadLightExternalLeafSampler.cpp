#include "QuadLightExternalLeafSampler.h"
#include "QuadLightBuildTiming.h"
#include "Core/Error.h"
#include "Core/API/Device.h"
#include "Utils/Timing/CpuTimer.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <fstream>

namespace Falcor
{
    namespace
    {
#pragma pack(push, 1)
        struct FileHeader
        {
            char magic[4];
            uint32_t width, height, count, mapBlock;
            uint32_t reserved[3];
        };
        struct FileRecord
        {
            uint16_t x0, y0, x1, y1;
            float density, gx, gy;
        };
#pragma pack(pop)
        static_assert(sizeof(FileHeader) == 32);
        static_assert(sizeof(FileRecord) == 20);

        struct GpuLeaf
        {
            float4 rect;
            float density, gx, gy, threshold;
            uint32_t alias;
            uint32_t pad[3];
        };
        static_assert(sizeof(GpuLeaf) == 48);
    }

    QuadLightExternalLeafSampler::QuadLightExternalLeafSampler(
        QuadLightSamplerType type, ref<Device> pDevice, ref<QuadLight> pQuadLight, const std::filesystem::path& framePath
    )
        : QuadLightSampler(type, pDevice, pQuadLight)
    {
        const char* dir = std::getenv("LEAFALIAS_EXTERNAL_DIR");
        FALCOR_CHECK(dir != nullptr, "ExternalLeaf samplers need LEAFALIAS_EXTERNAL_DIR to be set.");
        const std::filesystem::path path = std::filesystem::path(dir) / (framePath.stem().string() + ".leaf");

        std::ifstream file(path, std::ios::binary);
        FALCOR_CHECK(file.good(), "ExternalLeaf sampler: cannot open '{}'.", path);
        FileHeader header{};
        file.read(reinterpret_cast<char*>(&header), sizeof(header));
        FALCOR_CHECK(file.good() && std::memcmp(header.magic, "LEAF", 4) == 0, "ExternalLeaf sampler: bad header in '{}'.", path);
        FALCOR_CHECK(header.count > 0 && header.mapBlock > 0, "ExternalLeaf sampler: empty partition in '{}'.", path);
        std::vector<FileRecord> records(header.count);
        file.read(reinterpret_cast<char*>(records.data()), sizeof(FileRecord) * records.size());
        FALCOR_CHECK(file.good(), "ExternalLeaf sampler: truncated '{}'.", path);

        const uint32_t w = header.width, h = header.height, n = header.count;
        mGridDim = uint2(w, h);
        mLeafCount = n;
        mMapBlock = header.mapBlock;

        auto tableStart = CpuTimer::getCurrentTimePoint();

        std::vector<double> flux(n);
        double sum = 0.0;
        for (uint32_t i = 0; i < n; ++i)
        {
            const FileRecord& r = records[i];
            flux[i] = std::max(0.0, double(r.density)) * double(r.x1 - r.x0) * double(r.y1 - r.y0);
            sum += flux[i];
        }
        FALCOR_CHECK(sum > 0.0, "ExternalLeaf sampler: zero total flux in '{}'.", path);
        mWeightSum = float(sum);

        std::vector<GpuLeaf> leaves(n);
        std::vector<float> cdf(n + 1);
        double acc = 0.0;
        for (uint32_t i = 0; i < n; ++i)
        {
            const FileRecord& r = records[i];
            GpuLeaf& leaf = leaves[i];
            leaf.rect = float4(float(r.x0) / float(w), float(r.y0) / float(h), float(r.x1) / float(w), float(r.y1) / float(h));
            leaf.density = std::max(0.f, r.density);
            leaf.gx = r.gx;
            leaf.gy = r.gy;
            leaf.threshold = 1.f;
            leaf.alias = i;
            cdf[i] = float(acc / sum);
            acc += flux[i];
        }
        cdf[n] = 1.f;

        // Vose, in double precision, resorted so that a bucket's own index is its primary leaf.
        const double avg = sum / double(n);
        std::vector<double> residual = flux;
        std::vector<uint32_t> small, large;
        small.reserve(n);
        large.reserve(n);
        for (uint32_t i = 0; i < n; ++i)
            (residual[i] < avg ? small : large).push_back(i);
        while (!small.empty() && !large.empty())
        {
            uint32_t s = small.back();
            small.pop_back();
            uint32_t l = large.back();
            large.pop_back();
            leaves[s].threshold = float(residual[s] / avg);
            leaves[s].alias = l;
            residual[l] = (residual[l] + residual[s]) - avg;
            (residual[l] < avg ? small : large).push_back(l);
        }

        const uint32_t mapW = (w + mMapBlock - 1) / mMapBlock, mapH = (h + mMapBlock - 1) / mMapBlock;
        mMapDim = uint2(mapW, mapH);
        std::vector<uint32_t> map((size_t)mapW * mapH, 0);
        for (uint32_t i = 0; i < n; ++i)
        {
            const FileRecord& r = records[i];
            for (uint32_t y = r.y0 / mMapBlock; y < (uint32_t(r.y1) + mMapBlock - 1) / mMapBlock; ++y)
                for (uint32_t x = r.x0 / mMapBlock; x < (uint32_t(r.x1) + mMapBlock - 1) / mMapBlock; ++x)
                    map[(size_t)y * mapW + x] = i;
        }

        auto uploadStart = CpuTimer::getCurrentTimePoint();
        mpLeaves = mpDevice->createStructuredBuffer(sizeof(GpuLeaf), n, ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, leaves.data(), false);
        mpLeafCdf = mpDevice->createStructuredBuffer(sizeof(float), n + 1, ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, cdf.data(), false);
        mpLeafMap = mpDevice->createStructuredBuffer(sizeof(uint32_t), (uint32_t)map.size(), ResourceBindFlags::ShaderResource, MemoryType::DeviceLocal, map.data(), false);
        auto end = CpuTimer::getCurrentTimePoint();

        auto& timing = quadLightBuildTiming();
        timing.tableMs = CpuTimer::calcDuration(tableStart, uploadStart);
        timing.uploadMs = CpuTimer::calcDuration(uploadStart, end);
        timing.leaves = n;
        timing.bytes = sizeof(GpuLeaf) * uint64_t(n) + sizeof(float) * uint64_t(n + 1) + sizeof(uint32_t) * map.size();
    }

    void QuadLightExternalLeafSampler::bindShaderData(const ShaderVar& var) const
    {
        FALCOR_ASSERT(var.isValid());
        var["leaves"] = mpLeaves;
        var["leafCdf"] = mpLeafCdf;
        var["leafMap"] = mpLeafMap;
        var["gridDim"] = mGridDim;
        var["mapDim"] = mMapDim;
        var["mapBlock"] = mMapBlock;
        var["leafCount"] = mLeafCount;
        var["weightSum"] = mWeightSum;
        var["useCdf"] = uint32_t(getType() == QuadLightSamplerType::ExternalLeafCdf ? 1 : 0);
    }
}
