from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leduc_cfr.holdem.engine import evaluate_hand, fresh_holdem_state


def python_benchmark(hands: int, seed: int) -> dict:
    rng = random.Random(seed)
    utility_sum = 0
    transition_count = 0
    start = time.perf_counter()
    for _ in range(hands):
        state = fresh_holdem_state(rng=rng)
        while not state.terminal:
            state = state.apply(rng.choice(state.legal_actions()))
            transition_count += 1
        utility_sum += state.utility(0)
    hand_elapsed = time.perf_counter() - start

    evals = hands * 20
    start = time.perf_counter()
    for _ in range(evals):
        state = fresh_holdem_state(rng=rng)
        evaluate_hand(list(state.hole_cards[0] + tuple(state.deck_cards[:5])))
    eval_elapsed = time.perf_counter() - start

    return {
        "hands": hands,
        "random_hands_per_sec": hands / hand_elapsed,
        "state_transitions_per_sec": transition_count / hand_elapsed,
        "showdown_evaluations_per_sec": evals / eval_elapsed,
        "avg_utility_p0": utility_sum / hands if hands else 0,
        "avg_transitions_per_hand": transition_count / hands if hands else 0,
    }


def rust_benchmark(hands: int, seed: int) -> dict | None:
    result = subprocess.run(
        ["cargo", "run", "--release", "--quiet", "--bin", "holdem_bench", "--", str(hands), str(seed)],
        cwd="engine",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {"available": False, "stderr": result.stderr.strip()}
    return {"available": True, **json.loads(result.stdout)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the Python and Rust Hold'em engines.")
    parser.add_argument("--hands", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip-rust", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("data/holdem_benchmark.json"))
    args = parser.parse_args()

    payload = {
        "seed": args.seed,
        "python": python_benchmark(args.hands, args.seed),
        "rust": None if args.skip_rust else rust_benchmark(max(args.hands, 10_000), args.seed),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
