import numpy as np
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
from src.hardware import run_bb84_hardware
from src.hardware_eve import run_bb84_hardware_eve

backend = FakeSherbrooke()
seeds = range(1, 21)
honest, eve = [], []
for s in seeds:
    h = run_bb84_hardware(300, backend, sample_frac=0.3, seed=s)
    e = run_bb84_hardware_eve(300, backend, sample_frac=0.3, seed=s)
    honest.append(h["full_qber"])
    eve.append(e["full_qber"])
    print(f"seed {s}: honest {h['full_qber']:.3f} ({h['verdict']}) | eve {e['full_qber']:.3f} ({e['verdict']})")

print()
print(f"honest: mean {np.mean(honest):.3f}  std {np.std(honest):.3f}")
print(f"eve:    mean {np.mean(eve):.3f}  std {np.std(eve):.3f}")
