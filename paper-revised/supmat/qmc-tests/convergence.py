"""Convergence of the fence test: relative RMSE against sample count, separately on the floor between the emitter and
the fence (no occlusion) and on the floor in front of the fence (light partially blocked by the fence).

Uses every 4th floor pixel (the RMSE needs no more) and the exact reference of an earlier fence_test.py run.

Usage:
  python convergence.py results/fence_cinema_frame232_x704_y284_1024x512_128spp.npz [--max-spp 16384]
Writes results/convergence_<emitter>.json and prints a table and the sample count that reaches 1% error.
"""
import argparse
import json
import os
import time

import numpy as np

import fence_test as S
from samplers import Cdf2D, LeafAlias, PerPixelAlias, halton, load_emitter

HERE = os.path.dirname(os.path.abspath(__file__))
LUM = np.array([0.2126, 0.7152, 0.0722])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("reference", help="fence_test.py result (.npz) with the exact reference")
    ap.add_argument("--emitter", default=os.path.join(HERE, "data", "cinema_frame232_x704_y284_1024x512.hdr"))
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--max-spp", type=int, default=16384)
    ap.add_argument("--target", type=float, default=0.01)
    a = ap.parse_args()
    t0 = time.time()
    rgb, L = load_emitter(a.emitter)
    H, W = L.shape
    area = S.EMIT_W * S.EMIT_W * H / W
    _, _, floor, P = S.build_scene(rgb, (a.width, a.width * 9 // 16))
    prev = np.load(a.reference)
    assert np.array_equal(prev["floor_idx"], floor), "reference was rendered with a different setup"
    sel = np.arange(0, len(floor), 4)
    P, ref = P[sel], prev["ref"][sel] @ LUM
    regions = {"no occlusion": P[:, 2] < S.FENCE_Z, "partial occlusion": P[:, 2] > S.FENCE_Z}
    meanL = L.mean()
    lf = LeafAlias(L, 4000)
    methods = {"2D CDF": (Cdf2D(L), meanL / L), "PerPixelAlias": (PerPixelAlias(L), meanL / L),
               "LeafAlias 4000": (lf, meanL / lf.leaf_mean)}
    runs = [("2D CDF", "qmc"), ("PerPixelAlias", "qmc"), ("LeafAlias 4000", "qmc"), ("PerPixelAlias", "random")]
    ns = [128 * 2 ** k for k in range(20) if 128 * 2 ** k <= a.max_spp]
    shifts = np.random.default_rng(3).random((len(sel), 3))
    res = {f"{m} ({k})": {r: [] for r in regions} for m, k in runs}
    for N in ns:
        qmc = np.stack([halton(N, 2), halton(N, 3), halton(N, 5)])
        rng = np.random.default_rng(4 + N)
        for m, k in runs:
            smp, inv = methods[m]
            est = np.zeros(len(sel))
            chunk = max(1, (1 << 18) // N)
            for i in range(0, len(sel), chunk):
                n = min(chunk, len(sel) - i)
                uvw = (qmc[:, None, :] + shifts[i:i + n].T[:, :, None]) % 1.0 if k == "qmc" else rng.random((3, n, N))
                x, y = smp.sample(*uvw.reshape(3, -1))
                tx, ty = np.minimum((x * W).astype(int), W - 1), np.minimum((y * H).astype(int), H - 1)
                est[i:i + n] = S.shade(P[i:i + n], x.reshape(n, N), y.reshape(n, N), rgb[ty, tx].reshape(n, N, 3),
                                       inv[ty, tx].reshape(n, N), area) @ LUM
            for r, msk in regions.items():
                res[f"{m} ({k})"][r].append(float(np.sqrt(((est[msk] - ref[msk]) ** 2).mean()) / ref[msk].mean()))
        print(f"{N:6d} spp done ({time.time() - t0:.0f} s)", flush=True)

    def reach(errs):
        """Sample count where the error first drops below the target (log-log interpolation)."""
        e = np.array(errs)
        for i in range(len(e)):
            if e[i] <= a.target:
                if i == 0:
                    return ns[0]
                t = (np.log(a.target) - np.log(e[i - 1])) / (np.log(e[i]) - np.log(e[i - 1]))
                return float(np.exp(np.log(ns[i - 1]) + t * (np.log(ns[i]) - np.log(ns[i - 1]))))
        return None

    for r in regions:
        print(f"\n{r} ({int(regions[r].sum())} pixels): relative RMSE")
        print(f"{'':24s}" + "".join(f"{N:>8d}" for N in ns) + f"   spp for {a.target * 100:.0f}%")
        for key, v in res.items():
            s = reach(v[r])
            print(f"{key:24s}" + "".join(f"{x:8.4f}" for x in v[r]) + f"   {'> ' + str(ns[-1]) if s is None else f'{s:.0f}':>8s}")
    name = os.path.splitext(os.path.basename(a.emitter))[0]
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = os.path.join(HERE, "results", f"convergence_{name}.json")
    json.dump(dict(spp=ns, target=a.target, pixels_used=len(sel), results=res), open(out, "w"), indent=1)
    print("\nsaved", out)


if __name__ == "__main__":
    main()
