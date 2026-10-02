"""
Experiment 24: diffuse (Lambertian) convolution of a scene's real emissive HDR texture via
Monte Carlo importance sampling, comparing 2D CDF, AliasPerPixel, and BudgetLeafAlias(12000)
- reusing sampling_common.py (copied from experiment23; same validated Cdf2D/AliasMethod2D/
BudgetLeafAlias2D classes - BudgetLeafAlias2D gained a `pdf_uv` method here, which experiment23
never needed since its figures only ever plotted point positions, not a full MC estimator).

For each output direction n (a full-sphere equirectangular grid, not the input HDR's own
resolution - diffuse convolution is inherently very low-frequency, so a much coarser output
grid is standard and sufficient), estimate the diffuse response of a white (albedo=1)
Lambertian surface facing n:

    L_o(n) = (1/pi) * (1/N) * sum_i [ Le(w_i) * max(0, dot(n, w_i)) / pdf_solid_angle(w_i) ]

using N environment samples drawn via whichever technique's importance sampling (proportional
to the HDR's own luminance), for N in {1,4,6,8,12,16,20,24,30}. Reference: 2D CDF at N=300.

Sampling scheme: per-pixel-AND-per-sample stratified jittered (N-rooks) 2D sampling - see
stratified_jittered_2d()'s own docstring for why. Short version: round 1 used experiment23's
fig10_repro.py approach (a shared Hammersley(N) sequence, per-pixel Cranley-Patterson
rotation) and got wildly non-monotonic AliasPerPixel RMSE vs. N (0.10 at N=16, back up to
0.21 at N=20) - every requested N (1,4,6,8,12,16,20,24,30) divides 1920x1080's texel count
exactly, the same bucket-position resonance experiment23's fig9_repro.py found, and a CP
rotation does not fix it (verified there: it preserves the exact 1/N spacing that causes it).
Switched to continuous per-pixel-and-per-sample jitter instead, which breaks the exact grid
alignment entirely rather than working around it.

Errors (FLIP, RMSE, PSNR) are computed on the tonemapped (simple gamma 2.2, shared exposure
picked from the reference) LDR image, matching this project's usual metric convention -
FLIP additionally requires LDR [0,1] input by construction.

Usage: python diffuse_convolution.py [scene_name]  (default: rover)

Output: results/experiment24/results_<scene>.json (raw numbers),
        results/experiment24/convolution_grid_<scene>.png (visual grid).
"""
import os
import sys
import json
import time
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sampling_common import Cdf2D, AliasMethod2D, BudgetLeafAlias2D

REPO = r"C:\Users\Jose\Desktop\Falcor"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Verified directly from each scene's own .pyscene (QuadLight.createFromFile(...) call), not
# guessed - same real texture used for this project's actual calibrated real-time results.
SCENE_HDR = {
    "rover": "quadlight/road/frame_00150.hdr",
    "cinema": "quadlight/hdr/frame_00232.hdr",
    "fireplace_room": "quadlight/fireplace/4k/frame_00082.hdr",
    "phonehand": "quadlight/colors/frame_00987.hdr",
    "convergence": "quadlight/cave/frame_00221.hdr",
}

SAMPLE_COUNTS = [1, 4, 6, 8, 12, 16, 20, 24, 30]
REF_N = 300
OUT_W, OUT_H = 128, 64  # output convolution grid resolution (full-sphere equirect)
ROTATION_SEED = 0


def load_hdr_rgb(path):
    img = cv2.imread(path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float64)


def luminance(rgb):
    return np.clip(0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2], 1e-8, None)


def build_output_dirs(w, h):
    """Full-sphere equirect grid of output normals n (one per output pixel)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    theta_n = (yy + 0.5) / h * np.pi
    phi_n = (xx + 0.5) / w * 2 * np.pi
    nx = np.sin(theta_n) * np.cos(phi_n)
    ny = np.cos(theta_n)
    nz = np.sin(theta_n) * np.sin(phi_n)
    return np.stack([nx, ny, nz], axis=-1)  # (h,w,3)


def stratified_jittered_2d(h, w, N, seed):
    """Per-pixel N-rooks (Latin hypercube) stratified sampling: x-strata 0..N-1 in natural
    order, y-strata an INDEPENDENT RANDOM PERMUTATION per pixel, each jittered by a
    continuous random offset (also independent per pixel AND per sample).

    Why not Hammersley + a per-pixel Cranley-Patterson rotation (used in experiment23's
    fig10_repro.py): here every requested sample count (1,4,6,8,12,16,20,24,30) divides the
    HDR's own texel count (1920x1080 = 2^10*3^4*5^2, and every one of those N values is built
    only from factors 2/3/5) EXACTLY - the same bucket-position resonance fig9_repro.py found
    and fixed by picking a prime N. A CP rotation does NOT fix this (verified back in
    experiment23: it preserves the exact 1/N spacing that causes the resonance). Confirmed
    here empirically too: AliasPerPixel's RMSE was wildly non-monotonic in N (0.10 at N=16,
    back up to 0.21 at N=20) under Hammersley+rotation - a resonance artifact, not real
    convergence behavior. Continuous per-pixel-and-per-sample jitter (this function) breaks
    the exact grid alignment entirely, so no fixed N can resonate with the texel grid,
    while still keeping proper N-sample stratification (better than naive independent
    random) - the correct fix, not a workaround."""
    rng = np.random.default_rng(seed)
    xi_u = rng.random((h, w, N))
    xi_v = rng.random((h, w, N))
    perm = np.argsort(rng.random((h, w, N)), axis=-1)
    strata = np.arange(N)
    u_all = (strata[None, None, :] + xi_u) / N
    v_all = (perm + xi_v) / N
    return u_all, v_all


def convolve(sampler, rgb, N, normals, seed):
    """Diffuse (albedo=1) Lambertian convolution, N samples/output-pixel, per-pixel-and-
    per-sample stratified jittered (N-rooks) sampling - see stratified_jittered_2d."""
    h, w = normals.shape[:2]
    H_img, W_img = rgb.shape[:2]
    accum = np.zeros((h, w, 3))
    u_all, v_all = stratified_jittered_2d(h, w, N, seed)

    for k in range(N):
        hx = u_all[:, :, k]
        hy = v_all[:, :, k]
        sx, sy = sampler.sample(hx.ravel(), hy.ravel())
        sx = sx.reshape(h, w)
        sy = sy.reshape(h, w)

        theta = sy * np.pi
        phi = sx * 2 * np.pi
        wdir = np.stack([np.sin(theta) * np.cos(phi), np.cos(theta), np.sin(theta) * np.sin(phi)], axis=-1)

        row = np.clip((sy * H_img).astype(np.int64), 0, H_img - 1)
        col = np.clip((sx * W_img).astype(np.int64), 0, W_img - 1)
        le = rgb[row, col]  # (h,w,3)
        pdf_vals = sampler.pdf_uv(sx.ravel(), sy.ravel()).reshape(h, w)
        sin_theta = np.sin(theta)

        cos_i = np.einsum("hwi,hwi->hw", normals, wdir)
        cos_i = np.maximum(cos_i, 0.0)
        weight = cos_i * (2 * np.pi ** 2 * sin_theta) / np.maximum(pdf_vals, 1e-8)
        accum += le * weight[..., None]

    return accum / (N * np.pi)


def tonemap(img, exposure):
    x = np.clip(img * exposure, 0, None)
    return np.clip(x ** (1.0 / 2.2), 0, 1)


def run(scene):
    """`scene` is either one of the 5 official scene keys (SCENE_HDR), or a raw path to any
    other .hdr file - used to test the synthetic textures from experiment22/hdr_tests/ (read
    only, never modified - those are that experiment's own search results)."""
    if scene in SCENE_HDR:
        hdr_path = os.path.join(REPO, SCENE_HDR[scene])
    else:
        hdr_path = scene if os.path.isabs(scene) else os.path.join(REPO, scene)
        scene = os.path.splitext(os.path.basename(hdr_path))[0]
    print(f"Loading {scene}: {hdr_path}")
    rgb = load_hdr_rgb(hdr_path)
    lum = luminance(rgb)
    print(f"  resolution {lum.shape}, luminance range [{lum.min():.4f}, {lum.max():.4f}]")

    cdf = Cdf2D(lum)
    alias = AliasMethod2D(lum)
    t0 = time.time()
    budget = BudgetLeafAlias2D(lum, leaf_budget=12000)
    print(f"  BudgetLeafAlias(12000): {budget.leaf_count} leaves, built in {time.time()-t0:.2f}s")

    normals = build_output_dirs(OUT_W, OUT_H)

    def seed_for(n):
        # same seed for all techniques at a given N (fair, matched-noise comparison), a
        # different seed per N (each N gets its own independent jitter/permutation draw).
        return ROTATION_SEED * 100000 + n

    print(f"  Reference: 2D CDF, N={REF_N}")
    ref = convolve(cdf, rgb, REF_N, normals, seed_for(REF_N))
    exposure = 1.0 / max(np.percentile(ref, 99), 1e-6)
    ref_ldr = tonemap(ref, exposure)

    import flip_evaluator as flip

    techniques = {"2D CDF": cdf, "AliasPerPixel": alias, "BudgetLeafAlias(12000)": budget}
    results = {}
    for tech_name, sampler in techniques.items():
        results[tech_name] = {}
        for N in SAMPLE_COUNTS:
            img = convolve(sampler, rgb, N, normals, seed_for(N))
            ldr = tonemap(img, exposure)
            rmse = float(np.sqrt(((ldr - ref_ldr) ** 2).mean()))
            mse = float(((ldr - ref_ldr) ** 2).mean())
            psnr = float(99.0 if mse <= 1e-12 else 10.0 * np.log10(1.0 / mse))
            _, mean_flip, _ = flip.evaluate(ref_ldr.astype(np.float32), ldr.astype(np.float32), "LDR", applyMagma=False)
            results[tech_name][N] = {"rmse": rmse, "psnr": psnr, "flip": float(mean_flip)}
            print(f"    {tech_name:24s} N={N:3d}: RMSE={rmse:.5f} PSNR={psnr:.2f} FLIP={mean_flip:.5f}")

    out_json = os.path.join(OUT_DIR, f"results_{scene}.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print("Saved", out_json)

    # Visual grid: ONE reference panel on its own row (not repeated per column - an earlier
    # version wrongly plotted the same reference image into every column, which read as "5
    # different references"), then technique x N below it.
    show_ns = [1, 4, 8, 16, 30]
    n_rows = len(techniques) + 1
    n_cols = len(show_ns)
    fig = plt.figure(figsize=(3 * n_cols, 3 * n_rows))
    gs = fig.add_gridspec(n_rows, n_cols)

    ax_ref = fig.add_subplot(gs[0, n_cols // 2])
    ax_ref.imshow(ref_ldr)
    ax_ref.set_title(f"Reference (2D CDF, N={REF_N})", fontsize=11)
    ax_ref.set_xticks([]); ax_ref.set_yticks([])

    for ri, (tech_name, sampler) in enumerate(techniques.items(), start=1):
        for ci, N in enumerate(show_ns):
            img = convolve(sampler, rgb, N, normals, seed_for(N))
            ldr = tonemap(img, exposure)
            ax = fig.add_subplot(gs[ri, ci])
            ax.imshow(ldr)
            ax.set_xticks([]); ax.set_yticks([])
            if ci == 0:
                ax.set_ylabel(tech_name, fontsize=10)
            ax.set_title(f"N={N}", fontsize=9)
    plt.tight_layout()
    out_png = os.path.join(OUT_DIR, f"convolution_grid_{scene}.png")
    plt.savefig(out_png, dpi=130)
    plt.close(fig)
    print("Saved", out_png)

    return results


if __name__ == "__main__":
    scene = sys.argv[1] if len(sys.argv) > 1 else "rover"
    run(scene)
