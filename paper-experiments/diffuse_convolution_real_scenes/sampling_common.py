"""
Experiment 23: shared, reusable pieces factored out of fig9_repro.py so fig10_repro.py can
import them cleanly (no import-time side effects / no re-running fig9's own plotting code).
Nothing here changes fig9_repro.py's validated behavior - this is a pure extraction.

Contains: Hammersley 2D sequence, the synthetic corner-gradient PDF, and standard
(textbook/paper-matching, not Falcor-GPU-specific) 2D CDF inversion and Vose alias-method
classes, both exposing a `pdf_uv(x, y)` method giving the TRUE continuous density each
returns samples proportional to (needed for unbiased Monte Carlo direct-lighting estimators
in fig10_repro.py - since both methods target the identical distribution, this is a property
of the density grid itself, shared by both classes, not method-specific).
"""
import numpy as np


def radical_inverse_base2(i):
    i = np.asarray(i, dtype=np.uint32)
    i = ((i << 16) | (i >> 16)).astype(np.uint32)
    i = (((i & 0x55555555) << 1) | ((i & 0xAAAAAAAA) >> 1)).astype(np.uint32)
    i = (((i & 0x33333333) << 2) | ((i & 0xCCCCCCCC) >> 2)).astype(np.uint32)
    i = (((i & 0x0F0F0F0F) << 4) | ((i & 0xF0F0F0F0) >> 4)).astype(np.uint32)
    i = (((i & 0x00FF00FF) << 8) | ((i & 0xFF00FF00) >> 8)).astype(np.uint32)
    return i.astype(np.float64) / 4294967296.0


def hammersley_2d(n):
    idx = np.arange(n)
    return idx / n, radical_inverse_base2(idx)


def radical_inverse_base(i, base):
    """General-base van der Corput radical inverse (slower, pure-Python per-digit loop -
    base2 has the fast bit-twiddling version above; this covers any other prime base, used
    to build extra QMC dimensions independent of a Hammersley(base2) pair - e.g. Halton(3),
    Halton(5) - for a within-leaf offset that isn't just the leftover of the leaf-selection
    draw."""
    i = np.asarray(i, dtype=np.int64)
    result = np.zeros(i.shape, dtype=np.float64)
    f = 1.0 / base
    ii = i.copy()
    while np.any(ii > 0):
        result += f * (ii % base)
        ii //= base
        f /= base
    return result


def halton_dim(n, base, start_index=0):
    """1D Halton sequence in the given prime base, for indices [start_index, start_index+n)."""
    idx = np.arange(start_index, start_index + n)
    return radical_inverse_base(idx, base)


def make_corner_gradient(res):
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float64)
    xx /= (res - 1)
    yy /= (res - 1)
    d = np.sqrt(xx ** 2 + yy ** 2) / np.sqrt(2.0)
    density = np.clip(1.0 - d, 0.0, 1.0) ** 2.2
    density += 1e-6
    return density


class Cdf2D:
    """2D CDF inversion - Section 2.1: row marginal CDF, then per-row conditional CDF, each
    inverted via binary search (np.searchsorted IS a binary search)."""

    def __init__(self, density):
        self.H, self.W = density.shape
        self.density = density
        self.density_sum = density.sum()
        row_weights = density.sum(axis=1)
        self.row_cdf = np.concatenate([[0.0], np.cumsum(row_weights)])
        self.row_cdf /= self.row_cdf[-1]
        row_sums = density.sum(axis=1, keepdims=True)
        col_cdf = np.cumsum(density, axis=1) / row_sums
        self.col_cdf = np.concatenate([np.zeros((self.H, 1)), col_cdf], axis=1)

    def sample(self, u, v):
        row = np.clip(np.searchsorted(self.row_cdf, v, side="right") - 1, 0, self.H - 1)
        row_lo, row_hi = self.row_cdf[row], self.row_cdf[row + 1]
        row_frac = np.where(row_hi > row_lo, (v - row_lo) / np.maximum(row_hi - row_lo, 1e-12), 0.5)
        y = (row + row_frac) / self.H

        # Vectorized per-row binary search (equivalent to the per-element Python-loop version
        # fig9_repro.py uses - same result, just fast enough for fig10's ~millions of samples):
        # each row has its own col_cdf[row] to search; since W is small, gather the relevant
        # rows' CDFs and do the "searchsorted(...,'right')-1" comparison as a vectorized sum.
        row_cdfs = self.col_cdf[row]  # (M, W+1)
        col = (row_cdfs <= u[:, None]).sum(axis=1) - 1
        col = np.clip(col, 0, self.W - 1)
        col_lo = self.col_cdf[row, col]
        col_hi = self.col_cdf[row, col + 1]
        col_frac = np.where(col_hi > col_lo, (u - col_lo) / np.maximum(col_hi - col_lo, 1e-12), 0.5)
        x = (col + col_frac) / self.W
        return x, y

    def pdf_uv(self, x, y):
        row = np.clip((y * self.H).astype(np.int64), 0, self.H - 1)
        col = np.clip((x * self.W).astype(np.int64), 0, self.W - 1)
        return self.density[row, col] / self.density_sum * (self.W * self.H)


def build_vose_table(weights):
    """Standard/textbook Vose 1991 alias table construction (Section 2.2 of the paper):
    partition into insufficient/excess groups, pair them off, excess donates its surplus to
    insufficient, re-classify the residual. Shared by AliasMethod2D (over raw texels) and
    BudgetLeafAlias2D (over a budget-limited quadtree's leaves) - same algorithm, just a
    different, smaller set of items being weighted in the second case."""
    n = len(weights)
    w = np.asarray(weights, dtype=np.float64).copy()
    avg = w.sum() / n

    small = [i for i in range(n) if w[i] <= avg]
    large = [i for i in range(n) if w[i] > avg]

    prob = np.ones(n)
    alias = np.arange(n)

    while small and large:
        sm = small.pop()
        lg = large.pop()
        prob[sm] = w[sm] / avg
        alias[sm] = lg
        w[lg] = (w[lg] + w[sm]) - avg
        if w[lg] > avg:
            large.append(lg)
        else:
            small.append(lg)

    return prob, alias


class AliasMethod2D:
    """Alias method - Section 2.2, Vose 1991: partition into insufficient/excess groups,
    pair them off, excess donates its surplus to insufficient, re-classify the residual.
    Standard/textbook version (as the paper describes it - no GPU-specific storage-layout
    tricks)."""

    def __init__(self, density):
        self.H, self.W = density.shape
        self.density = density
        self.density_sum = density.sum()
        self.n = density.size
        self.prob, self.alias = build_vose_table(density.flatten())

    def sample(self, u, v):
        scaled = u * self.n
        i = np.minimum(np.floor(scaled).astype(np.int64), self.n - 1)
        chosen = np.where(v < self.prob[i], i, self.alias[i])
        row = chosen // self.W
        col = chosen % self.W
        thr = self.prob[i]
        fy = np.where(v < thr, v / np.maximum(thr, 1e-12), (v - thr) / np.maximum(1.0 - thr, 1e-12))
        fx = scaled - np.floor(scaled)
        x = (col + fx) / self.W
        y = (row + fy) / self.H
        return x, y

    def pdf_uv(self, x, y):
        row = np.clip((y * self.H).astype(np.int64), 0, self.H - 1)
        col = np.clip((x * self.W).astype(np.int64), 0, self.W - 1)
        return self.density[row, col] / self.density_sum * (self.W * self.H)


def build_budget_quadtree(density, leaf_budget):
    """Budget-limited best-first variance quadtree, matching this project's actual
    BudgetLeafAlias technique (Source/Falcor/Rendering/Lights/QuadLightBudgetLeafAliasSampler.cpp):
    SAT-based O(1) rectangle stats, priority = variance*area (total squared-error
    contribution), greedy best-first splitting until the leaf budget is (about to be)
    exceeded. Ported from the already-validated results/experiment14/samplers.py (same
    algorithm, copied not modified, since this part isn't Falcor-GPU-storage-specific the
    way the raw per-texel AliasTable was - it's just a quadtree builder)."""
    import heapq

    H, W = density.shape
    density = density.astype(np.float64)
    sat = np.zeros((H + 1, W + 1))
    satsq = np.zeros((H + 1, W + 1))
    sat[1:, 1:] = np.cumsum(np.cumsum(density, axis=0), axis=1)
    satsq[1:, 1:] = np.cumsum(np.cumsum(density * density, axis=0), axis=1)

    def query(x0, y0, x1, y1):
        s = sat[y1, x1] - sat[y0, x1] - sat[y1, x0] + sat[y0, x0]
        ssq = satsq[y1, x1] - satsq[y0, x1] - satsq[y1, x0] + satsq[y0, x0]
        return s, ssq

    final_leaves = []
    pq = []
    counter = 0

    def consider(x0, y0, x1, y1):
        nonlocal counter
        s, ssq = query(x0, y0, x1, y1)
        area = (x1 - x0) * (y1 - y0)
        mean = s / area if area > 0 else 0.0
        variance = max(0.0, ssq / area - mean * mean)
        can_split = (x1 - x0) > 1 and (y1 - y0) > 1 and variance > 0.0
        if can_split:
            counter += 1
            heapq.heappush(pq, (-(variance * area), counter, x0, y0, x1, y1, mean))
        else:
            final_leaves.append((x0, y0, x1, y1, mean))

    consider(0, 0, W, H)

    while pq and (len(final_leaves) + len(pq) + 3) <= leaf_budget:
        _, _, x0, y0, x1, y1, _mean = heapq.heappop(pq)
        xm = x0 + (x1 - x0) // 2
        ym = y0 + (y1 - y0) // 2
        consider(x0, y0, xm, ym)
        consider(xm, y0, x1, ym)
        consider(x0, ym, xm, y1)
        consider(xm, ym, x1, y1)

    while pq:
        _, _, x0, y0, x1, y1, mean = heapq.heappop(pq)
        final_leaves.append((x0, y0, x1, y1, mean))

    return final_leaves  # list of (x0,y0,x1,y1,avgLuma)


class BudgetLeafAlias2D:
    """BudgetLeafAlias - our own technique: a budget-limited quadtree over the density (see
    build_budget_quadtree), then a standard Vose alias table (build_vose_table, the SAME
    construction AliasMethod2D uses) over the resulting leaves, weighted by avgLuma*area
    (flux). Sampling picks a leaf via the alias table, then places a continuous point
    uniformly within that leaf's rectangle."""

    def __init__(self, density, leaf_budget=4000):
        self.H, self.W = density.shape
        leaves = build_budget_quadtree(density, leaf_budget)
        self.leaf_count = len(leaves)
        self.rect_min = np.array([[l[0], l[1]] for l in leaves], dtype=np.float64)
        self.rect_max = np.array([[l[2], l[3]] for l in leaves], dtype=np.float64)
        avg_luma = np.array([l[4] for l in leaves], dtype=np.float64)
        area = (self.rect_max[:, 0] - self.rect_min[:, 0]) * (self.rect_max[:, 1] - self.rect_min[:, 1])
        weights = avg_luma * area
        self.weights = weights
        self.weight_sum = weights.sum()
        self.prob, self.alias = build_vose_table(weights)
        self.n = len(weights)

        # Per-texel -> leaf-index lookup (needed for pdf_uv): each leaf's rectangle is a
        # numpy slice assignment, so this is O(leaf_count) slice-fills, not a per-texel loop.
        self.leaf_lookup = np.zeros((self.H, self.W), dtype=np.int64)
        for idx, (x0, y0, x1, y1, _mean) in enumerate(leaves):
            self.leaf_lookup[y0:y1, x0:x1] = idx

    def sample(self, u, v, leaf_u=None, leaf_v=None):
        """(u, v) always choose the leaf (discrete pick via the alias table). The continuous
        position WITHIN that leaf's rectangle defaults to the leftover-recycling trick (same
        as the real Falcor QuadLightBudgetLeafAliasSampler) - but if leaf_u/leaf_v are given
        (any independent sequence, e.g. a different Halton base), they are used for the
        within-leaf offset INSTEAD of the leftover bits, decoupling the two decisions."""
        scaled = u * self.n
        i = np.minimum(np.floor(scaled).astype(np.int64), self.n - 1)
        chosen = np.where(v < self.prob[i], i, self.alias[i])

        if leaf_u is None:
            fx = scaled - np.floor(scaled)
        else:
            fx = leaf_u
        if leaf_v is None:
            thr = self.prob[i]
            fy = np.where(v < thr, v / np.maximum(thr, 1e-12), (v - thr) / np.maximum(1.0 - thr, 1e-12))
        else:
            fy = leaf_v

        rmin = self.rect_min[chosen]
        rmax = self.rect_max[chosen]
        x = (rmin[:, 0] + fx * (rmax[:, 0] - rmin[:, 0])) / self.W
        y = (rmin[:, 1] + fy * (rmax[:, 1] - rmin[:, 1])) / self.H
        return x, y

    def pdf_uv(self, x, y):
        """Constant within each leaf: (leaf's weight / weight_sum) / (leaf's area in uv
        space). Looks up which leaf (x,y) falls in via the per-texel leaf_lookup table."""
        row = np.clip((y * self.H).astype(np.int64), 0, self.H - 1)
        col = np.clip((x * self.W).astype(np.int64), 0, self.W - 1)
        leaf_idx = self.leaf_lookup[row, col]
        area_uv = ((self.rect_max[leaf_idx, 0] - self.rect_min[leaf_idx, 0]) *
                   (self.rect_max[leaf_idx, 1] - self.rect_min[leaf_idx, 1])) / (self.W * self.H)
        return (self.weights[leaf_idx] / self.weight_sum) / np.maximum(area_uv, 1e-12)
