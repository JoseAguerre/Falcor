"""Repeatability probe: runs a few configurations back to back, several times each, and reports the
spread together with the GPU clock and temperature seen during each run. Used to decide how many
rounds the cost benchmark needs on a power-limited laptop GPU, where the clock is not lockable."""
import json
import os
import statistics
import subprocess
import time

import run_bench as R

CONFIGS = [("phonehand", "BudgetLeafAlias", 1000),
           ("phonehand", "BudgetLeafAlias", 4000),
           ("phonehand", "BudgetLeafAlias", 16000)]
REPS = 5
PROBE = os.path.join(R.HERE, "data", "probe")


def gpu_state():
    q = "clocks.sm,temperature.gpu,power.draw"
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
        return [float(x) for x in out.split(",")]
    except Exception:
        return [float("nan")] * 3


def main():
    os.makedirs(PROBE, exist_ok=True)
    res = {c: [] for c in CONFIGS}
    for rep in range(REPS):
        for scene, name, b in CONFIGS:
            tag = f"probe_{scene}_{name}_{b}_rep{rep}"
            out = os.path.join(PROBE, tag + ".json")
            env = dict(os.environ)
            env.update({"BENCH_MODE": "sampler", "BENCH_SAMPLER": name, "BENCH_LEAF_BUDGET": str(b),
                        "BENCH_DISPATCH_DIM": str(R.TABLE_DIM), "BENCH_SAMPLES_PER_THREAD": str(R.TABLE_SPT),
                        "BENCH_WARMUP": "15", "BENCH_FRAMES": str(R.TABLE_FRAMES), "BENCH_RESULT_PATH": out})
            cmd = [R.MOGWAI, "--headless", "-s", R.SCRIPT, "--scene", R.SCENES[scene][0],
                   "-l", os.path.join(R.LOGS, tag + ".log"), "-v", "2"]
            subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=900)
            clk, temp, pw = gpu_state()
            if os.path.exists(out):
                ms = json.load(open(out))["a_median_ms"]
                res[(scene, name, b)].append(ms)
                print(f"  rep{rep} {name}/{b}: {ms:8.2f} ms   sm={clk:.0f}MHz t={temp:.0f}C p={pw:.0f}W", flush=True)
            time.sleep(3)
    print()
    for c, v in res.items():
        if v:
            print(f"{c[1]}/{c[2]}: median {statistics.median(v):7.2f}  min {min(v):7.2f}  max {max(v):7.2f}  "
                  f"spread {100 * (max(v) - min(v)) / statistics.median(v):5.1f}%  n={len(v)}")


if __name__ == "__main__":
    main()
