"""Emitter samplers used by the QMC tests. Python ports of the Falcor implementations:

  Cdf2D            Rendering/Lights/QuadLightCdfSampler        marginal row from v, conditional column from u
  PerPixelAlias    Rendering/Lights/QuadLightAliasSampler      alias table over texels, Utils/Sampling/AliasTable.cpp
  LeafAlias        Rendering/Lights/QuadLightBudgetLeafAliasSampler
                   budget-limited variance quadtree, alias table over its leaves stored in the resorted layout

All samplers map (u, v) in [0,1)^2 to a continuous position (x, y) in [0,1)^2 over the emitter, with y = 0 the top row.
"""
import heapq

import numpy as np


def halton(n, base):
    """First n points of the radical inverse in the given base (index starts at 1)."""
    i = np.arange(1, n + 1, dtype=np.int64)
    r = np.zeros(n)
    f = 1.0
    while i.any():
        f /= base
        r += f * (i % base)
        i //= base
    return r


class AliasTable:
    """Vose alias table built exactly as Falcor's AliasTable.cpp.

    Below-mean and above-mean items are listed in index (scan) order and paired first-in first-out. Entry k stores a
    threshold, its own item index_b[k] and its redirect index_a[k]. Entries are stored in the order they are made."""

    def __init__(self, weights):
        n = len(weights)
        w = np.asarray(weights, dtype=np.float64).copy()
        avg = w.sum() / n
        low = np.full(n, -1, dtype=np.int64)
        high = np.full(n, -1, dtype=np.int64)
        nl = nh = 0
        for i in range(n):
            if w[i] < avg:
                low[nl] = i
                nl += 1
            else:
                high[nh] = i
                nh += 1
        self.threshold = np.zeros(n)
        self.index_a = np.zeros(n, dtype=np.int64)
        self.index_b = np.zeros(n, dtype=np.int64)
        for i in range(n):
            has_low, has_high = i < nl, i < nh
            if has_low and has_high:
                lo, hi = low[i], high[i]
                self.threshold[i] = w[lo] / avg
                self.index_a[i], self.index_b[i] = hi, lo
                w[hi] = (w[lo] + w[hi]) - avg
                if w[hi] < avg:
                    low[nl] = hi
                    nl += 1
                else:
                    high[nh] = hi
                    nh += 1
            elif has_high:
                self.threshold[i], self.index_a[i], self.index_b[i] = 1.0, high[i], high[i]
            elif has_low:
                self.threshold[i], self.index_a[i], self.index_b[i] = 1.0, low[i], low[i]
            else:
                raise AssertionError("alias table construction invariant violated")
        self.n = n

    def sample(self, u, v):
        """(u, v) -> (item, fx, fy). u picks entry floor(u n), its leftover is fx; v accepts the own item or takes the
        redirect, and its renormalized leftover is fy (as QuadLightAliasSampler.slang)."""
        s = u * self.n
        k = np.minimum(np.floor(s).astype(np.int64), self.n - 1)
        fx = s - k
        t = self.threshold[k]
        acc = v < t
        item = np.where(acc, self.index_b[k], self.index_a[k])
        fy = np.where(acc, v / np.maximum(t, 1e-12), (v - t) / np.maximum(1.0 - t, 1e-12))
        return item, fx, np.clip(fy, 0.0, 1.0 - 1e-12)


class Cdf2D:
    """2D CDF inversion with continuous position: v selects the row, u the column within it."""

    def __init__(self, L):
        self.H, self.W = L.shape
        rs = L.sum(1)
        self.row = np.concatenate([[0], np.cumsum(rs)]) / rs.sum()
        self.c = np.concatenate([np.zeros((self.H, 1)), np.cumsum(L, 1) / rs[:, None]], 1)
        self.flat = (self.c + 2 * np.arange(self.H)[:, None]).ravel()

    def sample(self, u, v, xi3=None):
        H, W = self.H, self.W
        r = np.clip(np.searchsorted(self.row, v, "right") - 1, 0, H - 1)
        fy = (v - self.row[r]) / np.maximum(self.row[r + 1] - self.row[r], 1e-300)
        k = np.clip(np.searchsorted(self.flat, u + 2 * r, "right") - 1 - r * (W + 1), 0, W - 1)
        lo, hi = self.c[r, k], self.c[r, k + 1]
        fx = (u - lo) / np.maximum(hi - lo, 1e-300)
        return (k + np.clip(fx, 0, 1 - 1e-9)) / W, (r + np.clip(fy, 0, 1 - 1e-9)) / H


class PerPixelAlias:
    """Alias table over texels (weights = luminance); the leftovers place the sample inside the texel."""

    def __init__(self, L):
        self.H, self.W = L.shape
        self.table = AliasTable(L.ravel())

    def sample(self, u, v, xi3=None):
        item, fx, fy = self.table.sample(u, v)
        return (item % self.W + fx) / self.W, (item // self.W + fy) / self.H


def budget_quadtree(L, budget):
    """Best-first quadtree: repeatedly split the block with the largest variance * area until the leaf budget would
    be exceeded. Returns an array of leaves (x0, y0, x1, y1, mean luminance), in the order they were finalized."""
    H, W = L.shape
    sat = np.zeros((H + 1, W + 1))
    sat2 = np.zeros((H + 1, W + 1))
    sat[1:, 1:] = np.cumsum(np.cumsum(L, 0), 1)
    sat2[1:, 1:] = np.cumsum(np.cumsum(L * L, 0), 1)

    def stats(x0, y0, x1, y1):
        s = sat[y1, x1] - sat[y0, x1] - sat[y1, x0] + sat[y0, x0]
        s2 = sat2[y1, x1] - sat2[y0, x1] - sat2[y1, x0] + sat2[y0, x0]
        return s, s2

    leaves, heap, count = [], [], [0]

    def consider(x0, y0, x1, y1):
        s, s2 = stats(x0, y0, x1, y1)
        area = (x1 - x0) * (y1 - y0)
        mean = s / area if area > 0 else 0.0
        var = max(0.0, s2 / area - mean * mean)
        if (x1 - x0) > 1 and (y1 - y0) > 1 and var > 0.0:
            count[0] += 1
            heapq.heappush(heap, (-(var * area), count[0], x0, y0, x1, y1, mean))
        else:
            leaves.append((x0, y0, x1, y1, mean))

    consider(0, 0, W, H)
    while heap and len(leaves) + len(heap) + 3 <= budget:
        _, _, x0, y0, x1, y1, _ = heapq.heappop(heap)
        xm, ym = x0 + (x1 - x0) // 2, y0 + (y1 - y0) // 2
        consider(x0, y0, xm, ym)
        consider(xm, y0, x1, ym)
        consider(x0, ym, xm, y1)
        consider(xm, ym, x1, y1)
    while heap:
        _, _, x0, y0, x1, y1, mean = heapq.heappop(heap)
        leaves.append((x0, y0, x1, y1, mean))
    return np.array(leaves)


class LeafAlias:
    """BudgetLeafAlias: alias table over quadtree leaves (weights = mean luminance * area), stored in the resorted
    layout of QuadLightBudgetLeafAliasSampler.cpp (entry k owns leaf k). Inside the chosen leaf the position is
    (fx, fy) from the alias leftovers (engine) or (fx, xi3) when a third number xi3 is given (paper, Algorithm 2)."""

    def __init__(self, L, budget):
        self.H, self.W = L.shape
        lv = budget_quadtree(L, budget)
        self.rects = lv[:, :4]
        T = AliasTable(lv[:, 4] * (self.rects[:, 2] - self.rects[:, 0]) * (self.rects[:, 3] - self.rects[:, 1]))
        self.n = T.n
        self.thr = np.ones(self.n)
        self.ali = np.arange(self.n)
        m = T.threshold < 1
        self.thr[T.index_b[m]] = T.threshold[m]
        self.ali[T.index_b[m]] = T.index_a[m]
        # Piecewise-constant density over the leaves, per texel (for the pdf).
        self.leaf_mean = np.empty((self.H, self.W))
        for x0, y0, x1, y1 in self.rects.astype(int):
            self.leaf_mean[y0:y1, x0:x1] = L[y0:y1, x0:x1].mean()

    def sample(self, u, v, xi3=None):
        s = u * self.n
        k = np.minimum(s.astype(np.int64), self.n - 1)
        fx = s - k
        t = self.thr[k]
        acc = v < t
        leaf = np.where(acc, k, self.ali[k])
        fy = np.where(acc, v / np.maximum(t, 1e-12), (v - t) / np.maximum(1 - t, 1e-12)) if xi3 is None else xi3
        fy = np.clip(fy, 0, 1 - 1e-12)
        r = self.rects[leaf]
        return (r[:, 0] + fx * (r[:, 2] - r[:, 0])) / self.W, (r[:, 1] + fy * (r[:, 3] - r[:, 1])) / self.H


def load_emitter(path):
    """Linear RGB (float64) and luminance of an .hdr/.exr (or 8-bit image, sRGB-decoded). A tiny floor keeps every
    texel's pdf positive."""
    import cv2
    img = cv2.imread(path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if rgb.dtype == np.uint8:
        c = rgb.astype(np.float64) / 255.0
        rgb = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    rgb = np.maximum(rgb.astype(np.float64), 0)
    L = rgb @ np.array([0.2126, 0.7152, 0.0722])
    floor = 1e-6 * L.max()
    return rgb + floor, L + floor
