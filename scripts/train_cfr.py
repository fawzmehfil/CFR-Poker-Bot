from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import random
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leduc_cfr.cfr.trainer import CFRTrainer, StrategyProfile
from leduc_cfr.eval.metrics import expected_game_value, head_to_head, heuristic_policy, nash_gap_upper_bound, random_policy


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


def _parse_rust_training_output(stdout: str) -> dict[str, str]:
    parsed = {}
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def run_rust_cfr(args: argparse.Namespace, settings: dict) -> None:
    output_dir = Path(args.output_dir)
    out_path = args.out or str(output_dir / "cfr_strategy.json")
    metrics_path = args.metrics or str(output_dir / "cfr_metrics.json")
    plot_path = args.plot if args.plot is not None else str(output_dir / "training_curves.png")
    iterations = settings["iterations"]
    eval_interval = settings["eval_interval"]
    selection_hands = settings["selection_hands"]
    cfr_plus = args.cfr_plus or args.algo == "cfr-plus"
    run_id = args.run_id or datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")
    engine_dir = Path(__file__).resolve().parents[1] / "engine"

    command = [
        "cargo",
        "run",
        "--release",
        "--bin",
        "train_cfr",
        "--",
        "--iterations",
        str(iterations),
        "--seed",
        str(args.seed),
        "--out",
        str(Path(out_path).resolve()),
        "--eval-interval",
        str(eval_interval),
        "--selection",
        args.selection,
        "--selection-hands",
        str(selection_hands),
    ]
    if cfr_plus:
        command.append("--cfr-plus")

    start = time.perf_counter()
    result = subprocess.run(command, cwd=engine_dir, check=True, text=True, capture_output=True)
    print(result.stdout, end="")
    elapsed = time.perf_counter() - start
    rust_output = _parse_rust_training_output(result.stdout)

    profile = StrategyProfile.load(out_path)
    gap = nash_gap_upper_bound(profile)
    random_avg_utility = head_to_head(profile, random_policy, hands=selection_hands, seed=args.seed)["avg_utility"]
    heuristic_avg_utility = head_to_head(profile, heuristic_policy, hands=selection_hands, seed=args.seed + 5)[
        "avg_utility"
    ]
    ev = expected_game_value(profile)
    root_traversals = iterations * 120
    rust_tps = float(rust_output.get("root_traversals_per_sec", "0") or 0.0)
    selected_iteration = int(rust_output.get("selected_iteration", iterations))
    selected_gap = float(rust_output.get("selected_nash_gap_upper_bound", gap))
    selected_avg_utility = float(rust_output.get("selected_avg_utility_p0", "0") or 0.0)
    runtime_sec = float(rust_output.get("runtime_sec", elapsed))
    point = {
        "iteration": selected_iteration,
        "expected_game_value_p0": ev,
        "nash_gap_upper_bound": gap,
        "selection_heuristic_avg_utility": heuristic_avg_utility,
        "selection_random_avg_utility": random_avg_utility,
        "training_utility_p0": selected_avg_utility,
        "avg_utility_p0": selected_avg_utility,
        "runtime_sec": runtime_sec,
        "root_traversals": root_traversals,
        "root_traversals_per_sec": rust_tps,
        "infosets": len(profile.strategies),
        "selected_best": True,
    }

    final_metrics = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "preset": args.preset,
        "algorithm": "cfr-plus" if cfr_plus else "cfr",
        "engine_requested": args.engine,
        "engine_used": "rust",
        "iterations": iterations,
        "seed": args.seed,
        "eval_interval": eval_interval,
        "selection_mode": args.selection,
        "selection_weights": {
            "gap": args.w_gap,
            "random": args.w_random,
            "heuristic": args.w_heuristic,
        },
        "gap_tolerance": settings["gap_tolerance"],
        "selection_hands": selection_hands,
        "cfr_plus": cfr_plus,
        "final_avg_utility_p0": float(rust_output.get("final_avg_utility_p0", "0") or 0.0),
        "best_observed_nash_gap_upper_bound": selected_gap,
        "selected_iteration": selected_iteration,
        "selected_gap": gap,
        "selected_vs_random_avg_utility": random_avg_utility,
        "selected_vs_heuristic_avg_utility": heuristic_avg_utility,
        "selected_checkpoint_iteration": selected_iteration,
        "selected_checkpoint_nash_gap_upper_bound": gap,
        "selected_checkpoint_heuristic_avg_utility": heuristic_avg_utility,
        "selected_checkpoint_random_avg_utility": random_avg_utility,
        "selected_balanced_scores": None,
        "infosets": len(profile.strategies),
        "runtime_sec": runtime_sec,
        "root_traversals": root_traversals,
        "root_traversals_per_sec": rust_tps,
        "series": [point],
    }

    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if Path(metrics_path).exists():
        existing = json.loads(Path(metrics_path).read_text())
    runs = existing.get("runs", {})
    runs[run_id] = final_metrics
    comparison = [
        {
            "run_id": key,
            "algorithm": value.get("algorithm", "cfr-plus" if value.get("cfr_plus") else "cfr"),
            "iterations": value["iterations"],
            "infosets": value["infosets"],
            "final_expected_game_value_p0": value["series"][-1]["expected_game_value_p0"],
            "final_nash_gap_upper_bound": value["series"][-1]["nash_gap_upper_bound"],
            "runtime_sec": value["runtime_sec"],
            "root_traversals_per_sec": value.get("root_traversals_per_sec", 0.0),
        }
        for key, value in sorted(runs.items())
    ]
    Path(metrics_path).write_text(json.dumps({"latest_run_id": run_id, "runs": runs, "comparison": comparison}, indent=2))
    if plot_path:
        plot_training_curves([point], plot_path)
    print(f"saved {len(profile.strategies)} infosets to {out_path}")
    print(f"saved training metrics to {metrics_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=["quick", "default", "strong"], default="default")
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--algo", choices=["cfr", "cfr-plus"], default="cfr")
    parser.add_argument("--cfr-plus", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--out", default=None)
    parser.add_argument("--metrics", default=None)
    parser.add_argument("--plot", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--track-every", type=int, default=None)
    parser.add_argument("--eval-interval", type=int, default=None)
    parser.add_argument("--selection", choices=["best_gap", "best_heuristic", "balanced"], default="best_gap")
    parser.add_argument("--w-gap", type=float, default=0.45)
    parser.add_argument("--w-random", type=float, default=0.20)
    parser.add_argument("--w-heuristic", type=float, default=0.35)
    parser.add_argument("--gap-tolerance", type=float, default=None)
    parser.add_argument("--selection-hands", type=int, default=None)
    parser.add_argument("--engine", choices=["python", "rust", "auto"], default="auto")
    args = parser.parse_args()

    preset_defaults = {
        "quick": {"iterations": 100, "track_every": 50, "gap_tolerance": 0.0, "selection_hands": 200},
        "default": {"iterations": 1000, "track_every": 100, "gap_tolerance": 0.0, "selection_hands": 500},
        "strong": {"iterations": 3000, "track_every": 100, "gap_tolerance": 0.15, "selection_hands": 1000},
    }
    preset = preset_defaults[args.preset]
    iterations = args.iterations or preset["iterations"]
    track_every = args.track_every or preset["track_every"]
    gap_tolerance = preset["gap_tolerance"] if args.gap_tolerance is None else args.gap_tolerance
    selection_hands = preset["selection_hands"] if args.selection_hands is None else args.selection_hands
    settings = {
        "iterations": iterations,
        "track_every": track_every,
        "eval_interval": args.eval_interval or track_every,
        "gap_tolerance": preset["gap_tolerance"] if args.gap_tolerance is None else args.gap_tolerance,
        "selection_hands": selection_hands,
    }
    if args.engine == "rust" or (args.engine == "auto" and args.selection == "best_gap"):
        try:
            run_rust_cfr(args, settings)
            return
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            if args.engine == "rust":
                raise
            print(f"Rust CFR unavailable; falling back to Python CFR ({exc})")

    random.seed(args.seed)
    output_dir = Path(args.output_dir)
    out_path = args.out or str(output_dir / "cfr_strategy.json")
    metrics_path = args.metrics or str(output_dir / "cfr_metrics.json")
    plot_path = args.plot if args.plot is not None else str(output_dir / "training_curves.png")
    eval_interval = args.eval_interval or track_every
    cfr_plus = args.cfr_plus or args.algo == "cfr-plus"
    run_id = args.run_id or datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")
    trainer_engine = "python" if args.engine == "auto" else args.engine
    trainer = CFRTrainer(cfr_plus=cfr_plus, engine=trainer_engine)
    utilities = []
    points = []
    best_gap = float("inf")
    checkpoint_profiles = []
    start = time.perf_counter()
    for iteration in range(1, iterations + 1):
        utilities.extend(trainer.train(1))
        if iteration == 1 or iteration == iterations or iteration % eval_interval == 0:
            elapsed = time.perf_counter() - start
            root_traversals = iteration * len(trainer.deals)
            profile_at_checkpoint = trainer.profile()
            gap = nash_gap_upper_bound(profile_at_checkpoint)
            if gap < best_gap:
                best_gap = gap
            heuristic_avg_utility = None
            random_avg_utility = None
            heuristic_avg_utility = head_to_head(
                profile_at_checkpoint, heuristic_policy, hands=selection_hands, seed=args.seed + 5
            )["avg_utility"]
            random_avg_utility = head_to_head(
                profile_at_checkpoint, random_policy, hands=selection_hands, seed=args.seed
            )["avg_utility"]
            point = {
                "iteration": iteration,
                "expected_game_value_p0": expected_game_value(profile_at_checkpoint),
                "nash_gap_upper_bound": gap,
                "selection_heuristic_avg_utility": heuristic_avg_utility,
                "selection_random_avg_utility": random_avg_utility,
                "training_utility_p0": utilities[-1],
                "avg_utility_p0": sum(utilities) / len(utilities),
                "runtime_sec": elapsed,
                "root_traversals": root_traversals,
                "root_traversals_per_sec": root_traversals / elapsed if elapsed > 0 else 0.0,
                "infosets": len(profile_at_checkpoint.strategies),
            }
            points.append(point)
            checkpoint_profiles.append((point, profile_at_checkpoint))
            print(
                "iter={iteration} elapsed={elapsed:.3f}s traversals_per_sec={tps:.1f} "
                "avg_utility={avg:.6f} gap_proxy={gap:.6f} heuristic={heuristic} infosets={infosets}".format(
                    iteration=iteration,
                    elapsed=elapsed,
                    tps=point["root_traversals_per_sec"],
                    avg=point["avg_utility_p0"],
                    gap=point["nash_gap_upper_bound"],
                    heuristic="n/a" if heuristic_avg_utility is None else f"{heuristic_avg_utility:.6f}",
                    infosets=point["infosets"],
                )
            )
    if args.selection == "best_gap":
        selected_point, profile = min(checkpoint_profiles, key=lambda item: item[0]["nash_gap_upper_bound"])
    elif args.selection == "best_heuristic":
        selected_point, profile = max(
            checkpoint_profiles,
            key=lambda item: (
                item[0]["selection_heuristic_avg_utility"],
                -item[0]["nash_gap_upper_bound"],
                item[0]["selection_random_avg_utility"],
            ),
        )
    else:
        gaps = [point["nash_gap_upper_bound"] for point, _ in checkpoint_profiles]
        random_utils = [point["selection_random_avg_utility"] for point, _ in checkpoint_profiles]
        heuristic_utils = [point["selection_heuristic_avg_utility"] for point, _ in checkpoint_profiles]
        total_weight = args.w_gap + args.w_random + args.w_heuristic
        if total_weight <= 0:
            raise ValueError("Balanced selection weights must sum to a positive value")
        weights = {
            "gap": args.w_gap / total_weight,
            "random": args.w_random / total_weight,
            "heuristic": args.w_heuristic / total_weight,
        }

        def normalize(value: float, values: list[float], invert: bool = False) -> float:
            lo = min(values)
            hi = max(values)
            if hi == lo:
                return 1.0
            score = (value - lo) / (hi - lo)
            return 1.0 - score if invert else score

        for point, _ in checkpoint_profiles:
            gap_score = normalize(point["nash_gap_upper_bound"], gaps, invert=True)
            random_score = normalize(point["selection_random_avg_utility"], random_utils)
            heuristic_score = normalize(point["selection_heuristic_avg_utility"], heuristic_utils)
            weighted_score = (
                weights["gap"] * gap_score
                + weights["random"] * random_score
                + weights["heuristic"] * heuristic_score
            )
            point["balanced_scores"] = {
                "gap_score": gap_score,
                "random_score": random_score,
                "heuristic_score": heuristic_score,
                "weighted_score": weighted_score,
                "weights": weights,
            }

        print("balanced checkpoint scores:")
        for point, _ in checkpoint_profiles:
            scores = point["balanced_scores"]
            print(
                "iter={iteration} gap_score={gap:.4f} random_score={random:.4f} "
                "heuristic_score={heuristic:.4f} weighted_score={weighted:.4f}".format(
                    iteration=point["iteration"],
                    gap=scores["gap_score"],
                    random=scores["random_score"],
                    heuristic=scores["heuristic_score"],
                    weighted=scores["weighted_score"],
                )
            )

        selected_point, profile = max(
            checkpoint_profiles,
            key=lambda item: (
                item[0]["balanced_scores"]["weighted_score"],
                -item[0]["nash_gap_upper_bound"],
            ),
        )
    for point in points:
        point["selected_best"] = point["iteration"] == selected_point["iteration"]
    profile.save(out_path)
    total_elapsed = time.perf_counter() - start
    total_root_traversals = iterations * len(trainer.deals)

    final_metrics = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "preset": args.preset,
        "algorithm": "cfr-plus" if cfr_plus else "cfr",
        "engine_requested": args.engine,
        "engine_used": trainer.engine,
        "iterations": iterations,
        "seed": args.seed,
        "eval_interval": eval_interval,
        "selection_mode": args.selection,
        "selection_weights": {
            "gap": args.w_gap,
            "random": args.w_random,
            "heuristic": args.w_heuristic,
        },
        "gap_tolerance": gap_tolerance,
        "selection_hands": selection_hands,
        "cfr_plus": cfr_plus,
        "final_avg_utility_p0": utilities[-1] if utilities else 0.0,
        "best_observed_nash_gap_upper_bound": best_gap,
        "selected_iteration": selected_point["iteration"],
        "selected_gap": selected_point["nash_gap_upper_bound"],
        "selected_vs_random_avg_utility": selected_point["selection_random_avg_utility"],
        "selected_vs_heuristic_avg_utility": selected_point["selection_heuristic_avg_utility"],
        "selected_checkpoint_iteration": selected_point["iteration"],
        "selected_checkpoint_nash_gap_upper_bound": selected_point["nash_gap_upper_bound"],
        "selected_checkpoint_heuristic_avg_utility": selected_point["selection_heuristic_avg_utility"],
        "selected_checkpoint_random_avg_utility": selected_point["selection_random_avg_utility"],
        "selected_balanced_scores": selected_point.get("balanced_scores"),
        "infosets": len(profile.strategies),
        "runtime_sec": total_elapsed,
        "root_traversals": total_root_traversals,
        "root_traversals_per_sec": total_root_traversals / total_elapsed if total_elapsed > 0 else 0.0,
        "series": points,
    }
    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if Path(metrics_path).exists():
        existing = json.loads(Path(metrics_path).read_text())
    runs = existing.get("runs", {})
    runs[run_id] = final_metrics
    comparison = [
        {
            "run_id": key,
            "algorithm": value.get("algorithm", "cfr-plus" if value.get("cfr_plus") else "cfr"),
            "iterations": value["iterations"],
            "infosets": value["infosets"],
            "final_expected_game_value_p0": value["series"][-1]["expected_game_value_p0"],
            "final_nash_gap_upper_bound": value["series"][-1]["nash_gap_upper_bound"],
            "runtime_sec": value["runtime_sec"],
            "root_traversals_per_sec": value.get("root_traversals_per_sec", 0.0),
        }
        for key, value in sorted(runs.items())
    ]
    Path(metrics_path).write_text(json.dumps({"latest_run_id": run_id, "runs": runs, "comparison": comparison}, indent=2))
    if plot_path:
        plot_training_curves(points, plot_path)
    print(f"saved {len(profile.strategies)} infosets to {out_path}")
    print(f"saved training metrics to {metrics_path}")


if __name__ == "__main__":
    main()
