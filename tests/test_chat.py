"""Tests for src/chat.py: end-to-end BB84 chat runs with a fixed seed."""
from src.chat import main


def test_clean_channel_delivers_the_message(capsys):
    assert main(["--message", "HELLO BOB", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "trust: SAFE" in out
    assert "Bob decrypts: HELLO BOB" in out


def test_eve_is_detected_and_no_message_is_sent(capsys):
    assert main(["--message", "HELLO BOB", "--seed", "1", "--eve"]) == 1
    out = capsys.readouterr().out
    assert "COMPROMISED" in out
    assert "Alice sends" not in out


def test_noisy_channel_is_corrected_and_decrypts(capsys):
    assert main(["--message", "HELLO BOB", "--seed", "1", "--noise", "0.05"]) == 0
    out = capsys.readouterr().out
    assert "trust: NOISY" in out
    assert "keys now equal = True" in out
    assert "Bob decrypts: HELLO BOB" in out


def test_message_longer_than_the_key_is_refused(capsys):
    assert main(["--message", "A" * 200, "--seed", "1", "--n", "256"]) == 2
    assert "key bits" in capsys.readouterr().out
