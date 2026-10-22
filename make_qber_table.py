"""Sweep noise level 0..1 (Eve off, plus Eve on at level 0) and save results/qber_vs_noise.csv."""
import csv
import os

import numpy as np

from src.pipeline import run_exchange, get_expected_qber

REPEATS = 3
rows = []
for i in range(11):
    level = round(i / 10, 1)
    for r in range(REPEATS):
        out = run_exchange(level, False, rng=np.random.default_rng(1000 * i + r))
        rows.append(["off", level, r, out["qber"], get_expected_qber(level),
                     out["verdict"], out["final_key_len"]])
for r in range(REPEATS):
    out = run_exchange(0.0, True, rng=np.random.default_rng(9000 + r))
    rows.append(["on", 0.0, r, out["qber"], get_expected_qber(0.0),
                 out["verdict"], out["final_key_len"]])

os.makedirs("results", exist_ok=True)
with open("results/qber_vs_noise.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["eve", "noise_level", "repeat", "observed_qber",
                "expected_qber", "verdict", "final_key_len"])
    w.writerows(rows)
print("wrote", len(rows), "rows")