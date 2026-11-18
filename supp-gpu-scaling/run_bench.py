"""Runs the E09-style GPU benchmarks of QuadLightSamplerBench on this machine.

Three phases, each launching one Mogwai process per configuration (the paper's protocol: a separate
process per point, so that a GPU clock state cannot favour one configuration over another, and the
median of several shuffled rounds is reported).

  chase    pointer chase, working set from 4 KB to 512 MB -> the cache hierarchy of the GPU.
  sampler  isolated light-sampling dispatch per sampler and leaf budget -> cost per sample.
  gpubuild the build passes of the 2D CDF -> construction cost.

Usage: python run_bench.py chase|sampler|gpubuild [--rounds N] [--quick]
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MOGWAI = os.path.join(REPO, "build", "windows-vs2022", "bin", "Release", "Mogwai.exe")
SCRIPT = os.path.join(HERE, "bench.py")
DATA = os.path.join(HERE, "data")
LOGS = os.path.join(HERE, "logs")

# Scenes whose emitter texture survives on this machine, with the emitter resolution.
SCENES = {
    "phonehand": (os.path.join(REPO, "paperscenes", "phonehand", "phonehand.pyscene"), "1080p"),
    "fireplace_room": (os.path.join(REPO, "paperscenes", "fireplace_room", "fireplace_room.pyscene"), "4K"),
    "convergence": (os.path.join(REPO, "paperscenes", "convergence", "convergence.pyscene"), "4K"),
}

# (engine sampler name, leaf budget) pairs. Budget 0 means "not applicable".
SAMPLERS = [
    ("BudgetLeafAlias", 1000),
    ("BudgetLeafAlias", 2000),
    ("BudgetLeafAlias", 4000),
    ("BudgetLeafAlias", 8000),
    ("BudgetLeafAlias", 16000),
    ("AliasCtu", 0),
    ("Cdf2DDiv8", 0),
    ("HierarchicalMip", 0),
    ("AliasPerPixel", 0),
    ("Cdf2D", 0),
]

# 1440x1440 threads = 2073600 = exactly the 1920x1080 of the paper's table, with 128 samples each.
TABLE_DIM, TABLE_SPT, TABLE_FRAMES = 1440, 128, 60
CHASE_DIM, CHASE_HOPS, CHASE_FRAMES = 512, 128, 70
CHASE_BYTES = [1 << k for k in range(12, 30)]  # 4 KB .. 512 MB
# Extra points that bracket the two knees, so that the L1 and L2 capacities can be read off directly.
CHASE_BYTES += [160 << 10, 192 << 10, 224 << 10,
                20 << 20, 24 << 20, 28 << 20, 40 << 20, 48 << 20]
CHASE_BYTES = sorted(set(CHASE_BYTES))


def run(tag, env_extra, scene, frames, timeout=900):
    """Runs one Mogwai process and returns the parsed result JSON, or None on failure."""
    out = os.path.join(DATA, tag + ".json")
    if os.path.exists(out):
        try:
            with open(out) as f:
                return json.load(f)
        except Exception:
            os.remove(out)
    env = dict(os.environ)
    env.update({k: str(v) for k, v in env_extra.items()})
    env["BENCH_RESULT_PATH"] = out
    env["BENCH_FRAMES"] = str(frames)
    log = os.path.join(LOGS, tag + ".log")
    cmd = [MOGWAI, "--headless", "-s", SCRIPT, "--scene", scene, "-l", log, "-v", "2"]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  {tag}: TIMEOUT after {timeout}s", flush=True)
        return None
    dt = time.time() - t0
    if not os.path.exists(out):
        print(f"  {tag}: FAILED rc={p.returncode} in {dt:.0f}s", flush=True)
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-6:]
        for line in tail:
            print(f"      {line}", flush=True)
        return None
    with open(out) as f:
        r = json.load(f)
    print(f"  {tag}: a={r.get('a_median_ms')} ms  ({dt:.0f}s)", flush=True)
    # This GPU is power limited and its clock is not lockable, so let it settle between processes.
    time.sleep(4)
    return r


def phase_chase(args):
    scene = SCENES["phonehand"][0]  # any scene; the chase does not touch scene data
    sizes = CHASE_BYTES[::3] if args.quick else CHASE_BYTES
    for rnd in range(args.rounds):
        for b in sizes:
            run(f"chase_b{b}_r{rnd}",
                {"BENCH_MODE": "chase", "BENCH_CHASE_BYTES": b, "BENCH_CHASE_HOPS": CHASE_HOPS,
                 "BENCH_DISPATCH_DIM": CHASE_DIM, "BENCH_WARMUP": 20},
                scene, CHASE_FRAMES)


def phase_sampler(args):
    dim = 512 if args.quick else TABLE_DIM
    spt = 8 if args.quick else TABLE_SPT
    frames = 20 if args.quick else TABLE_FRAMES
    scenes = ["phonehand"] if args.quick else list(SCENES)
    samplers = SAMPLERS[:3] if args.quick else SAMPLERS
    jobs = [(s, name, b, rnd) for rnd in range(args.rounds) for s in scenes for name, b in samplers]
    for rnd in range(args.rounds):
        batch = [j for j in jobs if j[3] == rnd]
        random.Random(1234 + rnd).shuffle(batch)
        for s, name, b, _ in batch:
            run(f"samp_{s}_{name}_{b}_d{dim}_s{spt}_r{rnd}",
                {"BENCH_MODE": "sampler", "BENCH_SAMPLER": name, "BENCH_LEAF_BUDGET": b,
                 "BENCH_DISPATCH_DIM": dim, "BENCH_SAMPLES_PER_THREAD": spt, "BENCH_WARMUP": max(8, frames // 4)},
                SCENES[s][0], frames)


def phase_gpubuild(args):
    for rnd in range(args.rounds):
        for s in (["phonehand"] if args.quick else list(SCENES)):
            run(f"build_{s}_r{rnd}",
                {"BENCH_MODE": "gpubuild", "BENCH_DISPATCH_DIM": 64, "BENCH_WARMUP": 20},
                SCENES[s][0], 80)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["chase", "sampler", "gpubuild"])
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    if not os.path.exists(MOGWAI):
        sys.exit(f"Mogwai not found at {MOGWAI}")
    t0 = time.time()
    {"chase": phase_chase, "sampler": phase_sampler, "gpubuild": phase_gpubuild}[args.phase](args)
    print(f"{args.phase} done in {(time.time() - t0) / 60:.1f} min", flush=True)
