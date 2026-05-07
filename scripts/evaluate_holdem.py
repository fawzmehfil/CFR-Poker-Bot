from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leduc_cfr.holdem_eval import BUILTIN_BOTS, BotSpec, MatchResult, evaluate_match


def resolve_bot(name: str) -> BotSpec:
    try:
        return BUILTIN_BOTS[name]
    except KeyError as exc:
        raise SystemExit(f"Unknown bot '{name}'. Available: {', '.join(sorted(BUILTIN_BOTS))}") from exc


def write_summary(result: MatchResult, path: Path, plot_status: str) -> None:
    metrics = result.metrics
    lines = [
        "# Texas Hold'em Evaluation Summary",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        f"Matchup: `{result.bot_a}` vs `{result.bot_b}`",
        f"Requested base hands: {result.hands_requested}",
        f"Actual evaluated hands: {metrics.total_hands}",
        f"Duplicate mode: {result.duplicate}",
        f"Seed: {result.seed}",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total chips | {metrics.total_chips} |",
        f"| EV/hand | {metrics.ev_per_hand:.4f} |",
        f"| bb/100 | {metrics.bb_per_100:.2f} |",
        f"| Win rate | {metrics.win_rate:.4f} |",
        f"| Fold frequency | {metrics.fold_frequency:.4f} |",
        f"| Call frequency | {metrics.call_frequency:.4f} |",
        f"| Raise frequency | {metrics.raise_frequency:.4f} |",
        f"| Aggression frequency | {metrics.aggression_frequency:.4f} |",
        f"| Showdown win rate | {metrics.showdown_win_rate:.4f} |",
        f"| Non-showdown winnings | {metrics.non_showdown_winnings} |",
        f"| Standard error | {metrics.standard_error:.4f} |",
        f"| Variance | {metrics.variance:.4f} |",
        f"| 95% CI EV/hand | [{metrics.confidence_interval[0]:.4f}, {metrics.confidence_interval[1]:.4f}] |",
        "",
        "Interpretation: bb/100 normalizes chip winnings to big blinds per 100 hands. The confidence interval",
        "is the uncertainty range around EV/hand; small samples can look decisive while still having wide intervals.",
        "",
        f"Plot: {plot_status}",
        "",
    ]
    path.write_text("\n".join(lines))


def write_plot(result: MatchResult, path: Path) -> str:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        return f"skipped ({exc})"

    metrics = result.metrics
    width, height = 760, 420
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((32, 24), f"Hold'em Eval: {result.bot_a} vs {result.bot_b}", fill="#172033", font=font)
    bars = [
        ("EV/hand", metrics.ev_per_hand),
        ("bb/100", metrics.bb_per_100),
        ("Win %", metrics.win_rate * 100),
        ("Agg %", metrics.aggression_frequency * 100),
    ]
    max_abs = max(1.0, max(abs(value) for _, value in bars))
    axis_y = 210
    draw.line((52, axis_y, width - 52, axis_y), fill="#94a3b8")
    slot = (width - 104) / len(bars)
    for index, (label, value) in enumerate(bars):
        cx = int(52 + slot * index + slot / 2)
        bar_h = int((value / max_abs) * 130)
        y0, y1 = sorted((axis_y, axis_y - bar_h))
        color = "#16a34a" if value >= 0 else "#dc2626"
        draw.rectangle((cx - 42, y0, cx + 42, y1), fill=color)
        draw.text((cx - 42, 345), label, fill="#172033", font=font)
        draw.text((cx - 36, min(y0, y1) - 18), f"{value:.2f}", fill="#172033", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate heads-up Texas Hold'em bots.")
    parser.add_argument("--bot-a", default="heuristic", choices=sorted(BUILTIN_BOTS))
    parser.add_argument("--bot-b", default="random", choices=sorted(BUILTIN_BOTS))
    parser.add_argument("--hands", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--duplicate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-dir", type=Path, default=Path("data/holdem"))
    args = parser.parse_args()

    result = evaluate_match(
        resolve_bot(args.bot_a),
        resolve_bot(args.bot_b),
        hands=args.hands,
        seed=args.seed,
        duplicate=args.duplicate,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    eval_path = args.out_dir / "holdem_eval.json"
    histories_path = args.out_dir / "holdem_hand_histories.json"
    summary_path = args.out_dir / "holdem_eval_summary.md"
    plot_path = args.out_dir / "holdem_eval.png"

    payload = {"generated_at": datetime.now(UTC).isoformat(), **result.to_dict()}
    eval_path.write_text(json.dumps(payload, indent=2) + "\n")
    histories_path.write_text(json.dumps(result.hand_histories, indent=2) + "\n")
    plot_status = write_plot(result, plot_path)
    write_summary(result, summary_path, plot_status)

    print(json.dumps({"eval": str(eval_path), "histories": str(histories_path), "summary": str(summary_path), "plot": plot_status}, indent=2))


if __name__ == "__main__":
    main()
