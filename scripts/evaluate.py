from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leduc_cfr.cfr.trainer import StrategyProfile
from leduc_cfr.eval.metrics import (
    expected_game_value,
    full_information_best_response_values,
    head_to_head,
    heuristic_policy,
    nash_gap_upper_bound,
    random_policy,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="data/cfr_strategy.json")
    parser.add_argument("--out", default="data/eval.json")
    parser.add_argument("--plot", default="data/eval.png")
    parser.add_argument("--hands", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    profile = StrategyProfile.load(args.strategy)
    p0_br, p1_br = full_information_best_response_values(profile)
    cfr_vs_random = head_to_head(profile, random_policy, hands=args.hands, seed=args.seed)
    cfr_vs_heuristic = head_to_head(profile, heuristic_policy, hands=args.hands, seed=args.seed + 1)
    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
        "expected_game_value_p0": expected_game_value(profile),
        "full_information_best_response_p0": p0_br,
        "full_information_best_response_p1": p1_br,
        "nash_gap_upper_bound": nash_gap_upper_bound(profile),
        "infosets": len(profile.strategies),
        "hands_played": args.hands,
        "cfr_vs_random": cfr_vs_random,
        "cfr_vs_heuristic": cfr_vs_heuristic,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))

    if args.plot:
        from PIL import Image, ImageDraw, ImageFont

        names = ["EV P0", "vs Random", "vs Heuristic", "Gap UB"]
        values = [
            metrics["expected_game_value_p0"],
            cfr_vs_random["avg_utility"],
            cfr_vs_heuristic["avg_utility"],
            metrics["nash_gap_upper_bound"],
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
