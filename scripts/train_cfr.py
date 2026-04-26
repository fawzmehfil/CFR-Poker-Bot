from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leduc_cfr.cfr.trainer import CFRTrainer
from leduc_cfr.eval.metrics import expected_game_value, nash_gap_upper_bound


def plot_training_curves(points: list[dict], path: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    width, height = 900, 420
    margin = 64
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((margin, 24), "CFR Training Curves", fill="#172033", font=font)
    if len(points) < 2:
        image.save(path)
        return

    xs = [point["iteration"] for point in points]
    evs = [point["expected_game_value_p0"] for point in points]
    gaps = [point["nash_gap_upper_bound"] for point in points]
    values = evs + gaps
    min_y = min(values + [0.0])
    max_y = max(values + [0.0])
    if max_y == min_y:
        max_y += 1.0
        min_y -= 1.0

    left, right = margin, width - margin
    top, bottom = margin, height - margin

    def xy(iteration: int, value: float) -> tuple[int, int]:
        x = left + int((iteration - xs[0]) / max(1, xs[-1] - xs[0]) * (right - left))
        y = bottom - int((value - min_y) / (max_y - min_y) * (bottom - top))
        return x, y

    zero_y = xy(xs[0], 0.0)[1]
    draw.line((left, bottom, right, bottom), fill="#94a3b8")
    draw.line((left, top, left, bottom), fill="#94a3b8")
    draw.line((left, zero_y, right, zero_y), fill="#cbd5e1")

    for series, color in ((evs, "#2563eb"), (gaps, "#dc2626")):
        coords = [xy(iteration, value) for iteration, value in zip(xs, series)]
        draw.line(coords, fill=color, width=3)
        for x, y in coords:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color)

    draw.text((right - 190, top + 8), "EV P0", fill="#2563eb", font=font)
    draw.text((right - 190, top + 26), "Gap upper bound", fill="#dc2626", font=font)
    draw.text((left, bottom + 16), f"iter {xs[0]}", fill="#475569", font=font)
    draw.text((right - 70, bottom + 16), f"iter {xs[-1]}", fill="#475569", font=font)
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cfr-plus", action="store_true")
    parser.add_argument("--out", default="data/cfr_strategy.json")
    parser.add_argument("--metrics", default="data/cfr_metrics.json")
    parser.add_argument("--plot", default="data/training_curves.png")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--track-every", type=int, default=100)
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")
    trainer = CFRTrainer(cfr_plus=args.cfr_plus)
    utilities = []
    points = []
    start = time.perf_counter()
    for iteration in range(1, args.iterations + 1):
        utilities.extend(trainer.train(1))
        if iteration == 1 or iteration == args.iterations or iteration % args.track_every == 0:
            profile_at_checkpoint = trainer.profile()
            points.append(
                {
                    "iteration": iteration,
                    "expected_game_value_p0": expected_game_value(profile_at_checkpoint),
                    "nash_gap_upper_bound": nash_gap_upper_bound(profile_at_checkpoint),
                    "training_utility_p0": utilities[-1],
                    "runtime_sec": time.perf_counter() - start,
                }
            )
    profile = trainer.profile()
    profile.save(args.out)

    final_metrics = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "iterations": args.iterations,
        "cfr_plus": args.cfr_plus,
        "final_avg_utility_p0": utilities[-1] if utilities else 0.0,
        "infosets": len(profile.strategies),
        "runtime_sec": time.perf_counter() - start,
        "series": points,
    }
    Path(args.metrics).parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if Path(args.metrics).exists():
        existing = json.loads(Path(args.metrics).read_text())
    runs = existing.get("runs", {})
    runs[run_id] = final_metrics
    comparison = [
        {
            "run_id": key,
            "iterations": value["iterations"],
            "infosets": value["infosets"],
            "final_expected_game_value_p0": value["series"][-1]["expected_game_value_p0"],
            "final_nash_gap_upper_bound": value["series"][-1]["nash_gap_upper_bound"],
            "runtime_sec": value["runtime_sec"],
        }
        for key, value in sorted(runs.items())
    ]
    Path(args.metrics).write_text(json.dumps({"latest_run_id": run_id, "runs": runs, "comparison": comparison}, indent=2))
    if args.plot:
        plot_training_curves(points, args.plot)
    print(f"saved {len(profile.strategies)} infosets to {args.out}")
    print(f"saved training metrics to {args.metrics}")


if __name__ == "__main__":
    main()
