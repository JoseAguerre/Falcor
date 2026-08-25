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
#include "QuadLightVideo.h"
#include "Scene/Lights/QuadLight.h"
#include "Rendering/Lights/QuadLightSampler.h"
#include "Rendering/Lights/QuadLightLuminance.h"
#include "Core/API/Texture.h"
#include "Utils/Image/Bitmap.h"
#include "Utils/Logger.h"
#include "Utils/Timing/CpuTimer.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <limits>
#include <sstream>

namespace Falcor
{
    std::optional<QuadLightPlaylist> QuadLightPlaylist::parseFile(const std::filesystem::path& playlistPath)
    {
        std::ifstream file(playlistPath);
        if (!file.is_open())
        {
            logWarning("QuadLightPlaylist: failed to open '{}'.", playlistPath);
            return std::nullopt;
        }

        const std::filesystem::path baseDir = playlistPath.parent_path();

        QuadLightPlaylist playlist;
        std::string line;
        uint32_t lineNumber = 0;
        while (std::getline(file, line))
        {
            ++lineNumber;

            // Strip a UTF-8 BOM (EF BB BF) if present on the very first line - common when a
            // file is saved as "UTF-8" from Notepad or similar. Left in place, it makes
            // line[0] some non-'#' BOM byte, silently routing a "#prefetch ..." first line
            // into the plain "<filename> <durationMs>" parser below instead (which then
            // either logs a clear parse-failure warning, or worse, silently misparses it as
            // a bogus entry) - so this is worth stripping unconditionally rather than
            // requiring users to know not to save with a BOM.
            if (lineNumber == 1 && line.size() >= 3 && (unsigned char)line[0] == 0xEF && (unsigned char)line[1] == 0xBB && (unsigned char)line[2] == 0xBF)
            {
                line.erase(0, 3);
            }

            // Trim leading/trailing whitespace.
            size_t begin = line.find_first_not_of(" \t\r\n");
            if (begin == std::string::npos) continue; // blank line
            size_t end = line.find_last_not_of(" \t\r\n");
            std::string trimmed = line.substr(begin, end - begin + 1);

            if (trimmed.empty()) continue;

            if (trimmed[0] == '#')
            {
                std::istringstream directive(trimmed.substr(1));
                std::string keyword;
                directive >> keyword;
                if (keyword == "prefetch")
                {
                    std::string value;
                    directive >> value;
                    if (value == "all")
                    {
                        playlist.mPrefetchDepth = std::numeric_limits<uint32_t>::max();
                        logInfo("QuadLightPlaylist: '{}' line {}: '#prefetch all' recognized - will request the entire playlist be kept resident.", playlistPath, lineNumber);
                    }
                    else
                    {
                        long long depth = -1;
                        std::istringstream(value) >> depth;
                        if (depth < 1)
                        {
                            logWarning(
                                "QuadLightPlaylist: '{}' line {}: expected '#prefetch <N>' or '#prefetch all', got '{}' - ignored.",
                                playlistPath, lineNumber, trimmed
                            );
                        }
                        else
                        {
                            playlist.mPrefetchDepth = (uint32_t)depth;
                            logInfo("QuadLightPlaylist: '{}' line {}: '#prefetch {}' recognized.", playlistPath, lineNumber, depth);
                        }
                    }
                }
                // Any other '#'-prefixed line (including plain comments) is silently skipped.
                continue;
            }

            std::istringstream iss(trimmed);
            std::string filename;
            long long durationMs = -1;
            if (!(iss >> filename >> durationMs) || durationMs < 0)
            {
                logWarning("QuadLightPlaylist: '{}' line {}: expected '<filename> <durationMs>', got '{}' - skipped.", playlistPath, lineNumber, trimmed);
                continue;
            }

            QuadLightPlaylistEntry entry;
            entry.path = (baseDir / filename).lexically_normal();
            entry.durationMs = (uint32_t)durationMs;
            playlist.mEntries.push_back(std::move(entry));
        }

        if (playlist.mEntries.empty())
        {
            logWarning("QuadLightPlaylist: '{}' contained no valid entries.", playlistPath);
            return std::nullopt;
        }

        return playlist;
    }

    QuadLightVideoPlayer::QuadLightVideoPlayer(ref<Device> pDevice, ref<QuadLight> pOwner, QuadLightPlaylist playlist, QuadLightSamplerType initialType)
        // Slot holds a unique_ptr<QuadLightSampler>, making it move-only - mSlots is sized
        // via the vector(count) fill-constructor (which only default-constructs each
        // element in place) rather than resize()/assign(), for consistency with that.
        : mpDevice(pDevice)
        , mpOwner(pOwner.get())
        , mPlaylist(std::move(playlist))
        , mSlots(std::max(1u, std::min(mPlaylist.requestedPrefetchDepth().value_or(kDefaultPrefetchDepth), (uint32_t)mPlaylist.size())))
        , mSlotRequestedPlaylistIndex(mSlots.size(), std::numeric_limits<uint32_t>::max()) // sentinel: never requested.
        , mSlotRequestedGeneration(mSlots.size(), 0)
        , mSamplerType(initialType)
    {
        std::string requested = "default";
        if (auto d = mPlaylist.requestedPrefetchDepth())
            requested = (*d == std::numeric_limits<uint32_t>::max()) ? "all" : std::to_string(*d);
        logInfo("QuadLightVideoPlayer: prefetch ring size = {} (requested: {}, playlist has {} frames).", mSlots.size(), requested, mPlaylist.size());
    }

    QuadLightVideoPlayer::~QuadLightVideoPlayer()
    {
        if (mWorker.joinable())
        {
            {
                std::lock_guard<std::mutex> lock(mJobMutex);
                mTerminate = true;
            }
            mJobCv.notify_all();
            mWorker.join();
        }
    }

    void QuadLightVideoPlayer::primeFirstFrame()
    {
        // Synchronous, main-thread only - both the decode and the GPU work happen here
        // before returning, so the very first frame is fully ready when this call finishes.
        Job job{0, 0, mSamplerType, mGeneration};
        finalizeResult(prepareJob(job));
        mSlotRequestedPlaylistIndex[0] = 0;
        mSlotRequestedGeneration[0] = mGeneration;

        mWorker = std::thread([this] { runWorker(); });
        ensureJobsQueued();

        // Block until every remaining ring slot has been decoded+built, so "#prefetch N"
        // means what it says - "load N frames before playback starts" - rather than just
        // capping how far ahead the background worker is allowed to get once already
        // running. Deliberately unconditional (not just for an explicit "#prefetch"
        // directive): the ring is always fully warm before this call returns, so there's
        // one predictable invariant instead of two different startup behaviors depending on
        // whether the playlist specified a depth. For the default ring size this is a small,
        // one-time cost; for a large explicit "#prefetch N"/"#prefetch all" it's the whole
        // point and can take a while.
        while (mPendingJobs.load(std::memory_order_acquire) != 0)
        {
            finalizeReadyResults();
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        finalizeReadyResults(); // mPendingJobs==0 confirmed above - drain whatever that last implies.

        const uint32_t readyCount = getReadySlotCount();
        if (readyCount < mSlots.size())
        {
            logWarning(
                "QuadLightVideoPlayer: only {}/{} ring slots primed - {} frame(s) failed to decode/build (see warnings above).",
                readyCount, mSlots.size(), mSlots.size() - readyCount
            );
        }
        else
        {
            logInfo("QuadLightVideoPlayer: prefetch ring fully primed ({}/{} slots ready).", readyCount, mSlots.size());
        }
    }

    QuadLightVideoPlayer::PreparedResult QuadLightVideoPlayer::prepareJob(const Job& job)
    {
        const QuadLightPlaylistEntry& entry = mPlaylist.entries()[job.playlistIndex];

        PreparedResult result;
        result.slotIndex = job.slotIndex;
        result.playlistIndex = job.playlistIndex;
        result.type = job.type;
        result.generation = job.generation;

        const auto decodeStart = CpuTimer::getCurrentTimePoint();
        Bitmap::DecodeTimings decodeTimings;
        result.pBitmap = Bitmap::createFromFile(entry.path, true, Bitmap::ImportFlags::None, &decodeTimings);
        const auto decodeEnd = CpuTimer::getCurrentTimePoint();
        if (!result.pBitmap)
        {
            logWarning("QuadLightVideoPlayer: failed to decode frame {} ('{}') - this ring slot won't become ready until a later job overwrites it.", job.playlistIndex, entry.path);
            return result;
        }
        logInfo(
            "QuadLightVideoPlayer: frame {} ('{}') decode time {:.3f} ms ({}x{}) "
            "[open+detect {:.3f} ms, FreeImage decode {:.3f} ms, conversion {:.3f} ms, raw-bits copy {:.3f} ms]",
            job.playlistIndex, entry.path, CpuTimer::calcDuration(decodeStart, decodeEnd), result.pBitmap->getWidth(), result.pBitmap->getHeight(),
            decodeTimings.formatDetectAndOpenMs, decodeTimings.freeImageDecodeMs, decodeTimings.conversionMs, decodeTimings.rawBitsCopyMs
        );

        // QuadLightSamplerType::Random needs no luminance data - skip computing it.
        if (job.type != QuadLightSamplerType::Random)
        {
            result.luminance = computeLuminanceFromBitmap(*result.pBitmap, result.width, result.height, entry.path);
        }

        return result;
    }

    void QuadLightVideoPlayer::finalizeResult(PreparedResult&& result)
    {
        if (!result.pBitmap) return; // decode failed - nothing to finalize, slot is left as-is.

        const QuadLightPlaylistEntry& entry = mPlaylist.entries()[result.playlistIndex];
        const auto buildStart = CpuTimer::getCurrentTimePoint();

        // QuadLight::eval() always samples mip 0 (see QuadLight.slang) - a full mip chain
        // is pure wasted GPU work here, so mip generation is disabled.
        ref<Texture> pTexture = Texture::createFromBitmap(mpDevice, *result.pBitmap, false, false);
        if (!pTexture)
        {
            logWarning("QuadLightVideoPlayer: failed to create GPU texture for frame {} ('{}').", result.playlistIndex, entry.path);
            return;
        }
        pTexture->setSourcePath(entry.path);

        // Built from the already-decoded luminance data computed on the worker thread
        // (prepareJob()), instead of going through computeQuadLightLuminance() (which would
        // decode the file a second time) - this is the whole point of the prefetch ring's
        // decode-once design.
        std::unique_ptr<QuadLightSampler> pSampler = createQuadLightSamplerFromLuminance(
            result.type, mpDevice, ref<QuadLight>(mpOwner), result.width, result.height, result.luminance
        );

        Slot& slot = mSlots[result.slotIndex];
        slot.pTexture = pTexture;
        slot.pSampler = std::move(pSampler);
        slot.playlistIndex = result.playlistIndex;
        slot.generation = result.generation;
        slot.ready = true;

        const auto buildEnd = CpuTimer::getCurrentTimePoint();
        logInfo(
            "QuadLightVideoPlayer: frame {} GPU build time {:.3f} ms (main thread: texture+sampler)",
            result.playlistIndex, CpuTimer::calcDuration(buildStart, buildEnd)
        );
    }

    void QuadLightVideoPlayer::runWorker()
    {
        while (true)
        {
            Job job;
            {
                std::unique_lock<std::mutex> lock(mJobMutex);
                mJobCv.wait(lock, [this] { return mTerminate || !mJobQueue.empty(); });

                // Checked first, before touching the queue - shutdown must win immediately
                // over any still-queued (not yet started) work. The previous version only
                // checked mTerminate once the queue was already empty, so on close it would
                // keep popping and decoding every remaining queued job (up to a whole
                // "#prefetch N" ring's worth) before ever noticing the shutdown request -
                // exactly why the worker kept visibly decoding frames for a while after the
                // app was closed.
                if (mTerminate) return;

                if (mJobQueue.empty()) continue; // spurious wakeup - nothing to do yet.

                job = mJobQueue.front();
                mJobQueue.pop_front();
            }

            // CPU-only: decode + luminance compute. No GPU calls happen on this thread - see
            // the class doc comment for why (a real crash was root-caused to this).
            PreparedResult result = prepareJob(job);
            {
                std::lock_guard<std::mutex> lock(mResultsMutex);
                mResultsQueue.push_back(std::move(result));
            }
            mPendingJobs.fetch_sub(1, std::memory_order_release);
        }
    }

    void QuadLightVideoPlayer::finalizeReadyResults()
    {
        std::deque<PreparedResult> results;
        {
            std::lock_guard<std::mutex> lock(mResultsMutex);
            results.swap(mResultsQueue);
        }
        for (auto& result : results) finalizeResult(std::move(result));
    }

    void QuadLightVideoPlayer::ensureJobsQueued()
    {
        const uint32_t ringSize = (uint32_t)mSlots.size();
        const uint32_t playlistSize = (uint32_t)mPlaylist.size();

        std::vector<Job> newJobs;
        for (uint32_t offset = 0; offset < ringSize; ++offset)
        {
            const uint64_t position = mSequence + offset;
            const uint32_t slotIndex = (uint32_t)(position % ringSize);
            const uint32_t wantedPlaylistIndex = (uint32_t)(position % playlistSize);
            Slot& slot = mSlots[slotIndex];

            // Already holds exactly the content we want - e.g. the playlist looped back
            // around to a frame this slot already built last pass (very common once
            // steady-state is reached, and the whole point of "#prefetch all": once every
            // slot is warm, nothing should ever be re-decoded). Checked against the slot's
            // own state, not a separate bookkeeping array, so this is correct regardless of
            // *when* that content was built.
            if (slot.ready && slot.playlistIndex == wantedPlaylistIndex && slot.generation == mGeneration) continue;

            // Otherwise, avoid spamming a duplicate job if one for this exact want is
            // already queued/in-flight (checked every tick, well before it completes).
            if (mSlotRequestedPlaylistIndex[slotIndex] == wantedPlaylistIndex && mSlotRequestedGeneration[slotIndex] == mGeneration) continue;

            mSlotRequestedPlaylistIndex[slotIndex] = wantedPlaylistIndex;
            mSlotRequestedGeneration[slotIndex] = mGeneration;
            newJobs.push_back(Job{slotIndex, wantedPlaylistIndex, mSamplerType, mGeneration});
        }

        if (newJobs.empty()) return;
        mPendingJobs.fetch_add((uint32_t)newJobs.size(), std::memory_order_relaxed);
        {
            std::lock_guard<std::mutex> lock(mJobMutex);
            for (auto& job : newJobs) mJobQueue.push_back(job);
        }
        mJobCv.notify_all();
    }

    void QuadLightVideoPlayer::tick(double currentTime)
    {
        mAdvancedThisTick = false;

        // Promote anything the worker finished since the last tick, so a frame that just
        // became ready is visible to the readiness check below within the same tick.
        finalizeReadyResults();

        if (mFrameStartTime < 0.0)
        {
            mFrameStartTime = currentTime;
            return;
        }

        const uint32_t playlistSize = (uint32_t)mPlaylist.size();
        const uint32_t currentPlaylistIndex = (uint32_t)(mSequence % playlistSize);

        const double elapsedMs = (currentTime - mFrameStartTime) * 1000.0;
        if (elapsedMs < (double)mPlaylist.entries()[currentPlaylistIndex].durationMs) return;

        // Due to advance - only do so if the next frame is actually ready (stall on the
        // current frame otherwise, accepting timing drift, rather than ever skipping a frame).
        const uint64_t nextSequence = mSequence + 1;
        Slot& nextSlot = mSlots[nextSequence % mSlots.size()];
        if (!nextSlot.ready) return;

        const uint32_t nextPlaylistIndex = (uint32_t)(nextSequence % playlistSize);
        if (nextSlot.playlistIndex != nextPlaylistIndex || nextSlot.generation != mGeneration) return; // stale content mid-rebuild - stall.

        mSequence = nextSequence;
        mFrameStartTime = currentTime;
        mAdvancedThisTick = true;

        ensureJobsQueued();
    }

    bool QuadLightVideoPlayer::consumeAdvanced()
    {
        const bool v = mAdvancedThisTick;
        mAdvancedThisTick = false;
        return v;
    }

    ref<Texture> QuadLightVideoPlayer::getCurrentTexture() const
    {
        return mSlots[mSequence % mSlots.size()].pTexture;
    }

    std::unique_ptr<QuadLightSampler> QuadLightVideoPlayer::takeCurrentSampler()
    {
        return std::move(mSlots[mSequence % mSlots.size()].pSampler);
    }

    void QuadLightVideoPlayer::onSamplerTypeChanged(QuadLightSamplerType newType)
    {
        mSamplerType = newType;
        ++mGeneration;
        ensureJobsQueued();
    }

    uint32_t QuadLightVideoPlayer::getPlaybackIndex() const
    {
        return (uint32_t)(mSequence % mPlaylist.size());
    }

    uint32_t QuadLightVideoPlayer::getReadySlotCount() const
    {
        uint32_t count = 0;
        for (const Slot& slot : mSlots)
        {
            if (slot.ready) ++count;
        }
        return count;
    }
}
