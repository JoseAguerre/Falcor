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
__exported import Utils.Sampling.SampleGeneratorInterface;
import Utils.Sampling.Pseudorandom.LCG;
import Utils.Sampling.Pseudorandom.SplitMix64;
import Utils.Math.BitTricks;
import Utils.Math.HashUtils;

/// Number of real low-discrepancy Halton dimensions before falling back to the PRNG - see kHaltonPrimes below.
static const uint kNumHaltonDimensions = 32;

/// The first 32 primes - the Halton bases for dimensions 0..31.
static const uint kHaltonPrimes[kNumHaltonDimensions] = {
    2,  3,  5,  7,  11,  13,  17,  19,  23,  29,  31,  37,  41,  43,  47,  53,
    59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131
};

/**
 * Radical inverse in base 2 (van der Corput sequence) via cascading bit-reversal - reused
 * from the caller's own existing RadicalInverse_VdC()/Hammersley() utility, ported to this
 * codebase's uint-fixed-point convention (next()'s callers rescale to a float themselves,
 * matching every other SampleGenerator's raw-uint return convention). Directly checkable:
 * index=1 (binary ...0001) reverses to 0x80000000 = 0.5; index=3 (...0011) reverses to
 * 0xC0000000 = 0.75, matching van der Corput(1)=0.5 and van der Corput(3)=0.75.
 */
uint radicalInverseBase2(uint index)
{
    index = (index << 16u) | (index >> 16u);
    index = ((index & 0x55555555u) << 1u) | ((index & 0xAAAAAAAAu) >> 1u);
    index = ((index & 0x33333333u) << 2u) | ((index & 0xCCCCCCCCu) >> 2u);
    index = ((index & 0x0F0F0F0Fu) << 4u) | ((index & 0xF0F0F0F0u) >> 4u);
    index = ((index & 0x00FF00FFu) << 8u) | ((index & 0xFF00FF00u) >> 8u);
    return index;
}

/**
 * Radical inverse in an arbitrary base: extracts `index`'s digits in `base` least-significant
 * first, accumulates them into a base-`base` integer with digit order reversed (so the
 * least-significant digit of `index` becomes the most-significant digit of the result - the
 * digit-reversal that defines a radical inverse), then rescales by base^-(digit count) into
 * the full 32-bit fixed-point range. Hand-verified: base=3, index=1 -> digit 1, reversedDigits=1,
 * one digit -> 1/3 (matches radical inverse of 1 in base 3 = "0.1"base3 = 1/3). index=3, base=3:
 * digits of 3 in base 3 are (0, 1) least-significant first -> reversedDigits accumulates to
 * 0*3+1=1 over 2 digits -> 1/9 (matches "3" = "10"base3 reversed to "01"base3 = 0.01base3 = 1/9).
 */
uint radicalInverseBaseN(uint index, uint base)
{
    const float invBase = 1.0f / float(base);
    float invBaseN = 1.0f;
    uint reversedDigits = 0;
    while (index > 0)
    {
        uint next = index / base;
        uint digit = index - next * base;
        reversedDigits = reversedDigits * base + digit;
        invBaseN *= invBase;
        index = next;
    }
    return uint(min(float(reversedDigits) * invBaseN * 4294967296.0f, 4294967295.0f));
}

/**
 * Scrambled Halton sample generator - EXPERIMENTAL, replaces the earlier Sobol attempt.
 *
 * The earlier Sobol generator was hard-capped at 2 real low-discrepancy dimensions: a proper
 * Sobol sequence needs a precomputed direction-number table per dimension, and only dimension
 * 0 (van der Corput base 2) and dimension 1 (the trivial degree-1 polynomial) are safe to
 * derive from first principles - every dimension beyond that needs values from a published,
 * verified table this codebase doesn't have. That made "works for all samples" unreachable
 * without a source for that table.
 *
 * Halton sidesteps the missing-table problem: dimension d's sequence is just the radical
 * inverse (digit-reversal) of the sample index in the d-th prime base, and "the d-th prime"
 * is a self-evidently correct, easily-checkable fact - no direction numbers, no published
 * table to trust. So this generator supports kNumHaltonDimensions (32) real low-discrepancy draws
 * per sample instead of 2, using the first 32 primes below, and only falls back to a PRNG
 * (the same 32-bit LCG the Sobol version used) past that. 32 real dimensions comfortably
 * covers realistic path depths (NEE + BSDF sampling + Russian roulette per bounce typically
 * cost 3-6 draws each, so 32 covers roughly 5-8 bounces of full QMC coverage) - the fallback
 * still exists because path length is unbounded (Russian roulette can run arbitrarily long),
 * so a literal, unconditional "every sample" guarantee isn't achievable by any fixed-size
 * table, Halton included.
 *
 * What this does NOT fix (inherent to applying QMC inside a general path tracer, not a
 * property of Sobol vs. Halton): dimension index d doesn't mean the same physical decision
 * for every pixel, since different materials and bounce histories consume draws in different
 * orders/counts. This is a structural approximation shared by both attempts.
 *
 * Quality note: Halton in higher dimensions (larger prime bases) is known to develop visible
 * correlation between dimensions unless mitigated - the per-dimension scramble below
 * (Cranley-Patterson rotation, decorrelating each dimension independently per pixel) is the
 * standard basic mitigation, not a full fix (e.g. Owen scrambling would be stronger but is a
 * materially bigger undertaking). Expect the benefit to be strongest in the first several
 * dimensions and to taper off in the higher ones.
 *
 * Kept to 16 bytes (PathState.sg's documented 4-16B budget - see the DXR ray payload size
 * comment in PathTracer.cpp's setMaxPayloadSize() call) by storing only one scramble word;
 * each dimension's scramble is derived from it via jenkinsHash(scramble + dimension) instead
 * of storing 32 independent words.
 */
export struct HaltonSampleGenerator : ISampleGenerator
{
    struct Padded
    {
        HaltonSampleGenerator internal;
    }

    /**
     * Initializes the sample generator for a given pixel and sample number.
     * @param[in] pixel Pixel id.
     * @param[in] sampleNumber Sample number - this is the Halton sequence index.
     */
    __init(uint2 pixel, uint sampleNumber)
    {
        this.index = sampleNumber;
        this.dimension = 0;

        // Same (pixel, sampleNumber) -> SplitMix64 seeding the other generators use.
        SplitMix64 seedGen = createSplitMix64(interleave_32bit(pixel), sampleNumber);
        uint64_t s = nextRandom64(seedGen);
        this.scramble = uint(s);
        this.fallbackRng = createLCG(uint(s >> 32));
    }

    /**
     * Returns the next sample value. This function updates the state.
     */
    [mutating]
    uint next()
    {
        uint d = dimension;
        dimension = d + 1;
        if (d >= kNumHaltonDimensions) return nextRandom(fallbackRng);

        uint base = kHaltonPrimes[d];
        uint raw = (base == 2) ? radicalInverseBase2(index) : radicalInverseBaseN(index, base);
        uint dimScramble = (d == 0) ? scramble : jenkinsHash(scramble + d);
        // Cranley-Patterson rotation: modular addition in fixed-point [0,1) space (uint
        // arithmetic wraps naturally). Addition, not XOR, is what's mathematically valid for
        // a general (non-binary) base's digit expansion.
        return raw + dimScramble;
    }

    uint index;      ///< The Halton sequence index (the sample number passed to __init) - shared by every dimension.
    uint dimension;  ///< Which dimension the next call should draw (>= kNumHaltonDimensions falls back to the PRNG).
    uint scramble;   ///< Per-pixel Cranley-Patterson scramble seed for dimension 0 (other dimensions' are derived from this via jenkinsHash).
    LCG fallbackRng; ///< PRNG used for every draw beyond kNumHaltonDimensions.
};
