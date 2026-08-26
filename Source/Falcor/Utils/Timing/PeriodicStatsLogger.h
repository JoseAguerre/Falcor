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
#pragma once
#include "Utils/Timing/CpuTimer.h"
#include "Utils/Logger.h"

#include <limits>
#include <map>
#include <mutex>
#include <string>

namespace Falcor
{
/** Accumulates named timing samples (record()) and periodically logs one summary line per
    name - count/avg/min/max over the interval - instead of logging every individual call.
    Intended for call sites that fire very frequently (e.g. once per frame), where logging
    each sample floods the console.

    Thread-safe: record() may be called concurrently from multiple threads under the same
    name (e.g. once per name, from one dedicated thread, is the common case here - but nothing
    stops two names being recorded from different threads on the same logger).

    Typical usage - a single instance (static/global, or owned by whatever object's lifetime
    should bound the aggregation) reused across many calls:
    \code
        static PeriodicStatsLogger gStats;
        gStats.record("MyDecoder", elapsedMs);
    \endcode
*/
class PeriodicStatsLogger
{
public:
    /// intervalMs: how often (in milliseconds) to flush accumulated samples to the log.
    explicit PeriodicStatsLogger(double intervalMs = 5000.0) : mIntervalMs(intervalMs) {}

    /// Records one sample under 'name'. May trigger a flush (one logInfo() per accumulated
    /// name) if the interval has elapsed since the last flush.
    void record(const std::string& name, double ms)
    {
        std::lock_guard<std::mutex> lock(mMutex);
        Entry& e = mEntries[name];
        e.count++;
        e.totalMs += ms;
        e.minMs = std::min(e.minMs, ms);
        e.maxMs = std::max(e.maxMs, ms);
        maybeFlushLocked();
    }

private:
    struct Entry
    {
        uint32_t count = 0;
        double totalMs = 0.0;
        double minMs = std::numeric_limits<double>::max();
        double maxMs = 0.0;
    };

    // Caller must hold mMutex.
    void maybeFlushLocked()
    {
        auto now = CpuTimer::getCurrentTimePoint();
        if (mLastFlush.time_since_epoch().count() == 0)
        {
            mLastFlush = now; // first sample ever - start the interval, nothing to report yet.
            return;
        }
        double elapsedMs = CpuTimer::calcDuration(mLastFlush, now);
        if (elapsedMs < mIntervalMs)
            return;

        for (auto& [name, e] : mEntries)
        {
            if (e.count == 0)
                continue;
            logInfo(
                "{}: {} samples over {:.1f}s - avg {:.3f} ms, min {:.3f} ms, max {:.3f} ms", name, e.count, elapsedMs / 1000.0,
                e.totalMs / e.count, e.minMs, e.maxMs
            );
        }
        mEntries.clear();
        mLastFlush = now;
    }

    double mIntervalMs;
    std::mutex mMutex;
    std::map<std::string, Entry> mEntries;
    CpuTimer::TimePoint mLastFlush{};
};
} // namespace Falcor
