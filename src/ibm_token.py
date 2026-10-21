"""Read the IBM Quantum token from the environment. Never hardcode it."""
import os

from dotenv import load_dotenv


def get_ibm_token() -> str:
    load_dotenv()  # reads a local .env file if present (git-ignored)
    token = os.environ.get("IBM_QUANTUM_TOKEN", "").strip()
    if not token or token == "your-token-here":
        raise RuntimeError(
            "IBM_QUANTUM_TOKEN is not set. Copy .env.example to .env and paste your token."
        )
    return token
