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

/// Number of real low-discrepancy Weyl dimensions before falling back to the PRNG - see kWeylPrimes below.
static const uint kNumWeylDimensions = 64;

/// The first 64 primes - sqrt() of each is this generator's per-dimension irrational constant (see next() below).
static const uint kWeylPrimes[kNumWeylDimensions] = {
    2,   3,   5,   7,   11,  13,  17,  19,  23,  29,  31,  37,  41,  43,  47,  53,
    59,  61,  67,  71,  73,  79,  83,  89,  97,  101, 103, 107, 109, 113, 127, 131,
    137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211, 223,
    227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277, 281, 283, 293, 307, 311
};

/**
 * Weyl/Kronecker additive-recurrence sample generator - EXPERIMENTAL, a second QMC option
 * alongside HaltonSampleGenerator with a different (and cheaper to extend) way of handling
 * "arbitrary" dimension counts.
 *
 * Construction: for irrational alpha, the sequence x_n = frac(n * alpha) is a classic
 * low-discrepancy 1D point set (Weyl's equidistribution theorem - true for ANY irrational
 * alpha, with the quality of the distribution governed by how well alpha resists rational
 * approximation). Extended to multiple dimensions by giving each dimension its own
 * *independent* irrational constant: dimension d uses alpha_d = frac(sqrt(prime(d))), since
 * the square root of a non-perfect-square integer is always irrational - a fact that doesn't
 * need a published/verified table to trust (unlike Sobol's direction numbers), and holds for
 * literally any prime you pick, which is what makes this "unbounded-dimension-friendly" in a
 * way Sobol fundamentally isn't: adding more dimensions here is a one-line table extension
 * (list more primes), not a research problem.
 *
 * This is NOT literally unbounded either, though: kNumWeylDimensions (64, double Halton's 32)
 * is still a fixed table size, past which this falls back to the same PRNG (LCG) pattern used
 * by the Halton and (now-removed) Sobol generators. The difference from Sobol/Halton is only
 * that *raising* this cap costs nothing but listing more primes - there's no missing-table
 * problem blocking it, so you can push it arbitrarily high if 64 dimensions isn't enough for
 * a given path depth.
 *
 * Numerical caveat specific to this construction (doesn't apply to Halton's digit-reversal
 * approach): x_n = frac(n * alpha) is computed in float32. For very large n (accumulated
 * sample index in the tens of thousands or more) the product n * alpha loses precision at the
 * bit-width of n, and frac() of an imprecise product can develop visible quantization/banding
 * rather than true low-discrepancy behavior. Fine for typical real-time accumulation lengths
 * (hundreds to a few thousand frames), degrades for very long unbroken accumulations.
 *
 * Same caveats as Halton beyond that: dimension index doesn't correspond to the same physical
 * decision across pixels with different materials/bounce counts, and the per-dimension
 * Cranley-Patterson scramble (derived from one stored word via jenkinsHash, not stored per
 * dimension) is a basic decorrelation mitigation, not a full one.
 *
 * Kept to 16 bytes (PathState.sg's documented 4-16B budget, see PathTracer.cpp's
 * setMaxPayloadSize() comment) - identical layout/fields to HaltonSampleGenerator.
 */
export struct WeylSampleGenerator : ISampleGenerator
{
    struct Padded
    {
        WeylSampleGenerator internal;
    }

    /**
     * Initializes the sample generator for a given pixel and sample number.
     * @param[in] pixel Pixel id.
     * @param[in] sampleNumber Sample number - this is the Weyl sequence index (n in x_n = frac(n * alpha)).
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
        if (d >= kNumWeylDimensions) return nextRandom(fallbackRng);

        // alpha_d = frac(sqrt(prime(d))) - computed via the GPU's own sqrt() intrinsic rather
        // than hand-transcribed decimal constants, so there's no risk of a copied-down digit
        // being wrong.
        float alpha = frac(sqrt(float(kWeylPrimes[d])));
        float x = frac(float(index) * alpha);
        uint raw = uint(min(x * 4294967296.0f, 4294967295.0f));

        uint dimScramble = (d == 0) ? scramble : jenkinsHash(scramble + d);
        // Cranley-Patterson rotation: modular addition in fixed-point [0,1) space (uint
        // arithmetic wraps naturally).
        return raw + dimScramble;
    }

    uint index;      ///< The Weyl sequence index (the sample number passed to __init) - shared by every dimension.
    uint dimension;  ///< Which dimension the next call should draw (>= kNumWeylDimensions falls back to the PRNG).
    uint scramble;   ///< Per-pixel Cranley-Patterson scramble seed for dimension 0 (other dimensions' are derived from this via jenkinsHash).
    LCG fallbackRng; ///< PRNG used for every draw beyond kNumWeylDimensions.
};
