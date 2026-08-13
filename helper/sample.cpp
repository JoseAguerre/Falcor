
static void build_sampling_basis()
{
    const int W = g_sample_w, H = g_sample_h;
    g_sample_N.resize((size_t)W * H);
    for (int y = 0; y < H; ++y) {
        for (int x = 0; x < W; ++x) {
            const float u = (x + 0.5f) / W, v = (y + 0.5f) / H;
            const float phi = (u - 0.5f) * 2.0f * kPi;
            const float theta = v * kPi;
            g_sample_N[(size_t)y * W + x] =
                Vec3{ sinf(theta) * cosf(phi), cosf(theta), sinf(theta) * sinf(phi) };
        }
    }
}

// Build the 2D luminance CDF used for importance sampling (mode 3): a linear
// (single-pass, O(W*H)) construction of one CDF per row plus a marginal CDF
// over rows, following section 2.1 of Cline et al.
//
// Deliberately NOT solid-angle/equirectangular corrected (no sin(theta) row
// weighting): modes 1/2 treat every texel as equally likely regardless of its
// row, so their accumulated average converges to mu = (1/N) * sum_j
// max(0,cosTheta_j)*color_j — the plain per-texel mean, not the physically
// exact sphere integral. For modes 3/4 to converge to that SAME mu (just
// faster, via importance sampling), they must importance-sample proportional
// to lum(j) alone and estimate mu as (1/N)*sum(f(j)/p(j)) via self-normalized
// importance sampling. That works out to weight = g_importance_flux/lum(j),
// with g_importance_flux = total_luma/(W*H). Mode 4's mip pyramid samples
// from this exact same per-texel distribution (just via a different
// traversal), so it reuses g_pixel_luma and g_importance_flux unchanged —
// see render_sampling_frame() for where that weight is applied.
static void build_sampling_cdf()
{
    const int W = g_sample_w, H = g_sample_h;
    g_pixel_luma.resize((size_t)W * H);
    g_cdf_rows.resize((size_t)W * H);
    g_cdf_marginal.resize(H);

    std::vector<float> row_weight(H);

    for (int y = 0; y < H; ++y) {
        const uint8_t* row = g_sample_rgb.data() + (size_t)y * W * 3;
        float* luma_row = g_pixel_luma.data() + (size_t)y * W;
        float* cdf_row  = g_cdf_rows.data() + (size_t)y * W;

        float acc = 0.0f;
        for (int x = 0; x < W; ++x) {
            const float lum = pixel_luma(row[x*3], row[x*3+1], row[x*3+2]);
            luma_row[x] = lum;
            acc += lum;
            cdf_row[x] = acc;
        }
        if (acc > 0.0f) {
            const float inv = 1.0f / acc;
            for (int x = 0; x < W; ++x) cdf_row[x] *= inv;
        }
        row_weight[y] = acc;
    }

    float acc = 0.0f;
    for (int y = 0; y < H; ++y) { acc += row_weight[y]; g_cdf_marginal[y] = acc; }
    const float total_luma = acc;
    if (total_luma > 0.0f) {
        const float inv = 1.0f / total_luma;
        for (int y = 0; y < H; ++y) g_cdf_marginal[y] *= inv;
    }

    g_importance_flux = total_luma / (float)(W * H);
}

// Invert the 2D CDF for uniform (xi1, xi2) via two binary searches — the
// "standard method" of section 2.1, generalized to 2D with a row marginal.
static inline void sample_from_cdf(float xi1, float xi2, int& outX, int& outY)
{
    const int W = g_sample_w, H = g_sample_h;
    const float* mbeg = g_cdf_marginal.data();
    int y = (int)(std::upper_bound(mbeg, mbeg + H, xi1) - mbeg);
    if (y >= H) y = H - 1;

    const float* rbeg = g_cdf_rows.data() + (size_t)y * W;
    int x = (int)(std::upper_bound(rbeg, rbeg + W, xi2) - rbeg);
    if (x >= W) x = W - 1;

    outX = x; outY = y;
}

// Build the hierarchical importance mip pyramid used by mode 4 (SAMPLE_MIP),
// following EnvMapSampler.slang: level 0 is g_pixel_luma at native
// resolution, and each coarser level is the 2x2 box SUM of the level below —
// not an average — so a node's value is exactly the total weight of the
// texels underneath it. Odd dimensions are handled by treating a missing
// right/bottom neighbor as weight 0 (no double-counting), which keeps things
// correct without requiring power-of-two video resolutions. O(W*H) total
// work (the level sizes form a geometric series), built once per snapshot.
static void build_importance_mips()
{
    g_mip_levels.clear();
    g_mip_w.clear();
    g_mip_h.clear();

    g_mip_levels.push_back(g_pixel_luma);   // level 0 = native-resolution luminance
    g_mip_w.push_back(g_sample_w);
    g_mip_h.push_back(g_sample_h);

    while (g_mip_w.back() > 1 || g_mip_h.back() > 1) {
        const int pw = g_mip_w.back(), ph = g_mip_h.back();
        const float* prev = g_mip_levels.back().data();
        const int cw = (pw + 1) / 2, ch = (ph + 1) / 2;

        std::vector<float> level((size_t)cw * ch);
        for (int y = 0; y < ch; ++y) {
            const int y0 = 2 * y, y1 = std::min(2 * y + 1, ph - 1);
            for (int x = 0; x < cw; ++x) {
                const int x0 = 2 * x, x1 = std::min(2 * x + 1, pw - 1);
                float sum = prev[(size_t)y0 * pw + x0];
                if (x1 != x0)               sum += prev[(size_t)y0 * pw + x1];
                if (y1 != y0)               sum += prev[(size_t)y1 * pw + x0];
                if (x1 != x0 && y1 != y0)   sum += prev[(size_t)y1 * pw + x1];
                level[(size_t)y * cw + x] = sum;
            }
        }
        g_mip_levels.push_back(std::move(level));
        g_mip_w.push_back(cw);
        g_mip_h.push_back(ch);
    }
}

// Warp a uniform 2D sample down the mip pyramid to pick a texel, mirroring
// EnvMapSampler.slang's sample(): starting from the 1x1 root, at each level
// look at the four children of the current node, split the sample first by
// the left/right column-weight ratio and then by the top/bottom ratio within
// the chosen column, renormalizing (rx, ry) into [0,1) at each split so the
// next level sees a fresh uniform sample. Because every node's weight is the
// exact sum of its children (see build_importance_mips()), the leaf reached
// this way is distributed exactly proportional to its luminance — the same
// target distribution as sample_from_cdf(), just reached in O(log(W*H))
// cache-friendly steps through small levels instead of two binary searches
// through the full-resolution array.
static inline void sample_mips(float rx, float ry, int& outX, int& outY)
{
    int px = 0, py = 0;  // current node, in the coordinates of the level about to be entered
    for (int level = (int)g_mip_levels.size() - 2; level >= 0; --level) {
        px *= 2; py *= 2;
        const int lw = g_mip_w[level], lh = g_mip_h[level];
        const float* cur = g_mip_levels[level].data();

        auto at = [&](int xx, int yy) -> float {
            return (xx < lw && yy < lh) ? cur[(size_t)yy * lw + xx] : 0.0f;
        };

        const float w00 = at(px, py), w10 = at(px + 1, py);
        const float w01 = at(px, py + 1), w11 = at(px + 1, py + 1);
        const float left = w00 + w01, right = w10 + w11;
        const float total = left + right;
        if (total <= 0.0f) continue;  // dead region (shouldn't normally happen); keep (px,py)

        int offx, offy;
        const float d = left / total;
        if (rx < d) { offx = 0; rx = rx / d; }
        else        { offx = 1; rx = (rx - d) / (1.0f - d); }

        const float colTotal = (offx == 0) ? left : right;
        const float topW     = (offx == 0) ? w00  : w10;
        const float e = (colTotal > 0.0f) ? topW / colTotal : 0.5f;
        if (ry < e) { offy = 0; ry = (e > 0.0f) ? ry / e : 0.0f; }
        else        { offy = 1; ry = (1.0f - e > 0.0f) ? (ry - e) / (1.0f - e) : 0.0f; }

        px += offx; py += offy;
    }
    outX = std::min(px, g_sample_w - 1);
    outY = std::min(py, g_sample_h - 1);
}

// Alias-method tables for mode 5 (SAMPLE_ALIAS / GGX_ALIAS): O(1) sampling
// with a single random draw, via Vose's/Walker's alias method — the same
// technique as section 2.2 of the paper and Burke's reference construction.
// Flattens the WxH grid into one 1D discrete distribution over N=W*H texels
// (a 2D alias table isn't a standard thing; you just let table entries point
// anywhere in the flattened array, per the paper). Reuses g_pixel_luma, so it
// targets the exact same per-texel distribution as SAMPLE_CDF/SAMPLE_MIP.
static std::vector<float>    g_alias_prob;   // W*H; per slot, P(no aliasing away from this slot)
static std::vector<uint32_t> g_alias_index;  // W*H; per slot, the alias target if we do alias away
static long long             g_alias_iterations = 0;  // while-loop trip count, last build_alias_table() call

// Work-list item for build_alias_table(): the probability travels WITH the
// index instead of living in a separate array indexed by it. The first cut
// of this kept a probs[total] array and did probs[sm]/probs[lg] through
// whatever arbitrary index was on top of the small/large stacks — a random
// gather/scatter into 16MB of doubles on every iteration, which turned out
// to be the actual cost (reusing buffers across calls didn't help, since the
// access pattern, not allocation, was the bottleneck). Packing {idx, prob}
// together means every read/write during the loop is on a local copy already
// in a register/cache line from the pop_back() — the only touch of the
// (cache-cold, randomly-ordered) output arrays is the single, final,
// once-per-slot write to g_alias_prob/g_alias_index.
struct AliasItem { uint32_t idx; float prob; };  // 8 bytes, no padding

// Persistent globals (like g_cdf_rows/g_pixel_luma elsewhere) so clear()+reserve()
// reuses already-committed memory instead of allocating fresh on every snapshot.
static std::vector<AliasItem> g_alias_work_small, g_alias_work_large;

// O(N) construction: classify each entry as "large" (probability above the
// uniform share 1/N) or "small" (at or below it), then repeatedly pair one
// small entry with one large entry — the small entry's alias slot points at
// the large entry, and the large entry gives up exactly the probability the
// small entry was short of 1/N. The large entry is re-classified with its
// shrunken probability and the process repeats until every entry has been
// fully redistributed.
static void build_alias_table()
{
    const int total = g_sample_w * g_sample_h;
    g_alias_prob.assign((size_t)std::max(total, 0), 1.0f);
    g_alias_index.assign((size_t)std::max(total, 0), 0);
    if (total <= 0) return;

    double sum = 0.0;
    for (int i = 0; i < total; ++i) sum += g_pixel_luma[i];
    const float inv_sum = (sum > 0.0) ? (float)(1.0 / sum) : 0.0f;
    const float std_weight = 1.0f / (float)total;

    std::vector<AliasItem>& small = g_alias_work_small;
    std::vector<AliasItem>& large = g_alias_work_large;
    small.clear(); large.clear();
    small.reserve(total); large.reserve(total);
    for (int i = 0; i < total; ++i) {
        const float p = g_pixel_luma[i] * inv_sum;
        (p > std_weight ? large : small).push_back(AliasItem{ (uint32_t)i, p });
    }

    g_alias_iterations = 0;
    while (!small.empty() && !large.empty()) {
        ++g_alias_iterations;
        const AliasItem sm = small.back(); small.pop_back();
        AliasItem lg = large.back(); large.pop_back();

        g_alias_index[sm.idx] = lg.idx;
        g_alias_prob[sm.idx]  = sm.prob * (float)total;

        lg.prob -= std_weight - sm.prob;
        (lg.prob > std_weight ? large : small).push_back(lg);
    }
    // Whatever's left (floating-point stragglers only, in theory) is already
    // at/near the full 1/N share — leave it as a non-aliased, always-hit slot.
    for (const AliasItem& item : small) g_alias_prob[item.idx] = 1.0f;
    for (const AliasItem& item : large) g_alias_prob[item.idx] = 1.0f;
}

// Single uniform draw -> texel index in O(1): land in slot i, then a coin
// flip weighted by g_alias_prob[i] decides whether to keep i or jump to its
// alias.
static inline void sample_alias(float u, int& outX, int& outY)
{
    const int total = g_sample_w * g_sample_h;
    float scaled = u * (float)total;
    int i = (int)scaled;
    if (i >= total) i = total - 1;
    const float frac = scaled - (float)i;
    const int idx = (frac > g_alias_prob[i]) ? (int)g_alias_index[i] : i;
    outY = idx / g_sample_w;
    outX = idx % g_sample_w;
}

// ─── Leaf alias (mode 6): alias method over CTU partition-tree leaves ─────────
//
// Same alias technique as mode 5, but the discrete distribution is built over
// the VP9 partition tree's LEAF BLOCKS (via the existing iterate_blocks()
// helper — the same one the CTU overlays and VIS_LUMA_AVG use) instead of one
// entry per pixel. A leaf's weight is its area times its average luminance,
// i.e. simply the sum of g_pixel_luma over its pixels — so leaf count can be
// anywhere from a few hundred to a few thousand instead of W*H, and
// construction is correspondingly cheaper (reported separately below).
// Sampling: alias-pick a leaf (1 draw), then a pixel uniformly within that
// leaf's rect (2 more draws).
//
// This trades precision for speed: the induced probability of picking a
// specific pixel j is avgLuma(leaf containing j) / total_luma, not j's own
// exact luminance — a blocky approximation of the same target distribution.
// Since sum_leaf(area*avgLuma) == sum_pixel(luma) == total_luma exactly (the
// leaves partition every pixel with no gaps or overlap), substituting
// avgLuma(leaf) for lum(j) in the same g_importance_flux-based weight formula
// used by modes 3-5 still converges to the identical target image mu.
struct LeafRect { int x, y, w, h; };
static std::vector<LeafRect>  g_leaf_rects;
static std::vector<float>     g_leaf_avg_luma;    // parallel to g_leaf_rects
static std::vector<float>     g_leaf_alias_prob;  // parallel to g_leaf_rects
static std::vector<uint32_t>  g_leaf_alias_index; // parallel to g_leaf_rects
static long long              g_leaf_alias_iterations = 0;
static std::vector<AliasItem> g_leaf_alias_work_small, g_leaf_alias_work_large;  // persistent scratch

static void build_leaf_alias_table()
{
    g_leaf_rects.clear();
    g_leaf_avg_luma.clear();
    g_leaf_alias_prob.clear();
    g_leaf_alias_index.clear();
    g_leaf_alias_iterations = 0;
    if (!g_current_fd || g_sample_w <= 0 || g_sample_h <= 0) return;

    // dst == native resolution so iterate_blocks()'s internal sx/sy scale is
    // exactly 1 and rects come out directly in g_sample_rgb/g_pixel_luma space.
    const SDL_Rect dst = { 0, 0, g_sample_w, g_sample_h };
    iterate_blocks(*g_current_fd, dst, [](const BlockCtx& b) {
        const int x0 = b.c * 8, y0 = b.r * 8;
        const int x1 = std::min(x0 + b.mw * 8, g_sample_w);
        const int y1 = std::min(y0 + b.mh * 8, g_sample_h);
        if (x1 <= x0 || y1 <= y0) return;

        double sum = 0.0;
        for (int y = y0; y < y1; ++y) {
            const float* row = g_pixel_luma.data() + (size_t)y * g_sample_w;
            for (int x = x0; x < x1; ++x) sum += row[x];
        }
        const int area = (x1 - x0) * (y1 - y0);
        g_leaf_rects.push_back(LeafRect{ x0, y0, x1 - x0, y1 - y0 });
        g_leaf_avg_luma.push_back((float)(sum / area));
    });

    const int nleaves = (int)g_leaf_rects.size();
    g_leaf_alias_prob.assign((size_t)std::max(nleaves, 0), 1.0f);
    g_leaf_alias_index.assign((size_t)std::max(nleaves, 0), 0);
    if (nleaves <= 0) return;

    double total_weight = 0.0;
    for (int i = 0; i < nleaves; ++i)
        total_weight += (double)g_leaf_avg_luma[i] *
                         (double)(g_leaf_rects[i].w * g_leaf_rects[i].h);
    const float inv_total = (total_weight > 0.0) ? (float)(1.0 / total_weight) : 0.0f;
    const float std_weight = 1.0f / (float)nleaves;

    std::vector<AliasItem>& small = g_leaf_alias_work_small;
    std::vector<AliasItem>& large = g_leaf_alias_work_large;
    small.clear(); large.clear();
    small.reserve(nleaves); large.reserve(nleaves);
    for (int i = 0; i < nleaves; ++i) {
        const float area = (float)(g_leaf_rects[i].w * g_leaf_rects[i].h);
        const float p = g_leaf_avg_luma[i] * area * inv_total;
        (p > std_weight ? large : small).push_back(AliasItem{ (uint32_t)i, p });
    }

    while (!small.empty() && !large.empty()) {
        ++g_leaf_alias_iterations;
        const AliasItem sm = small.back(); small.pop_back();
        AliasItem lg = large.back(); large.pop_back();

        g_leaf_alias_index[sm.idx] = lg.idx;
        g_leaf_alias_prob[sm.idx]  = sm.prob * (float)nleaves;

        lg.prob -= std_weight - sm.prob;
        (lg.prob > std_weight ? large : small).push_back(lg);
    }
    for (const AliasItem& item : small) g_leaf_alias_prob[item.idx] = 1.0f;
    for (const AliasItem& item : large) g_leaf_alias_prob[item.idx] = 1.0f;
}

// Alias-pick a leaf (u_leaf), then sample uniformly within it (u_x, u_y).
// Returns the leaf's average luminance too, since that's what the caller
// needs for the importance weight (see the big comment above).
static inline void sample_leaf_alias(float u_leaf, float u_x, float u_y,
                                     int& outX, int& outY, float& outLeafAvgLuma)
{
    const int nleaves = (int)g_leaf_rects.size();
    float scaled = u_leaf * (float)nleaves;
    int i = (int)scaled;
    if (i >= nleaves) i = nleaves - 1;
    const float frac = scaled - (float)i;
    const int leaf = (frac > g_leaf_alias_prob[i]) ? (int)g_leaf_alias_index[i] : i;

    const LeafRect& r = g_leaf_rects[leaf];
    int lx = (int)(u_x * r.w); lx = std::clamp(lx, 0, r.w - 1);
    int ly = (int)(u_y * r.h); ly = std::clamp(ly, 0, r.h - 1);
    outX = r.x + lx;
    outY = r.y + ly;
    outLeafAvgLuma = g_leaf_avg_luma[leaf];
}