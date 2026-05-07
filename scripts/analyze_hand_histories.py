from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def analyze(histories: list[dict]) -> dict:
    street_actions: dict[str, Counter] = defaultdict(Counter)
    bot_actions: dict[str, Counter] = defaultdict(Counter)
    terminal = Counter()
    largest_pots = []
    for history in histories:
        terminal["showdown" if history.get("showdown_hands") else "non_showdown"] += 1
        terminal_result = history["terminal_result"]
        largest_pots.append(
            {
                "hand_index": history["hand_index"],
                "seed": history["seed"],
                "pot": terminal_result["pot"],
                "winner": history["winner"],
                "utilities": terminal_result["utilities"],
            }
        )
        for decision in history["bot_decisions"]:
            street_actions[decision["street"]][decision["action"]] += 1
            bot_actions[decision["bot"]][decision["action"]] += 1
    largest_pots.sort(key=lambda item: item["pot"], reverse=True)
    return {
        "hands": len(histories),
        "terminal_counts": dict(terminal),
        "street_actions": {street: dict(counter) for street, counter in street_actions.items()},
        "bot_actions": {bot: dict(counter) for bot, counter in bot_actions.items()},
        "largest_pots": largest_pots[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Hold'em JSON hand histories.")
    parser.add_argument("--histories", type=Path, default=Path("data/holdem/holdem_hand_histories.json"))
    parser.add_argument("--out", type=Path, default=Path("data/holdem/holdem_history_analysis.json"))
    args = parser.parse_args()

    histories = json.loads(args.histories.read_text())
    payload = analyze(histories)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
