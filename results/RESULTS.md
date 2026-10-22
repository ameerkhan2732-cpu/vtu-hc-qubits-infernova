# BB84 results

All runs: 300 qubits (simulation) or 200 qubits (real device), 5-qubit circuits,
1 shot each, abort threshold 11% QBER. Eve = intercept-resend, modeled in
software; Alice's preparation and Bob's measurement run on the backend.

## Real hardware (ibm_marrakesh, IBM Quantum Open plan, 2026-10-22)

| Scenario | Seed | Sifted | Full QBER | Verdict | Job ID |
|---|---|---|---|---|---|
| Honest | 1 | 115 | 2.6% | SAFE | dbcp9sgc77vs7386ocm0 |
| Eve | 1 | 115 | 32.2% | EAVESDROPPER | dbcprck24mrc73ck5h70 |

Command: `python run_real.py --backend ibm_marrakesh --n 200 [--eve]`
One run per scenario, so no averages are claimed.

## Noise-model simulation (FakeSherbrooke, 20 runs, seeds 1 to 20)

| Scenario | Mean full QBER | Std | Range | Verdict |
|---|---|---|---|---|
| Honest | 1.8% | 1.4% | 0.0% to 5.6% | SAFE 20/20 |
| Eve | 25.8% | 2.7% | 21.8% to 29.3% | EAVESDROPPER 20/20 |

Command: `python run_compare.py`
Measurement sampling on the fake backend is not seeded, so reruns differ slightly.

## Limitations

- Eve is simulated classically; only Bob's measurement is on the device.
- Small keys: sampled QBER uses about 30 bits, so full QBER is the cross-check.
- Only intercept-resend was tested, not other attacks.
