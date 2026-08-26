// Standalone HDR (Radiance RGBE) image-loading benchmark, independent of the Falcor build.
// Compares several ways of getting the same .hdr file into a CPU-side float RGB buffer:
//   1. FreeImage        - the library Falcor::Bitmap actually uses today (baseline).
//   2. stb_image        - a widely-used single-header decoder (stbi_loadf).
//   3. CustomRGBE       - a minimal hand-rolled Radiance RGBE reader (new-style per-channel
//                         RLE scanlines, with an old-style/flat fallback), reading the whole
//                         file into memory once rather than streaming through a FILE*.
//   4. ReferenceRGBE    - Bruce Walter's canonical public-domain rgbe.c/rgbe.h reference
//                         implementation (the format's own reference decoder), FILE*-
//                         streaming style - a genuine second, independently-written library.
//   5. CustomRGBE-LUT   - same as #3, but replaces the per-pixel ldexpf() exponent-scale
//                         call (measured as >50% of decode time - see the phase breakdown)
//                         with a precomputed 256-entry lookup table.
//   6. CustomRGBE-AVX2  - same as #5, but gathers 8 lookups at once via _mm256_i32gather_ps,
//                         to see whether that beats a plain scalar LUT for a table this small.
//   7. libvips          - a real general-purpose library, deps/vips/ (libvips 8.18.6,
//                         prebuilt MXE/MinGW Windows package from libvips/build-win64-mxe).
//                         That package ships GNU-ar-format .lib files MSVC's linker can't
//                         read directly, so deps/vips/vips-dev-8.18/*_msvc.lib were
//                         regenerated from the DLLs' export tables (dumpbin /exports -> a
//                         .def file -> `lib /def:`) - a standard technique for linking MSVC
//                         code against a MinGW-built DLL. Only viable because libvips's
//                         public C API is plain, unmangled C - the bundled libvips-cpp.dll
//                         (C++ wrapper) is NOT usable this way, since MinGW/MSVC C++ name
//                         mangling schemes are incompatible.
//
//   8. DevIL            - deps/devil/ (DevIL Windows SDK 1.8.0, prebuilt MSVC binaries from
//                         SourceForge - already MSVC-compatible .lib files, no relinking
//                         needed).
//   9. OpenImageIO      - deps/vcpkg/ (a real vcpkg checkout, bootstrapped and used to build
//                         openimageio:x64-windows 3.1.14.0 from source - no prebuilt Windows
//                         package exists anywhere: the official releases ship source only,
//                         and the one community-maintained Windows binary mirror found
//                         (analogstudio/OpenImageIO-win64) turned out to be runtime DLLs
//                         only, no headers/import libs, so it couldn't be linked against.
//                         vcpkg builds natively with MSVC, so unlike libvips's package,
//                         nothing needed relinking - see CMakeLists.txt's find_package call.
//
// All variants are cross-checked against each other with a real per-pixel comparison (not
// just an aggregate average) so a silently-broken decoder shows up immediately as a large
// discrepancy rather than just a suspiciously fast number.

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_HDR
#include "stb_image.h"

#include <FreeImage.h>

extern "C"
{
#include "rgbe_ref/rgbe.h"
}

// vips.h already self-guards its own plain-C API with extern "C" internally, but also pulls
// in C++ standard headers (<atomic>/<type_traits> etc. via GLib) - wrapping the whole
// include in an outer extern "C" block (as done for rgbe.h above) forces those into C
// linkage too, which is illegal for templates. Include unwrapped and let vips.h's own
// guards do the right thing.
#include <vips/vips.h>

#include <IL/il.h>

#include <OpenImageIO/imageio.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <immintrin.h>
#include <omp.h>
#include <string>
#include <vector>

static const char* kPath = R"(C:\Users\Elojo\Downloads\vp9macroblock\vp9macroblock-viewer\encoded\frames\hdr\frame_00048.hdr)";
static const char* kExrPath = R"(C:\Users\Elojo\Downloads\vp9macroblock\vp9macroblock-viewer\encoded\frames\frame_00048.exr)";
static const char* kPlaylistPath = R"(C:\Users\Elojo\Downloads\vp9macroblock\vp9macroblock-viewer\encoded\frames\hdr\fear.hdrplaylist)";
static const int kIterations = 8;

using Clock = std::chrono::high_resolution_clock;

static double elapsedMs(Clock::time_point a, Clock::time_point b)
{
    return std::chrono::duration<double, std::milli>(b - a).count();
}

struct LoadResult
{
    bool ok = false;
    int width = 0, height = 0;
    double totalMs = 0.0;
    float r00 = 0.f, g00 = 0.f, b00 = 0.f; // first-pixel sample - informational only (top-down vs bottom-up storage differs between libraries, so this is not directly comparable across them)
    double avgLuminance = 0.0;             // a weak check on its own (see below) - kept as a quick eyeball summary.
    bool bottomUp = false;                 // true for FreeImage (row 0 = bottom of image), false for stb_image/CustomRGBE (row 0 = top).
    std::vector<float> pixels;             // full RGB buffer, row-major according to `bottomUp` above - retained so verifyPixelsMatch() can do a real per-pixel comparison, not just compare a single aggregate scalar.
};

static double computeAvgLuminance(const float* rgb, size_t pixelCount)
{
    double sum = 0.0;
    for (size_t i = 0; i < pixelCount; ++i)
    {
        sum += 0.2126 * rgb[i * 3 + 0] + 0.7152 * rgb[i * 3 + 1] + 0.0722 * rgb[i * 3 + 2];
    }
    return sum / (double)pixelCount;
}

// --- 1. FreeImage ---

static LoadResult loadWithFreeImage(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    FREE_IMAGE_FORMAT fif = FreeImage_GetFileType(path, 0);
    if (fif == FIF_UNKNOWN) fif = FreeImage_GetFIFFromFilename(path);
    if (fif == FIF_UNKNOWN) return res;

    FIBITMAP* dib = FreeImage_Load(fif, path, 0);
    if (!dib) return res;

    unsigned w = FreeImage_GetWidth(dib);
    unsigned h = FreeImage_GetHeight(dib);
    FREE_IMAGE_TYPE type = FreeImage_GetImageType(dib);

    std::vector<float> pixels((size_t)w * h * 3);
    if (type == FIT_RGBF)
    {
        for (unsigned y = 0; y < h; ++y)
        {
            const FIRGBF* row = (const FIRGBF*)FreeImage_GetScanLine(dib, (int)y);
            for (unsigned x = 0; x < w; ++x)
            {
                size_t idx = ((size_t)y * w + x) * 3;
                pixels[idx + 0] = row[x].red;
                pixels[idx + 1] = row[x].green;
                pixels[idx + 2] = row[x].blue;
            }
        }
    }
    else
    {
        FreeImage_Unload(dib);
        return res; // unexpected type for a .hdr - don't silently report a bogus result.
    }

    auto t1 = Clock::now();
    FreeImage_Unload(dib);

    res.ok = true;
    res.width = (int)w;
    res.height = (int)h;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), (size_t)w * h);
    res.bottomUp = true;
    res.pixels = std::move(pixels);
    return res;
}

// --- 2. stb_image ---

static LoadResult loadWithStbImage(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    int w = 0, h = 0, channelsInFile = 0;
    float* data = stbi_loadf(path, &w, &h, &channelsInFile, 3); // force 3 channels for a fair comparison

    auto t1 = Clock::now();
    if (!data) return res;

    res.ok = true;
    res.width = w;
    res.height = h;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = data[0];
    res.g00 = data[1];
    res.b00 = data[2];
    res.avgLuminance = computeAvgLuminance(data, (size_t)w * h);
    res.bottomUp = false;
    res.pixels.assign(data, data + (size_t)w * h * 3);

    stbi_image_free(data);
    return res;
}

// --- 3. Minimal hand-rolled Radiance RGBE reader ---
//
// Deliberately split into 4 clean, non-overlapping phases (unlike a typical streaming
// reader, which would interleave disk reads with parsing): read the whole file into memory
// first, then do everything else purely from that in-memory buffer. This is what makes it
// possible to time "disk I/O" separately from "decode" at all - a FILE*-streaming version
// has no such boundary, since every fgetc()/fread() call is doing both at once.

struct RGBEDecodeTimings
{
    double readFileMs = 0.0;    // fopen+fread the whole file into memory.
    double headerParseMs = 0.0; // ASCII header + resolution line, from the in-memory buffer.
    double rleUnpackMs = 0.0;   // per-scanline RLE decode into raw RGBE bytes (still integers, no conversion).
    double rgbeToFloatMs = 0.0; // the numeric RGBE -> float conversion pass.
    double totalMs = 0.0;
};

// Minimal read cursor over an in-memory buffer - same role fread/fgetc played against a
// FILE*, but with no system calls once the initial read (phase 1) is done.
struct ByteReader
{
    const unsigned char* data;
    size_t size;
    size_t pos = 0;

    int getc()
    {
        return pos < size ? data[pos++] : -1;
    }
    size_t read(unsigned char* dst, size_t n)
    {
        size_t toRead = std::min(n, size - pos);
        memcpy(dst, data + pos, toRead);
        pos += toRead;
        return toRead;
    }
};

static bool readHeaderMem(ByteReader& r, int& width, int& height)
{
    auto readLine = [&](std::string& out) -> bool
    {
        out.clear();
        if (r.pos >= r.size) return false;
        while (r.pos < r.size)
        {
            char c = (char)r.data[r.pos++];
            if (c == '\n') break;
            if (c != '\r') out.push_back(c);
        }
        return true;
    };

    std::string line;
    while (readLine(line))
    {
        if (line.empty()) break; // blank line ends the header
    }
    if (!readLine(line)) return false;

    int h = 0, w = 0;
    if (sscanf(line.c_str(), "-Y %d +X %d", &h, &w) == 2 || sscanf(line.c_str(), "+Y %d +X %d", &h, &w) == 2)
    {
        width = w;
        height = h;
        return width > 0 && height > 0;
    }
    return false;
}

static inline void rgbeToFloat(unsigned char r, unsigned char g, unsigned char b, unsigned char e, float& outR, float& outG, float& outB)
{
    if (e == 0)
    {
        outR = outG = outB = 0.f;
        return;
    }
    float f = ldexpf(1.0f, (int)e - (128 + 8));
    outR = r * f;
    outG = g * f;
    outB = b * f;
}

// New-style scanline: 4 planar-RLE-encoded channels (R,G,B,E), each independently
// run-length-encoded: a length byte >128 means "repeat the next byte (len-128) times",
// <=128 means "len literal bytes follow".
static bool readScanlineNewRLEMem(ByteReader& r, int width, unsigned char* planar)
{
    for (int channel = 0; channel < 4; ++channel)
    {
        int x = 0;
        unsigned char* dst = planar + (size_t)channel * width;
        while (x < width)
        {
            int c = r.getc();
            if (c < 0) return false;
            if (c > 128)
            {
                int count = c - 128;
                int val = r.getc();
                if (val < 0 || x + count > width) return false;
                memset(dst + x, (unsigned char)val, count);
                x += count;
            }
            else
            {
                int count = c;
                if (x + count > width) return false;
                if (r.read(dst + x, count) != (size_t)count) return false;
                x += count;
            }
        }
    }
    return true;
}

// --- Shared helpers, reused by all CustomRGBE-* variants below ---

static bool readWholeFile(const char* path, std::vector<unsigned char>& out)
{
    FILE* f = fopen(path, "rb");
    if (!f) return false;
    fseek(f, 0, SEEK_END);
    long fileSize = ftell(f);
    fseek(f, 0, SEEK_SET);
    out.resize((size_t)fileSize);
    size_t got = fread(out.data(), 1, (size_t)fileSize, f);
    fclose(f);
    return got == (size_t)fileSize;
}

// RLE-unpacks every scanline into a raw RGBE byte buffer (integers, no floating-point
// conversion yet) - isolates "parse the compression" from "convert the numbers", mirroring
// FreeImage's own separate decode/conversion phases. `r` must already be positioned right
// after the header (see readHeaderMem()).
static bool rleUnpackAll(ByteReader& r, int width, int height, std::vector<unsigned char>& rgbeOut)
{
    rgbeOut.assign((size_t)width * height * 4, 0);
    std::vector<unsigned char> planar((size_t)width * 4);
    for (int y = 0; y < height; ++y)
    {
        size_t rowStart = r.pos;
        unsigned char marker[4];
        size_t got4 = r.read(marker, 4);
        bool isNewRLE = got4 == 4 && marker[0] == 2 && marker[1] == 2 && width >= 8 && width < 0x8000 &&
                        ((marker[2] << 8) | marker[3]) == width;

        unsigned char* rowOut = rgbeOut.data() + (size_t)y * width * 4;
        if (isNewRLE)
        {
            if (!readScanlineNewRLEMem(r, width, planar.data())) return false;
            for (int x = 0; x < width; ++x)
            {
                rowOut[x * 4 + 0] = planar[0 * width + x];
                rowOut[x * 4 + 1] = planar[1 * width + x];
                rowOut[x * 4 + 2] = planar[2 * width + x];
                rowOut[x * 4 + 3] = planar[3 * width + x];
            }
        }
        else
        {
            // Old-style (flat, or run-length via an R=G=B=1 repeat-marker pixel).
            r.pos = rowStart;
            int x = 0;
            unsigned char prev[4] = {0, 0, 0, 0};
            while (x < width)
            {
                unsigned char px[4];
                if (r.read(px, 4) != 4) return false;
                if (px[0] == 1 && px[1] == 1 && px[2] == 1)
                {
                    int count = px[3];
                    for (int i = 0; i < count && x < width; ++i, ++x) memcpy(rowOut + x * 4, prev, 4);
                }
                else
                {
                    memcpy(prev, px, 4);
                    memcpy(rowOut + x * 4, px, 4);
                    ++x;
                }
            }
        }
    }
    return true;
}

// 256-entry lookup table of the exponent's scale factor (2^(e-136)), replacing a per-pixel
// ldexpf() call - built once, on first use.
static const float* getExpTable()
{
    static float table[256];
    static bool built = false;
    if (!built)
    {
        table[0] = 0.f;
        for (int e = 1; e < 256; ++e) table[e] = ldexpf(1.0f, e - (128 + 8));
        built = true;
    }
    return table;
}

static LoadResult loadWithCustomRGBE(const char* path, RGBEDecodeTimings* timings = nullptr)
{
    LoadResult res;

    // Phase 1: read the entire file into memory - the only actual disk I/O.
    auto t0 = Clock::now();
    std::vector<unsigned char> fileData;
    if (!readWholeFile(path, fileData)) return res;
    auto t1 = Clock::now();

    // Phase 2: parse the ASCII header, purely from the in-memory buffer.
    ByteReader r{fileData.data(), fileData.size()};
    int width = 0, height = 0;
    if (!readHeaderMem(r, width, height)) return res;
    auto t2 = Clock::now();

    // Phase 3: RLE-unpack every scanline into raw RGBE bytes.
    std::vector<unsigned char> rgbe;
    if (!rleUnpackAll(r, width, height, rgbe)) return res;
    auto t3 = Clock::now();

    // Phase 4: RGBE -> float RGB conversion (the ldexpf-based baseline - see
    // loadWithCustomRGBE_LUT/_AVX2 below for the optimized variants of just this phase).
    std::vector<float> pixels((size_t)width * height * 3);
    for (size_t i = 0; i < (size_t)width * height; ++i)
    {
        rgbeToFloat(rgbe[i * 4 + 0], rgbe[i * 4 + 1], rgbe[i * 4 + 2], rgbe[i * 4 + 3], pixels[i * 3 + 0], pixels[i * 3 + 1], pixels[i * 3 + 2]);
    }
    auto t4 = Clock::now();

    if (timings)
    {
        timings->readFileMs = elapsedMs(t0, t1);
        timings->headerParseMs = elapsedMs(t1, t2);
        timings->rleUnpackMs = elapsedMs(t2, t3);
        timings->rgbeToFloatMs = elapsedMs(t3, t4);
        timings->totalMs = elapsedMs(t0, t4);
    }

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t4);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), (size_t)width * height);
    res.bottomUp = false;
    res.pixels = std::move(pixels);
    return res;
}

// --- 5. CustomRGBE, but with a LUT-based conversion instead of ldexpf() ---

static LoadResult loadWithCustomRGBE_LUT(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    std::vector<unsigned char> fileData;
    if (!readWholeFile(path, fileData)) return res;

    ByteReader r{fileData.data(), fileData.size()};
    int width = 0, height = 0;
    if (!readHeaderMem(r, width, height)) return res;

    std::vector<unsigned char> rgbe;
    if (!rleUnpackAll(r, width, height, rgbe)) return res;

    const float* table = getExpTable();
    const size_t n = (size_t)width * height;
    std::vector<float> pixels(n * 3);
    for (size_t i = 0; i < n; ++i)
    {
        float scale = table[rgbe[i * 4 + 3]];
        pixels[i * 3 + 0] = rgbe[i * 4 + 0] * scale;
        pixels[i * 3 + 1] = rgbe[i * 4 + 1] * scale;
        pixels[i * 3 + 2] = rgbe[i * 4 + 2] * scale;
    }

    auto t1 = Clock::now();

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), n);
    res.bottomUp = false;
    res.pixels = std::move(pixels);
    return res;
}

// --- CustomRGBE-LUT-MT: two-pass parallel decode (OpenMP), on top of the LUT conversion above ---
//
// Radiance's RLE encoding is a serial bitstream: you can't know where row N+1 starts without
// having decoded row N (the same reason DEFLATE/gzip streams resist parallel decoding without
// pre-inserted sync points). This works around that with two passes over the SAME data:
//   Pass 1 (serial): walk the compressed stream WITHOUT writing any pixel data, purely to
//                     record each row's starting byte offset. Still O(n) over the whole file
//                     and still single-threaded - there's no way around that - but cheaper
//                     than the real decode since it skips every memcpy/memset/LUT-multiply,
//                     doing only the run-length bookkeeping.
//   Pass 2 (parallel over rows, OpenMP): every row's start offset is now known, so each
//                     thread can independently decode+convert its own slice of rows straight
//                     into the final float buffer - rows write disjoint memory, so this needs
//                     no locking/synchronization beyond OpenMP's own work distribution.
// Doesn't touch loadWithCustomRGBE_LUT or any of its helpers above - this duplicates the
// per-row decode logic into decodeOneRowRGBE() below rather than risk changing the existing,
// already-verified-correct code path.

// Same RLE state machine as rleUnpackAll()/readScanlineNewRLEMem() above, but skips every
// write - only advances a read cursor far enough to find where each row starts. Takes `r` by
// value (a cheap 3-word copy) so the caller's own reader position is left untouched.
static bool rleFindRowOffsets(ByteReader r, int width, int height, std::vector<size_t>& rowOffsets)
{
    rowOffsets.resize(height);
    for (int y = 0; y < height; ++y)
    {
        rowOffsets[y] = r.pos;
        size_t rowStart = r.pos;
        unsigned char marker[4];
        size_t got4 = r.read(marker, 4);
        bool isNewRLE = got4 == 4 && marker[0] == 2 && marker[1] == 2 && width >= 8 && width < 0x8000 &&
                        ((marker[2] << 8) | marker[3]) == width;

        if (isNewRLE)
        {
            for (int channel = 0; channel < 4; ++channel)
            {
                int x = 0;
                while (x < width)
                {
                    int c = r.getc();
                    if (c < 0) return false;
                    if (c > 128)
                    {
                        int count = c - 128;
                        int val = r.getc();
                        if (val < 0 || x + count > width) return false;
                        x += count;
                    }
                    else
                    {
                        int count = c;
                        if (x + count > width || r.pos + (size_t)count > r.size) return false;
                        r.pos += count;
                        x += count;
                    }
                }
            }
        }
        else
        {
            r.pos = rowStart;
            int x = 0;
            while (x < width)
            {
                unsigned char px[4];
                if (r.read(px, 4) != 4) return false;
                if (px[0] == 1 && px[1] == 1 && px[2] == 1)
                    x += px[3];
                else
                    ++x;
            }
        }
    }
    return true;
}

// Decodes exactly one scanline (either encoding style), starting at r.pos, into a caller-
// supplied interleaved RGBE scratch buffer (width*4 bytes) - the parallel Pass 2 loop below
// calls this once per row, each thread on its own row range. `planarScratch` (also width*4
// bytes, caller-supplied so no per-row heap allocation) is only used internally for the new-
// style RLE case, matching readScanlineNewRLEMem()'s planar-then-reshuffle shape above.
static bool decodeOneRowRGBE(ByteReader& r, int width, unsigned char* rowOut, unsigned char* planarScratch)
{
    size_t rowStart = r.pos;
    unsigned char marker[4];
    size_t got4 = r.read(marker, 4);
    bool isNewRLE = got4 == 4 && marker[0] == 2 && marker[1] == 2 && width >= 8 && width < 0x8000 &&
                    ((marker[2] << 8) | marker[3]) == width;

    if (isNewRLE)
    {
        if (!readScanlineNewRLEMem(r, width, planarScratch)) return false;
        for (int x = 0; x < width; ++x)
        {
            rowOut[x * 4 + 0] = planarScratch[0 * width + x];
            rowOut[x * 4 + 1] = planarScratch[1 * width + x];
            rowOut[x * 4 + 2] = planarScratch[2 * width + x];
            rowOut[x * 4 + 3] = planarScratch[3 * width + x];
        }
    }
    else
    {
        r.pos = rowStart;
        int x = 0;
        unsigned char prev[4] = {0, 0, 0, 0};
        while (x < width)
        {
            unsigned char px[4];
            if (r.read(px, 4) != 4) return false;
            if (px[0] == 1 && px[1] == 1 && px[2] == 1)
            {
                int count = px[3];
                for (int i = 0; i < count && x < width; ++i, ++x) memcpy(rowOut + x * 4, prev, 4);
            }
            else
            {
                memcpy(prev, px, 4);
                memcpy(rowOut + x * 4, px, 4);
                ++x;
            }
        }
    }
    return true;
}

static LoadResult loadWithCustomRGBE_LUT_MT(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    std::vector<unsigned char> fileData;
    if (!readWholeFile(path, fileData)) return res;

    ByteReader headerReader{fileData.data(), fileData.size()};
    int width = 0, height = 0;
    if (!readHeaderMem(headerReader, width, height)) return res;

    // Pass 1 (serial): find every row's starting byte offset.
    std::vector<size_t> rowOffsets;
    if (!rleFindRowOffsets(headerReader, width, height, rowOffsets)) return res;

    const float* table = getExpTable();
    const size_t n = (size_t)width * height;
    std::vector<float> pixels(n * 3);
    bool ok = true;

    // Per-thread scratch buffers, reused across that thread's rows - avoids a heap allocation
    // per row (height of them, one per iteration) which would otherwise dominate at this scale
    // and add allocator lock contention across threads.
    int maxThreads = omp_get_max_threads();
    std::vector<std::vector<unsigned char>> rowBufs(maxThreads, std::vector<unsigned char>((size_t)width * 4));
    std::vector<std::vector<unsigned char>> planarBufs(maxThreads, std::vector<unsigned char>((size_t)width * 4));

    // Pass 2 (parallel over rows): each row is now independently decodable+convertible.
    #pragma omp parallel for schedule(dynamic, 16)
    for (int y = 0; y < height; ++y)
    {
        int tid = omp_get_thread_num();
        unsigned char* rowRGBE = rowBufs[tid].data();
        unsigned char* planarScratch = planarBufs[tid].data();

        ByteReader r{fileData.data(), fileData.size(), rowOffsets[y]};
        if (!decodeOneRowRGBE(r, width, rowRGBE, planarScratch))
        {
            ok = false; // benign: only ever written false->false or true->false, so a torn/racy write can't hide a real failure.
            continue;
        }

        float* rowPixels = pixels.data() + (size_t)y * width * 3;
        for (int x = 0; x < width; ++x)
        {
            float scale = table[rowRGBE[x * 4 + 3]];
            rowPixels[x * 3 + 0] = rowRGBE[x * 4 + 0] * scale;
            rowPixels[x * 3 + 1] = rowRGBE[x * 4 + 1] * scale;
            rowPixels[x * 3 + 2] = rowRGBE[x * 4 + 2] * scale;
        }
    }
    if (!ok) return res;

    auto t1 = Clock::now();

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), n);
    res.bottomUp = false;
    res.pixels = std::move(pixels);
    return res;
}

// --- 6. CustomRGBE, gathering 8 LUT lookups at once via AVX2 ---
// (Answers "does vectorizing the lookup itself help, or is a cache-resident 256-entry
// scalar table already about as fast as this gets" - informative either way.)

static LoadResult loadWithCustomRGBE_AVX2(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    std::vector<unsigned char> fileData;
    if (!readWholeFile(path, fileData)) return res;

    ByteReader r{fileData.data(), fileData.size()};
    int width = 0, height = 0;
    if (!readHeaderMem(r, width, height)) return res;

    std::vector<unsigned char> rgbe;
    if (!rleUnpackAll(r, width, height, rgbe)) return res;

    const float* table = getExpTable();
    const size_t n = (size_t)width * height;
    std::vector<float> pixels(n * 3);

    size_t i = 0;
    for (; i + 8 <= n; i += 8)
    {
        int32_t idx[8];
        for (int k = 0; k < 8; ++k) idx[k] = rgbe[(i + k) * 4 + 3];
        __m256i vidx = _mm256_loadu_si256((const __m256i*)idx);
        __m256 vscale = _mm256_i32gather_ps(table, vidx, 4);

        float scale[8];
        _mm256_storeu_ps(scale, vscale);
        for (int k = 0; k < 8; ++k)
        {
            const unsigned char* px = &rgbe[(i + k) * 4];
            pixels[(i + k) * 3 + 0] = px[0] * scale[k];
            pixels[(i + k) * 3 + 1] = px[1] * scale[k];
            pixels[(i + k) * 3 + 2] = px[2] * scale[k];
        }
    }
    for (; i < n; ++i) // tail (n not a multiple of 8)
    {
        float scale = table[rgbe[i * 4 + 3]];
        pixels[i * 3 + 0] = rgbe[i * 4 + 0] * scale;
        pixels[i * 3 + 1] = rgbe[i * 4 + 1] * scale;
        pixels[i * 3 + 2] = rgbe[i * 4 + 2] * scale;
    }

    auto t1 = Clock::now();

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), n);
    res.bottomUp = false;
    res.pixels = std::move(pixels);
    return res;
}

// --- 4. Bruce Walter's reference rgbe.c/rgbe.h (FILE*-streaming, like the original format spec) ---

static LoadResult loadWithReferenceRGBE(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    FILE* f = fopen(path, "rb");
    if (!f) return res;

    int width = 0, height = 0;
    if (RGBE_ReadHeader(f, &width, &height, nullptr) != RGBE_RETURN_SUCCESS)
    {
        fclose(f);
        return res;
    }

    std::vector<float> pixels((size_t)width * height * 3);
    if (RGBE_ReadPixels_RLE(f, pixels.data(), width, height) != RGBE_RETURN_SUCCESS)
    {
        fclose(f);
        return res;
    }

    auto t1 = Clock::now();
    fclose(f);

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), (size_t)width * height);
    res.bottomUp = false; // Radiance's "-Y H +X W" convention is top-down, same as CustomRGBE/stb_image.
    res.pixels = std::move(pixels);
    return res;
}

// --- 7. libvips ---

static LoadResult loadWithLibvips(const char* path)
{
    LoadResult res;

    static bool vipsInitialized = false;
    if (!vipsInitialized)
    {
        if (VIPS_INIT("image_load_bench")) return res;
        vipsInitialized = true;
    }

    auto t0 = Clock::now();

    VipsImage* raw = vips_image_new_from_file(path, nullptr);
    if (!raw) return res;

    // Force a float RGB result regardless of what the HDR loader natively produces
    // internally, for a fair apples-to-apples comparison with the other decoders (this
    // also forces the actual pixel decode - vips_image_new_from_file() alone is lazy).
    VipsImage* floatImg = nullptr;
    if (vips_cast(raw, &floatImg, VIPS_FORMAT_FLOAT, nullptr))
    {
        g_object_unref(raw);
        return res;
    }
    g_object_unref(raw);

    size_t memSize = 0;
    void* buf = vips_image_write_to_memory(floatImg, &memSize);
    int width = vips_image_get_width(floatImg);
    int height = vips_image_get_height(floatImg);
    int bands = vips_image_get_bands(floatImg);
    g_object_unref(floatImg);

    if (!buf || (bands != 3 && bands != 4))
    {
        if (buf) g_free(buf);
        return res;
    }

    auto t1 = Clock::now();

    const size_t n = (size_t)width * height;
    std::vector<float> pixels(n * 3);
    const float* fbuf = (const float*)buf;
    if (bands == 3)
    {
        memcpy(pixels.data(), fbuf, n * 3 * sizeof(float));
    }
    else // bands == 4 - drop the alpha channel, matching the other decoders' RGB-only output.
    {
        for (size_t i = 0; i < n; ++i)
        {
            pixels[i * 3 + 0] = fbuf[i * 4 + 0];
            pixels[i * 3 + 1] = fbuf[i * 4 + 1];
            pixels[i * 3 + 2] = fbuf[i * 4 + 2];
        }
    }
    g_free(buf);

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), n);
    res.bottomUp = false; // libvips uses top-left origin by convention.
    res.pixels = std::move(pixels);
    return res;
}

// --- 8. DevIL ---

static LoadResult loadWithDevIL(const char* path)
{
    LoadResult res;

    // Matches the fix applied to Falcor's Bitmap::tryCreateFromFileDevIL(): one persistent
    // image handle reused across calls (ilLoadImage() fully overwrites it), instead of
    // gen/delete-ing a new DevIL image object on every single decode.
    static bool ilInitialized = false;
    static ILuint imgId = 0;
    if (!ilInitialized)
    {
        ilInit();
        ilEnable(IL_ORIGIN_SET);
        ilOriginFunc(IL_ORIGIN_UPPER_LEFT); // force top-down, same convention as CustomRGBE/stb_image/libvips.
        ilGenImages(1, &imgId);
        ilInitialized = true;
    }
    ilBindImage(imgId);

    auto t0 = Clock::now();

    if (!ilLoadImage(path))
    {
        printf("             [DevIL] ilLoadImage failed, ilGetError=0x%X\n", ilGetError());
        return res;
    }
    if (!ilConvertImage(IL_RGB, IL_FLOAT))
    {
        printf("             [DevIL] ilConvertImage failed, ilGetError=0x%X\n", ilGetError());
        return res;
    }

    int width = ilGetInteger(IL_IMAGE_WIDTH);
    int height = ilGetInteger(IL_IMAGE_HEIGHT);
    const float* data = (const float*)ilGetData();
    if (!data || width <= 0 || height <= 0)
    {
        return res;
    }

    auto t1 = Clock::now();

    const size_t n = (size_t)width * height;
    std::vector<float> pixels(data, data + n * 3);

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), n);
    res.bottomUp = false; // forced via ilOriginFunc(IL_ORIGIN_UPPER_LEFT) above.
    res.pixels = std::move(pixels);
    return res;
}

// --- 9. OpenImageIO ---

static LoadResult loadWithOpenImageIO(const char* path)
{
    LoadResult res;
    auto t0 = Clock::now();

    auto in = OIIO::ImageInput::open(path);
    if (!in) return res;

    const OIIO::ImageSpec& spec = in->spec();
    int width = spec.width;
    int height = spec.height;
    int channels = spec.nchannels;
    if (channels != 3 && channels != 4)
    {
        in->close();
        return res;
    }

    std::vector<float> raw((size_t)width * height * channels);
    bool ok = in->read_image(0, 0, 0, channels, OIIO::TypeDesc::FLOAT, raw.data());
    in->close();
    if (!ok) return res;

    auto t1 = Clock::now();

    const size_t n = (size_t)width * height;
    std::vector<float> pixels(n * 3);
    if (channels == 3)
    {
        pixels = std::move(raw);
    }
    else // channels == 4 - drop alpha, matching the other decoders' RGB-only output.
    {
        for (size_t i = 0; i < n; ++i)
        {
            pixels[i * 3 + 0] = raw[i * 4 + 0];
            pixels[i * 3 + 1] = raw[i * 4 + 1];
            pixels[i * 3 + 2] = raw[i * 4 + 2];
        }
    }

    res.ok = true;
    res.width = width;
    res.height = height;
    res.totalMs = elapsedMs(t0, t1);
    res.r00 = pixels[0];
    res.g00 = pixels[1];
    res.b00 = pixels[2];
    res.avgLuminance = computeAvgLuminance(pixels.data(), n);
    res.bottomUp = false; // OIIO's ImageSpec convention is top-down (y increases downward), same as the other top-down decoders.
    res.pixels = std::move(pixels);
    return res;
}

// Real correctness check: compares every RGB value, not just an aggregate scalar an
// unrelated bug could accidentally leave unchanged (a shifted scanline, a transposed
// block, a wrong RLE run boundary, etc. can all cancel out in a sum/average but would show
// up here as a large maxAbsDiff or mismatch count). Normalizes for the known bottomUp vs
// top-down storage difference between FreeImage and the other two before comparing.
static void comparePixels(const char* nameA, const LoadResult& a, const char* nameB, const LoadResult& b)
{
    if (!a.ok || !b.ok || a.width != b.width || a.height != b.height)
    {
        printf("%-25s cannot compare (load failed or dimension mismatch)\n", (std::string(nameA) + " vs " + nameB + ":").c_str());
        return;
    }

    const int w = a.width, h = a.height;
    double maxAbsDiff = 0.0, sumSqDiff = 0.0;
    size_t mismatchCount = 0;
    const double kEps = 1e-4; // generous - decoders may round the RGBE exponent scale differently in the last bit.

    for (int y = 0; y < h; ++y)
    {
        int ay = a.bottomUp ? (h - 1 - y) : y;
        int by = b.bottomUp ? (h - 1 - y) : y;
        const float* rowA = a.pixels.data() + (size_t)ay * w * 3;
        const float* rowB = b.pixels.data() + (size_t)by * w * 3;
        for (int x = 0; x < w * 3; ++x)
        {
            double diff = std::abs((double)rowA[x] - (double)rowB[x]);
            maxAbsDiff = std::max(maxAbsDiff, diff);
            sumSqDiff += diff * diff;
            if (diff > kEps) ++mismatchCount;
        }
    }

    size_t totalValues = (size_t)w * h * 3;
    double rmse = std::sqrt(sumSqDiff / (double)totalValues);
    printf(
        "%-22s maxAbsDiff=%.6f  RMSE=%.6f  mismatched values (>%.0e)=%zu / %zu (%.5f%%)\n",
        (std::string(nameA) + " vs " + nameB + ":").c_str(), maxAbsDiff, rmse, kEps, mismatchCount, totalValues,
        100.0 * (double)mismatchCount / (double)totalValues
    );
}

// --- driver ---

template<typename Fn>
static LoadResult runBenchmark(const char* name, Fn loadFn, const char* path = kPath)
{
    std::vector<double> times;
    LoadResult last;
    for (int i = 0; i < kIterations; ++i)
    {
        LoadResult r = loadFn(path);
        if (!r.ok)
        {
            printf("%-12s FAILED to load\n", name);
            return {};
        }
        times.push_back(r.totalMs);
        last = r;
    }

    double sum = 0.0, mn = times[0], mx = times[0];
    for (double t : times)
    {
        sum += t;
        mn = std::min(mn, t);
        mx = std::max(mx, t);
    }
    double avg = sum / times.size();

    printf("%-12s %dx%d\n", name, last.width, last.height);
    printf("             avg=%.3fms  min=%.3fms  max=%.3fms  (", avg, mn, mx);
    for (size_t i = 0; i < times.size(); ++i) printf("%s%.2f", i ? "," : "", times[i]);
    printf(")\n");
    printf("             avgLuminance=%.6f  firstPixel=(%.4f, %.4f, %.4f) [orientation may differ between libraries]\n\n", last.avgLuminance, last.r00, last.g00, last.b00);

    return last;
}

// Same iteration/averaging logic as runBenchmark() above, but also captures and prints the
// CustomRGBE decoder's internal phase breakdown (disk read / header / RLE unpack / RGBE->float).
static void runCustomRGBEPhaseBreakdown()
{
    std::vector<RGBEDecodeTimings> allTimings;
    for (int i = 0; i < kIterations; ++i)
    {
        RGBEDecodeTimings t;
        LoadResult r = loadWithCustomRGBE(kPath, &t);
        if (!r.ok)
        {
            printf("CustomRGBE phase breakdown: FAILED to load\n");
            return;
        }
        allTimings.push_back(t);
    }

    auto avgOf = [&](double RGBEDecodeTimings::* member)
    {
        double sum = 0.0;
        for (const auto& t : allTimings) sum += t.*member;
        return sum / allTimings.size();
    };

    double avgTotal = avgOf(&RGBEDecodeTimings::totalMs);
    auto pctOf = [&](double part) { return avgTotal > 0.0 ? 100.0 * part / avgTotal : 0.0; };

    double avgRead = avgOf(&RGBEDecodeTimings::readFileMs);
    double avgHeader = avgOf(&RGBEDecodeTimings::headerParseMs);
    double avgRle = avgOf(&RGBEDecodeTimings::rleUnpackMs);
    double avgConvert = avgOf(&RGBEDecodeTimings::rgbeToFloatMs);

    printf("CustomRGBE phase breakdown (%d iterations, average per phase):\n", kIterations);
    printf("             read file (disk I/O):  %6.3fms  (%5.1f%%)\n", avgRead, pctOf(avgRead));
    printf("             header parse:          %6.3fms  (%5.1f%%)\n", avgHeader, pctOf(avgHeader));
    printf("             RLE unpack (scanlines): %6.3fms  (%5.1f%%)\n", avgRle, pctOf(avgRle));
    printf("             RGBE -> float convert:  %6.3fms  (%5.1f%%)\n", avgConvert, pctOf(avgConvert));
    printf("             total:                  %6.3fms\n\n", avgTotal);
}

// --- playlist round ---
// Parses a real .hdrplaylist/.exrplaylist ("<filename> <durationMs>" per line, "#"-prefixed
// lines - including "#prefetch N" directives - are comments/ignored) and decodes every real
// production frame in it, once each, with no repeated warm-cache iterations - this is the
// same access pattern QuadLightVideoPlayer's background thread actually uses in Falcor, unlike
// the single-file/8-iterations-warm-cache benchmark above. Falcor's own logs showed DevIL
// settling around 35-40ms/frame on real playlist frames, well above this benchmark's ~20ms
// single-frame number - this round exists to check whether that gap is explained by frame-to-
// frame content variation (RLE-compressibility differs per frame, unlike the fixed-cost
// exponent-LUT conversion) rather than anything specific to how Falcor calls DevIL.
static std::vector<std::string> parsePlaylist(const char* playlistPath)
{
    std::vector<std::string> paths;
    FILE* f = fopen(playlistPath, "rb");
    if (!f)
    {
        printf("Failed to open playlist: %s\n", playlistPath);
        return paths;
    }

    std::string dir(playlistPath);
    size_t slash = dir.find_last_of("\\/");
    dir = (slash == std::string::npos) ? "" : dir.substr(0, slash + 1);

    char line[1024];
    while (fgets(line, sizeof(line), f))
    {
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;

        char* p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == 0 || *p == '#') continue; // blank line or comment/directive (e.g. "#prefetch 5")

        char filename[900] = {0};
        int durationMs = 0;
        if (sscanf(p, "%899s %d", filename, &durationMs) < 1) continue;

        paths.push_back(dir + filename);
    }
    fclose(f);
    return paths;
}

template<typename Fn>
static void runPlaylistBenchmark(const char* name, Fn loadFn, const std::vector<std::string>& paths)
{
    std::vector<double> times;
    times.reserve(paths.size());
    int failCount = 0;

    for (const auto& path : paths)
    {
        auto t0 = Clock::now();
        LoadResult r = loadFn(path.c_str());
        auto t1 = Clock::now();
        if (!r.ok) { failCount++; continue; }
        times.push_back(elapsedMs(t0, t1));
    }

    if (times.empty())
    {
        printf("%-14s FAILED to load any frame (failed=%d/%zu)\n\n", name, failCount, paths.size());
        return;
    }

    double sum = 0.0, mn = times[0], mx = times[0];
    for (double t : times)
    {
        sum += t;
        mn = std::min(mn, t);
        mx = std::max(mx, t);
    }

    printf(
        "%-14s frames=%zu (failed=%d)  avg=%.3fms  min=%.3fms  max=%.3fms  total=%.1fms\n\n", name, times.size(), failCount,
        sum / times.size(), mn, mx, sum
    );
}

int main()
{
    FreeImage_Initialise();

    printf("HDR load benchmark\nFile: %s\n%d iterations per library (first iteration may be cold-cache)\n\n", kPath, kIterations);

    LoadResult fi = runBenchmark("FreeImage", loadWithFreeImage);
    LoadResult stb = runBenchmark("stb_image", loadWithStbImage);
    LoadResult rgbe = runBenchmark("CustomRGBE", [](const char* path) { return loadWithCustomRGBE(path); });
    LoadResult ref = runBenchmark("ReferenceRGBE", loadWithReferenceRGBE);
    LoadResult lut = runBenchmark("CustomRGBE-LUT", loadWithCustomRGBE_LUT);
    LoadResult lutMt = runBenchmark("CustomRGBE-LUT-MT", loadWithCustomRGBE_LUT_MT);
    LoadResult avx = runBenchmark("CustomRGBE-AVX2", loadWithCustomRGBE_AVX2);
    LoadResult vips = runBenchmark("libvips", loadWithLibvips);
    LoadResult devil = runBenchmark("DevIL", loadWithDevIL);
    LoadResult oiio = runBenchmark("OpenImageIO", loadWithOpenImageIO);

    runCustomRGBEPhaseBreakdown();

    printf("--- Sanity check ---\n");
    bool dimsMatch = fi.width == stb.width && fi.width == rgbe.width && fi.width == ref.width && fi.width == lut.width && fi.width == lutMt.width && fi.width == avx.width &&
                      fi.width == vips.width && fi.width == devil.width && fi.width == oiio.width &&
                      fi.height == stb.height && fi.height == rgbe.height && fi.height == ref.height && fi.height == lut.height && fi.height == lutMt.height &&
                      fi.height == avx.height && fi.height == vips.height && fi.height == devil.height && fi.height == oiio.height;
    printf("Dimensions match across all ten: %s\n\n", dimsMatch ? "yes" : "NO - something is wrong, don't trust the timings above");

    printf("--- Per-pixel comparison (the actual correctness check - catches spatial bugs a global average can't) ---\n");
    comparePixels("FreeImage", fi, "stb_image", stb);
    comparePixels("FreeImage", fi, "CustomRGBE", rgbe);
    comparePixels("FreeImage", fi, "ReferenceRGBE", ref);
    comparePixels("CustomRGBE", rgbe, "CustomRGBE-LUT", lut);
    comparePixels("CustomRGBE-LUT", lut, "CustomRGBE-LUT-MT", lutMt);
    comparePixels("CustomRGBE", rgbe, "CustomRGBE-AVX2", avx);
    comparePixels("CustomRGBE-LUT", lut, "CustomRGBE-AVX2", avx);
    comparePixels("FreeImage", fi, "libvips", vips);
    comparePixels("FreeImage", fi, "DevIL", devil);
    comparePixels("FreeImage", fi, "OpenImageIO", oiio);

    // --- EXR round ---
    // Only the four general-purpose libraries apply here - stb_image has no EXR support at
    // all, and the RGBE-specific decoders (CustomRGBE/ReferenceRGBE/LUT/AVX2) only understand
    // Radiance's format, not OpenEXR's (a fundamentally different container - DEFLATE/PIZ/
    // etc. compressed, half/float channels, multi-part support). All four loader functions
    // below are unchanged from the HDR round - they auto-detect format from file content, so
    // simply pointing them at a .exr file exercises their EXR path with no new code.
    printf("\n=== EXR round ===\n");
    printf("File: %s\n\n", kExrPath);

    LoadResult fiExr = runBenchmark("FreeImage", loadWithFreeImage, kExrPath);
    LoadResult vipsExr = runBenchmark("libvips", loadWithLibvips, kExrPath);
    LoadResult devilExr = runBenchmark("DevIL", loadWithDevIL, kExrPath);
    LoadResult oiioExr = runBenchmark("OpenImageIO", loadWithOpenImageIO, kExrPath);

    printf("--- EXR sanity check ---\n");
    bool exrDimsMatch = fiExr.width == vipsExr.width && fiExr.width == devilExr.width && fiExr.width == oiioExr.width &&
                         fiExr.height == vipsExr.height && fiExr.height == devilExr.height && fiExr.height == oiioExr.height;
    printf("Dimensions match across all four: %s\n\n", exrDimsMatch ? "yes" : "NO - something is wrong, don't trust the timings above");

    printf("--- EXR per-pixel comparison ---\n");
    comparePixels("FreeImage", fiExr, "libvips", vipsExr);
    comparePixels("FreeImage", fiExr, "DevIL", devilExr);
    comparePixels("FreeImage", fiExr, "OpenImageIO", oiioExr);

    // --- Playlist round ---
    printf("\n=== Playlist round (real production frames, one decode pass each) ===\n");
    printf("File: %s\n", kPlaylistPath);
    auto playlistPaths = parsePlaylist(kPlaylistPath);
    printf("%zu frames\n\n", playlistPaths.size());
    if (!playlistPaths.empty())
    {
        runPlaylistBenchmark("FreeImage", loadWithFreeImage, playlistPaths);
        runPlaylistBenchmark("DevIL", loadWithDevIL, playlistPaths);
        runPlaylistBenchmark("libvips", loadWithLibvips, playlistPaths);
        runPlaylistBenchmark("CustomRGBE-LUT", loadWithCustomRGBE_LUT, playlistPaths);
        runPlaylistBenchmark("CustomRGBE-LUT-MT", loadWithCustomRGBE_LUT_MT, playlistPaths);
    }

    FreeImage_DeInitialise();
    return 0; // (skipping vips_shutdown()/ilShutDown() - the process is exiting anyway, and both are only safe to call if their library was actually initialized, which loadWithLibvips()/loadWithDevIL() track as function-local state not visible here.)
}
