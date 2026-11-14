#pragma once
#include "Core/Macros.h"
#include <cstdint>

namespace Falcor
{
    /** TOG major-revision instrumentation: stage timing of the most recent sampler build on
        the calling thread. Samplers fill in whichever fields apply; the video player reads
        them straight after construction and appends a row to LEAFALIAS_TIMING_CSV.
    */
    struct QuadLightBuildTiming
    {
        double partitionMs = 0.0; ///< Statistics + partition construction (SAT + best-first, or recursive split).
        double tableMs = 0.0;     ///< CDF prefix sums, or alias-table construction.
        double uploadMs = 0.0;    ///< Creating/filling the GPU buffers.
        uint32_t leaves = 0;      ///< Number of table entries (leaves, or texels for per-pixel techniques).
        uint64_t bytes = 0;       ///< Size of the GPU sampling structure, in bytes.
    };

    FALCOR_API QuadLightBuildTiming& quadLightBuildTiming();
}
