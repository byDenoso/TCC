#!/usr/bin/env python3
import json, math, os, platform, random, statistics, time
from pathlib import Path

SEED = 20260911
N_STEPS = int(os.getenv("BENCH_STEPS", "2000000"))
BURN = int(os.getenv("BENCH_BURN", "200000"))
THIN = int(os.getenv("BENCH_THIN", "50"))

# Fixed synthetic cosmic-chronometer H(z) dataset generated once from a flat LCDM-like model.
# Units: z, H(z) km/s/Mpc, sigma km/s/Mpc.
DATA = [
(0.07,69.0,19.6),(0.09,69.0,12.0),(0.12,68.6,26.2),(0.17,83.0,8.0),
(0.179,75.0,4.0),(0.199,75.0,5.0),(0.20,72.9,29.6),(0.27,77.0,14.0),
(0.28,88.8,36.6),(0.352,83.0,14.0),(0.38,83.0,13.5),(0.40,95.0,17.0),
(0.4004,77.0,10.2),(0.4247,87.1,11.2),(0.4497,92.8,12.9),(0.47,89.0,49.6),
(0.4783,80.9,9.0),(0.48,97.0,62.0),(0.593,104.0,13.0),(0.68,92.0,8.0),
(0.781,105.0,12.0),(0.875,125.0,17.0),(0.88,90.0,40.0),(0.90,117.0,23.0),
(1.037,154.0,20.0),(1.30,168.0,17.0),(1.363,160.0,33.6),(1.43,177.0,18.0),
(1.53,140.0,14.0),(1.75,202.0,40.0),(1.965,186.5,50.4)
]

LIKELIHOOD_EVALS = 0

def loglike(h0, om):
    global LIKELIHOOD_EVALS
    LIKELIHOOD_EVALS += 1
    if not (50.0 < h0 < 90.0 and 0.05 < om < 0.60):
        return -1e300
    chi2 = 0.0
    for z, obs, sig in DATA:
        model = h0 * math.sqrt(om * (1.0 + z)**3 + (1.0 - om))
        d = (obs - model) / sig
        chi2 += d*d
    return -0.5 * chi2

def run():
    global LIKELIHOOD_EVALS
    rng = random.Random(SEED)
    h0, om = 70.0, 0.30
    ll = loglike(h0, om)
    accepted = 0
    kept_h0, kept_om, kept_ll = [], [], []
    t0 = time.perf_counter()

    for i in range(N_STEPS):
        ph0 = h0 + rng.gauss(0.0, 0.85)
        pom = om + rng.gauss(0.0, 0.018)
        pll = loglike(ph0, pom)
        if math.log(rng.random()) < (pll - ll):
            h0, om, ll = ph0, pom, pll
            accepted += 1
        if i >= BURN and ((i - BURN) % THIN == 0):
            kept_h0.append(h0); kept_om.append(om); kept_ll.append(ll)

    scientific_s = time.perf_counter() - t0
    out = {
        "benchmark": "flat_lcdm_cosmic_chronometer_metropolis",
        "seed": SEED,
        "n_steps": N_STEPS,
        "burn": BURN,
        "thin": THIN,
        "n_data": len(DATA),
        "likelihood_evals": LIKELIHOOD_EVALS,
        "scientific_seconds": scientific_s,
        "evals_per_second": LIKELIHOOD_EVALS / scientific_s,
        "acceptance_rate": accepted / N_STEPS,
        "samples_kept": len(kept_h0),
        "posterior": {
            "H0_mean": statistics.fmean(kept_h0),
            "H0_sd": statistics.stdev(kept_h0),
            "Omega_m_mean": statistics.fmean(kept_om),
            "Omega_m_sd": statistics.stdev(kept_om),
            "best_loglike": max(kept_ll)
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count()
        }
    }
    Path("benchmark_result.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    run()
