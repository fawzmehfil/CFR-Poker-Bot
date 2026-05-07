from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leduc_cfr.holdem.engine import Card, deck, evaluate_hand, fresh_holdem_state

SHOWDOWN_ACTIONS = ["call", "check", "check", "check", "check", "check", "check", "check"]


def python_trace_text(seed: int, actions: list[str]) -> tuple[str, str]:
    state = fresh_holdem_state(seed=seed)
    cards = list(state.hole_cards[0][:1] + state.hole_cards[1][:1] + state.hole_cards[0][1:] + state.hole_cards[1][1:])
    cards.extend(state.deck_cards[:5])
    for action in actions:
        state = state.apply(action)  # type: ignore[arg-type]
    trace = (
        f"street={state.street};current={state.current_player};board={' '.join(str(card) for card in state.board)};"
        f"stacks={list(state.stacks)};contributions={list(state.contributions)};"
        f"terminal={str(state.terminal).lower()};history={','.join(state.history)};"
        f"legal={','.join(state.legal_actions())};u0={state.utility(0) if state.terminal else 0}"
    )
    return ",".join(str(card) for card in cards), trace


def _trace_text_from_state(state, actions: list[str]) -> str:
    for action in actions:
        state = state.apply(action)  # type: ignore[arg-type]
    return (
        f"street={state.street};current={state.current_player};board={' '.join(str(card) for card in state.board)};"
        f"stacks={list(state.stacks)};contributions={list(state.contributions)};"
        f"terminal={str(state.terminal).lower()};history={','.join(state.history)};"
        f"legal={','.join(state.legal_actions())};u0={state.utility(0) if state.terminal else 0}"
    )


def python_seed_trace_text(seed: int, actions: list[str]) -> str:
    return _trace_text_from_state(fresh_holdem_state(seed=seed, shuffle_algorithm="lcg"), actions)


def run_command(command: list[str], cwd: str | None = None) -> dict:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "command": " ".join(command),
        "cwd": cwd or ".",
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def verify_trace(seed: int) -> dict:
    cards, expected = python_trace_text(seed, SHOWDOWN_ACTIONS)
    result = run_command(
        ["cargo", "run", "--quiet", "--bin", "holdem_bench", "--", "--trace", cards, ",".join(SHOWDOWN_ACTIONS)],
        cwd="engine",
    )
    actual = result["stdout"]
    return {
        "seed": seed,
        "cards": cards,
        "actions": SHOWDOWN_ACTIONS,
        "passed": result["returncode"] == 0 and actual == expected,
        "python_trace": expected,
        "rust_trace": actual,
        "rust_command": result,
    }


def verify_seed_trace(seed: int) -> dict:
    expected = python_seed_trace_text(seed, SHOWDOWN_ACTIONS)
    result = run_command(
        ["cargo", "run", "--quiet", "--bin", "holdem_bench", "--", "--seed-trace", str(seed), ",".join(SHOWDOWN_ACTIONS)],
        cwd="engine",
    )
    actual = result["stdout"]
    return {
        "seed": seed,
        "actions": SHOWDOWN_ACTIONS,
        "passed": result["returncode"] == 0 and actual == expected,
        "python_trace": expected,
        "rust_trace": actual,
        "rust_command": result,
    }


def verify_static_invariants() -> dict:
    cards = deck()
    wheel = evaluate_hand([Card.parse(value) for value in ["As", "2d", "3h", "4c", "5s"]])
    royal = evaluate_hand([Card.parse(value) for value in ["As", "Ks", "Qs", "Js", "Ts", "2c", "3d"]])
    return {
        "deck_52_unique": len(cards) == 52 and len({str(card) for card in cards}) == 52,
        "wheel_straight_score": wheel,
        "royal_flush_score": royal,
        "evaluator_order_sample": royal > wheel,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hold'em engine correctness checks.")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-cargo", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("data/holdem_verify.json"))
    args = parser.parse_args()

    checks: dict = {
        "static": verify_static_invariants(),
        "trace_equivalence": verify_trace(args.seed),
        "seed_trace_equivalence": verify_seed_trace(args.seed),
    }
    if not args.skip_tests:
        checks["pytest"] = run_command([sys.executable, "-m", "pytest", "tests/test_holdem.py", "tests/test_holdem_rust_equivalence.py", "-q"])
    if not args.skip_cargo:
        checks["cargo_test"] = run_command(["cargo", "test"], cwd="engine")

    passed = (
        checks["static"]["deck_52_unique"]
        and checks["static"]["evaluator_order_sample"]
        and checks["trace_equivalence"]["passed"]
        and checks["seed_trace_equivalence"]["passed"]
    )
    if "pytest" in checks:
        passed = passed and checks["pytest"]["returncode"] == 0
    if "cargo_test" in checks:
        passed = passed and checks["cargo_test"]["returncode"] == 0
    checks["passed"] = passed

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))
    print(f"wrote {args.out}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
