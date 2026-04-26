from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leduc_cfr.cfr.trainer import StrategyProfile
from leduc_cfr.eval.metrics import (
    expected_game_value,
    full_information_best_response_values,
    head_to_head,
    heuristic_policy,
    nash_gap_upper_bound,
    policy_head_to_head,
    random_policy,
    strategy_profile_policy,
)
from leduc_cfr.neural.policy import NeuralPolicy


def summarize_seeded_matchups(profile: StrategyProfile, policy, hands: int, seed: int, seeds: int) -> dict:
    runs = [head_to_head(profile, policy, hands=hands, seed=seed + offset) for offset in range(seeds)]
    win_rates = [run["win_rate"] for run in runs]
    avg_utilities = [run["avg_utility"] for run in runs]

    def ci95(values: list[float]) -> list[float]:
        if len(values) < 2:
            return [values[0], values[0]]
        mean = statistics.mean(values)
        half_width = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
        return [mean - half_width, mean + half_width]

    return {
        "hands_per_seed": hands,
        "seeds": seeds,
        "hands_total": hands * seeds,
        "win_rate": statistics.mean(win_rates),
        "win_rate_ci95": ci95(win_rates),
        "avg_utility": statistics.mean(avg_utilities),
        "avg_utility_ci95": ci95(avg_utilities),
        "runs": runs,
    }


def summarize_policy_matchups(agent_policy, opponent_policy, hands: int, seed: int, seeds: int) -> dict:
    runs = [policy_head_to_head(agent_policy, opponent_policy, hands=hands, seed=seed + offset) for offset in range(seeds)]
    win_rates = [run["win_rate"] for run in runs]
    avg_utilities = [run["avg_utility"] for run in runs]

    def ci95(values: list[float]) -> list[float]:
        if len(values) < 2:
            return [values[0], values[0]]
        mean = statistics.mean(values)
        half_width = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
        return [mean - half_width, mean + half_width]

    return {
        "hands_per_seed": hands,
        "seeds": seeds,
        "hands_total": hands * seeds,
        "win_rate": statistics.mean(win_rates),
        "win_rate_ci95": ci95(win_rates),
        "avg_utility": statistics.mean(avg_utilities),
        "avg_utility_ci95": ci95(avg_utilities),
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="data/cfr_strategy.json")
    parser.add_argument("--out", default="data/eval.json")
    parser.add_argument("--plot", default="data/eval.png")
    parser.add_argument("--hands", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--policy", default="data/policy.pt")
    args = parser.parse_args()

    profile = StrategyProfile.load(args.strategy)
    cfr_policy = strategy_profile_policy(profile)
    p0_br, p1_br = full_information_best_response_values(profile)
    cfr_vs_random = summarize_seeded_matchups(profile, random_policy, args.hands, args.seed, args.seeds)
    cfr_vs_heuristic = summarize_seeded_matchups(profile, heuristic_policy, args.hands, args.seed + args.seeds, args.seeds)
    neural_metrics = None
    if Path(args.policy).exists():
        neural = NeuralPolicy.load(args.policy)

        def neural_policy(state, player, rng):
            return neural.sample_action(state, player, rng)

        neural_metrics = {
            "policy_path": args.policy,
            "neural_vs_random": summarize_policy_matchups(
                neural_policy, random_policy, args.hands, args.seed + 2 * args.seeds, args.seeds
            ),
            "neural_vs_heuristic": summarize_policy_matchups(
                neural_policy, heuristic_policy, args.hands, args.seed + 3 * args.seeds, args.seeds
            ),
            "neural_vs_cfr": summarize_policy_matchups(
                neural_policy, cfr_policy, args.hands, args.seed + 4 * args.seeds, args.seeds
            ),
        }
    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
        "metric_labels": {
            "expected_game_value_p0": "Exact expected value for player 0 when both seats use the saved average strategy.",
            "nash_gap_upper_bound": "Full-information best-response diagnostic; upper-bound proxy, not exact exploitability.",
            "head_to_head": "Monte Carlo simulation over seeded deals/actions with confidence intervals across seeds.",
        },
        "expected_game_value_p0": expected_game_value(profile),
        "full_information_best_response_p0": p0_br,
        "full_information_best_response_p1": p1_br,
        "nash_gap_upper_bound": nash_gap_upper_bound(profile),
        "infosets": len(profile.strategies),
        "hands_played": args.hands * args.seeds,
        "cfr_vs_random": cfr_vs_random,
        "cfr_vs_heuristic": cfr_vs_heuristic,
    }
    if neural_metrics:
        metrics["neural"] = neural_metrics
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))

    if args.plot:
        from PIL import Image, ImageDraw, ImageFont

        names = ["EV P0", "CFR Random", "CFR Heur", "Gap UB"]
        values = [metrics["expected_game_value_p0"], cfr_vs_random["avg_utility"], cfr_vs_heuristic["avg_utility"], metrics["nash_gap_upper_bound"]]
        if neural_metrics is not None:
            names = ["CFR Random", "CFR Heur", "NN Random", "NN Heur"]
            values = [
                cfr_vs_random["avg_utility"],
                cfr_vs_heuristic["avg_utility"],
                neural_metrics["neural_vs_random"]["avg_utility"],
                neural_metrics["neural_vs_heuristic"]["avg_utility"],
            ]
        width, height = 760, 420
        margin = 62
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.text((margin, 22), f"Leduc CFR Evaluation ({args.hands} simulated hands)", fill="#172033", font=font)

        zero_y = height - margin
        max_abs = max(1.0, max(abs(v) for v in values))
        scale = (height - 2 * margin - 42) / (2 * max_abs)
        axis_y = int(zero_y - max_abs * scale)
        draw.line((margin, axis_y, width - margin, axis_y), fill="#94a3b8", width=1)
        draw.line((margin, margin, margin, height - margin), fill="#94a3b8", width=1)
        draw.text((12, axis_y - 7), "0", fill="#475569", font=font)

        colors = ["#2563eb", "#16a34a", "#f97316", "#dc2626"]
        slot = (width - 2 * margin) / len(values)
        bar_w = 72
        for idx, (name, value) in enumerate(zip(names, values)):
            cx = int(margin + slot * idx + slot / 2)
            y = int(axis_y - value * scale)
            top, bottom = sorted((axis_y, y))
            draw.rectangle((cx - bar_w // 2, top, cx + bar_w // 2, bottom), fill=colors[idx])
            draw.text((cx - 28, height - margin + 16), name, fill="#172033", font=font)
            draw.text((cx - 30, top - 16), f"{value:.3f}", fill="#172033", font=font)

        Path(args.plot).parent.mkdir(parents=True, exist_ok=True)
        image.save(args.plot)
        print(f"saved plot to {args.plot}")


if __name__ == "__main__":
    main()
