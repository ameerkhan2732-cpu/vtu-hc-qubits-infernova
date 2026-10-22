<div align="center">

# Qubits Infernova

**VTU-QFF-HC-0094** &nbsp;|&nbsp; Tier: **Both**

</div>

---

<div align="center">

| | |
| :--- | :--- |
| **Team** | Qubits Infernova |
| **Team ID** | VTU-QFF-HC-0094 |
| **Tier** | Both |
| **Repository** | [vtu-hc-qubits-infernova](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-qubits-infernova.git) |
| **Organisation** | [vtu-qiskit-fall-fest-2026](https://github.com/vtu-qiskit-fall-fest-2026) |
| **Event** | VTU-QFF Hackathon — VTU-Qiskit Fall Fest 2026 |

</div>

---

## 📌 Table of Contents

- [Team Members](#-team-members-github-ids)
- [Problem Statement](#-problem-statement)
- [Proposed Solution](#-proposed-solution)
- [Approach & Architecture](#-approach--architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [How to Run](#-how-to-run)
- [How to Push Code](#-how-to-push-code)
- [Submission Checklist](#-submission-checklist)
- [Resources](#-resources)
- [License](#-license)

---

## 👥 Team Members (GitHub IDs)

| # | Name | GitHub Username | Role |
|---|------|-----------------|------|
| 1 | Harshavardhaan S | sharshavardhaan05-rgb | Team Lead  |
| 2 | Garima Mishra V | garimamishrav2007-cmd | Developer (Quantum core)|
| 3 | Ameerkhan S | ameerkhan2732-cpu | Developer (App and UI) |

## ❓ Problem Statement

**Problem:** Adversaries are recording encrypted defence, government and journalist communications today to decrypt them once quantum computers mature ("harvest now, decrypt later"). Quantum key distribution (QKD) can expose eavesdropping, but real channels such as fibre, satellite and field links are noisy, so operators cannot tell a degraded link from an active attack.

**Why it matters:** Sensitive messages often need to stay secret for decades, and a message cracked later cannot be protected again. Without a way to separate noise from interception, QKD links are either blindly trusted or wrongly abandoned. A clear, automatic verdict on link safety also lets teams judge a channel before investing in QKD hardware, and gives defence and security teams a hands-on way to see how noise and attacks affect key security.

**Track / Category:** Track 1: Quantum Cryptography & Security · Mode: Online / Offline (update after shortlisting)

## 💡 Proposed Solution

**Solution:** QuantaGuard Chat is a Qiskit-based secure chat that generates encryption keys with the BB84 quantum protocol, simulates real-world noise with Aer and IBM fake backends, and uses a Channel Trust Meter to classify the link as safe, noisy but usable, or compromised. Noise automatically shortens the key, and a detected eavesdropper discards the key and blocks messaging.

**Key idea:** A quantum-key secure chat that tells channel noise apart from eavesdropping and automatically shortens the key or blocks messaging to stay safe on noisy real-world links.

**Why this works:**
1. Keys come from BB84, whose security rests on quantum physics rather than on encryption math that future computers may break.
2. Alice and Bob sift on matching bases and sample part of the key to measure the quantum bit error rate (QBER). An intercept-resend attack drives QBER to about 25%, well above the ~11% BB84 safety limit.
3. Aer noise models and IBM fake-backend profiles show how ordinary noise differs from an attack in the measured results, and a batch is validated on real IBM hardware.
4. The Channel Trust Meter compares observed QBER with the QBER expected from the known noise profile and returns a clear verdict.
5. In the usable range, error correction and privacy amplification shorten the key to a secure length. Above the threshold, the key is discarded and messaging is blocked.
6. The final key encrypts messages in a working Streamlit chat, so the full path from quantum key exchange to protected communication can be shown live.

## 🧩 Approach & Architecture

1. **Input:** Random bits and random measurement bases (Z or X) generated for Alice and Bob; a noise level and an optional eavesdropper setting chosen in the app.
2. **Preprocessing:** Bits are encoded into qubits (X for bit 1, H for the X basis); many rounds are packed into multi-qubit circuits with fresh randomness for every batch.
3. **Quantum core:** BB84 circuits built in Qiskit and run on Aer with depolarizing and readout noise, on IBM fake backends, and on a real IBM backend for validation. An intercept-resend attacker (Eve) can be inserted into the channel.
4. **Post-processing:** Sifting on matching bases, QBER estimation from a sampled subset, Trust Meter classification, then error correction and privacy amplification to produce the final secure key.
5. **Output:** A derived AES key that encrypts chat messages (AES-GCM), plus a live dashboard showing QBER, the Trust Meter verdict, key length, and whether the chat is open or blocked.

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Quantum SDK | Qiskit >=1.0, Qiskit Aer, Qiskit Runtime |
| Simulation | AerSimulator with noise models, IBM fake backends |
| Hardware | IBM Quantum backend via Qiskit Runtime (SamplerV2) |
| Key processing | NumPy, error correction, privacy amplification |
| Security layer | cryptography library (HKDF, AES-GCM) |
| App and charts | Streamlit, matplotlib, pandas |
| Environment | VS Code, venv |
| Version control | Git + GitHub |

## 📁 Project Structure

```
vtu-hc-qubits-infernova/
├── README.md
├── requirements.txt
├── .gitignore
├── notebooks/             # Experiments and result charts
│   └── exploration.ipynb
├── src/
│   ├── __init__.py
│   ├── bb84.py            # BB84 circuits, sifting, QBER
│   ├── noise.py           # Aer noise models and fake backends
│   ├── eve.py             # Intercept-resend attack
│   ├── postprocess.py     # Error correction, privacy amplification
│   ├── trust_meter.py     # Safe / noisy / compromised classifier
│   ├── chat.py            # Key-derived message encryption
│   └── app.py             # Streamlit entry point
├── results/               # Saved hardware counts and charts
├── tests/                 # Unit tests
│   └── test_bb84.py
└── docs/                  # Notes, diagrams, reports
```

## 🚀 How to Run (step 4)

```
streamlit run src/app.py
```
