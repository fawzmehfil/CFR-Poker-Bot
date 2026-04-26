from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leduc_cfr.cfr.trainer import CFRTrainer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cfr-plus", action="store_true")
    parser.add_argument("--out", default="data/cfr_strategy.json")
    parser.add_argument("--metrics", default="data/cfr_metrics.json")
    args = parser.parse_args()

    trainer = CFRTrainer(cfr_plus=args.cfr_plus)
    utilities = trainer.train(args.iterations)
    profile = trainer.profile()
    profile.save(args.out)

    Path(args.metrics).parent.mkdir(parents=True, exist_ok=True)
    Path(args.metrics).write_text(
        json.dumps(
            {
                "iterations": args.iterations,
                "cfr_plus": args.cfr_plus,
                "final_avg_utility_p0": utilities[-1] if utilities else 0.0,
                "infosets": len(profile.strategies),
            },
            indent=2,
        )
    )
    print(f"saved {len(profile.strategies)} infosets to {args.out}")


if __name__ == "__main__":
    main()
