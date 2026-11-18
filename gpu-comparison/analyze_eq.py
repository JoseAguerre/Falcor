"""Equal-quality analysis, applied by the same code to both GPUs.

The RTX 4050 ladders come from run_render.py on this machine. The RTX 4080 SUPER ladders are the
spp=4 slice of the project's own dense sweep (paper-experiments/realtime_tradeoff_curves), which
records the same three quantities per rung: light samples per shading point, mean frame time and
RMSE against a converged reference. Both are reduced here by one Ladder class, so neither GPU gets
a different treatment.

Per scene we take the 2D CDF as the reference technique, find the light-sample count whose frame
time fills a 33.3 ms real-time budget, and read its RMSE there. For every technique we then report
  speedup   33.3 ms divided by the frame time at which that technique reaches the same RMSE
  rmse_rel  that technique's RMSE inside 33.3 ms, over the 2D CDF's
RMSE is smoothed by a quadratic fit of log(MSE) against log(samples), as in the paper, because a
single rung's RMSE is noisy.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
SWEEP = os.path.join(REPO, "paper-experiments", "realtime_tradeoff_curves")

BUDGET_MS = 1000 / 30
SPP = 4

SCENES = ["phonehand", "fireplace_room", "convergence"]
SCENE_LAB = {"phonehand": "Phone", "fireplace_room": "Fireplace Room", "convergence": "Convergence"}
EMITTER = {"phonehand": "1920x1080", "fireplace_room": "3840x2160", "convergence": "3840x2160"}

# label -> (engine name, leaf budget) as run on the 4050
TECHS = [("2D CDF", ("Cdf2D", 0)), ("2D CDF/8", ("Cdf2DDiv8", 0)), ("Mipmap", ("HierarchicalMip", 0)),
         ("Alias per pixel", ("AliasPerPixel", 0)), ("BudgetLeafAlias", ("BudgetLeafAlias", 4000)),
         ("CodecLeafAlias", ("AliasCtu", 0))]
OURS = ("BudgetLeafAlias", "CodecLeafAlias")
# The 4080 SUPER sweep names its techniques differently and covers only three of them.
SWEEP_NAME = {"2D CDF": "Cdf2D", "Mipmap": "HierarchicalMip", "BudgetLeafAlias": "Ours"}
SWEEP_SCENES = ["phonehand", "convergence"]


class Ladder:
    """One technique's rungs in one scene on one GPU."""

    def __init__(self, rows):
        rows = sorted((r for r in rows if r.get("rmse") and r.get("frame_ms")), key=lambda r: r["lspv"])
        self.n = np.array([r["lspv"] for r in rows], float)
        self.t_pts = np.array([r["frame_ms"] for r in rows], float)
        self.rmse_pts = np.array([r["rmse"] for r in rows], float)
        # Frame time must not decrease with more samples; the running maximum removes clock dips.
        self.t = np.maximum.accumulate(self.t_pts)
        mse = np.array([r["mse"] for r in rows], float)
        self.p = np.polyfit(np.log(self.n), np.log(mse), 2)
        self.grid = np.linspace(self.n[0], self.n[-1], 8000)

    def time(self, n):
        return np.interp(n, self.n, self.t)

    def rmse(self, n):
        return np.sqrt(np.exp(np.polyval(self.p, np.log(n))))

    def samples_in(self, ms):
        ok = self.time(self.grid) <= ms
        return float(self.grid[ok][-1]) if ok.any() else float(self.n[0])

    def samples_for(self, rmse):
        ok = self.rmse(self.grid) <= rmse
        return float(self.grid[ok][0]) if ok.any() else None

    def capped(self):
        return self.time(self.n[-1]) <= BUDGET_MS


def load_4050():
    out = {}
    for s in SCENES:
        for lab, (name, leaf) in TECHS:
            p = os.path.join(DATA, f"{s}_{name}_{leaf}.json")
            if not os.path.exists(p):
                continue
            rows = json.load(open(p))["ladder"]
            if sum(1 for r in rows if r.get("rmse")) >= 5:
                out[(s, lab)] = Ladder(rows)
    return out


def load_4080():
    out = {}
    for s in SWEEP_SCENES:
        p = os.path.join(SWEEP, f"{s}_all_data.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        for lab, key in SWEEP_NAME.items():
            rows = [{"lspv": x["lspv"], "frame_ms": x["meanFrameTimeMs"], "rmse": x["rmse"],
                     "mse": x["rmse"] ** 2}
                    for x in d if x["technique"] == key and x["spp"] == SPP]
            if len(rows) >= 5:
                out[(s, lab)] = Ladder(rows)
    return out


def equal_quality(L, scene):
    """Returns per-technique results for one scene on one GPU, or None if the 2D CDF is missing."""
    c = L.get((scene, "2D CDF"))
    if c is None:
        return None
    n0 = c.samples_in(BUDGET_MS)
    r0 = float(c.rmse(n0))
    res = {"2D CDF": dict(n=n0, rmse=r0, speedup=1.0, rmse_rel=1.0, ms=float(c.time(n0)))}
    for lab, _ in TECHS:
        if lab == "2D CDF" or (scene, lab) not in L:
            continue
        l = L[(scene, lab)]
        nq = l.samples_for(r0)
        nt = l.samples_in(BUDGET_MS)
        res[lab] = dict(n=nt, rmse=float(l.rmse(nt)),
                        speedup=None if nq is None else BUDGET_MS / float(l.time(nq)),
                        rmse_rel=float(l.rmse(nt)) / r0, ms=float(l.time(nt)),
                        capped=l.capped())
    return res


def report():
    A, B = load_4050(), load_4080()
    print("=== ladders loaded ===")
    print("  4050:", len(A), " 4080S:", len(B))
    for s in SCENES:
        print(f"\n### {SCENE_LAB[s]}  (emitter {EMITTER[s]})")
        ra, rb = equal_quality(A, s), equal_quality(B, s)
        print(f"  {'technique':16} | {'4050 spd':>9} {'rmse_rel':>9} {'n@33ms':>7} | "
              f"{'4080S spd':>9} {'rmse_rel':>9} {'n@33ms':>7}")
        for lab, _ in TECHS:
            def fmt(r):
                if r is None or lab not in r:
                    return f"{'--':>9} {'--':>9} {'--':>7}"
                x = r[lab]
                sp = "--" if x["speedup"] is None else f"{x['speedup']:.2f}"
                return f"{sp:>9} {x['rmse_rel']:>9.3f} {x['n']:>7.1f}"
            print(f"  {lab:16} | {fmt(ra)} | {fmt(rb)}")
    return A, B


if __name__ == "__main__":
    report()
