from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leduc_cfr.holdem.engine import fresh_holdem_state, heuristic_action


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate deterministic heads-up Texas Hold'em hands.")
    parser.add_argument("--hands", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--policy", choices=["random", "heuristic"], default="heuristic")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    summaries = []
    utility_sum = 0
    for hand_index in range(args.hands):
        state = fresh_holdem_state(rng=rng)
        while not state.terminal:
            legal = state.legal_actions()
            if args.policy == "random":
                action = rng.choice(legal)
            else:
                action = heuristic_action(state, state.current_player, rng)
            state = state.apply(action)
        utility_sum += state.utility(0)
        summaries.append(
            {
                "hand": hand_index,
                "hero_cards": [str(card) for card in state.hole_cards[0]],
                "villain_cards": [str(card) for card in state.hole_cards[1]],
                "board": [str(card) for card in state.board],
                "history": list(state.history),
                "winner": state.showdown_winner() if state.folded_player is None else 1 - state.folded_player,
                "utility_p0": state.utility(0),
                "final_stacks": list(state.final_stacks()),
            }
        )

    print(
        json.dumps(
            {
                "hands": args.hands,
                "seed": args.seed,
                "policy": args.policy,
                "avg_utility_p0": utility_sum / args.hands if args.hands else 0,
                "hands_detail": summaries,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
