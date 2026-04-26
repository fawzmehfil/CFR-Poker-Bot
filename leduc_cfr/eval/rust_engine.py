from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path
from typing import Literal

from leduc_cfr.poker.leduc import LeducState, random_deal

EngineMode = Literal["auto", "python", "rust"]

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "engine"
BENCHMARK_PATH = ROOT / "data" / "rust_benchmark.json"
SUMMARY_PATH = ROOT / "data" / "performance_summary.md"


def _python_trace() -> str:
    def legal_text(state: LeducState) -> str:
        return ",".join(state.legal_actions())

    folded = LeducState(deal=("K1", "Q1", "J1")).apply("b").apply("f")
    showdown = LeducState(deal=("K1", "Q1", "J1")).apply("k").apply("k").apply("k").apply("k")
    return (
        f"fold:round={folded.round_index};current={folded.current_player};"
        f"terminal={str(folded.terminal).lower()};pot={folded.pot};"
        f"u0={folded.utility(0):.1f};legal={legal_text(folded)}|"
        f"showdown:round={showdown.round_index};current={showdown.current_player};"
        f"terminal={str(showdown.terminal).lower()};pot={showdown.pot};"
        f"u0={showdown.utility(0):.1f};legal={legal_text(showdown)}"
    )


def python_benchmark(hands: int = 50_000, seed: int = 7) -> dict:
    rng = random.Random(seed)
    utility = 0.0
    start = time.perf_counter()
    for _ in range(hands):
        state = LeducState(deal=random_deal(rng))
        while not state.terminal:
            state = state.apply(rng.choice(state.legal_actions()))
        utility += state.utility(0)
    elapsed = time.perf_counter() - start
    return {
        "python_hands": hands,
        "python_hands_per_sec": hands / elapsed if elapsed > 0 else 0.0,
        "python_avg_utility_p0": utility / hands if hands else 0.0,
        "python_trace": _python_trace(),
    }


def _load_existing_benchmark() -> dict:
    if BENCHMARK_PATH.exists():
        return json.loads(BENCHMARK_PATH.read_text())
    return {}


def _write_benchmark(data: dict) -> None:
    BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCHMARK_PATH.write_text(json.dumps(data, indent=2))
    SUMMARY_PATH.write_text(
        "\n".join(
            [
                "# Performance Summary",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Engine used for evaluation | {data.get('engine_used_for_evaluation', 'unknown')} |",
                f"| Rust random hands/sec | {data.get('rust_hands_per_sec', 0.0):.2f} |",
                f"| Rust terminal rollouts/sec | {data.get('terminal_rollouts_per_sec', 0.0):.2f} |",
                f"| Rust state transitions/sec | {data.get('state_transitions_per_sec', 0.0):.2f} |",
                f"| Python hands/sec | {data.get('python_hands_per_sec', 0.0):.2f} |",
                f"| Speedup factor | {data.get('speedup_factor', 0.0):.2f}x |",
                f"| Correctness comparison | {'passed' if data.get('correctness_comparison_passed') else 'failed'} |",
                "",
            ]
        )
    )


def simulate_random_hands(n: int, seed: int = 7) -> dict:
    return run_rust_benchmark(n=n, seed=seed)


def benchmark_hands_per_sec(n: int, seed: int = 7) -> float:
    return float(run_rust_benchmark(n=n, seed=seed)["rust_hands_per_sec"])


def compare_trace(seed: int = 7) -> bool:
    del seed
    benchmark = run_rust_benchmark(n=10_000, seed=7)
    return bool(benchmark.get("correctness_comparison_passed"))


def run_rust_benchmark(n: int = 1_000_000, seed: int = 7) -> dict:
    if not ENGINE_DIR.exists():
        raise RuntimeError("Rust engine directory is missing")
    subprocess.run(
        ["cargo", "run", "--release", "--bin", "bench", "--", str(n), str(seed)],
        cwd=ENGINE_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    if not BENCHMARK_PATH.exists():
        raise RuntimeError("Rust benchmark did not write data/rust_benchmark.json")
    return json.loads(BENCHMARK_PATH.read_text())


def resolve_evaluation_engine(mode: EngineMode, hands: int = 1_000_000, seed: int = 7) -> dict:
    if mode in ("auto", "rust"):
        try:
            data = run_rust_benchmark(n=hands, seed=seed)
            data["engine_requested"] = mode
            data["engine_used_for_evaluation"] = "rust"
            _write_benchmark(data)
            return data
        except Exception as exc:
            if mode == "rust":
                fallback_reason = f"Rust unavailable; fell back to Python: {exc}"
            else:
                fallback_reason = f"Rust unavailable in auto mode; used Python: {exc}"
        data = _load_existing_benchmark()
        data.update(python_benchmark(seed=seed))
        data["engine_requested"] = mode
        data["engine_used_for_evaluation"] = "python"
        data["fallback_reason"] = fallback_reason
        data["correctness_comparison_passed"] = data.get("correctness_comparison_passed", False)
        if data.get("rust_hands_per_sec") and data.get("python_hands_per_sec"):
            data["speedup_factor"] = data["rust_hands_per_sec"] / data["python_hands_per_sec"]
        _write_benchmark(data)
        return data

    data = _load_existing_benchmark()
    data.update(python_benchmark(seed=seed))
    data["engine_requested"] = mode
    data["engine_used_for_evaluation"] = "python"
    data["correctness_comparison_passed"] = data.get("correctness_comparison_passed", False)
    if data.get("rust_hands_per_sec") and data.get("python_hands_per_sec"):
        data["speedup_factor"] = data["rust_hands_per_sec"] / data["python_hands_per_sec"]
    _write_benchmark(data)
    return data
