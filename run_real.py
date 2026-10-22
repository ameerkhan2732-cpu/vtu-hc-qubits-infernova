import argparse
import numpy as np
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import SamplerV2
from src.bb84 import random_bits, build_circuit, sift, estimate_qber, decide


def bits_from_pub(pub):
    data = pub.data
    reg = data.c if hasattr(data, "c") else next(iter(data.values()))
    bitstring = list(reg.get_counts().keys())[0]
    return [int(b) for b in reversed(bitstring.replace(" ", ""))]


def run_sampler(bits, a_bases, b_bases, backend, chunk=5):
    n = len(bits)
    circuits = [build_circuit(bits[s:s + chunk], a_bases[s:s + chunk], b_bases[s:s + chunk])
                for s in range(0, n, chunk)]
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
    isa = pm.run(circuits)
    job = SamplerV2(mode=backend).run(isa, shots=1)
    print("job id:", getattr(job, "job_id", lambda: "local")())
    result = job.result()
    out = []
    for pub in result:
        out.extend(bits_from_pub(pub))
    return np.array(out)


def run_round(n, backend, eve=False, sample_frac=0.3, seed=None):
    rng = np.random.default_rng(seed)
    bits = random_bits(n, rng)
    a_bases = random_bits(n, rng)
    b_bases = random_bits(n, rng)
    if eve:
        e_bases = random_bits(n, rng)
        e_bits = np.where(e_bases == a_bases, bits, random_bits(n, rng))
        bob = run_sampler(e_bits, e_bases, b_bases, backend)
    else:
        bob = run_sampler(bits, a_bases, b_bases, backend)
    a_key, b_key = sift(bits, a_bases, bob, b_bases)
    full = float((a_key != b_key).mean())
    qber, _, _ = estimate_qber(a_key, b_key, sample_frac, rng)
    return len(a_key), qber, full, decide(qber)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fake", action="store_true", help="use FakeSherbrooke, no token")
    p.add_argument("--dry-run", action="store_true", help="list devices only")
    p.add_argument("--backend", default=None)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--eve", action="store_true")
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()

    if a.fake:
        from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
        backend = FakeSherbrooke()
    else:
        from qiskit_ibm_runtime import QiskitRuntimeService
        from src.ibm_token import get_ibm_token
        service = QiskitRuntimeService(channel="ibm_quantum_platform", token=get_ibm_token())
        if a.dry_run:
            for b in service.backends(operational=True, simulator=False):
                print(b.name, b.num_qubits, "pending jobs:", b.status().pending_jobs)
            raise SystemExit
        backend = service.backend(a.backend) if a.backend else service.least_busy(
            operational=True, simulator=False, min_num_qubits=10)
    print("backend:", backend.name)
    sifted, qber, full, verdict = run_round(a.n, backend, eve=a.eve, seed=a.seed)
    print(f"sifted {sifted} | sampled qber {qber:.3f} | full qber {full:.3f} | {verdict}")
