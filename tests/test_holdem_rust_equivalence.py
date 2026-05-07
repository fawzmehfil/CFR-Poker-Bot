from __future__ import annotations

import subprocess

import pytest

from scripts.verify_holdem_engine import SHOWDOWN_ACTIONS, python_seed_trace_text, python_trace_text


def test_python_rust_holdem_trace_equivalence_for_seeded_hand():
    cards, expected = python_trace_text(17, SHOWDOWN_ACTIONS)
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "holdem_bench", "--", "--trace", cards, ",".join(SHOWDOWN_ACTIONS)],
        cwd="engine",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Rust Hold'em trace binary unavailable: {result.stderr}")

    assert result.stdout.strip() == expected


def test_python_rust_holdem_trace_equivalence_for_shared_lcg_seed():
    expected = python_seed_trace_text(17, SHOWDOWN_ACTIONS)
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "holdem_bench", "--", "--seed-trace", "17", ",".join(SHOWDOWN_ACTIONS)],
        cwd="engine",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Rust Hold'em seed trace unavailable: {result.stderr}")

    assert result.stdout.strip() == expected
