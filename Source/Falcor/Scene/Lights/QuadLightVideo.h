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
#include "Core/Macros.h"
#include "Core/Object.h"
#include "Rendering/Lights/QuadLightSamplerType.slangh"
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <memory>
#include <mutex>
#include <optional>
#include <thread>
#include <vector>

namespace Falcor
{
    class Device;
    class Texture;
    class QuadLight;
    class QuadLightSampler;
    class Bitmap;

    /** One entry of a parsed playlist (.exrplaylist/.hdrplaylist): a source image path and
        how long (in milliseconds) it should be the minimum display time before playback
        advances.
    */
    struct QuadLightPlaylistEntry
    {
        std::filesystem::path path; ///< Absolute, resolved relative to the playlist file's own directory.
        uint32_t durationMs = 0;    ///< Minimum display time in milliseconds.
    };

    /** Parses a playlist text file (conventionally named .exrplaylist or .hdrplaylist -
        parsing itself is format-agnostic; QuadLight.cpp is what decides, by extension,
        whether a given path should be treated as a playlist at all): one
        "<filename> <durationMs>" pair per non-blank,
        non-comment line, whitespace-separated. Each entry's image is decoded via
        Bitmap::createFromFile, which auto-detects format from file content, so a single
        playlist may even mix formats (e.g. EXR and HDR frames) if desired. Filenames are
        resolved relative to the playlist file's own directory (there is no scene-builder/
        Python asset-resolution context available at the arbitrary runtime points this gets
        parsed from, unlike .pyscene asset paths).

        An optional directive line "#prefetch <N>" or "#prefetch all" may appear anywhere
        in the file to override the default prefetch ring depth (see
        QuadLightVideoPlayer) - "all" requests the entire playlist be kept resident at
        once. Ordinary "#"-prefixed comment lines are otherwise ignored.

        Individual malformed lines are skipped with a logged warning rather than failing
        the whole playlist (matches QuadLightLuminance.cpp's tolerance style) - parsing
        only fails outright if the playlist file itself can't be opened, or if it
        contains zero valid entries.
    */
    class FALCOR_API QuadLightPlaylist
    {
    public:
        /** Parse a playlist file (.exrplaylist/.hdrplaylist).
            \param[in] playlistPath Path to the playlist file.
            \return The parsed playlist, or std::nullopt if the file couldn't be opened or contained no valid entries.
        */
        static std::optional<QuadLightPlaylist> parseFile(const std::filesystem::path& playlistPath);

        const std::vector<QuadLightPlaylistEntry>& entries() const { return mEntries; }
        size_t size() const { return mEntries.size(); }

        /** Requested prefetch ring depth from a "#prefetch <N>"/"#prefetch all" directive
            line, or std::nullopt if the playlist didn't specify one (caller should fall
            back to its own default). "all" is represented as a very large sentinel value -
            callers should clamp against size() rather than compare against a magic number.
        */
        std::optional<uint32_t> requestedPrefetchDepth() const { return mPrefetchDepth; }

    private:
        std::vector<QuadLightPlaylistEntry> mEntries;
        std::optional<uint32_t> mPrefetchDepth;
    };

    /** Plays back a QuadLightPlaylist on a background worker thread: keeps a ring buffer
        of prefetched frames (decoded texture + fully-built QuadLightSampler for the
        currently-selected technique) a configurable number of frames ahead of playback,
        so advancing to the next frame is an instant pointer swap rather than a blocking
        decode+build. Advances to the next frame once the current one's minimum duration
        has elapsed (looping back to the start at the end of the playlist) - or stalls on
        the current frame if the next one isn't ready yet (background decode fell behind),
        rather than ever skipping/dropping a frame.

        Two-phase build, split specifically along the "touches the GPU" line:
          1. The background worker thread only decodes the source image (Bitmap::createFromFile)
             and computes CPU-side luminance data - genuinely thread-safe, no GPU API calls
             at all. Results are packaged into a PreparedResult and handed off through a
             plain mutex-guarded queue.
          2. The MAIN thread (inside tick(), via finalizeReadyResults()) does the actual GPU
             work - Texture::createFromBitmap() and building the QuadLightSampler's GPU
             buffers - and writes the finished result into the target Slot.
        This split is required, not just a style choice: Texture/Buffer creation with
        initial data both upload through the single Device-wide RenderContext
        (Texture::uploadInitData()/Buffer::setBlob(), see Texture.cpp/Buffer.cpp), which is
        the exact same RenderContext the main thread records its own per-frame rendering
        commands through - it is not thread-safe, and having a background thread call it
        concurrently with the main render loop corrupts shared command-encoder state (this
        was root-caused from a real crash: the corruption surfaced later, in unrelated main-
        thread rendering code, which is the classic signature of this kind of race). Because
        of this, Slot itself is now written only by the main thread - no atomics needed on
        it - and the only cross-thread synchronization left is the two plain job/result
        queues below.

        Ring buffer design: each of the `ringSize` slots is claimed by exactly one
        "playback position" (a monotonically increasing sequence number, decoupled from the
        playlist's own wraparound) at a time, via slot = position % ringSize.

        Live technique switches (onSamplerTypeChanged()) use a generation counter rather
        than flushing in-flight work: bumping it makes every slot's cached generation stale,
        so ensureJobsQueued() re-requests the whole window under the new technique, and any
        in-flight job for the old technique is simply discarded (its generation won't match)
        once finalizeReadyResults() gets to it.
    */
    class FALCOR_API QuadLightVideoPlayer
    {
    public:
        /** Default prefetch ring depth used when a playlist doesn't specify "#prefetch". */
        static constexpr uint32_t kDefaultPrefetchDepth = 6;

        QuadLightVideoPlayer(ref<Device> pDevice, ref<QuadLight> pOwner, QuadLightPlaylist playlist, QuadLightSamplerType initialType);
        ~QuadLightVideoPlayer(); // joins the worker thread.

        /** Blocking: synchronously decodes+builds the first frame, starts the background
            worker, then BLOCKS until the entire prefetch ring is warm before returning - so
            e.g. "#prefetch 100" genuinely means "load 100 frames before playback starts",
            not just "allow up to 100 frames of lookahead once already running". This can
            take a while for a large ring (that's the whole point when explicitly
            requested, e.g. "#prefetch all" on a long playlist). Called once, right after
            construction.
        */
        void primeFirstFrame();

        /** Called once per frame (from QuadLight::updateVideoPlayback(), itself called from
            Scene::update()) with the current scene-clock time in seconds. Advances to the
            next frame if its minimum duration has elapsed AND it's ready in the ring;
            otherwise stalls on the current frame (accepting timing drift) until it is.
        */
        void tick(double currentTimeSeconds);

        /** True exactly once after a tick() that advanced the frame, then clears. */
        bool consumeAdvanced();

        ref<Texture> getCurrentTexture() const;

        /** Returns the prebuilt sampler for the current frame, consuming it - a second call
            returns null until the next advance. Null if it isn't ready yet (shouldn't
            normally happen for the *current* frame, since tick() only advances once the
            next slot is ready, but the very first frame's sampler is only available once
            primeFirstFrame()'s synchronous build completes).
        */
        std::unique_ptr<QuadLightSampler> takeCurrentSampler();

        /** Notifies the player that the selected sampling technique changed - invalidates
            (via generation bump) all in-flight/cached prefetch work and re-requests the
            current window under the new technique.
        */
        void onSamplerTypeChanged(QuadLightSamplerType newType);

        uint32_t getPlaybackIndex() const;
        uint32_t getPlaylistSize() const { return (uint32_t)mPlaylist.size(); }
        uint32_t getReadySlotCount() const;
        uint32_t getPrefetchDepth() const { return (uint32_t)mSlots.size(); }

    private:
        /** One ring-buffer slot: prefetched GPU texture + sampler for a single playback
            position. Written only by the main thread, via finalizeReadyResults() - see the
            class doc comment for why GPU work can't happen on the worker thread.
        */
        struct Slot
        {
            ref<Texture> pTexture;
            std::unique_ptr<QuadLightSampler> pSampler;
            uint32_t playlistIndex = 0;
            uint64_t generation = 0;
            bool ready = false;
        };

        /** A unit of background work: decode one playlist frame under one sampler
            technique/generation, for one target slot.
        */
        struct Job
        {
            uint32_t slotIndex;
            uint32_t playlistIndex;
            QuadLightSamplerType type;
            uint64_t generation;
        };

        /** The CPU-only result of one Job, produced by the worker thread and handed off
            through mResultsQueue for the main thread to turn into actual GPU resources.
            Deliberately carries no GPU objects.
        */
        struct PreparedResult
        {
            uint32_t slotIndex;
            uint32_t playlistIndex;
            QuadLightSamplerType type;
            uint64_t generation;
            std::unique_ptr<const Bitmap> pBitmap; ///< Decoded source image - texture creation is deferred to the main thread.
            std::vector<float> luminance;          ///< Empty for QuadLightSamplerType::Random, which needs none.
            uint32_t width = 0, height = 0;
        };

        /** Worker thread only: decode+compute the CPU-side data for one job (no GPU calls),
            and push the result to mResultsQueue. Also used directly (synchronously, on the
            main thread) by primeFirstFrame().
        */
        PreparedResult prepareJob(const Job& job);

        /** Main thread only: does the actual GPU work (Texture::createFromBitmap() +
            building the QuadLightSampler's GPU buffers) for one already-decoded
            PreparedResult, and writes the result into its target Slot.
        */
        void finalizeResult(PreparedResult&& result);

        void runWorker();

        /** Main-thread only: drains any results the worker has finished since the last
            call and finalizes them (see finalizeResult()) - must run before tick() checks
            slot readiness, so newly-completed frames are visible this frame.
        */
        void finalizeReadyResults();

        /** Main-thread only: tops up the ring so every position in
            [mSequence, mSequence + ringSize - 1] has an in-flight or completed job matching
            the current sampler technique/generation, skipping positions already requested.
        */
        void ensureJobsQueued();

        ref<Device> mpDevice;
        QuadLight* mpOwner; ///< Non-owning - the player is itself owned by this QuadLight, so its lifetime always exceeds the player's. A ref<QuadLight> here would create an ownership cycle (see QuadLightSampler.h's getQuadLight() comment for the same issue).
        QuadLightPlaylist mPlaylist;

        std::vector<Slot> mSlots; ///< Main-thread only.
        // Main-thread only: which (playlistIndex, generation) each slot was last requested to
        // build, so ensureJobsQueued() doesn't spam duplicate jobs for an already-in-flight
        // want. Deliberately keyed by *content wanted*, not by the raw ring-cycle position -
        // a slot whose ready content already matches what's wanted (e.g. the playlist looped
        // back to a frame this slot cached last pass) is recognized as already satisfied
        // directly from the slot itself (see ensureJobsQueued()), without ever re-requesting
        // a rebuild of identical content.
        std::vector<uint32_t> mSlotRequestedPlaylistIndex;
        std::vector<uint64_t> mSlotRequestedGeneration;

        QuadLightSamplerType mSamplerType; ///< Main-thread only.
        uint64_t mGeneration = 0;          ///< Main-thread only; bumped by onSamplerTypeChanged().

        uint64_t mSequence = 0;        ///< Monotonically increasing playback position (never wraps in practice); playlist index = mSequence % playlist.size().
        double mFrameStartTime = -1.0; ///< -1 sentinel = "not yet started".
        bool mAdvancedThisTick = false;

        std::mutex mJobMutex;
        std::condition_variable mJobCv;
        std::deque<Job> mJobQueue; ///< Main thread pushes, worker thread pops.
        bool mTerminate = false;
        std::thread mWorker;

        std::mutex mResultsMutex;
        std::deque<PreparedResult> mResultsQueue; ///< Worker thread pushes (CPU-only data), main thread pops and finalizes.

        // Count of jobs pushed to mJobQueue that haven't yet had their PreparedResult pushed
        // to mResultsQueue - incremented by the main thread (ensureJobsQueued()), decremented
        // by the worker thread right after it pushes a result (release ordering, so a main-
        // thread observation of 0 guarantees every push it implies is already visible through
        // mResultsMutex). Used by primeFirstFrame() to block until the whole ring is warm.
        std::atomic<uint32_t> mPendingJobs{0};
    };
}
