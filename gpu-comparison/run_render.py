"""Runs the equal-quality ladder on this machine.

  python run_render.py reference    one converged image per scene, used as the ground truth
  python run_render.py ladder       for each scene and technique, a ladder over the light-sample
                                    count: mean frame time and a captured image per rung
  python run_render.py rmse         compares every captured rung against its scene's reference

Each (scene, technique) is one Mogwai process that walks the whole ladder, so a sampling structure
is built once per process and the GPU stays busy between rungs.
"""
import argparse
import json
import os
import re
import statistics as st
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MOGWAI = os.path.join(REPO, "build", "windows-vs2022", "bin", "Release", "Mogwai.exe")
SCRIPT = os.path.join(HERE, "render_ladder.py")
DATA, RENDERS = os.path.join(HERE, "data"), os.path.join(HERE, "renders")

SCENES = {
    "phonehand": os.path.join(REPO, "paperscenes", "phonehand", "phonehand.pyscene"),
    "fireplace_room": os.path.join(REPO, "paperscenes", "fireplace_room", "fireplace_room.pyscene"),
    "convergence": os.path.join(REPO, "paperscenes", "convergence", "convergence.pyscene"),
}
# (engine name, leaf budget, label used in the note)
TECHS = [
    ("Cdf2D", 0, "2D CDF"),
    ("Cdf2DDiv8", 0, "2D CDF/8"),
    ("HierarchicalMip", 0, "Mipmap"),
    ("AliasPerPixel", 0, "Alias per pixel"),
    ("BudgetLeafAlias", 4000, "BudgetLeafAlias"),
    ("AliasCtu", 0, "CodecLeafAlias"),
]
# The 4K-emitter scenes cost roughly five times a frame of Phone on this GPU, and their 33.3 ms
# budget is already exceeded well below 64 samples, so their ladder stops earlier.
LSPV_BY_SCENE = {s: [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]
                 for s in ("phonehand", "fireplace_room", "convergence")}
SPP = 1
FRAMES = 40          # frames rendered per rung
WARMUP = 12          # leading frames of each rung discarded, so the clock settles after the switch
REF_FRAMES, REF_SPP, REF_LSPV = 1200, 1, 64
LEAF_BUDGETS = [250, 1000, 2000, 8000, 16000]   # 4000 is already covered by TECHS
WIDTH, HEIGHT = 1920, 1080


def launch(env_extra, scene, out_dir, timeout=5400):
    env = dict(os.environ)
    env.update({k: str(v) for k, v in env_extra.items()})
    env.update({"RB_WIDTH": str(WIDTH), "RB_HEIGHT": str(HEIGHT), "RB_OUT": out_dir})
    os.makedirs(out_dir, exist_ok=True)
    cmd = [MOGWAI, "--headless", "-s", SCRIPT, "--scene", scene, "-v", "1"]
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return p.returncode == 0, (p.stderr or p.stdout or "")[-400:]


def phase_reference(args):
    for s, path in SCENES.items():
        out = os.path.join(RENDERS, s + "_ref")
        if any(f.endswith(".png") for f in os.listdir(out)) if os.path.isdir(out) else False:
            print(f"  {s}: reference already present", flush=True)
            continue
        t0 = time.time()
        ok, msg = launch({"RB_MODE": "reference", "RB_REF_FRAMES": REF_FRAMES, "RB_REF_SPP": REF_SPP,
                          "RB_REF_LSPV": REF_LSPV, "RB_NAME": "ref"}, path, out)
        print(f"  {s}: reference {'ok' if ok else 'FAILED ' + msg} ({time.time() - t0:.0f}s)", flush=True)


def phase_ladder(args):
    for s, path in SCENES.items():
        for name, leaf, _ in TECHS:
            tag = f"{s}_{name}_{leaf}"
            res = os.path.join(DATA, tag + ".json")
            if os.path.exists(res):
                continue
            out = os.path.join(RENDERS, tag)
            times = os.path.join(DATA, tag + "_times.txt")
            t0 = time.time()
            lspv = LSPV_BY_SCENE[s]
            ok, msg = launch({"RB_MODE": "ladder", "RB_SAMPLER": name, "RB_LEAF": leaf,
                              "RB_SPP": SPP, "RB_LSPV": ",".join(map(str, lspv)),
                              "RB_FRAMES": FRAMES, "RB_NAME": "f", "RB_TIMES": times}, path, out)
            if not ok or not os.path.exists(times):
                print(f"  {tag}: FAILED {msg}", flush=True)
                continue
            rows = segment(times, lspv)
            json.dump({"scene": s, "sampler": name, "leaf": leaf, "spp": SPP, "ladder": rows},
                      open(res, "w"), indent=1)
            print(f"  {tag}: {rows[0]['frame_ms']:.1f} .. {rows[-1]['frame_ms']:.1f} ms "
                  f"({time.time() - t0:.0f}s)", flush=True)


def phase_leaves(args):
    """Same ladder, but sweeping BudgetLeafAlias's leaf budget instead of the technique."""
    for s, path in SCENES.items():
        for leaf in LEAF_BUDGETS:
            tag = f"{s}_BudgetLeafAlias_{leaf}"
            res = os.path.join(DATA, tag + ".json")
            if os.path.exists(res):
                continue
            out, times = os.path.join(RENDERS, tag), os.path.join(DATA, tag + "_times.txt")
            lspv = LSPV_BY_SCENE[s]
            t0 = time.time()
            ok, msg = launch({"RB_MODE": "ladder", "RB_SAMPLER": "BudgetLeafAlias", "RB_LEAF": leaf,
                              "RB_SPP": SPP, "RB_LSPV": ",".join(map(str, lspv)),
                              "RB_FRAMES": FRAMES, "RB_NAME": "f", "RB_TIMES": times}, path, out)
            if not ok or not os.path.exists(times):
                print(f"  {tag}: FAILED {msg}", flush=True)
                continue
            rows = segment(times, lspv)
            json.dump({"scene": s, "sampler": "BudgetLeafAlias", "leaf": leaf, "spp": SPP,
                       "ladder": rows}, open(res, "w"), indent=1)
            print(f"  {tag}: {rows[0]['frame_ms']:.1f} .. {rows[-1]['frame_ms']:.1f} ms "
                  f"({time.time() - t0:.0f}s)", flush=True)


def segment(times_path, lspv):
    """Splits Mogwai's frame-time log into one block per rung, discarding each block's warmup.
    Mogwai logs the real-time delta in seconds, so the values are converted to milliseconds here."""
    v = [float(x) * 1000.0 for x in open(times_path).read().split() if x.strip()]
    # The log starts at frame 2, so frame i (1-based) is at index i-2.
    rows = []
    for i, n in enumerate(lspv):
        lo, hi = i * FRAMES + WARMUP, (i + 1) * FRAMES
        blk = [v[j - 2] for j in range(lo, hi + 1) if 0 <= j - 2 < len(v)]
        rows.append({"lspv": n, "frame_ms": st.median(blk) if blk else None,
                     "n_frames": len(blk), "capture_frame": (i + 1) * FRAMES})
    return rows


def phase_rmse(args):
    os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
    import cv2
    import numpy as np

    def load(d, frame=None):
        if not os.path.isdir(d):
            return None
        fs = [f for f in os.listdir(d) if f.endswith(".png")]
        if frame is not None:
            fs = [f for f in fs if re.search(rf"\.{frame}\.png$", f)]
        if not fs:
            return None
        img = cv2.imread(os.path.join(d, sorted(fs)[0]), cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.ndim == 3 and img.shape[2] == 4:
            img = img[:, :, :3]
        return img.astype(np.float64) / 255.0

    for s in SCENES:
        ref = load(os.path.join(RENDERS, s + "_ref"))
        if ref is None:
            print(f"  {s}: no reference, skipping", flush=True)
            continue
        jobs = [(n, l) for n, l, _ in TECHS] + [("BudgetLeafAlias", b) for b in LEAF_BUDGETS]
        for name, leaf in jobs:
            tag = f"{s}_{name}_{leaf}"
            res = os.path.join(DATA, tag + ".json")
            if not os.path.exists(res):
                continue
            d = json.load(open(res))
            for row in d["ladder"]:
                img = load(os.path.join(RENDERS, tag), row["capture_frame"])
                if img is None or img.shape != ref.shape:
                    row["rmse"] = row["mse"] = None
                    continue
                mse = float(np.mean((img - ref) ** 2))
                row["mse"], row["rmse"] = mse, mse ** 0.5
            json.dump(d, open(res, "w"), indent=1)
            got = [r for r in d["ladder"] if r.get("rmse")]
            print(f"  {tag}: {len(got)}/{len(d['ladder'])} rungs, rmse "
                  f"{got[0]['rmse']:.4f} .. {got[-1]['rmse']:.4f}" if got else f"  {tag}: no rmse",
                  flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["reference", "ladder", "leaves", "rmse"])
    args = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)
    if not os.path.exists(MOGWAI):
        sys.exit(f"Mogwai not found at {MOGWAI}")
    t0 = time.time()
    {"reference": phase_reference, "ladder": phase_ladder, "leaves": phase_leaves,
     "rmse": phase_rmse}[args.phase](args)
    print(f"{args.phase} done in {(time.time() - t0) / 60:.1f} min", flush=True)
