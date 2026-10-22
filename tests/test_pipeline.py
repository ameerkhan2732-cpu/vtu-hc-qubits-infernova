import numpy as np
from src.pipeline import run_exchange


def test_normal_is_safe():
    r = run_exchange(0.0, False, rng=np.random.default_rng(1))
    assert r["verdict"] == "safe" and len(r["key"]) == 32 and r["final_key_len"] > 0


def test_high_noise_still_usable():
    r = run_exchange(0.6, False, rng=np.random.default_rng(1))
    assert r["verdict"] in ("safe", "noisy") and r["key"] is not None


def test_eve_blocks():
    r = run_exchange(0.0, True, rng=np.random.default_rng(1))
    assert r["verdict"] == "compromised" and r["key"] is None and r["final_key_len"] == 0


def test_seeded_repeatable():
    a = run_exchange(0.3, False, rng=np.random.default_rng(7))
    b = run_exchange(0.3, False, rng=np.random.default_rng(7))
    assert a["qber"] == b["qber"] and a["key"] == b["key"]
