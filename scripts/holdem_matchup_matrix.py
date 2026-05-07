from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leduc_cfr.holdem_eval import BUILTIN_BOTS, evaluate_match


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a matrix of Hold'em bot matchups.")
    parser.add_argument("--bots", default="check_call,random,heuristic")
    parser.add_argument("--hands", type=int, default=500)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--duplicate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-dir", type=Path, default=Path("data/holdem"))
    args = parser.parse_args()

    names = [name.strip() for name in args.bots.split(",") if name.strip()]
    missing = [name for name in names if name not in BUILTIN_BOTS]
    if missing:
        raise SystemExit(f"Unknown bots {missing}. Available: {', '.join(sorted(BUILTIN_BOTS))}")

    matrix = {}
    for row_index, bot_a_name in enumerate(names):
        matrix[bot_a_name] = {}
        for col_index, bot_b_name in enumerate(names):
            result = evaluate_match(
                BUILTIN_BOTS[bot_a_name],
                BUILTIN_BOTS[bot_b_name],
                hands=args.hands,
                seed=args.seed + row_index * 10_000 + col_index * 101,
                duplicate=args.duplicate,
                store_histories=False,
            )
            matrix[bot_a_name][bot_b_name] = result.metrics.to_dict()

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "hands_per_matchup": args.hands,
        "duplicate": args.duplicate,
        "seed": args.seed,
        "bots": names,
        "matrix": matrix,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "holdem_matchup_matrix.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"matrix": str(out)}, indent=2))


if __name__ == "__main__":
    main()
