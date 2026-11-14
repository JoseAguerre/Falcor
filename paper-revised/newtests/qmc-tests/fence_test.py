"""Fence test: a diffuse floor lit by a textured area light through a fence.

Scene: the emitter image on a vertical quad (plane z = 0, facing +z), a square-mesh fence in front of it (plane
z = FENCE_Z), and a diffuse floor (y = 0). The camera sees the floor; each floor pixel gets direct lighting from the
emitter by light sampling only (no BSDF sampling, no MIS), with the fence as the only occluder.

Every pixel draws N samples from the Halton set (bases 2, 3, 5) with its own random toroidal shift (per-pixel
randomized QMC). The same scene is also rendered with independent pseudorandom numbers. The reference is exact:
quadrature over the emitter, checked against a grid twice as fine on 200 pixels.

Samplers: 2D CDF, per-pixel alias, LeafAlias with 1000 and 4000 leaves (paper placement, Algorithm 2).

Usage:
  python fence_test.py [--emitter data/cinema_frame232_x704_y284_1024x512.hdr] [--spp 128] [--width 480]
Writes results/fence_<emitter>_<spp>spp.npz and prints the relative RMSE of every render.
"""
import argparse
import os
import time

import cv2
import numpy as np

from samplers import Cdf2D, LeafAlias, PerPixelAlias, halton, load_emitter

HERE = os.path.dirname(os.path.abspath(__file__))
ALBEDO = 0.7
EMIT_W = 2.4                                  # emitter width (m); height follows the image aspect ratio
EMIT_Y0 = 0.6                                 # emitter bottom edge height (m)
FENCE_Z, FENCE_W, FENCE_H = 3.0, 6.0, 1.6      # fence plane z, width and height (m)
FENCE_PERIOD, FENCE_BAR = 0.34, 0.07           # square mesh: period and bar width (m)
CAM, LOOK, FOV = np.array([0.0, 2.4, 8.8]), np.array([0.0, 0.5, 3.4]), 50.0
LEAF_BUDGETS = (1000, 4000)
LUM = np.array([0.2126, 0.7152, 0.0722])


def fence_blocks(x, y):
    inside = (np.abs(x) < FENCE_W / 2) & (y > 0) & (y < FENCE_H)
    return inside & (((x + FENCE_W / 2) % FENCE_PERIOD < FENCE_BAR) | (y % FENCE_PERIOD < FENCE_BAR))


def camera_rays(res):
    W, H = res
    f = LOOK - CAM
    f = f / np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    t = np.tan(np.radians(FOV) / 2)
    px = ((np.arange(W) + 0.5) / W * 2 - 1) * t
    py = (1 - (np.arange(H) + 0.5) / H * 2) * t * H / W
    d = f[None, None] + px[None, :, None] * r[None, None] + py[:, None, None] * u[None, None]
    return (d / np.linalg.norm(d, axis=-1, keepdims=True)).reshape(-1, 3)


def shade(P, qx, qy, Le, inv_pdf, area):
    """Mean over samples of Le * G * V / pdf * albedo / pi. P: (n, 3) floor points; qx, qy: (n, s) emitter uv;
    Le: (n, s, 3); inv_pdf: (n, s) inverse of the pdf with respect to uv in [0,1)^2."""
    X = (qx - 0.5) * EMIT_W
    Y = EMIT_Y0 + (1 - qy) * (area / EMIT_W)
    dx, dy, dz = X - P[:, 0:1], Y - P[:, 1:2], -P[:, 2:3] * np.ones_like(X)
    r2 = dx * dx + dy * dy + dz * dz
    G = np.maximum(dy, 0) * np.maximum(-dz, 0) / (r2 * r2)  # cos at floor * cos at emitter / r^2
    t = (FENCE_Z - P[:, 2:3]) / dz
    blocked = (P[:, 2:3] > FENCE_Z) & (t > 0) & (t < 1) & fence_blocks(P[:, 0:1] + t * dx, P[:, 1:2] + t * dy)
    w = G * ~blocked * inv_pdf * area * ALBEDO / np.pi
    return (Le * w[..., None]).mean(1)


def build_scene(rgb, res):
    """Primary visibility. Returns per-pixel kind (0 background, 1 emitter, 2 fence, 3 floor), the base image for the
    non-floor pixels, the floor pixel indices and their 3D points."""
    H, W = rgb.shape[:2]
    eh = EMIT_W * H / W
    d = camera_rays(res)
    n = len(d)
    t_em = -CAM[2] / d[:, 2]
    t_fe = (FENCE_Z - CAM[2]) / d[:, 2]
    t_fl = -CAM[1] / np.where(d[:, 1] < 0, d[:, 1], -1e-9)
    kind = np.zeros(n, int)
    tbest = np.full(n, np.inf)
    Xe = CAM[None] + t_em[:, None] * d
    m = (t_em > 0) & (np.abs(Xe[:, 0]) < EMIT_W / 2) & (Xe[:, 1] > EMIT_Y0) & (Xe[:, 1] < EMIT_Y0 + eh)
    kind[m], tbest[m] = 1, t_em[m]
    Xf = CAM[None] + t_fe[:, None] * d
    m = (t_fe > 0) & (t_fe < tbest) & fence_blocks(Xf[:, 0], Xf[:, 1])
    kind[m], tbest[m] = 2, t_fe[m]
    m = (t_fl > 0) & (t_fl < tbest) & (CAM[2] + t_fl * d[:, 2] > 0)  # the floor ends at the emitter plane
    kind[m], tbest[m] = 3, t_fl[m]
    base = np.zeros((n, 3))
    e = kind == 1
    ue, ve = Xe[e, 0] / EMIT_W + 0.5, 1 - (Xe[e, 1] - EMIT_Y0) / eh
    base[e] = rgb[np.clip((ve * H).astype(int), 0, H - 1), np.clip((ue * W).astype(int), 0, W - 1)]
    base[kind == 2] = 0.004 * rgb.mean((0, 1))  # unlit back of the fence
    floor = np.where(kind == 3)[0]
    return kind, base, floor, CAM[None] + tbest[floor, None] * d[floor]


def exact_floor(rgb, P, area, factor):
    """Quadrature over the emitter downsampled by `factor` (area average), in chunks of 48 pixels."""
    H, W = rgb.shape[:2]
    g = cv2.resize(rgb.astype(np.float32), (W // factor, H // factor), interpolation=cv2.INTER_AREA).astype(np.float64)
    hh, ww = g.shape[:2]
    qx, qy = np.meshgrid((np.arange(ww) + 0.5) / ww, (np.arange(hh) + 0.5) / hh)
    qx, qy, Lq = qx.ravel()[None], qy.ravel()[None], g.reshape(-1, 3)[None]
    out = np.zeros((len(P), 3))
    for i in range(0, len(P), 48):
        out[i:i + 48] = shade(P[i:i + 48], qx, qy, Lq, np.ones((1, 1)), area)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--emitter", default=os.path.join(HERE, "data", "cinema_frame232_x704_y284_1024x512.hdr"))
    ap.add_argument("--spp", type=int, default=128)
    ap.add_argument("--width", type=int, default=480, help="image width; height is width * 9 / 16")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--reference", help="reuse the exact image from an earlier .npz of the same emitter and width")
    a = ap.parse_args()
    t0 = time.time()
    res = (a.width, a.width * 9 // 16)
    rgb, L = load_emitter(a.emitter)
    H, W = L.shape
    area = EMIT_W * EMIT_W * H / W
    kind, base, floor, P = build_scene(rgb, res)
    name = os.path.splitext(os.path.basename(a.emitter))[0]
    print(f"{name}: {W}x{H} emitter, {len(floor)} floor pixels, {a.spp} spp", flush=True)

    if a.reference:
        prev = np.load(a.reference)
        assert np.array_equal(prev["floor_idx"], floor), "reference was rendered with a different setup"
        ref = prev["ref"]
    else:
        f = max(2, W // 256)
        ref = exact_floor(rgb, P, area, f)
        chk = np.random.default_rng(0).choice(len(floor), 200, replace=False)
        fine = exact_floor(rgb, P[chk], area, max(1, f // 2))
        diff = np.sqrt((((ref[chk] - fine) @ LUM) ** 2).mean()) / (fine @ LUM).mean()
        print(f"  reference: quadrature vs a grid twice as fine, rel. RMS difference {diff:.1e}  ({time.time() - t0:.0f} s)", flush=True)

    meanL = L.mean()
    methods = {"2D CDF": (Cdf2D(L), meanL / L), "PerPixelAlias": (PerPixelAlias(L), meanL / L)}
    for B in LEAF_BUDGETS:
        lf = LeafAlias(L, B)
        methods[f"LeafAlias {B}"] = (lf, meanL / lf.leaf_mean)
    qmc = np.stack([halton(a.spp, 2), halton(a.spp, 3), halton(a.spp, 5)])
    shifts = np.random.default_rng(3).random((len(floor), 3))
    rng = np.random.default_rng(4)
    out = {}
    for input_kind in ("qmc", "random"):
        for mname, (smp, inv) in methods.items():
            est = np.zeros((len(floor), 3))
            chunk = max(1, (1 << 18) // a.spp)
            for i in range(0, len(floor), chunk):
                n = min(chunk, len(floor) - i)
                if input_kind == "qmc":
                    uvw = (qmc[:, None, :] + shifts[i:i + n].T[:, :, None]) % 1.0
                else:
                    uvw = rng.random((3, n, a.spp))
                x, y = smp.sample(*uvw.reshape(3, -1))
                tx = np.minimum((x * W).astype(int), W - 1)
                ty = np.minimum((y * H).astype(int), H - 1)
                est[i:i + n] = shade(P[i:i + n], x.reshape(n, a.spp), y.reshape(n, a.spp), rgb[ty, tx].reshape(n, a.spp, 3),
                                     inv[ty, tx].reshape(n, a.spp), area)
            key = f"{mname} ({input_kind})"
            out[key] = est
            rmse = np.sqrt((((est - ref) @ LUM) ** 2).mean()) / (ref @ LUM).mean()
            print(f"  {key:26s} relative RMSE {rmse:.4f}", flush=True)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"fence_{name}_{a.spp}spp.npz")
    em = cv2.resize(rgb.astype(np.float32), (512, int(512 * H / W)), interpolation=cv2.INTER_AREA)
    np.savez(path, kind=kind, base=base.reshape(res[1], res[0], 3), floor_idx=floor, ref=ref, emitter=em, spp=a.spp, **out)
    print(f"saved {path}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
